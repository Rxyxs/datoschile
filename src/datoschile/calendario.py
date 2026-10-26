"""Feriados legales de Chile y días hábiles, calculados desde la ley y sin conexión.

Los feriados fijos y los que se mueven (Semana Santa, San Pedro y San Pablo, Encuentro de
Dos Mundos, Iglesias Evangélicas, Pueblos Indígenas, los "sándwich" de Fiestas Patrias y el
2 de enero) salen de las reglas de cada ley, así que sirven también para años futuros. Las
elecciones, el censo de 2017 y los feriados de una sola vez se declaran por ley cada vez, y
van en :data:`EXTRAORDINARIOS` hasta el último año revisado (:data:`ULTIMO_ANIO_REVISADO`).

Validado contra la tabla anual de feriados.cl de 2009 a 2027 y contra los días en que el
Banco Central no publicó dólar observado (ver ``tests/test_calendario.py``).

    >>> from datoschile import calendario
    >>> calendario.feriados(2026)                          # tabla del año
    >>> calendario.dias_habiles("2026-09-01", "2026-09-30")
    >>> calendario.sumar_habiles("2026-09-17", 1)          # 2026-09-21
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import pandas as pd

#: Desde 2008 rigen todas las leyes que mueven feriados (la última, la 20.299 de las
#: Iglesias Evangélicas). Antes de eso las reglas eran otras y no están validadas.
PRIMER_ANIO = 2008
#: Último año cuyos feriados extraordinarios (elecciones, leyes de una vez) están cargados.
ULTIMO_ANIO_REVISADO = 2027

# Feriados irrenunciables para el comercio (Ley 19.973); el 19 de septiembre, desde la Ley
# 20.629 de 2012.
_IRRENUNCIABLES = {"Año Nuevo", "Día Nacional del Trabajo", "Independencia Nacional", "Navidad"}


def _es_irrenunciable(nombre: str, anio: int) -> bool:
    return nombre in _IRRENUNCIABLES or (nombre == "Día de las Glorias del Ejército" and anio >= 2012)


#: Elecciones, plebiscitos y feriados de una sola vez, de alcance nacional.
#: fecha -> (nombre, ley, irrenunciable). Las elecciones son irrenunciables para el comercio
#: desde las municipales de 2016; antes eran feriado común.
EXTRAORDINARIOS: dict[str, tuple[str, str, bool]] = {
    "2008-10-26": ("Elecciones municipales", "Ley 18.700", False),
    "2009-12-13": ("Elecciones presidenciales y parlamentarias", "Ley 18.700", False),
    "2010-01-17": ("Segunda vuelta presidencial", "Ley 18.700", False),
    "2010-09-17": ("Feriado del Bicentenario", "Ley 20.450", False),
    "2010-09-20": ("Feriado del Bicentenario", "Ley 20.450", True),
    "2012-10-28": ("Elecciones municipales", "Ley 18.700", False),
    "2013-06-30": ("Primarias presidenciales", "Ley 20.640", False),
    "2013-11-17": ("Elecciones presidenciales y parlamentarias", "Ley 18.700", False),
    "2013-12-15": ("Segunda vuelta presidencial", "Ley 18.700", False),
    "2016-06-19": ("Primarias municipales", "Ley 20.640", False),
    "2016-10-23": ("Elecciones municipales", "Ley 20.873", True),
    "2017-04-19": ("Censo abreviado", "Ley 19.790", True),
    "2017-07-02": ("Primarias presidenciales y parlamentarias", "Ley 20.640", True),
    "2017-11-19": ("Elecciones presidenciales y parlamentarias", "Ley 18.700", True),
    "2017-12-17": ("Segunda vuelta presidencial", "Ley 18.700", True),
    "2020-10-25": ("Plebiscito constitucional", "Ley 21.200", True),
    "2021-05-15": ("Elecciones municipales, regionales y de convencionales", "Ley 21.324", True),
    "2021-05-16": ("Elecciones municipales, regionales y de convencionales", "Ley 21.324", True),
    "2021-06-13": ("Segunda vuelta de gobernadores regionales", "Ley 18.700", True),
    "2021-07-18": ("Primarias presidenciales", "Ley 20.640", True),
    "2021-11-21": ("Elecciones presidenciales y parlamentarias", "Ley 18.700", True),
    "2021-12-19": ("Segunda vuelta presidencial", "Ley 18.700", True),
    "2022-09-04": ("Plebiscito constitucional de salida", "Ley 18.700", True),
    "2022-09-16": ("Feriado adicional de Fiestas Patrias", "Ley 21.482", False),
    "2023-05-07": ("Elección de consejeros constitucionales", "Ley 21.533", True),
    "2023-12-17": ("Plebiscito constitucional", "Ley 21.533", True),
    "2024-06-09": ("Primarias de alcaldes y gobernadores", "Ley 20.640", True),
    "2024-10-27": ("Elecciones municipales y regionales", "Ley 18.700", True),
    "2024-11-24": ("Segunda vuelta de gobernadores regionales", "Ley 18.700", True),
    "2025-06-29": ("Primarias presidenciales y parlamentarias", "Ley 20.640", True),
    "2025-11-16": ("Elecciones presidenciales y parlamentarias", "Ley 18.700", True),
    "2025-12-14": ("Segunda vuelta presidencial", "Ley 18.700", True),
}

#: Feriados regionales permanentes: (mes, día, nombre, alcance, ley, primer año).
REGIONALES = [
    (6, 7, "Asalto y Toma del Morro de Arica", "Región de Arica y Parinacota", "Ley 20.663", 2013),
    (8, 20, "Nacimiento del Prócer de la Independencia", "Chillán y Chillán Viejo", "Ley 20.768", 2014),
]


def pascua(anio: int) -> date:
    """Domingo de Pascua (calendario gregoriano, algoritmo anónimo de Meeus/Jones/Butcher)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes, dia = divmod(h + l_ - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


# Términos periódicos de Meeus, "Astronomical Algorithms", tabla 27.C: (A, B, C)
_SOLSTICIO_TERMINOS = [
    (485, 324.96, 1934.136), (203, 337.23, 32964.467), (199, 342.08, 20.186),
    (182, 27.85, 445267.112), (156, 73.14, 45036.886), (136, 171.52, 22518.443),
    (77, 222.54, 65928.934), (74, 296.72, 3034.906), (70, 243.58, 9037.513),
    (58, 119.81, 33718.147), (52, 297.17, 150.678), (50, 21.02, 2281.226),
    (45, 247.54, 29929.562), (44, 325.15, 31555.956), (29, 60.93, 4443.417),
    (18, 155.12, 67555.328), (17, 288.79, 4562.452), (16, 198.04, 62894.029),
    (14, 199.76, 31436.921), (12, 95.39, 14577.848), (12, 287.11, 31931.756),
    (12, 320.81, 34777.259), (9, 227.73, 1222.114), (8, 15.45, 16859.074),
]


def solsticio_de_junio(anio: int) -> datetime:
    """Instante del solsticio de junio (invierno austral) en UTC, con error de pocos minutos."""
    y = (anio - 2000) / 1000
    jde0 = 2451716.56767 + 365241.62603 * y + 0.00325 * y**2 + 0.00888 * y**3 - 0.00030 * y**4
    t = (jde0 - 2451545.0) / 36525
    w = math.radians(35999.373 * t - 2.47)
    dl = 1 + 0.0334 * math.cos(w) + 0.0007 * math.cos(2 * w)
    s = sum(a * math.cos(math.radians(b + c * t)) for a, b, c in _SOLSTICIO_TERMINOS)
    jde = jde0 + 0.00001 * s / dl
    # Día juliano -> fecha; la diferencia TT-UTC (~69 s) es despreciable aquí.
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jde - 2451545.0)


