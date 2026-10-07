"""Indicadores económicos diarios y mensuales: UF, dólar, euro, UTM, IPC, TPM, IMACEC,
desempleo y precio del cobre.

Fuente: `mindicador.cl <https://mindicador.cl>`_, una API abierta que replica series del
Banco Central de Chile, el INE y el SII. Es un agregador de terceros, no el publicador
oficial, y trae errores reales que este módulo detecta (ver :func:`uf`).

    >>> from datoschile import indicadores
    >>> indicadores.uf(desde=2020)                       # UF diaria, limpia
    >>> indicadores.serie("libra_cobre", desde=2024)     # cualquier serie disponible
"""
from __future__ import annotations

import json
import math
import time

import pandas as pd

from . import _red
from ._fechas import es_periodo_cerrado, rango

URL = "https://mindicador.cl/api/{codigo}/{anio}"

#: Series disponibles: código -> (descripción, unidad, frecuencia, primer año con datos)
SERIES: dict[str, tuple[str, str, str, int]] = {
    "uf": ("Unidad de fomento", "pesos", "diaria", 1977),
    "ivp": ("Índice de valor promedio", "pesos", "diaria", 1990),
    "dolar": ("Dólar observado", "pesos", "diaria", 1984),
    "euro": ("Euro", "pesos", "diaria", 1999),
    "utm": ("Unidad tributaria mensual", "pesos", "mensual", 1990),
    "ipc": ("Variación mensual del IPC", "%", "mensual", 1928),
    "tpm": ("Tasa de política monetaria", "%", "diaria", 2001),
    "imacec": ("IMACEC, variación anual", "%", "mensual", 1997),
    "tasa_desempleo": ("Tasa de desempleo (trimestre móvil)", "%", "mensual", 2009),
    "libra_cobre": ("Precio de la libra de cobre", "dólares", "diaria", 2012),
    "bitcoin": ("Bitcoin", "dólares", "diaria", 2009),
}

# La UF no puede moverse 1% en un día: equivaldría a ~35% de inflación mensual. El mayor
# movimiento diario legítimo entre 2002 y 2026 es 0,063% (marzo de 2022).
MAX_MOVIMIENTO_DIARIO_UF = 0.01
MAX_DIAS_A_INTERPOLAR = 3


def _validar_codigo(codigo: str) -> None:
    if codigo not in SERIES:
        raise ValueError(f"Serie desconocida '{codigo}'. Disponibles: {', '.join(SERIES)}")


def descargar_anio(codigo: str, anio: int, cache: bool = True) -> list[dict]:
    """Observaciones crudas de un año, tal como las entrega la API (sin limpiar)."""
    _validar_codigo(codigo)
    contenido = _red.con_cache(
        f"mindicador/{codigo}/{anio}.json",
        lambda: _red.descargar(URL.format(codigo=codigo, anio=anio)),
        usar_cache=cache and es_periodo_cerrado(anio),
    )
    serie = json.loads(contenido).get("serie") or []
    # La API entrega la fecha como timestamp UTC de la medianoche chilena (T03:00Z o T04:00Z);
    # los primeros 10 caracteres son el día chileno.
    return [{"fecha": s["fecha"][:10], "valor": float(s["valor"])} for s in serie]


def _a_dataframe(filas: list[dict], nombre: str) -> pd.DataFrame:
    """Ordena, quita duplicados idénticos y falla si dos copias de un día no coinciden."""
    if not filas:
        return pd.DataFrame({"fecha": pd.Series(dtype="datetime64[ns]"), nombre: pd.Series(dtype=float)})
    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    distintos = df.drop_duplicates().groupby("fecha")["valor"].nunique()
    conflictos = distintos[distintos > 1]
    if len(conflictos):
        raise ValueError(f"Valores distintos para el mismo día en {nombre}: {list(conflictos.index.date)[:5]}")
    duplicados = [d.date() for d in df.loc[df["fecha"].duplicated(), "fecha"]]
    df = df.drop_duplicates("fecha").sort_values("fecha").reset_index(drop=True)
    df = df.rename(columns={"valor": nombre})
    df.attrs["duplicados"] = duplicados
    return df


def serie(codigo: str, desde=None, hasta=None, cache: bool = True, pausa: float = 0.2) -> pd.DataFrame:
    """Una serie de mindicador como DataFrame con columnas ``fecha`` y ``<codigo>``.

    ``desde``/``hasta`` aceptan un año (``2020``), una fecha (``"2020-03-15"``) o ``None``
    (desde el primer año con datos / hasta hoy). Los años cerrados se guardan en caché.
    Para la UF conviene :func:`uf`, que además corrige los errores conocidos de la fuente.
    """
    _validar_codigo(codigo)
    ini, fin = rango(desde, hasta, minimo=SERIES[codigo][3])
    filas: list[dict] = []
    for anio in range(ini.year, fin.year + 1):
        filas.extend(descargar_anio(codigo, anio, cache=cache))
        if pausa and not (cache and es_periodo_cerrado(anio)):
            time.sleep(pausa)  # API pública y gratuita: sin apuro
    df = _a_dataframe(filas, codigo)
    out = df[(df["fecha"] >= ini) & (df["fecha"] <= fin)].reset_index(drop=True)
    out.attrs["duplicados"] = df.attrs.get("duplicados", [])
    return out


