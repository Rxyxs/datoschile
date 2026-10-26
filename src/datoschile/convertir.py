"""Conversiones para comparar montos en el tiempo: pesos a UF, UF a pesos y pesos de una
fecha a pesos de otra (deflactar por IPC).

Aceptan un número y una fecha, o columnas completas (listas, ``Series``) de montos y fechas.

    >>> from datoschile import convertir
    >>> convertir.pesos_a_uf(1_000_000, "2020-03-15")
    >>> convertir.uf_a_pesos(df["monto_uf"], df["fecha"])
    >>> convertir.deflactar(df["sueldo"], df["fecha"], a="2026-09")   # pesos de sep-2026
"""
from __future__ import annotations

import pandas as pd

from . import indicadores, sii


def _como_series(montos, fechas) -> tuple[pd.Series, pd.Series, bool]:
    escalar = pd.api.types.is_scalar(montos)
    m = pd.Series([montos] if escalar else montos, dtype=float)
    f = pd.Series(pd.to_datetime([fechas] if pd.api.types.is_scalar(fechas) else list(fechas)))
    if len(f) == 1 and len(m) > 1:
        f = pd.Series([f.iloc[0]] * len(m))
    if len(f) != len(m):
        raise ValueError(f"{len(m)} montos y {len(f)} fechas: deben tener el mismo largo")
    f = f.dt.normalize()
    if isinstance(montos, pd.Series):
        m.index = f.index = montos.index
    return m, f, escalar


def _devolver(valores: pd.Series, escalar: bool):
    return float(valores.iloc[0]) if escalar else valores


def _uf_en(fechas: pd.Series, cache: bool) -> pd.Series:
    uf = indicadores.uf(desde=str(fechas.min().date()), hasta=str(fechas.max().date()), cache=cache)
    return fechas.map(uf.set_index("fecha")["uf"])


def pesos_a_uf(montos, fechas, cache: bool = True):
    """Pesos de cada fecha expresados en UF de esa misma fecha."""
    m, f, escalar = _como_series(montos, fechas)
    return _devolver(m / _uf_en(f, cache), escalar)


def uf_a_pesos(montos_uf, fechas, cache: bool = True):
    """UF expresadas en pesos de cada fecha."""
    m, f, escalar = _como_series(montos_uf, fechas)
    return _devolver(m * _uf_en(f, cache), escalar)


def deflactar(montos, fechas, a=None, cache: bool = True):
    """Pesos de cada fecha llevados a pesos del mes ``a`` (por omisión, el último IPC publicado).

    Usa el IPC empalmado (:func:`datoschile.sii.utm_ipc`): con el IPC en puntos tal como se
    publica, cualquier comparación que cruce enero de 2010, 2014, 2019 o 2024 queda mal por
    el cambio de base. Un mes sin IPC publicado devuelve ``NaN``.
    """
    m, f, escalar = _como_series(montos, fechas)
    ipc = sii.utm_ipc(cache=cache).dropna(subset=["ipc_empalmado"]).set_index("fecha")["ipc_empalmado"]
    mes = f.dt.to_period("M").dt.to_timestamp()
    destino = ipc.index[-1] if a is None else pd.Timestamp(a).to_period("M").to_timestamp()
    if destino not in ipc.index:
        raise ValueError(f"No hay IPC publicado para {destino:%Y-%m}; el último es {ipc.index[-1]:%Y-%m}")
    return _devolver(m * ipc[destino] / mes.map(ipc), escalar)
