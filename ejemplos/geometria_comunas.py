"""Genera src/datoschile/datos/comunas_2024.geojson desde la cartografía oficial del Censo 2024.

El INE publica la cartografía por región (capa "Comunal_CPV24" dentro de cada GeoPackage, 765 MB
en total). Este script se corre una sola vez, a mano, para dejar una versión liviana en la
librería: límites simplificados como cobertura (las comunas vecinas siguen compartiendo borde,
sin huecos ni traslapes), sin los islotes de menos de ~2 km² (los fiordos del sur pesan
más que el resto del país junto) y coordenadas a 3 decimales (~100 m). Queda en ~0,9 MB.

    python ejemplos/geometria_comunas.py CARPETA   # CARPETA con los c01.gpkg ... c16.gpkg

Para obtener cada cNN.gpkg: bajar storage.googleapis.com/bktdescargascenso2024/Cartografia/
GPKG/Cartografia_censo2024_RNN.zip y guardar solo la capa Comunal_CPV24.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

SALIDA = Path(__file__).resolve().parents[1] / "src" / "datoschile" / "datos" / "comunas_2024.geojson"
TOLERANCIA = 0.008  # grados (~800 m): invisible a la escala de una comuna
ISLOTE = 2e-4       # grados² (~2 km²); la parte más grande de cada comuna se conserva siempre


def _sin_islotes(geom):
    partes = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon"]
    mayor = max(partes, key=lambda p: p.area)
    return shapely.MultiPolygon([p for p in partes if p.area >= ISLOTE or p is mayor])


def main(carpeta: str) -> None:
    capas = [gpd.read_file(p) for p in sorted(Path(carpeta).glob("c*.gpkg"))]
    g = pd.concat(capas, ignore_index=True)[["CUT", "COMUNA", "geometry"]]
    g = g.to_crs(4326).dissolve("CUT", as_index=False, aggfunc="first")
    if len(g) != 345:  # la cartografía del INE no dibuja la comuna Antártica (12202)
        raise SystemExit(f"Se esperaban 345 comunas y hay {len(g)}")
    g["geometry"] = shapely.make_valid(shapely.coverage_simplify(shapely.make_valid(g.geometry.values), TOLERANCIA))
    g["geometry"] = shapely.set_precision([_sin_islotes(x) for x in g.geometry.values], 1e-3)
    g = g.rename(columns={"CUT": "cut", "COMUNA": "comuna"}).astype({"cut": "int64"}).sort_values("cut")
    datos = json.loads(g.to_json(drop_id=True))
    datos.pop("bbox", None)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{SALIDA.name}: {len(g)} comunas, {SALIDA.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
