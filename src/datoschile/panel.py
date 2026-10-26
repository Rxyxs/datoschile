"""Panel de referencia: el último valor de los indicadores clave de Chile, con su variación
en 12 meses y la fuente de cada uno.

    >>> import datoschile as dc
    >>> dc.resumen()
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from . import cmf, cochilco, indicadores, sii

COLUMNAS = ["indicador", "valor", "unidad", "fecha", "var_12m", "fuente"]


def _ultimo(serie: pd.Series, relativa: bool = True) -> tuple[float, pd.Timestamp, float]:
    """Último valor, su fecha y la variación contra el dato más cercano de un año antes."""
    s = serie.dropna()
    fecha, valor = s.index[-1], float(s.iloc[-1])
    previo = s[s.index <= fecha - pd.DateOffset(years=1)]
    if previo.empty:
        return valor, fecha, float("nan")
    antes = float(previo.iloc[-1])
    return valor, fecha, (valor / antes - 1) * 100 if relativa else valor - antes


def _diaria_sii(codigo: str, desde: date, cache: bool) -> pd.Series:
    filas = []
    for anio in range(desde.year, date.today().year + 1):
        filas.extend(sii.descargar_anio(codigo, anio, cache=cache))
    s = pd.DataFrame(filas).drop_duplicates("fecha")
    s = s.set_index(pd.to_datetime(s["fecha"]))["valor"].sort_index()
    return s[s.index <= pd.Timestamp(date.today())]


def resumen(cache: bool = True) -> pd.DataFrame:
    """Una fila por indicador: ``indicador``, ``valor``, ``unidad``, ``fecha`` del dato,
    ``var_12m`` (% para precios y niveles; puntos porcentuales para tasas) y ``fuente``.

    Cada indicador sale de su fuente oficial cuando la hay (SII, Cochilco, CMF). TPM,
    IMACEC y desempleo vienen de mindicador; si no responde, esas filas quedan vacías con el
    motivo en ``fuente`` y el resto del panel se entrega igual.
    """
    hace_dos_anios = date(date.today().year - 2, 1, 1)
    filas = []

    def agregar(indicador, unidad, fuente, obtener, relativa=True):
        try:
            valor, fecha, var = _ultimo(obtener(), relativa)
            filas.append([indicador, valor, unidad, fecha, var, fuente])
        except (ConnectionError, ValueError, KeyError, IndexError, TypeError) as e:
            filas.append([indicador, float("nan"), unidad, pd.NaT, float("nan"), f"{fuente} (no disponible: {e})"])

    agregar("UF", "pesos", "SII", lambda: _diaria_sii("uf", hace_dos_anios, cache))
    # El SII carga el dólar del mes con atraso; mindicador lo tiene al día y, si no responde,
    # indicadores.dolar() cae solo al SII.
    agregar("Dólar observado", "pesos", "Banco Central vía mindicador o SII",
            lambda: indicadores.dolar(desde=hace_dos_anios.year, cache=cache).set_index("fecha")["dolar"])
    agregar("Cobre (LME)", "dólares por libra", "Cochilco",
            lambda: cochilco.cobre(desde=hace_dos_anios.year, cache=cache).set_index("fecha")["cobre"])

    ipc = None

    def utm_ipc():
        nonlocal ipc
        ipc = sii.utm_ipc(desde=hace_dos_anios.year - 1, cache=cache).set_index("fecha")
        return ipc["utm"]

    agregar("UTM", "pesos", "SII", utm_ipc)
    agregar("Inflación (IPC, 12 meses)", "%", "INE vía SII", lambda: (
        ipc["ipc_empalmado"] / ipc["ipc_empalmado"].shift(12) * 100 - 100), relativa=False)

    caido = None  # si mindicador no responde, no se espera el timeout tres veces

    def de_mindicador(codigo):
        nonlocal caido
        if caido:
            raise ConnectionError(caido)
        try:
            return indicadores.serie(codigo, desde=hace_dos_anios.year, cache=cache).set_index("fecha")[codigo]
        except ConnectionError as e:
            caido = "mindicador no respondió"
            raise ConnectionError(caido) from e

    for codigo, nombre in (("tpm", "Tasa de política monetaria"), ("imacec", "IMACEC (variación anual)"),
                           ("tasa_desempleo", "Desempleo (trimestre móvil)")):
        agregar(nombre, "%", "Banco Central / INE vía mindicador", lambda c=codigo: de_mindicador(c), relativa=False)

    def morosidad():
        df = cmf.morosidad(desde=f"{hace_dos_anios.year}-01", solo_sistema=True, cache=cache)
        return df.set_index("fecha")["total"]

    agregar("Morosidad bancaria 90+ días", "% de la cartera", "CMF", morosidad, relativa=False)
    return pd.DataFrame(filas, columns=COLUMNAS)
