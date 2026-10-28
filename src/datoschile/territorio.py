"""Regiones, provincias y comunas de Chile con su código CUT, y los agregados del Censo 2024.

* :func:`comunas`, :func:`regiones` y :func:`buscar_cut` funcionan **sin conexión**: la
  división político-administrativa (346 comunas, 56 provincias, 16 regiones) viene con la
  librería, tomada del diccionario oficial del Censo 2024 (hoja "DPA").
* :func:`censo` baja la base agregada por zona y localidad que publica el INE (2,9 MB, una
  sola vez: el censo no cambia) y la suma por comuna, provincia o región: población por
  sexo y edad, inmigrantes, pueblos originarios, educación, empleo, hogares, viviendas,
  hacinamiento, servicios básicos y más (unas 190 variables).

El código CUT es la llave para cruzar datos por comuna. Los nombres no lo son: una misma
comuna aparece como "Ñuñoa", "NUNOA" o "Nunoa", y algunas tienen grafías antiguas
("Llay-Llay", "Marchigüe", "Aisén"). :func:`buscar_cut` resuelve esas variantes.

    >>> from datoschile import territorio
    >>> territorio.comunas()                         # sin conexión
    >>> territorio.buscar_cut(["Ñuñoa", "LLAY-LLAY", "santiago centro"])
    >>> territorio.censo()                           # una fila por comuna, ~190 columnas
    >>> territorio.censo(nivel="region")[["region", "n_per", "n_inmigrantes"]]
"""
from __future__ import annotations

import io
import re
import unicodedata
import warnings
import zipfile
from functools import lru_cache
from importlib import resources

import numpy as np
import pandas as pd

from . import _red

URL_CENSO = "https://storage.googleapis.com/bktdescargascenso2024/Datos_agregados/Base_zona_localidad_CPV24.zip"
#: Población censada total publicada por el INE; la suma de la base debe dar exactamente esto.
POBLACION_CENSO_2024 = 18_480_432

#: Grafías antiguas o alternativas -> nombre oficial de la comuna (ya normalizado).
ALIAS = {
    "LLAY LLAY": "LLAILLAY",
    "MARCHIGUE": "MARCHIHUE",
    "COIHAIQUE": "COYHAIQUE",
    "AISEN": "AYSEN",
    "NAVARINO": "CABO DE HORNOS",
    "SANTIAGO CENTRO": "SANTIAGO",
    "CON CON": "CONCON",
    "PAIGUANO": "PAIHUANO",
    "TREGUACO": "TREHUACO",
    "OHIGGINS": "O'HIGGINS",
}

_NIVELES = {
    "comuna": ["cod_region", "region", "cod_provincia", "provincia", "cut", "comuna"],
    "provincia": ["cod_region", "region", "cod_provincia", "provincia"],
    "region": ["cod_region", "region"],
}


def normalizar(nombre: str) -> str:
    """'Ñuñoa' -> 'NUNOA'; 'Llay-Llay' -> 'LLAY LLAY'. Mayúsculas, sin tildes ni signos."""
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9' ]+", " ", s).upper()
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=1)
def _dpa() -> pd.DataFrame:
    with resources.files("datoschile").joinpath("datos/dpa_censo2024.csv").open(encoding="utf-8") as f:
        return pd.read_csv(f)


def comunas() -> pd.DataFrame:
    """Las 346 comunas: ``cut``, ``comuna``, ``cod_provincia``, ``provincia``, ``cod_region``,
    ``region`` (nombres oficiales del Censo 2024, en mayúsculas). Sin conexión."""
    return _dpa()[["cut", "comuna", "cod_provincia", "provincia", "cod_region", "region"]].copy()


def regiones() -> pd.DataFrame:
    """Las 16 regiones con su código y número de provincias y comunas. Sin conexión."""
    d = _dpa()
    return (d.groupby(["cod_region", "region"], as_index=False)
             .agg(provincias=("cod_provincia", "nunique"), comunas=("cut", "nunique")))


def buscar_cut(nombres, region=None):
    """Código CUT de uno o varios nombres de comuna, tolerando tildes, mayúsculas, guiones y
    grafías antiguas. Un nombre que no se encuentra devuelve ``None`` (en una lista, con
    un ``warning`` que los nombra). Con ``region`` (código) se restringe la búsqueda.
    """
    d = _dpa() if region is None else _dpa()[_dpa()["cod_region"] == region]
    llave = dict(zip(d["comuna"].map(normalizar), d["cut"]))
    escalar = isinstance(nombres, str)
    salida, faltan = [], []
    for n in ([nombres] if escalar else list(nombres)):
        k = normalizar(n)
        cut = llave.get(ALIAS.get(k, k))
        if cut is None:
            faltan.append(n)
        salida.append(None if cut is None else int(cut))
    if faltan and not escalar:
        warnings.warn(f"Sin código CUT para {len(faltan)} nombre(s): {faltan[:5]}", stacklevel=2)
    return salida[0] if escalar else salida