def _trasladar_a_lunes(d: date) -> date:
    """Ley 19.668: de martes a jueves, al lunes anterior; el viernes, al lunes siguiente."""
    wd = d.weekday()  # lunes = 0
    if wd in (1, 2, 3):
        return d - timedelta(days=wd)
    if wd == 4:
        return d + timedelta(days=3)
    return d


def _iglesias_evangelicas(anio: int) -> date:
    """Ley 20.299: si el 31 de octubre es martes, pasa al viernes anterior; si es miércoles,
    al viernes siguiente."""
    d = date(anio, 10, 31)
    if d.weekday() == 1:
        return d - timedelta(days=4)
    if d.weekday() == 2:
        return d + timedelta(days=2)
    return d


def _feriados_anio(anio: int, regionales: bool) -> list[tuple[date, str, str, str]]:
    """(fecha, nombre, ley, alcance, irrenunciable) de un año."""
    nac = "Nacional"
    p = pascua(anio)
    f = [
        (date(anio, 1, 1), "Año Nuevo", "Ley 2.977"),
        (p - timedelta(days=2), "Viernes Santo", "Ley 2.977"),
        (p - timedelta(days=1), "Sábado Santo", "Ley 2.977"),
        (date(anio, 5, 1), "Día Nacional del Trabajo", "Código del Trabajo"),
        (date(anio, 5, 21), "Día de las Glorias Navales", "Ley 2.977"),
        (_trasladar_a_lunes(date(anio, 6, 29)), "San Pedro y San Pablo", "Ley 19.668"),
        (date(anio, 7, 16), "Día de la Virgen del Carmen", "Ley 20.148"),
        (date(anio, 8, 15), "Asunción de la Virgen", "Ley 2.977"),
        (date(anio, 9, 18), "Independencia Nacional", "Ley 2.977"),
        (date(anio, 9, 19), "Día de las Glorias del Ejército", "Ley 2.977"),
        (_trasladar_a_lunes(date(anio, 10, 12)), "Encuentro de Dos Mundos", "Ley 19.668"),
        (_iglesias_evangelicas(anio), "Día de las Iglesias Evangélicas y Protestantes", "Ley 20.299"),
        (date(anio, 11, 1), "Día de Todos los Santos", "Ley 2.977"),
        (date(anio, 12, 8), "Inmaculada Concepción", "Ley 2.977"),
        (date(anio, 12, 25), "Navidad", "Ley 2.977"),
    ]
    if anio >= 2017 and date(anio, 1, 2).weekday() == 0:
        f.append((date(anio, 1, 2), "Feriado adicional de Año Nuevo", "Ley 20.983"))
    if anio >= 2021:
        # Ley 21.357: el día del solsticio de invierno, en hora de Chile continental (UTC-4 en
        # junio). En 2025 el solsticio fue el 21 a las 02:43 UTC, el 20 a las 22:43 en Chile,
        # y el feriado fue el 20. En 2021 la ley se promulgó ese mismo mes y fijó el día 21
        # (en Chile el solsticio cayó el 20 a las 23:32).
        dia = date(2021, 6, 21) if anio == 2021 else (solsticio_de_junio(anio) - timedelta(hours=4)).date()
        f.append((dia, "Día Nacional de los Pueblos Indígenas", "Ley 21.357"))
    sep17, sep20 = date(anio, 9, 17), date(anio, 9, 20)
    if sep17.weekday() == 0 or (anio >= 2017 and sep17.weekday() == 4):
        ley = "Ley 20.215" if sep17.weekday() == 0 else "Ley 20.983"
        f.append((sep17, "Feriado adicional de Fiestas Patrias", ley))
    if sep20.weekday() == 4:
        f.append((sep20, "Feriado adicional de Fiestas Patrias", "Ley 20.215"))
    out = [(d, n, ley, nac, _es_irrenunciable(n, anio)) for d, n, ley in f]
    for fecha, (nombre, ley, irrenunciable) in EXTRAORDINARIOS.items():
        if fecha.startswith(f"{anio}-"):
            out.append((date.fromisoformat(fecha), nombre, ley, nac, irrenunciable))
    if regionales:
        out += [(date(anio, m, d), n, ley, alc, False) for m, d, n, alc, ley, desde in REGIONALES if anio >= desde]
    return out


