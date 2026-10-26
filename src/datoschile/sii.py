"""UF, dólar observado, UTM, UTA e IPC desde el SII, la fuente oficial que los publica.

`mindicador.cl` es un agregador de terceros: cuando se cae (devolvió 500 durante días en
octubre de 2026) la librería no tenía de dónde más sacar la UF. El SII publica una página
por año con la UF y el dólar observado de cada día, sin clave ni registro:

- desde 2013: https://www.sii.cl/valores_y_fechas/uf/uf2014.htm, con un bloque por mes
  (``id='mes_enero'`` ...) y pares día/valor;
- hasta 2012: https://www.sii.cl/pagina/valores/uf/uf2008.htm, una sola tabla con un día
  por fila y un mes por columna.

El dólar sigue las mismas dos rutas (``dolar/dolar2014.htm``). Ojo con el formato: la UF
usa coma decimal (``24.627,10``) y el dólar punto (``541.59``).

La UTM, la UTA y el IPC van en una tabla mensual por año (``utm/utm2025.htm``) desde 1990;
ver :func:`utm_ipc`.

    >>> from datoschile import sii
    >>> sii.descargar_anio("uf", 2014)[:2]
    >>> sii.utm_ipc(desde=2010)          # UTM, UTA, IPC publicado e IPC empalmado
"""
from __future__ import annotations

import math
import re
import time

import pandas as pd

from . import _red
from ._fechas import es_periodo_cerrado, rango

URLS = {
    "uf": "https://www.sii.cl/valores_y_fechas/uf/uf{anio}.htm",
    "dolar": "https://www.sii.cl/valores_y_fechas/dolar/dolar{anio}.htm",
}
URLS_HISTORICAS = {
    "uf": "https://www.sii.cl/pagina/valores/uf/uf{anio}.htm",
    "dolar": "https://www.sii.cl/pagina/valores/dolar/dolar{anio}.htm",
}
PRIMER_ANIO_FORMATO_NUEVO = 2013
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
_BLOQUE_MES = re.compile(r"id=['\"]mes_(" + "|".join(MESES) + r")['\"](.*?)</table>", re.S)
_PAR_DIA_VALOR = re.compile(r"<strong>\s*(\d{1,2})\s*</strong>\s*</th>\s*<td[^>]*>\s*([^<]*?)\s*</td>", re.S)
# El día va en <th> o en <td> según la época, y algunas filas traen atributos (onmouseover).
_FILA_HISTORICA = re.compile(r"<tr[^>]*>\s*<t[hd][^>]*>\s*(\d{1,2})\s*</t[hd]>(.*?)</tr>", re.S)
_CELDA = re.compile(r"<td[^>]*>\s*([^<]*?)\s*</td>", re.S)


def _numero(texto: str) -> float:
    """``24.627,10`` -> 24627.10 y ``541.59`` -> 541.59."""
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def _parsear_historica(html: str, anio: int) -> list[dict]:
    filas = []
    for dia, celdas in _FILA_HISTORICA.findall(html):
        for numero_mes, valor in enumerate(_CELDA.findall(celdas)[:12], start=1):
            valor = valor.replace("&nbsp;", "").strip()
            if not valor:
                continue
            filas.append({"fecha": f"{anio:04d}-{numero_mes:02d}-{int(dia):02d}", "valor": _numero(valor)})
    return sorted(filas, key=lambda f: f["fecha"])


def parsear_pagina(html: str, anio: int) -> list[dict]:
    """Pares fecha/valor de una página anual del SII (cualquiera de los dos formatos);
    los días sin valor se omiten."""
    if "id='mes_" not in html and 'id="mes_' not in html:
        return _parsear_historica(html, anio)
    filas = []
    for mes, bloque in _BLOQUE_MES.findall(html):
        numero_mes = MESES.index(mes) + 1
        for dia, valor in _PAR_DIA_VALOR.findall(bloque):
            if not valor.strip():
                continue
            filas.append({"fecha": f"{anio:04d}-{numero_mes:02d}-{int(dia):02d}", "valor": _numero(valor)})
    return sorted(filas, key=lambda f: f["fecha"])


def descargar_anio(codigo: str, anio: int, cache: bool = True) -> list[dict]:
    """UF (``"uf"``) o dólar observado (``"dolar"``) de un año, desde el SII."""
    if codigo not in URLS:
        raise ValueError(f"El SII solo publica {', '.join(URLS)}; pedido: '{codigo}'")
    contenido = _red.con_cache(
        f"sii/{codigo}/{anio}.htm",
        lambda: _red.descargar((URLS if anio >= PRIMER_ANIO_FORMATO_NUEVO else URLS_HISTORICAS)[codigo].format(anio=anio)),
        usar_cache=cache and es_periodo_cerrado(anio),
    )
    return parsear_pagina(contenido.decode("latin-1"), anio)


# --- UTM, UTA e IPC -------------------------------------------------------------------------

URL_UTM = "https://www.sii.cl/valores_y_fechas/utm/utm{anio}.htm"
URL_UTM_HISTORICA = "https://www.sii.cl/pagina/valores/utm/utm{anio}.htm"
PRIMER_ANIO_UTM = 1990
_FILA_MES = re.compile(r"<th[^>]*>\s*(" + "|".join(MESES) + r")\s*</th>(.*?)</tr>", re.S | re.I)
# Una diferencia mayor que esto entre el IPC publicado y el que implica la variación mensual
# oficial no es redondeo (la variación viene con un decimal): es un cambio de base.
TOLERANCIA_BASE_IPC = 0.003


def _miles(texto: str) -> float:
    """UTM y UTA: ``69.751`` -> 69751."""
    texto = texto.replace("&nbsp;", "").strip()
    return float(texto.replace(".", "")) if texto else math.nan