def _base_zonas(cache: bool = True) -> pd.DataFrame:
    contenido = _red.con_cache("censo2024/Base_zona_localidad_CPV24.zip", lambda: _red.descargar(URL_CENSO),
                               usar_cache=cache)
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        nombre = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nombre) as f:
            return pd.read_csv(f, sep=";", encoding="utf-8-sig", low_memory=False)


def censo(nivel: str = "comuna", cache: bool = True) -> pd.DataFrame:
    """Agregados del Censo 2024 por ``"comuna"``, ``"provincia"`` o ``"region"``.

    Las columnas ``n_*`` son conteos (personas, hogares o viviendas; ver el diccionario del
    INE). El INE reserva con ``*`` algunos conteos de zonas muy pequeñas: se suman como
    cero y el número de celdas reservadas de cada fila queda en ``celdas_reservadas``, así
    que esos totales son un mínimo. ``prom_edad`` se recalcula ponderando por personas y
    ``prom_per_hog`` como personas por hogar; ``prom_escolaridad18`` (años de estudio de los
    mayores de 18) ponderando por esa población. El INE los publica con coma decimal.
    """
    if nivel not in _NIVELES:
        raise ValueError(f"nivel debe ser uno de {list(_NIVELES)}")
    z = _base_zonas(cache)
    conteos = [c for c in z.columns if c.startswith("n_")]
    valores = z[conteos].apply(lambda c: pd.to_numeric(c, errors="coerce"))
    reservadas = valores.isna().sum(axis=1)
    def decimal(col: str) -> pd.Series:  # el INE publica los promedios con coma decimal: "32,8"
        return pd.to_numeric(z[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    edad, escolaridad = decimal("prom_edad"), decimal("prom_escolaridad18")
    adultos = valores[["n_edad_18_24", "n_edad_25_44", "n_edad_45_59", "n_edad_60_mas"]].sum(axis=1, min_count=1)
    base = pd.concat([z[["CUT"]].rename(columns={"CUT": "cut"}), valores.fillna(0)], axis=1)
    base["celdas_reservadas"] = reservadas
    base["_edad_x_per"] = (edad * valores["n_per"]).fillna(0)
    base["_esc_x_adulto"] = (escolaridad * adultos).fillna(0)
    base["_adultos_con_esc"] = adultos.where(escolaridad.notna()).fillna(0)
    por_comuna = base.groupby("cut", as_index=False).sum()
    out = _dpa().merge(por_comuna, on="cut", how="left", validate="one_to_one")
    if out["n_per"].isna().any():
        raise ValueError("Hay comunas de la DPA sin datos en la base del censo (¿cambió el archivo?)")
    if int(out["n_per"].sum()) != POBLACION_CENSO_2024:
        raise ValueError(f"La base suma {int(out['n_per'].sum()):,} personas y el INE publicó "
                         f"{POBLACION_CENSO_2024:,}: el archivo cambió")
    claves = _NIVELES[nivel]
    if nivel != "comuna":
        sobran = [c for c in _NIVELES["comuna"] if c not in claves]
        out = out.drop(columns=sobran).groupby(claves, as_index=False).sum()
    out["prom_edad"] = (out.pop("_edad_x_per") / out["n_per"]).round(2)
    out["prom_escolaridad18"] = (out.pop("_esc_x_adulto") / out.pop("_adultos_con_esc").replace(0, np.nan)).round(2)
    out["prom_per_hog"] = (out["n_per"] / out["n_hog"].replace(0, np.nan)).round(2)
    num = [c for c in out.columns if c.startswith("n_") or c == "celdas_reservadas"]
    out[num] = out[num].astype("int64")
    return out[claves + ["n_per", "prom_edad", "prom_escolaridad18", "prom_per_hog"]
               + [c for c in num if c != "n_per"]].reset_index(drop=True)


def poblacion(nivel: str = "comuna", cache: bool = True) -> pd.DataFrame:
    """Resumen del censo: población, sexo, grupos de edad, inmigrantes, hogares y viviendas,
    con los porcentajes que más se usan para comparar territorios."""
    c = censo(nivel, cache)
    claves = _NIVELES[nivel]
    out = c[claves].copy()
    out["poblacion"] = c["n_per"]
    out["hombres"], out["mujeres"] = c["n_hombres"], c["n_mujeres"]
    out["edad_promedio"] = c["prom_edad"]
    out["escolaridad_promedio_18"] = c["prom_escolaridad18"]
    out["pct_0_13"] = (c["n_edad_0_5"] + c["n_edad_6_13"]) / c["n_per"] * 100
    out["pct_60_mas"] = c["n_edad_60_mas"] / c["n_per"] * 100
    out["pct_inmigrantes"] = c["n_inmigrantes"] / c["n_per"] * 100
    out["pct_pueblos_originarios"] = c["n_pueblos_orig"] / c["n_per"] * 100
    out["hogares"], out["personas_por_hogar"] = c["n_hog"], c["prom_per_hog"]
    out["viviendas"] = c["n_vp"]
    out["pct_viviendas_hacinadas"] = c["n_viv_hacinadas"] / c["n_vp_ocupada"].replace(0, np.nan) * 100
    pct = [x for x in out.columns if x.startswith("pct_")]
    out[pct] = out[pct].round(2)
    return out