def _anios(desde, hasta) -> tuple[date, date]:
    hoy = date.today()

    def a_fecha(v, fin: bool) -> date:
        if v is None:
            return date(hoy.year, 12, 31) if fin else date(hoy.year, 1, 1)
        if isinstance(v, int):
            return date(v, 12, 31) if fin else date(v, 1, 1)
        ts = pd.Timestamp(v)
        if isinstance(v, str) and len(v.strip()) == 7:  # "AAAA-MM"
            return (ts + pd.offsets.MonthEnd(0)).date() if fin else ts.date()
        return ts.date()

    ini = a_fecha(desde, fin=False)
    # Un solo año: feriados(2026) es todo 2026.
    fin = a_fecha(desde if hasta is None and isinstance(desde, int) else hasta, fin=True)
    if ini.year < PRIMER_ANIO:
        raise ValueError(f"Los feriados están validados desde {PRIMER_ANIO}; pedido: {ini.year}")
    if ini > fin:
        raise ValueError(f"Rango vacío: {ini} es posterior a {fin}")
    return ini, fin


def feriados(desde=None, hasta=None, regionales: bool = False) -> pd.DataFrame:
    """Feriados legales entre ``desde`` y ``hasta`` (por defecto, el año en curso).

    ``feriados(2026)`` es todo 2026. Columnas: ``fecha``, ``nombre``, ``irrenunciable``
    (comercio cerrado, Ley 19.973), ``ley`` y ``alcance`` (``"Nacional"``, o la región o
    comuna si ``regionales=True``). Un día con dos motivos aparece una sola vez, con ambos
    nombres.
    """
    ini, fin = _anios(desde, hasta)
    filas = []
    for anio in range(ini.year, fin.year + 1):
        filas.extend(_feriados_anio(anio, regionales))
    df = pd.DataFrame(filas, columns=["fecha", "nombre", "ley", "alcance", "irrenunciable"])
    df = (df.groupby(["fecha", "alcance"], as_index=False, sort=True)
            .agg({"nombre": " / ".join, "ley": lambda s: ", ".join(dict.fromkeys(s)), "irrenunciable": "any"}))
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df[(df["fecha"] >= pd.Timestamp(ini)) & (df["fecha"] <= pd.Timestamp(fin))]
    df = df.sort_values(["fecha", "alcance"]).reset_index(drop=True)
    return df[["fecha", "nombre", "irrenunciable", "ley", "alcance"]]