def limpiar_uf(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Corrige la serie diaria de UF y devuelve ``(serie limpia, informe de cambios)``.

    Tres defectos reales de la fuente:

    * **Días duplicados** (2015-07-11 aparece cinco veces): se colapsan si son idénticos.
    * **Días faltantes** (2015-12-12, 2015-12-31): la UF crece a tasa geométrica constante
      entre el 10 de un mes y el 9 del siguiente, así que interpolar geométricamente entre
      los vecinos reproduce el valor que habría publicado la fórmula. Huecos de más de
      ``MAX_DIAS_A_INTERPOLAR`` días levantan un error en vez de rellenarse.
    * **El dólar filtrado en la UF**: el 29 y 30 de diciembre de 2014 la "UF" vale 608,15 y
      607,38, que es el dólar observado. Todo día que se mueva más de 1% respecto del último
      valor válido se descarta y se interpola como un día faltante.
    """
    if df.empty:
        return df.copy(), {"duplicados": 0, "descartados": [], "interpolados": []}
    valores = df.set_index("fecha")["uf"].astype(float)
    duplicados = int(valores.index.duplicated().sum())
    valores = valores[~valores.index.duplicated()].sort_index()

    # Comparar contra el último valor *válido*, no el anterior crudo: dos días corruptos
    # seguidos (como en 2014) se validarían entre sí.
    descartados = []
    ultimo = None
    for dia, v in valores.items():
        if ultimo is not None and abs(math.log(v / ultimo)) > MAX_MOVIMIENTO_DIARIO_UF:
            descartados.append(dia)
            continue
        ultimo = v
    valores = valores.drop(descartados)

    completo = pd.date_range(valores.index.min(), valores.index.max(), freq="D")
    faltantes = completo.difference(valores.index)
    if len(faltantes):
        # Largo de cada hueco: días consecutivos faltantes
        bloques = (pd.Series(faltantes).diff() != pd.Timedelta(days=1)).cumsum()
        largo = pd.Series(faltantes).groupby(bloques).transform("size")
        if largo.max() > MAX_DIAS_A_INTERPOLAR:
            peor = pd.Series(faltantes)[largo == largo.max()].iloc[0]
            raise ValueError(f"Hueco de {largo.max()} días en la UF desde {peor.date()}: "
                             "demasiado largo para interpolar")
    log = pd.Series(valores.apply(math.log)).reindex(completo).interpolate(method="time")
    limpio = pd.DataFrame({"fecha": completo, "uf": log.apply(math.exp).values})
    informe = {
        "duplicados": duplicados,
        "descartados": [d.date() for d in descartados],
        "interpolados": [d.date() for d in faltantes],
    }
    return limpio, informe


def uf(desde=None, hasta=None, cache: bool = True) -> pd.DataFrame:
    """UF diaria (un valor por día calendario), corregida con :func:`limpiar_uf`.

    El informe de lo corregido queda en ``df.attrs["informe"]``.
    """
    ini, fin = rango(desde, hasta, minimo=SERIES["uf"][3])
    # Se baja un margen de 10 días a cada lado para poder validar e interpolar también el
    # primer y el último día pedidos (la UF se publica por adelantado hasta el día 9).
    margen = pd.Timedelta(days=10)
    crudo = serie("uf", desde=str((ini - margen).date()), hasta=str((fin + margen).date()), cache=cache)
    limpio, informe = limpiar_uf(crudo)
    # serie() ya quitó las copias idénticas: se suman a las que haya encontrado limpiar_uf()
    informe["duplicados"] += sum(ini.date() <= d <= fin.date() for d in crudo.attrs.get("duplicados", []))
    en_rango = lambda dias: [d for d in dias if ini.date() <= d <= fin.date()]  # noqa: E731
    informe["descartados"] = en_rango(informe["descartados"])
    informe["interpolados"] = en_rango(informe["interpolados"])
    out = limpio[(limpio["fecha"] >= ini) & (limpio["fecha"] <= fin)].reset_index(drop=True)
    out.attrs["informe"] = informe
    return out


def dolar(desde=None, hasta=None, cache: bool = True) -> pd.DataFrame:
    """Dólar observado (pesos por dólar), días hábiles."""
    return serie("dolar", desde, hasta, cache)


def cobre(desde=None, hasta=None, cache: bool = True) -> pd.DataFrame:
    """Precio de la libra de cobre (dólares), días hábiles."""
    return serie("libra_cobre", desde, hasta, cache)
