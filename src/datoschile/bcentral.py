"""Series oficiales del Banco Central de Chile desde sus páginas públicas, sin clave.

La Base de Datos Estadísticos del Banco Central pide usuario y clave para su API, pero la
página "Indicadores diarios" (https://si3.bcentral.cl/Indicadoressiete/secure/Indicadoresdiarios.aspx)
publica sin registro la historia de 17 series. Cada serie es una tabla HTML:

* **diarias** (TPM, dólar, euro, UF, cobre...): un año por página, días en filas y meses en
  columnas; los otros años se piden con el selector de año de la página (un *postback* de
  ASP.NET), uno por uno;
* **mensuales** (IMACEC, IPC, desempleo, UTM, reservas): toda la historia en una página,
  años en filas y meses en columnas;
* **trimestrales** (PIB): años en filas y trimestres en columnas.

Es la fuente oficial de lo que mindicador.cl replica, y el respaldo cuando mindicador no
responde.

    >>> from datoschile import bcentral
    >>> bcentral.serie("tpm", desde=2020)
    >>> bcentral.serie("imacec")                 # mensual, desde 1997
    >>> bcentral.serie("desempleo", desde=2015)
"""
from __future__ import annotations

import re
import time

import pandas as pd

from . import _red
from ._fechas import es_periodo_cerrado, rango

URL_BASE = "https://si3.bcentral.cl/Indicadoressiete/secure/"
URL_INDICE = URL_BASE + "Indicadoresdiarios.aspx"

#: código -> (código del Banco Central, descripción, unidad, frecuencia)
SERIES: dict[str, tuple[str, str, str, str]] = {
    "dolar": ("PRE_TCO", "Dólar observado", "pesos por dólar", "diaria"),
    "euro": ("PRE_EUR", "Euro", "pesos por euro", "diaria"),
    "uf": ("UF", "Unidad de fomento", "pesos", "diaria"),
    "ivp": ("IVP", "Índice de valor promedio", "pesos", "diaria"),
    "tpm": ("TPM", "Tasa de política monetaria", "%", "diaria"),
    "cobre": ("LIBRA_COBRE", "Precio del cobre", "dólares por libra", "diaria"),
    "oro": ("ONZA_ORO", "Precio del oro", "dólares por onza", "diaria"),
    "plata": ("ONZA_PLATA", "Precio de la plata", "dólares por onza", "diaria"),
    "tcm": ("IND_TCM", "Tipo de cambio multilateral", "índice 2-ene-1998 = 100", "diaria"),
    "euro_por_dolar": ("PAR_EUR", "Paridad euro", "euros por dólar", "diaria"),
    "yen_por_dolar": ("PAR_JPY", "Paridad yen", "yenes por dólar", "diaria"),
    "utm": ("PRE_UTM", "Unidad tributaria mensual", "pesos", "mensual"),
    "ipc": ("IPC", "IPC, variación mensual", "%", "mensual"),
    "imacec": ("IMC_EP03_YTYPCT", "IMACEC, variación anual (serie empalmada)", "%", "mensual"),
    "desempleo": ("TAS_DES_INE", "Tasa de desocupación nacional (INE)", "%", "mensual"),
    "reservas": ("ACT_RES_USD", "Activos de reserva", "millones de dólares", "mensual"),
    "pib": ("PIB_RE_EP03", "PIB a precios del año anterior encadenado", "miles de millones de pesos", "trimestral"),
}

