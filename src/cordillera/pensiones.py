"""Valores cuota y patrimonio diarios de los fondos de pensiones (multifondos A–E), por AFP.

Fuente: el archivo que genera el botón "Genera archivo" de la Superintendencia de Pensiones
(https://www.spensiones.cl/apps/valoresCuotaFondo/vcfAFP.php). Sin clave ni formulario.

    >>> from cordillera import pensiones
    >>> pensiones.valor_cuota(fondos="AE", desde=2020)   # una fila por día, fondo y AFP
    >>> pensiones.indice(desde=2008, real=True)          # índice del fondo ponderado por patrimonio, en UF
"""
from __future__ import annotations

import re
import time
from datetime import date

import pandas as pd

from . import _red
from ._fechas import es_periodo_cerrado, rango

URL = "https://www.spensiones.cl/apps/valoresCuotaFondo/vcfAFPxls.php"
FONDOS = "ABCDE"
#: Primer año publicado. C y E traen datos desde enero de 2002 (el fondo único previo a la
#: reforma); A, B y D parten en agosto de 2002, cuando la reforma creó los cinco fondos.
PRIMER_ANIO = 2002

_FILA_DATOS = re.compile(r"^\d{4}-\d{2}-\d{2};")


def _normalizar_fondos(fondos) -> list[str]:
    lista = list(fondos.upper()) if isinstance(fondos, str) else [f.upper() for f in fondos]
    malos = [f for f in lista if f not in FONDOS]
    if malos or not lista:
        raise ValueError(f"Fondos inválidos {malos or fondos}: usa letras de {FONDOS}")
    return lista


def _numero_clp(texto: str) -> float | None:
    """'96.092,23' -> 96092.23 (punto de miles, coma decimal)."""
    texto = texto.strip()
    if not texto:
        return None
    return float(texto.replace(".", "").replace(",", "."))


