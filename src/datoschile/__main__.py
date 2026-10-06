"""Línea de comandos: baja una serie y la guarda en CSV.

    python -m datoschile uf --desde 2020 --salida uf.csv
    python -m datoschile serie libra_cobre --desde 2024
    python -m datoschile valor-cuota --fondos AE --desde 2024
    python -m datoschile indice --fondos A --desde 2008 --real
    python -m datoschile morosidad --desde 2020-01 --solo-sistema
"""
from __future__ import annotations

import argparse
import sys

from . import cmf, indicadores, pensiones


def _desde_hasta(v: str | None):
    return int(v) if v and v.isdigit() else v


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="datoschile", description="Datos públicos de Chile a CSV.")
    sub = p.add_subparsers(dest="comando", required=True)

    def comun(sp):
        sp.add_argument("--desde", help="año, AAAA-MM o AAAA-MM-DD")
        sp.add_argument("--hasta", help="año, AAAA-MM o AAAA-MM-DD")
        sp.add_argument("--salida", "-o", help="archivo CSV (por defecto, la pantalla)")
        sp.add_argument("--sin-cache", action="store_true", help="no leer ni guardar la caché en disco")

    comun(sub.add_parser("uf", help="UF diaria limpia"))
    s = sub.add_parser("serie", help="cualquier serie de mindicador")
    s.add_argument("codigo", choices=sorted(indicadores.SERIES))
    comun(s)
    v = sub.add_parser("valor-cuota", help="valor cuota y patrimonio por AFP")
    v.add_argument("--fondos", default="ABCDE")
    comun(v)
    i = sub.add_parser("indice", help="índice del fondo ponderado por patrimonio")
    i.add_argument("--fondos", default="ABCDE")
    i.add_argument("--real", action="store_true", help="deflactado por UF")
    comun(i)
    m = sub.add_parser("morosidad", help="morosidad 90+ días por banco (CMF)")
    m.add_argument("--solo-sistema", action="store_true")
    comun(m)

    a = p.parse_args(argv)
    desde, hasta, cache = _desde_hasta(a.desde), _desde_hasta(a.hasta), not a.sin_cache
    if a.comando == "uf":
        df = indicadores.uf(desde, hasta, cache=cache)
    elif a.comando == "serie":
        df = indicadores.serie(a.codigo, desde, hasta, cache=cache)
    elif a.comando == "valor-cuota":
        df = pensiones.valor_cuota(a.fondos, desde, hasta, cache=cache)
    elif a.comando == "indice":
        df = pensiones.indice(a.fondos, desde, hasta, real=a.real, cache=cache)
    else:
        df = cmf.morosidad(desde, hasta, solo_sistema=a.solo_sistema, cache=cache)

    if a.salida:
        df.to_csv(a.salida, index=False)
        print(f"{len(df):,} filas -> {a.salida}", file=sys.stderr)
    else:
        df.to_csv(sys.stdout, index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
