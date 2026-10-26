"""Precios diarios de metales desde Cochilco: cobre (LME y COMEX), oro, plata, zinc, aluminio,
níquel, plomo y estaño.

Fuente: el boletín de estadísticas de la Comisión Chilena del Cobre
(https://boletin.cochilco.cl/estadisticas/grafico.asp), que exporta a Excel cualquier rango de
fechas sin clave ni registro. Es la fuente oficial chilena del precio LME.

Cochilco publica el cobre y los metales base en **centavos** de dólar por libra; aquí se
convierten a dólares por libra, la unidad en que se habla del cobre en Chile. El oro y la
plata van en dólares por onza troy.

El cobre y los metales base están al día. El oro y la plata no: en octubre de 2026 Cochilco
publicaba Londres solo hasta noviembre de 2025 y COMEX hasta marzo de 2026. Cuando una serie
lleva más de :data:`DIAS_SIN_DATOS` días sin datos, :func:`precio` lo avisa con un ``warning``.

    >>> from datoschile import cochilco
    >>> cochilco.precio("cobre", desde=2024)                  # LME, US$/lb
    >>> cochilco.precio("cobre", desde=2024, bolsa="COMEX")
    >>> cochilco.precio("oro", desde=2020)                     # US$/oz troy
"""
from __future__ import annotations

import re
import time
import warnings

import pandas as pd

from . import _red
from ._fechas import es_periodo_cerrado, rango

URL = "https://boletin.cochilco.cl/estadisticas/grafico/crear_excel.asp"

#: metal -> (nombre en Cochilco, bolsas disponibles (la primera es la de omisión), unidad,
#: divisor para llegar a la unidad, primer año con datos por bolsa)
METALES: dict[str, tuple[str, tuple[str, ...], str, float, dict[str, int]]] = {
    "cobre": ("Cobre", ("LME", "COMEX"), "dólares por libra", 100, {"LME": 1996, "COMEX": 2005}),
    "oro": ("Oro", ("LBM Inicial", "Handy & Harman", "COMEX"), "dólares por onza troy", 1, {}),
    "plata": ("Plata", ("London Fix", "Handy & Harman", "COMEX"), "dólares por onza troy", 1, {}),
    "zinc": ("Zinc", ("LME",), "dólares por libra", 100, {}),
    "aluminio": ("Aluminio", ("LME",), "dólares por libra", 100, {}),
    "niquel": ("Niquel", ("LME",), "dólares por libra", 100, {}),
    "plomo": ("Plomo", ("LME",), "dólares por libra", 100, {}),
    "estanio": ("Estanio", ("LME",), "dólares por libra", 100, {}),
}
#: Primer año para los metales que no lo indican en :data:`METALES`.
PRIMER_ANIO = 2001
#: Días sin datos al final del rango pedido a partir de los cuales se avisa que la serie
#: dejó de actualizarse (más que cualquier feriado largo de las bolsas).
DIAS_SIN_DATOS = 30

_FILA = re.compile(r"<TD>\s*(\d{2})/(\d{2})/(\d{4})\s*</TD>\s*<TD>\s*([-\d.,]+)\s*</TD>", re.I)


def _formulario(nombre: str, bolsa: str, anio: int) -> dict:
    """Los campos que envía el botón "Exportar a Excel" del boletín, para un año completo."""
    return {
        "tipo_metal": nombre, "tipo_metal_excel": nombre, "tipo_consulta": 1, "tipo_consulta_excel": 1,
        "bolsa_final": bolsa, "bolsa3": bolsa, "bolsa_excel": bolsa, "bandera": "S",
        "dia": 1, "mes": 1, "anio": anio, "dia1": 31, "mes1": 12, "anio1": anio,
    }


def _numero(texto: str) -> float:
    """``393,97`` -> 393.97 y ``1.280,26`` -> 1280.26."""
    return float(texto.replace(".", "").replace(",", ".")) if "," in texto else float(texto)