def parsear_archivo(texto: str, fondo: str) -> pd.DataFrame:
    """Convierte un archivo de la Superintendencia en una tabla larga.

    El archivo es texto separado por ``;``. Su encabezado (qué AFP va en qué columna) **se
    repite y cambia** cada vez que una AFP entra, sale o se fusiona: 31 veces solo en el
    fondo C entre 2002 y 2026. Leerlo con un único encabezado desalinea las columnas en
    silencio desde el primer cambio, así que se vuelve a leer el encabezado cada vez que
    aparece.
    """
    filas = []
    afps: list[str] | None = None
    for linea in texto.splitlines():
        if linea.startswith("Fecha;"):
            afps = [a.strip() for a in linea.split(";")[1:] if a.strip()]
            continue
        if afps is None or not _FILA_DATOS.match(linea):
            continue
        campos = linea.split(";")
        fecha, valores = campos[0], campos[1:]
        for i, afp in enumerate(afps):
            cuota = _numero_clp(valores[2 * i]) if 2 * i < len(valores) else None
            if cuota is None:
                continue  # la AFP no tenía ese fondo ese día
            patrimonio = _numero_clp(valores[2 * i + 1]) if 2 * i + 1 < len(valores) else None
            filas.append((fecha, fondo, afp, cuota, patrimonio))
    df = pd.DataFrame(filas, columns=["fecha", "fondo", "afp", "valor_cuota", "valor_patrimonio"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def descargar_anio(fondo: str, anio: int, cache: bool = True) -> str:
    """Archivo crudo de un fondo y un año (texto)."""
    fondo = _normalizar_fondos(fondo)[0]
    params = {"aaaaini": anio, "aaaafin": anio, "tf": fondo, "fecconf": date.today().strftime("%Y%m%d")}
    contenido = _red.con_cache(
        f"pensiones/valor_cuota_{fondo}_{anio}.txt",
        lambda: _red.descargar(URL, params=params),
        usar_cache=cache and es_periodo_cerrado(anio),
    )
    return contenido.decode("latin-1")


def valor_cuota(fondos="ABCDE", desde=None, hasta=None, afps=None, cache: bool = True,
                pausa: float = 0.2) -> pd.DataFrame:
    """Valor cuota y patrimonio diario por fecha, fondo y AFP.

    Columnas: ``fecha``, ``fondo``, ``afp``, ``valor_cuota`` (pesos por cuota) y
    ``valor_patrimonio`` (pesos). El valor cuota de cada AFP es su propia serie: no se puede
    comparar el nivel entre AFP, solo su variación. Para un índice del fondo usa :func:`indice`.

    La serie incluye fines de semana y feriados con valores casi planos; para modelos de
    volatilidad conviene quedarse con días hábiles (``df[df.fecha.dt.dayofweek < 5]``).
    """
    lista = _normalizar_fondos(fondos)
    ini, fin = rango(desde, hasta, minimo=PRIMER_ANIO)
    partes = []
    for fondo in lista:
        for anio in range(ini.year, fin.year + 1):
            partes.append(parsear_archivo(descargar_anio(fondo, anio, cache=cache), fondo))
            if pausa and not (cache and es_periodo_cerrado(anio)):
                time.sleep(pausa)
    df = pd.concat(partes, ignore_index=True) if partes else parsear_archivo("", lista[0])
    df = df[(df["fecha"] >= ini) & (df["fecha"] <= fin)]
    if afps is not None:
        nombres = {afps.upper()} if isinstance(afps, str) else {a.upper() for a in afps}
        df = df[df["afp"].str.upper().isin(nombres)]
    return df.sort_values(["fondo", "afp", "fecha"]).reset_index(drop=True)


def indice_ponderado(valores: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Índice diario por fondo, ponderando el retorno de cada AFP por su patrimonio del día anterior.

    No se pueden promediar valores cuota (cada AFP partió su serie en un nivel distinto), pero
    sí sus retornos: es la forma estándar de armar un índice ponderado por activos a partir de
    series de precios de sus componentes. Devuelve ``fecha``, ``fondo``, ``retorno`` e ``indice``
    (igual a ``base`` el primer día de cada fondo).
    """
    df = valores.sort_values(["fondo", "afp", "fecha"]).copy()
    g = df.groupby(["fondo", "afp"])
    df["retorno"] = g["valor_cuota"].pct_change()
    df["peso"] = g["valor_patrimonio"].shift()
    df = df[df["retorno"].notna() & (df["peso"] > 0)].copy()
    df["ponderado"] = df["retorno"] * df["peso"]
    agg = df.groupby(["fondo", "fecha"])[["ponderado", "peso"]].sum()
    out = (agg["ponderado"] / agg["peso"]).rename("retorno").reset_index()
    acumulado = (1 + out["retorno"]).groupby(out["fondo"]).cumprod()
    out["indice"] = base * acumulado / acumulado.groupby(out["fondo"]).transform("first")
    return out


def indice(fondos="ABCDE", desde=None, hasta=None, real: bool = False, base: float = 100.0,
           cache: bool = True) -> pd.DataFrame:
    """Índice del fondo (todas las AFP, ponderadas por patrimonio), igual a ``base`` el primer día pedido.

    Con ``real=True`` se deflacta por la UF diaria limpia (:func:`cordillera.indicadores.uf`):
    el índice queda en poder adquisitivo constante, que es como se miden las pensiones.
    ``retorno`` es el retorno diario (real, si ``real=True``) respecto del día anterior.
    """
    ini, fin = rango(desde, hasta, minimo=PRIMER_ANIO)
    # Unos días antes, para que el primer día pedido también tenga retorno respecto del anterior.
    valores = valor_cuota(fondos, str((ini - pd.Timedelta(days=10)).date()), str(fin.date()), cache=cache)
    out = indice_ponderado(valores, base=base)
    if real:
        from .indicadores import uf

        serie_uf = uf(desde=str(out["fecha"].min().date()), hasta=str(out["fecha"].max().date()), cache=cache)
        out = out.merge(serie_uf, on="fecha", how="left")
        if out["uf"].isna().any():
            raise ValueError(f"{int(out['uf'].isna().sum())} días del índice sin valor de UF")
        out["indice"] = out["indice"] / out["uf"]
        out["retorno"] = out.groupby("fondo")["indice"].pct_change()
        out = out.drop(columns="uf")
    out = out[out["fecha"] >= ini].copy()
    out["indice"] = base * out["indice"] / out.groupby("fondo")["indice"].transform("first")
    return out.reset_index(drop=True)
