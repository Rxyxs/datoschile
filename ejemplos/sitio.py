"""Genera el panel web interactivo (sitio/index.html) con datos bajados con datoschile.

    python ejemplos/sitio.py

Lo corre cada semana el workflow ``panel`` y lo publica en GitHub Pages.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import _series  # noqa: E402

import datoschile as dc  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
EPOCA = pd.Timestamp("1970-01-01")

# id -> metadatos que muestra la página
META = {
    "uf": dict(nombre="UF", unidad="pesos", prefijo="$", dec=2, var="pct", fuente="SII (respaldo de mindicador)",
               fuente_corta="SII", funcion="dc.indicadores.uf()",
               descripcion="Unidad de fomento diaria, con el dólar filtrado de 2014 corregido."),
    "dolar": dict(nombre="Dólar observado", unidad="pesos por dólar", prefijo="$", dec=2, var="pct",
                  fuente="Banco Central", fuente_corta="BCCh",
                  funcion='dc.bcentral.serie("dolar")', descripcion="Dólar observado, días hábiles."),
    "cobre": dict(nombre="Cobre LME", unidad="dólares por libra", prefijo="US$", dec=2, var="pct",
                  fuente="Cochilco", fuente_corta="Cochilco", funcion="dc.cochilco.cobre()",
                  descripcion="Precio contado de la Bolsa de Metales de Londres, el mismo día de la bolsa."),
    "ipc12": dict(nombre="Inflación 12 meses", unidad="%", sufijo="%", dec=1, var="pp", mensual=True, cero=True,
                  fuente="INE vía SII", fuente_corta="INE", funcion="dc.sii.utm_ipc()",
                  descripcion="Variación en 12 meses del IPC empalmado a través de los cuatro cambios de base."),
    "tpm": dict(nombre="Tasa de política monetaria", unidad="%", sufijo="%", dec=2, var="pp", cero=True,
                fuente="Banco Central", fuente_corta="BCCh", funcion='dc.bcentral.serie("tpm")',
                descripcion="Tasa de interés de referencia del Banco Central."),
    "imacec": dict(nombre="IMACEC, variación anual", unidad="%", sufijo="%", dec=1, var="pp", mensual=True, cero=True,
                   fuente="Banco Central", fuente_corta="BCCh",
                   funcion='dc.bcentral.serie("imacec")',
                   descripcion="Indicador mensual de actividad económica, variación contra el mismo mes del año anterior."),
    "desempleo": dict(nombre="Desempleo", unidad="%", sufijo="%", dec=1, var="pp", mensual=True,
                      fuente="INE vía Banco Central", fuente_corta="INE",
                      funcion='dc.bcentral.serie("desempleo")',
                      descripcion="Tasa de desocupación nacional, trimestre móvil."),
    "morosidad": dict(nombre="Morosidad bancaria 90+ días", unidad="% de la cartera", sufijo="%", dec=2, var="pp",
                      mensual=True, fuente="CMF", fuente_corta="CMF", funcion="dc.cmf.morosidad(solo_sistema=True)",
                      descripcion="Deuda con 90 días o más de atraso sobre las colocaciones del sistema bancario."),
    "pib12": dict(nombre="PIB, variación anual", unidad="%", sufijo="%", dec=1, var="pp", mensual="T", cero=True,
                  fuente="Banco Central", fuente_corta="BCCh", funcion='dc.bcentral.serie("pib")',
                  descripcion="Crecimiento del PIB real contra el mismo trimestre del año anterior."),
    "reservas": dict(nombre="Reservas internacionales", unidad="millones de dólares", prefijo="US$", dec=0, var="pct",
                     mensual=True, fuente="Banco Central", fuente_corta="BCCh", funcion='dc.bcentral.serie("reservas")',
                     descripcion="Activos de reserva del Banco Central al cierre de cada mes."),
    "euro": dict(nombre="Euro", unidad="pesos por euro", prefijo="$", dec=2, var="pct", fuente="Banco Central",
                 fuente_corta="BCCh", funcion='dc.bcentral.serie("euro")', descripcion="Tipo de cambio del euro, días hábiles."),
    "oro": dict(nombre="Oro", unidad="dólares por onza", prefijo="US$", dec=0, var="pct", fuente="Banco Central",
                fuente_corta="BCCh", funcion='dc.bcentral.serie("oro")',
                descripcion="Precio del oro (Cochilco dejó de publicarlo en 2025; el Banco Central sigue al día)."),
    "tcm": dict(nombre="Tipo de cambio multilateral", unidad="índice 1998 = 100", dec=1, var="pct", fuente="Banco Central",
                fuente_corta="BCCh", funcion='dc.bcentral.serie("tcm")',
                descripcion="El peso contra una canasta de monedas de los socios comerciales; sube cuando el peso se deprecia."),
    "ipc": dict(nombre="IPC empalmado", unidad="índice", dec=2, var="pct", mensual=True, oculto=True,
                fuente="INE vía SII", fuente_corta="INE", funcion="dc.sii.utm_ipc()", descripcion=""),
    "utm": dict(nombre="UTM", unidad="pesos", prefijo="$", dec=0, var="pct", mensual=True, fuente="SII",
                fuente_corta="SII", funcion="dc.sii.utm_ipc()", descripcion="Unidad tributaria mensual."),
}
for f in "ABCDE":
    META[f"fondo_{f}"] = dict(nombre=f"Fondo {f}", unidad="índice real", dec=1, var="pct",
                              fuente="Superintendencia de Pensiones", fuente_corta="SP",
                              funcion=f'dc.pensiones.indice("{f}", real=True)', descripcion="")
TARJETAS = ["uf", "dolar", "cobre", "ipc12", "tpm", "imacec", "desempleo", "morosidad"]

HALLAZGOS = [
    ("El dólar dentro de la UF", "El 29 y 30 de diciembre de 2014 la UF de mindicador vale 608,15 y 607,38: es el dólar. "
     "La librería descarta todo salto diario mayor a 1% y usa el SII cuando mindicador no responde."),
    ("El IPC cambia de base cuatro veces", "En enero de 2010, 2014, 2019 y 2024 el IPC publicado salta (de 134,10 a 101,72 "
     "en 2024). Sin empalmar, la inflación a 12 meses se equivoca hasta 25,8 puntos; empalmado, calza con la oficial "
     "con 0,08 puntos de diferencia como máximo."),
    ("El cobre del Banco Central no es el del día", "Su libra de cobre (que mindicador copia) coincide al centavo con el "
     "precio LME de Cochilco solo el 9% de los días de 2013 a 2025 y, con el mejor desfase, ~20%. Para análisis diario: "
     "<code>dc.cochilco.cobre()</code>."),
    ("El IMACEC de mindicador no es el vigente", "Guarda la primera cifra publicada: abril de 2020 aparece como −14,1% y "
     "el Banco Central hoy dice −15,1%. Solo el 3,8% de los meses de 2013 a 2025 coincide. "
     "<code>dc.bcentral.serie(\"imacec\")</code> trae la serie vigente."),
    ("Feriados que ninguna lista tenía bien", "El 17 y 20 de septiembre de 2010 (Ley 20.450, Bicentenario) no aparecen en "
     "las listas usuales; una tabla pone la elección de 2009 el viernes 11 y fue el domingo 13. Validado contra los días "
     "sin dólar observado 2008–2026: cero diferencias."),
    ("31 cambios de encabezado", "El archivo de valores cuota del fondo C cambia 31 veces qué AFP va en cada columna. "
     "Leído con un solo encabezado, las columnas se desalinean en silencio."),
    ("Tres formatos de Excel en la CMF", "128 archivos de morosidad entre 2016 y 2026 con tres diseños y bancos que se "
     "fusionan. En 2023-07 el total del sistema viene en <code>---</code> y queda vacío, no inventado."),
]


def _puntos(s: pd.Series, id_: str) -> list:
    s = s.dropna()
    if id_.startswith("fondo_"):
        # Semanal (el panel no necesita el detalle diario), con la fecha real del último dato
        # de cada semana y no la etiqueta del fin de semana, que puede caer en el futuro.
        s = s.groupby(pd.Grouper(freq="W-FRI")).tail(1)
    dias = ((s.index - EPOCA).days).tolist()
    return [[d, round(float(v), 4)] for d, v in zip(dias, s.values)]


def construir(series: dict[str, pd.Series]) -> dict:
    hoy = pd.Timestamp(date.today())
    salida = []
    for id_, meta in META.items():
        if id_ not in series:
            continue
        salida.append({"id": id_, **meta, "puntos": _puntos(series[id_], id_)})
    feriados = dc.calendario.feriados(hoy, hoy + pd.DateOffset(months=12))
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    filas = [{"dia": f"{dias[f.weekday()]} {f.day} {meses[f.month - 1]} {f.year}", "nombre": n, "ley": ley,
              "irrenunciable": bool(i)} for f, n, i, ley in feriados[["fecha", "nombre", "irrenunciable", "ley"]]
             .head(8).itertuples(index=False)]
    fin_mes = hoy + pd.offsets.MonthEnd(0)
    sig_ini, sig_fin = fin_mes + pd.Timedelta(days=1), fin_mes + pd.offsets.MonthEnd(1)
    habiles = (f"{meses[hoy.month - 1].capitalize()} {hoy.year} tiene "
               f"{len(dc.calendario.dias_habiles(hoy.replace(day=1), fin_mes))} días hábiles y "
               f"{meses[sig_ini.month - 1]} {sig_ini.year}, {len(dc.calendario.dias_habiles(sig_ini, sig_fin))}. "
               "dc.calendario.dias_habiles()")
    return {"generado": int((hoy - EPOCA).days), "series": salida, "tarjetas": TARJETAS,
            "feriados": filas, "habiles": habiles, "hallazgos": HALLAZGOS, "comunas": _comunas()}


def _comunas() -> list:
    """Tabla compacta del Censo 2024 por comuna para la sección territorial del panel."""
    try:
        p = dc.territorio.poblacion()
    except (ConnectionError, ValueError) as e:
        print(f"[aviso] censo: {e}")
        return []
    cols = ["cut", "comuna", "cod_region", "region", "poblacion", "edad_promedio", "escolaridad_promedio_18",
            "pct_60_mas", "pct_inmigrantes", "pct_pueblos_originarios", "personas_por_hogar", "pct_viviendas_hacinadas"]
    return [[None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in fila]
            for fila in p[cols].itertuples(index=False)]


def main(series: dict[str, pd.Series] | None = None) -> Path:
    datos = construir(series or _series.cargar())
    plantilla = (Path(__file__).parent / "panel_plantilla.html").read_text(encoding="utf-8")
    html = plantilla.replace("/*DATOS*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    salida = RAIZ / "sitio" / "index.html"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    print(f"-> {salida} ({salida.stat().st_size / 1024:.0f} KB)")
    return salida


if __name__ == "__main__":
    main()