_cache_anios: dict[int, frozenset] = {}


def _no_habiles(anio: int) -> frozenset:
    if anio not in _cache_anios:
        _cache_anios[anio] = frozenset(d for d, *_ in _feriados_anio(anio, regionales=False))
    return _cache_anios[anio]


def es_feriado(fecha) -> bool:
    """``True`` si la fecha es feriado nacional."""
    d = pd.Timestamp(fecha).date()
    return d in _no_habiles(d.year)


def es_habil(fecha, bancario: bool = False) -> bool:
    """Lunes a viernes que no es feriado nacional.

    Con ``bancario=True`` el 31 de diciembre tampoco es hábil: los bancos no atienden
    público ese día (feriado bancario de la Ley General de Bancos).
    """
    d = pd.Timestamp(fecha).date()
    if d.weekday() >= 5 or d in _no_habiles(d.year):
        return False
    return not (bancario and d.month == 12 and d.day == 31)


def dias_habiles(desde, hasta, bancario: bool = False) -> pd.DatetimeIndex:
    """Días hábiles entre ``desde`` y ``hasta``, ambos incluidos."""
    ini, fin = pd.Timestamp(desde).normalize(), pd.Timestamp(hasta).normalize()
    dias = pd.date_range(ini, fin, freq="D")
    return dias[[es_habil(d, bancario) for d in dias]]


def sumar_habiles(fecha, n: int, bancario: bool = False) -> pd.Timestamp:
    """La fecha ``n`` días hábiles después (o antes, si ``n`` es negativo) de ``fecha``.

    ``sumar_habiles(f, 0)`` devuelve ``f`` si es hábil, o el siguiente hábil si no lo es.
    """
    d = pd.Timestamp(fecha).normalize()
    paso = 1 if n >= 0 else -1
    if n == 0:
        while not es_habil(d, bancario):
            d += pd.Timedelta(days=1)
        return d
    restantes = abs(n)
    while restantes:
        d += pd.Timedelta(days=paso)
        if es_habil(d, bancario):
            restantes -= 1
    return d