_ENLACE = re.compile(r'Serie\.aspx\?gcode=([A-Z0-9_]+)&amp;param=([^"]+)"')
_OCULTO = re.compile(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"')
_TABLA = re.compile(r'<table[^>]*id="gr"(.*?)</table>', re.S)
_FILA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELDA = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
_ANIO_OPCION = re.compile(r'<option[^>]*value="(\d{4})"')
_ANIO_ELEGIDO = re.compile(r'<option selected="selected" value="(\d{4})"')

_enlaces: dict[str, str] = {}


def _validar(codigo: str) -> None:
    if codigo not in SERIES:
        raise ValueError(f"Serie desconocida '{codigo}'. Disponibles: {', '.join(SERIES)}")


def _url(gcode: str) -> str:
    """La página de cada serie lleva un parámetro opaco que se lee del índice (una vez por sesión)."""
    if gcode not in _enlaces:
        html = _red.descargar(URL_INDICE).decode("latin-1")
        _enlaces.update({g: p for g, p in _ENLACE.findall(html)})
        if gcode not in _enlaces:
            raise ValueError(f"El Banco Central ya no publica {gcode} en Indicadores diarios")
    return f"{URL_BASE}Serie.aspx?gcode={gcode}&param={_enlaces[gcode]}"


def _numero(texto: str) -> float | None:
    """``1.071,09`` -> 1071.09; vacío -> None."""
    texto = re.sub(r"<[^>]+>|&nbsp;", "", texto).strip()
    if not texto:
        return None
    return float(texto.replace(".", "").replace(",", "."))


def _filas(html: str) -> list[list[str]]:
    m = _TABLA.search(html)
    if not m:
        raise ValueError("La página del Banco Central no trae la tabla de datos (¿cambió el formato?)")
    return [_CELDA.findall(f) for f in _FILA.findall(m.group(1))]


def parsear_diaria(html: str, anio: int) -> list[dict]:
    """Tabla de un año: fila = día del mes, columna = mes."""
    filas = _filas(html)
    out = []
    for celdas in filas[1:]:
        dia = int(re.sub(r"<[^>]+>", "", celdas[0]).strip())
        for mes, celda in enumerate(celdas[1:13], start=1):
            v = _numero(celda)
            if v is not None:
                out.append({"fecha": f"{anio:04d}-{mes:02d}-{dia:02d}", "valor": v})
    return sorted(out, key=lambda f: f["fecha"])


def parsear_por_anio(html: str, por_anio: int) -> list[dict]:
    """Tabla con un año por fila y 12 meses (o 4 trimestres) por columna."""
    out = []
    for celdas in _filas(html)[1:]:
        anio = int(re.sub(r"<[^>]+>", "", celdas[0]).strip())
        for k, celda in enumerate(celdas[1:por_anio + 1]):
            v = _numero(celda)
            if v is not None:
                mes = k + 1 if por_anio == 12 else 3 * k + 1  # trimestre -> su primer mes
                out.append({"fecha": f"{anio:04d}-{mes:02d}-01", "valor": v})
    return out


def anios_disponibles(html: str) -> list[int]:
    return sorted(int(a) for a in _ANIO_OPCION.findall(html))


def _postback_anio(url: str, html_actual: str, anio: int) -> bytes:
    """Lo que hace el selector de año de la página: reenviar el formulario con otro año."""
    campos = dict(_OCULTO.findall(html_actual))
    campos.update({"__EVENTTARGET": "DrDwnFechas", "__EVENTARGUMENT": "", "DrDwnFechas": str(anio)})
    return _red.descargar(url, datos=campos)


def descargar_anio(codigo: str, anio: int, cache: bool = True) -> list[dict]:
    """Observaciones de un año de una serie diaria."""
    _validar(codigo)
    gcode, _, _, frecuencia = SERIES[codigo]
    if frecuencia != "diaria":
        raise ValueError(f"{codigo} es {frecuencia}: usa serie()")

    def obtener() -> bytes:
        url = _url(gcode)
        portada = _red.descargar(url)
        html = portada.decode("latin-1")
        elegido = _ANIO_ELEGIDO.search(html)
        if elegido and int(elegido.group(1)) == anio:
            return portada  # la página abre en el último año
        if anio not in anios_disponibles(html):
            return b""  # la serie no tiene ese año
        return _postback_anio(url, html, anio)

    contenido = _red.con_cache(f"bcentral/{gcode}/{anio}.htm", obtener, usar_cache=cache and es_periodo_cerrado(anio))
    return parsear_diaria(contenido.decode("latin-1"), anio) if contenido else []


def serie(codigo: str, desde=None, hasta=None, cache: bool = True, pausa: float = 0.3) -> pd.DataFrame:
    """Una serie del Banco Central: columnas ``fecha`` y ``<codigo>``.

    Las mensuales y trimestrales vienen fechadas el primer día de su periodo y se bajan
    enteras en una sola página (sin caché: el Banco Central revisa cifras pasadas, como el
    IMACEC). Las diarias se piden por año y los años cerrados se guardan en caché.
    """
    _validar(codigo)
    gcode, descripcion, unidad, frecuencia = SERIES[codigo]
    ini, fin = rango(desde, hasta, minimo=1928)
    if frecuencia == "diaria":
        filas: list[dict] = []
        for anio in range(max(ini.year, 1997), fin.year + 1):
            filas.extend(descargar_anio(codigo, anio, cache=cache))
            if pausa and not (cache and es_periodo_cerrado(anio)):
                time.sleep(pausa)
    else:
        html = _red.descargar(_url(gcode)).decode("latin-1")
        filas = parsear_por_anio(html, 12 if frecuencia == "mensual" else 4)
    if filas:
        df = pd.DataFrame(filas).drop_duplicates("fecha")
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.rename(columns={"valor": codigo}).sort_values("fecha")
    else:
        df = pd.DataFrame({"fecha": pd.Series(dtype="datetime64[ns]"), codigo: pd.Series(dtype=float)})
    inicio = ini if frecuencia == "diaria" else ini.to_period("M").to_timestamp()
    out = df[(df["fecha"] >= inicio) & (df["fecha"] <= fin)].reset_index(drop=True)
    out.attrs.update({"descripcion": descripcion, "unidad": unidad, "frecuencia": frecuencia,
                      "fuente": "Banco Central de Chile"})
    return out