def _decimal(texto: str) -> float:
    """IPC y variaciones: ``109,71`` -> 109.71. Dos rarezas reales: diciembre de 2011 trae
    ``0.6`` con punto y febrero de 1992 ``(-0,6)`` entre paréntesis."""
    texto = texto.replace("&nbsp;", "").strip().strip("()")
    return float(texto.replace(",", ".")) if texto else math.nan


def parsear_utm(html: str, anio: int) -> list[dict]:
    """Filas mensuales de una página de UTM/IPC del SII.

    Hay tres diseños según la época, que se distinguen por el número de columnas:

    * 3 (1990 a ~2001): UTM, variación mensual del IPC, IPC;
    * 4 (~2002 a 2007): UTM, UTA, variación mensual, IPC;
    * 6 (desde 2008): UTM, UTA, IPC, variación mensual, acumulada en el año y en 12 meses.
    """
    filas = []
    for mes, resto in _FILA_MES.findall(html):
        celdas = _CELDA.findall(resto)
        if len(celdas) == 6:
            utm, uta, ipc, var = celdas[0], celdas[1], celdas[2], celdas[3]
        elif len(celdas) == 4:
            utm, uta, var, ipc = celdas
        elif len(celdas) == 3:
            utm, var, ipc = celdas
            uta = ""
        else:
            raise ValueError(f"Formato de UTM/IPC del SII desconocido en {anio}: {len(celdas)} columnas")
        fila = {"fecha": f"{anio:04d}-{MESES.index(mes.lower()) + 1:02d}-01", "utm": _miles(utm),
                "uta": _miles(uta), "ipc": _decimal(ipc), "ipc_var_mensual": _decimal(var)}
        if math.isnan(fila["uta"]) and not math.isnan(fila["utm"]):
            fila["uta"] = fila["utm"] * 12  # UTA = UTM de diciembre x 12; antes de 2002 no se publicaba
        filas.append(fila)
    return filas


def descargar_utm_anio(anio: int, cache: bool = True) -> list[dict]:
    """UTM, UTA, IPC y variación mensual del IPC de un año, desde el SII."""
    url = (URL_UTM if anio >= PRIMER_ANIO_FORMATO_NUEVO else URL_UTM_HISTORICA).format(anio=anio)
    contenido = _red.con_cache(f"sii/utm/{anio}.htm", lambda: _red.descargar(url),
                               usar_cache=cache and es_periodo_cerrado(anio))
    return parsear_utm(contenido.decode("latin-1"), anio)


def empalmar_ipc(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega ``ipc_empalmado``: el IPC en una sola base (la del último dato).

    El IPC en puntos que publica el SII cambia de base cada vez que el INE la cambia: en
    enero de 2010, 2014, 2019 y 2024 el índice salta (de 134,10 a 101,72 en 2024), y una
    inflación a 12 meses calculada sobre esa serie cruda se equivoca hasta en 25,8 puntos.
    Un cambio de base se detecta porque el salto no coincide con la variación mensual
    oficial; en ese mes se encadena con la variación y el tramo anterior se reescala. Los
    cambios detectados quedan en ``df.attrs["cambios_de_base"]``.
    """
    out = df.copy()
    ipc = out["ipc"].to_numpy(dtype=float)
    var = out["ipc_var_mensual"].to_numpy(dtype=float) / 100
    empalmado = ipc.copy()
    cambios = []
    for i in range(1, len(ipc)):
        if math.isnan(ipc[i]) or math.isnan(ipc[i - 1]) or math.isnan(var[i]):
            continue
        implicito = ipc[i - 1] * (1 + var[i])
        if abs(ipc[i] / implicito - 1) > TOLERANCIA_BASE_IPC:
            factor = ipc[i] / implicito
            empalmado[:i] *= factor
            cambios.append(out["fecha"].iloc[i].date())
    out["ipc_empalmado"] = empalmado
    out.attrs["cambios_de_base"] = cambios
    return out


def utm_ipc(desde=None, hasta=None, cache: bool = True, pausa: float = 0.2) -> pd.DataFrame:
    """Serie mensual desde 1990: ``utm``, ``uta`` (pesos), ``ipc`` (puntos, tal como lo
    publica el SII), ``ipc_var_mensual`` (%, la oficial del INE) e ``ipc_empalmado``
    (el IPC en una sola base, ver :func:`empalmar_ipc`; es el que sirve para deflactar).

    Los meses del año en curso que aún no se publican quedan fuera.
    """
    ini, fin = rango(desde, hasta, minimo=PRIMER_ANIO_UTM)
    # El empalme necesita toda la historia hasta el último dato, aunque se pida un tramo.
    filas: list[dict] = []
    for anio in range(PRIMER_ANIO_UTM, pd.Timestamp.today().year + 1):
        filas.extend(descargar_utm_anio(anio, cache=cache))
        if pausa and not (cache and es_periodo_cerrado(anio)):
            time.sleep(pausa)
    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.dropna(subset=["utm", "ipc"], how="all").sort_values("fecha").reset_index(drop=True)
    # El último IPC publicado define la base del empalme: se cortan los meses sin IPC al final.
    ultimo_ipc = df["ipc"].last_valid_index()
    df = empalmar_ipc(df.loc[:ultimo_ipc].reset_index(drop=True)).set_index("fecha").combine_first(
        df.set_index("fecha")).reset_index()
    out = df[(df["fecha"] >= ini.replace(day=1)) & (df["fecha"] <= fin)].reset_index(drop=True)
    out.attrs["cambios_de_base"] = [d for d in empalmar_ipc(df.dropna(subset=["ipc"])).attrs["cambios_de_base"]]
    return out[["fecha", "utm", "uta", "ipc", "ipc_var_mensual", "ipc_empalmado"]]
