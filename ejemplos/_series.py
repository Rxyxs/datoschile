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


def _crecimiento_pib() -> pd.Series:
    """Variación del PIB contra el mismo trimestre del año anterior, en %."""
    pib = _indexada(dc.bcentral.serie("pib", desde=DESDE - 1), "pib")
    return ((pib / pib.shift(4) - 1) * 100).dropna()[lambda x: x.index.year >= DESDE]


def cargar() -> dict[str, pd.Series]:
    """Todas las series del panel. Las que fallan quedan fuera con un aviso."""
    fuentes = {
        "uf": lambda: _indexada(dc.indicadores.uf(desde=DESDE), "uf"),
        "dolar": lambda: _indexada(dc.bcentral.serie("dolar", desde=DESDE), "dolar"),
        "cobre": lambda: _indexada(dc.cochilco.cobre(desde=DESDE), "cobre"),
        "tpm": lambda: _indexada(dc.bcentral.serie("tpm", desde=DESDE), "tpm"),
        "imacec": lambda: _indexada(dc.bcentral.serie("imacec", desde=DESDE), "imacec"),
        "desempleo": lambda: _indexada(dc.bcentral.serie("desempleo", desde=DESDE), "desempleo"),
        "pib12": lambda: _crecimiento_pib(),
        "reservas": lambda: _indexada(dc.bcentral.serie("reservas", desde=DESDE), "reservas"),
        "euro": lambda: _indexada(dc.bcentral.serie("euro", desde=DESDE), "euro"),
        "oro": lambda: _indexada(dc.bcentral.serie("oro", desde=DESDE), "oro"),
        "tcm": lambda: _indexada(dc.bcentral.serie("tcm", desde=DESDE), "tcm"),
        "morosidad": lambda: _indexada(dc.cmf.morosidad(solo_sistema=True), "total"),
    }
    series: dict[str, pd.Series] = {}
    for nombre, obtener in fuentes.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                series[nombre] = obtener()
        except (ConnectionError, ValueError) as e:
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
