"""Morosidad de 90 días o más del sistema bancario, por banco y cartera (CMF), desde 2016.

Fuente: la página de estadísticas de la Comisión para el Mercado Financiero
(https://www.cmfchile.cl/portal/estadisticas/626/w4-propertyvalue-28914.html), que
publica un Excel por mes. Sin clave ni formulario.

    >>> from cordillera import cmf
    >>> cmf.morosidad(desde="2020-01")              # una fila por mes y banco
    >>> cmf.morosidad(solo_sistema=True)            # solo el total del sistema bancario
"""
from __future__ import annotations

import io
import re
import time
from datetime import date

import numpy as np
import pandas as pd

from . import _red

URL_BASE = "https://www.cmfchile.cl/portal/estadisticas/626/"
URL_INDICE = URL_BASE + "w4-propertyvalue-28914.html"

CARTERAS = ["total", "clientes", "comercial", "personas", "consumo", "vivienda"]
SISTEMA = "Sistema Bancario"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_ENLACE = re.compile(r'<a href="(articles-\d+_recurso_1\.xlsx)[^"]*"[^>]*aria-label="Descargar ([^"(]+?) \(xlsx')

# (columna del banco, columnas de los 6 porcentajes, columna del monto en MM$)
_FORMATOS = {"antiguo": (0, [1, 2, 3, 4, 5, 6], 8), "nuevo": (1, [2, 3, 4, 5, 6, 7], 10)}

# Fusiones y cambios de nombre: nombre en el archivo -> nombre de la serie continua.
ALIAS_BANCOS = {
    "Itaú Corpbanca": "Banco Itaú Chile",
    "Jp Morgan Chase Bank, N.A.": "JP Morgan Chase Bank, N.A.",
    "Banco Bilbao Vizcaya Argentaria, Chile": "BBVA Chile / Scotiabank Azul",
    "Scotiabank Azul": "BBVA Chile / Scotiabank Azul",
    "The Bank of Tokyo-Mitsubishi UFJ, Ltd.": "MUFG Bank",
    "MUFG Bank, Ltd.": "MUFG Bank",
}
# Entre 2016-01 y 2016-03, "Banco Itaú Chile" es la entidad previa a la fusión con
# Corpbanca: no es la misma serie que el Itaú posterior, así que se excluye.
_FIN_ITAU_PREVIO = pd.Timestamp("2016-03-01")
# Un mes publicado puede corregirse en las semanas siguientes: los últimos meses no se guardan.
MESES_SIN_CACHE = 3


def parsear_indice(html: str) -> dict[pd.Timestamp, str]:
    """``{primer día del mes: archivo}`` a partir del HTML de la página de estadísticas."""
    out = {}
    for archivo, etiqueta in _ENLACE.findall(html):
        mes, _, anio = etiqueta.strip().lower().partition(" ")
        if mes in MESES and anio.strip().isdigit():
            out[pd.Timestamp(year=int(anio), month=MESES[mes], day=1)] = archivo
    return dict(sorted(out.items()))


def meses_disponibles() -> dict[pd.Timestamp, str]:
    """Meses publicados por la CMF y el archivo de cada uno."""
    indice = parsear_indice(_red.descargar(URL_INDICE).decode("utf-8", errors="replace"))
    if not indice:
        raise RuntimeError("No se encontraron enlaces mensuales: la CMF cambió el formato de su página.")
    return indice


def _es_valor(v) -> bool:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    return isinstance(v, (int, float, np.integer, np.floating)) or str(v).strip() in {"---", "--", "-"}


def _a_float(v) -> float:
    return float(v) if isinstance(v, (int, float, np.integer, np.floating)) else np.nan  # '---' = no aplica


def detectar_formato(hoja: pd.DataFrame) -> str:
    """El archivo cambió tres veces: 9 columnas hasta 2021 (``antiguo``) y 12 desde 2022 (``nuevo``,
    con o sin encabezados de texto). Verifica que los encabezados calcen cuando existen."""
    formato = "antiguo" if hoja.shape[1] == 9 else "nuevo"
    _, columnas, _ = _FORMATOS[formato]
    cabeza = hoja.iloc[:16].astype(str).apply(lambda c: c.str.lower())
    if formato == "nuevo" and not cabeza.apply(lambda c: c.str.contains("comerciales")).any().any():
        return formato  # 2022-01 a 2023-03: mismo orden, sin encabezados de texto
    esperado = {"comerciales": columnas[2], "consumo": columnas[4], "vivienda": columnas[5]}
    for palabra, col in esperado.items():
        if not cabeza.iloc[:, col].str.contains(palabra).any():
            raise ValueError(f"Formato no reconocido: no aparece '{palabra}' en la columna {col}")
    return formato


