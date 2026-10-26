"""Series que usan la portada y el panel web, todas bajadas con datoschile.

Cada función devuelve una ``pd.Series`` indexada por fecha. Si una fuente no responde, el
panel la omite en vez de fallar entero.
"""
from __future__ import annotations

import warnings

import pandas as pd

import datoschile as dc

DESDE = 2008


def _indexada(df: pd.DataFrame, col: str) -> pd.Series:
    return df.set_index("fecha")[col].dropna().sort_index()


def cargar() -> dict[str, pd.Series]:
    """Todas las series del panel. Las que fallan quedan fuera con un aviso."""
    fuentes = {
        "uf": lambda: _indexada(dc.indicadores.uf(desde=DESDE), "uf"),
        "dolar": lambda: _indexada(dc.indicadores.dolar(desde=DESDE), "dolar"),
        "cobre": lambda: _indexada(dc.cochilco.cobre(desde=DESDE), "cobre"),
        "tpm": lambda: _indexada(dc.indicadores.serie("tpm", desde=DESDE), "tpm"),
        "imacec": lambda: _indexada(dc.indicadores.serie("imacec", desde=DESDE), "imacec"),
        "desempleo": lambda: _indexada(dc.indicadores.serie("tasa_desempleo", desde=DESDE), "tasa_desempleo"),
        "morosidad": lambda: _indexada(dc.cmf.morosidad(solo_sistema=True), "total"),
    }
    series: dict[str, pd.Series] = {}
    for nombre, obtener in fuentes.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                series[nombre] = obtener()
        except ConnectionError as e:
            print(f"[aviso] {nombre}: {e}")
    ipc = dc.sii.utm_ipc().set_index("fecha")  # desde 1990: la calculadora del panel lo usa entero
    series["ipc12"] = (ipc["ipc_empalmado"] / ipc["ipc_empalmado"].shift(12) * 100 - 100).dropna()
    series["ipc12"] = series["ipc12"][series["ipc12"].index.year >= DESDE]
    series["utm"] = ipc["utm"].dropna()[lambda x: x.index.year >= DESDE]
    series["ipc"] = ipc["ipc_empalmado"].dropna()
    fondos = dc.pensiones.indice(fondos="ABCDE", desde=DESDE, real=True)
    for fondo in "ABCDE":
        s = _indexada(fondos[fondos["fondo"] == fondo], "indice")
        series[f"fondo_{fondo}"] = s
    return series