def parsear(html: str) -> list[dict]:
    """Pares fecha/valor del "Excel" (una tabla HTML) que entrega Cochilco."""
    filas = [{"fecha": f"{a}-{m}-{d}", "valor": _numero(v)} for d, m, a, v in _FILA.findall(html)]
    return sorted(filas, key=lambda f: f["fecha"])


def _validar(metal: str, bolsa: str | None) -> tuple[str, str]:
    if metal not in METALES:
        raise ValueError(f"Metal desconocido '{metal}'. Disponibles: {', '.join(METALES)}")
    bolsas = METALES[metal][1]
    bolsa = bolsa or bolsas[0]
    if bolsa not in bolsas:
        raise ValueError(f"Bolsa '{bolsa}' no disponible para {metal}. Disponibles: {', '.join(bolsas)}")
    return metal, bolsa


def primer_anio(metal: str, bolsa: str | None = None) -> int:
    metal, bolsa = _validar(metal, bolsa)
    return METALES[metal][4].get(bolsa, PRIMER_ANIO)


def descargar_anio(metal: str, anio: int, bolsa: str | None = None, cache: bool = True) -> list[dict]:
    """Precios de un año tal como los publica Cochilco (centavos por libra en metales base)."""
    metal, bolsa = _validar(metal, bolsa)
    nombre = METALES[metal][0]
    carpeta = re.sub(r"[^a-z0-9]+", "_", bolsa.lower())
    contenido = _red.con_cache(
        f"cochilco/{metal}/{carpeta}/{anio}.htm",
        lambda: _red.descargar(URL, datos=_formulario(nombre, bolsa, anio)),
        usar_cache=cache and es_periodo_cerrado(anio),
    )
    return parsear(contenido.decode("latin-1"))


def precio(metal: str = "cobre", desde=None, hasta=None, bolsa: str | None = None,
           cache: bool = True, pausa: float = 0.3) -> pd.DataFrame:
    """Precio diario de un metal: columnas ``fecha`` y ``<metal>``.

    La unidad queda en ``df.attrs["unidad"]`` y la bolsa en ``df.attrs["bolsa"]``.
    """
    metal, bolsa = _validar(metal, bolsa)
    ini, fin = rango(desde, hasta, minimo=primer_anio(metal, bolsa))
    filas: list[dict] = []
    for anio in range(ini.year, fin.year + 1):
        filas.extend(descargar_anio(metal, anio, bolsa, cache=cache))
        if pausa and not (cache and es_periodo_cerrado(anio)):
            time.sleep(pausa)
    divisor = METALES[metal][3]
    if filas:
        df = pd.DataFrame(filas).drop_duplicates("fecha")
        df["fecha"] = pd.to_datetime(df["fecha"])
        df[metal] = (df.pop("valor") / divisor).round(6)
    else:
        df = pd.DataFrame({"fecha": pd.Series(dtype="datetime64[ns]"), metal: pd.Series(dtype=float)})
    out = df[(df["fecha"] >= ini) & (df["fecha"] <= fin)].sort_values("fecha").reset_index(drop=True)
    ultimo = out["fecha"].max() if len(out) else ini
    if (fin - ultimo).days > DIAS_SIN_DATOS:
        warnings.warn(f"Cochilco no publica {metal} ({bolsa}) desde {ultimo.date()}; el rango pedido "
                      f"llega a {fin.date()}.", stacklevel=2)
    out.attrs.update({"unidad": METALES[metal][2], "bolsa": bolsa, "fuente": "Cochilco"})
    return out


def cobre(desde=None, hasta=None, bolsa: str = "LME", cache: bool = True) -> pd.DataFrame:
    """Precio diario del cobre en dólares por libra (LME por omisión), el mismo día de la bolsa."""
    return precio("cobre", desde, hasta, bolsa=bolsa, cache=cache)
