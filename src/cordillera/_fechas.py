from __future__ import annotations

import re
from datetime import date

import pandas as pd


def rango(desde, hasta, minimo: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Normaliza ``desde``/``hasta`` (año, 'AAAA-MM', 'AAAA-MM-DD' o date) a un rango cerrado.

    Un año o un mes como ``desde`` significa su primer día; como ``hasta``, su último día.
    """
    hoy = pd.Timestamp(date.today())

    def a_fecha(v, por_defecto: pd.Timestamp, fin: bool) -> pd.Timestamp:
        if v is None:
            return por_defecto
        if isinstance(v, int):
            return pd.Timestamp(year=v, month=12, day=31) if fin else pd.Timestamp(year=v, month=1, day=1)
        if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}", v.strip()):
            mes = pd.Period(v.strip(), freq="M")  # "AAAA-MM": el mes completo
            return mes.end_time.normalize() if fin else mes.start_time
        return pd.Timestamp(v).normalize()

    ini = a_fecha(desde, pd.Timestamp(year=minimo, month=1, day=1), fin=False)
    fin = a_fecha(hasta, hoy, fin=True)
    ini = max(ini, pd.Timestamp(year=minimo, month=1, day=1))
    fin = min(fin, hoy)
    if ini > fin:
        raise ValueError(f"Rango vacío: desde {ini.date()} es posterior a hasta {fin.date()}")
    return ini, fin


def es_periodo_cerrado(anio: int) -> bool:
    return anio < date.today().year
