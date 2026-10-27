"""Línea de comandos: baja una serie y la guarda en CSV.

    python -m datoschile uf --desde 2020 --salida uf.csv
    python -m datoschile serie libra_cobre --desde 2024
    python -m datoschile valor-cuota --fondos AE --desde 2024
    python -m datoschile indice --fondos A --desde 2008 --real
    python -m datoschile morosidad --desde 2020-01 --solo-sistema
    python -m datoschile resumen
    python -m datoschile bcentral imacec --desde 2015
    python -m datoschile metal cobre --desde 2024 --bolsa COMEX
    python -m datoschile utm-ipc --desde 2010
    python -m datoschile feriados --desde 2026 --regionales
"""
from __future__ import annotations

import argparse
import sys

from . import bcentral, calendario, cmf, cochilco, indicadores, pensiones, sii
from .panel import resumen


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
    r = sub.add_parser("resumen", help="último valor de los indicadores clave")
    r.add_argument("--salida", "-o", help="archivo CSV (por defecto, la pantalla)")
    r.add_argument("--sin-cache", action="store_true", help="no leer ni guardar la caché en disco")
    bc = sub.add_parser("bcentral", help="serie oficial del Banco Central (TPM, IMACEC, desempleo, PIB...)")
    bc.add_argument("codigo", choices=sorted(bcentral.SERIES))
    comun(bc)
    me = sub.add_parser("metal", help="precio diario de un metal (Cochilco)")
    me.add_argument("metal", choices=sorted(cochilco.METALES))
    me.add_argument("--bolsa", help="LME, COMEX, ... (por defecto, la principal del metal)")
    comun(me)
    comun(sub.add_parser("utm-ipc", help="UTM, UTA e IPC mensual (SII), con el IPC empalmado"))
    fe = sub.add_parser("feriados", help="feriados legales (sin conexión)")
    fe.add_argument("--regionales", action="store_true", help="incluir los feriados regionales")
    fe.add_argument("--desde", help="año, AAAA-MM o AAAA-MM-DD")
    fe.add_argument("--hasta", help="año, AAAA-MM o AAAA-MM-DD")
    fe.add_argument("--salida", "-o", help="archivo CSV (por defecto, la pantalla)")

    a = p.parse_args(argv)
    desde, hasta = _desde_hasta(getattr(a, "desde", None)), _desde_hasta(getattr(a, "hasta", None))
    cache = not getattr(a, "sin_cache", False)
    if a.comando == "resumen":
        df = resumen(cache=cache)
    elif a.comando == "bcentral":
        df = bcentral.serie(a.codigo, desde, hasta, cache=cache)
    elif a.comando == "metal":
        df = cochilco.precio(a.metal, desde, hasta, bolsa=a.bolsa, cache=cache)
    elif a.comando == "utm-ipc":
        df = sii.utm_ipc(desde, hasta, cache=cache)
    elif a.comando == "feriados":
        df = calendario.feriados(desde, hasta, regionales=a.regionales)
    elif a.comando == "uf":
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