def parsear_mes(contenido: bytes, mes: pd.Timestamp) -> pd.DataFrame:
    """Una fila por banco (más la del sistema) con el % de morosidad 90+ días de cada cartera."""
    hoja = pd.read_excel(io.BytesIO(contenido), header=None)
    formato = detectar_formato(hoja)
    col_banco, cols_valores, col_monto = _FORMATOS[formato]
    filas = []
    for i in range(len(hoja)):
        nombre = hoja.iat[i, col_banco]
        if not isinstance(nombre, str) or not _es_valor(hoja.iat[i, cols_valores[0]]):
            continue
        nombre = re.sub(r"\s+", " ", nombre).strip()
        fila = {"fecha": mes, "banco_original": nombre, "formato": formato}
        for cartera, col in zip(CARTERAS, cols_valores):
            fila[cartera] = _a_float(hoja.iat[i, col])
        fila["monto_moroso_mm"] = _a_float(hoja.iat[i, col_monto]) if col_monto < hoja.shape[1] else np.nan
        filas.append(fila)
        if nombre == SISTEMA:
            break  # después vienen notas al pie
    if not filas or filas[-1]["banco_original"] != SISTEMA:
        raise ValueError(f"{mes:%Y-%m}: no se encontró la fila '{SISTEMA}'")
    return pd.DataFrame(filas)


def nombre_canonico(nombre: str, mes: pd.Timestamp) -> str | None:
    """Nombre de la serie continua del banco; ``None`` si la fila no pertenece a ninguna."""
    if nombre == "Banco Itaú Chile" and mes <= _FIN_ITAU_PREVIO:
        return None
    return ALIAS_BANCOS.get(nombre, nombre)


def _descargar_mes(mes: pd.Timestamp, archivo: str, cache: bool) -> bytes:
    hoy = pd.Timestamp(date.today()).to_period("M")
    cerrado = (hoy - mes.to_period("M")).n >= MESES_SIN_CACHE

    def obtener() -> bytes:
        contenido = _red.descargar(URL_BASE + archivo)
        if contenido[:2] != b"PK":
            raise ValueError(f"{mes:%Y-%m}: la CMF no devolvió un .xlsx")
        return contenido

    return _red.con_cache(f"cmf/morosidad_{mes:%Y-%m}.xlsx", obtener, usar_cache=cache and cerrado)


def _primer_dia_del_mes(v, fin_de_anio: bool) -> pd.Timestamp:
    """Año, 'AAAA-MM' o fecha -> primer día de su mes. Un año como ``hasta`` es diciembre."""
    if isinstance(v, int):
        v = f"{v}-12" if fin_de_anio else f"{v}-01"
    return pd.Timestamp(v).to_period("M").to_timestamp()


def morosidad(desde=None, hasta=None, solo_sistema: bool = False, cache: bool = True,
              pausa: float = 0.4) -> pd.DataFrame:
    """Panel mensual de morosidad 90+ días: una fila por mes y banco.

    Columnas: ``fecha`` (primer día del mes), ``banco``, ``es_sistema``, el % de cartera morosa
    en ``total``, ``clientes``, ``comercial``, ``personas``, ``consumo`` y ``vivienda`` (``NaN``
    si el banco no tiene esa cartera), ``monto_moroso_mm`` (millones de pesos) y, para
    auditoría, ``banco_original`` y ``formato``. Las fusiones se unen en una sola serie
    (ver ``ALIAS_BANCOS``). ``desde``/``hasta`` aceptan ``"AAAA-MM"``, una fecha o un año.

    La fuente tiene un hueco real: en el archivo de 2023-07 la fila del sistema viene en ``---``
    aunque los bancos sí traen sus datos. Ese mes queda en ``NaN`` en vez de rellenarse.
    """
    indice = meses_disponibles()
    ini = _primer_dia_del_mes(desde, fin_de_anio=False) if desde else min(indice)
    fin = _primer_dia_del_mes(hasta, fin_de_anio=True) if hasta else max(indice)
    partes = []
    for mes, archivo in indice.items():
        if ini <= mes <= fin:
            partes.append(parsear_mes(_descargar_mes(mes, archivo, cache), mes))
            if pausa:
                time.sleep(pausa)
    if not partes:
        raise ValueError(f"La CMF no tiene meses publicados entre {ini:%Y-%m} y {fin:%Y-%m}")
    panel = pd.concat(partes, ignore_index=True)
    panel["banco"] = [nombre_canonico(n, m) for n, m in zip(panel["banco_original"], panel["fecha"])]
    panel = panel.dropna(subset=["banco"])
    panel["es_sistema"] = panel["banco"] == SISTEMA
    if panel.duplicated(["fecha", "banco"]).any():
        raise ValueError("Filas duplicadas (fecha, banco) tras unir los nombres de bancos fusionados")
    if solo_sistema:
        panel = panel[panel["es_sistema"]]
    columnas = ["fecha", "banco", "es_sistema", *CARTERAS, "monto_moroso_mm", "banco_original", "formato"]
    return panel[columnas].sort_values(["fecha", "es_sistema", "banco"]).reset_index(drop=True)
