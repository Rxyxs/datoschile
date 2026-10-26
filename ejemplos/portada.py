"""Genera docs/portada.png: un tablero con el último valor de ocho indicadores de Chile, su
variación en 12 meses y su trayectoria de dos años, todo bajado con datoschile.

    python ejemplos/portada.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, str(Path(__file__).parent))
import _series  # noqa: E402

FONDO, TARJETA, BORDE = "#0d1117", "#161b22", "#30363d"
TEXTO, TEXTO_2, TEXTO_3 = "#f0f6fc", "#9198a1", "#6e7681"
ACENTO = "#3987e5"
FUENTE = "Segoe UI" if any(f.name == "Segoe UI" for f in plt.matplotlib.font_manager.fontManager.ttflist) else "DejaVu Sans"
MONO = "Consolas" if FUENTE == "Segoe UI" else "DejaVu Sans Mono"


def cl(x: float, dec: int) -> str:
    """Formato chileno: 41.221,08."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".").replace("-", "−")


# (clave, etiqueta, formato del valor, "pct" o "pp" para la variación, fuente)
TARJETAS = [
    ("uf", "UF", lambda v: f"${cl(v, 2)}", "pct", "SII"),
    ("dolar", "Dólar observado", lambda v: f"${cl(v, 2)}", "pct", "BCCh"),
    ("cobre", "Cobre LME", lambda v: f"US${cl(v, 2)} /lb", "pct", "Cochilco"),
    ("ipc12", "Inflación 12 meses", lambda v: f"{cl(v, 1)}%", "pp", "INE"),
    ("tpm", "Tasa de política monetaria", lambda v: f"{cl(v, 2)}%", "pp", "BCCh"),
    ("imacec", "IMACEC, variación anual", lambda v: f"{cl(v, 1)}%", "pp", "BCCh"),
    ("desempleo", "Desempleo", lambda v: f"{cl(v, 1)}%", "pp", "INE"),
    ("morosidad", "Morosidad bancaria 90+ días", lambda v: f"{cl(v, 2)}%", "pp", "CMF"),
]


def variacion(s: pd.Series, tipo: str) -> str:
    fin = s.index[-1]
    antes = s[s.index <= fin - pd.DateOffset(years=1)]
    if antes.empty:
        return ""
    if tipo == "pct":
        d = (s.iloc[-1] / antes.iloc[-1] - 1) * 100
        texto = f"{cl(abs(d), 1)}% en 12 meses"
    else:
        d = s.iloc[-1] - antes.iloc[-1]
        texto = f"{cl(abs(d), 2)} pp en 12 meses"
    flecha = "▲" if d > 0.0005 else "▼" if d < -0.0005 else "="
    return f"{flecha} {texto}"


def fecha_dato(s: pd.Series, clave: str) -> str:
    f = s.index[-1]
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    if clave in ("ipc12", "imacec", "desempleo", "morosidad"):
        return f"{meses[f.month - 1]} {f.year}"
    return f"{f.day} {meses[f.month - 1]}"


def tarjeta(fig, x, y, w, h, s, etiqueta, formato, tipo, fuente, clave):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                      transform=fig.transFigure, facecolor=TARJETA, edgecolor=BORDE, lw=1,
                                      zorder=-1))  # bajo los ejes de la trayectoria
    px = 0.018
    fig.text(x + px, y + h - 0.035, etiqueta, color=TEXTO_2, fontsize=12.5, family=FUENTE, va="top")
    fig.text(x + px, y + h - 0.078, formato(s.iloc[-1]), color=TEXTO, fontsize=27, family=FUENTE,
             weight="semibold", va="top")
    fig.text(x + px, y + h - 0.145, variacion(s, tipo), color=TEXTO_2, fontsize=11.5, family=FUENTE, va="top")
    fig.text(x + w - px, y + h - 0.147, f"{fuente} · {fecha_dato(s, clave)}", color=TEXTO_3, fontsize=10,
             family=FUENTE, va="top", ha="right")
    # Trayectoria de dos años: una sola serie, sin ejes; el punto marca el último dato.
    tramo = s[s.index >= s.index[-1] - pd.DateOffset(years=2)]
    ax = fig.add_axes([x + px, y + 0.022, w - 2 * px, 0.128])
    ax.plot(tramo.index, tramo.values, color=ACENTO, lw=2, solid_capstyle="round", solid_joinstyle="round")
    ax.fill_between(tramo.index, tramo.values, tramo.min() - (tramo.max() - tramo.min()) * 0.15,
                    color=ACENTO, alpha=0.10, lw=0)
    ax.scatter([tramo.index[-1]], [tramo.iloc[-1]], s=46, color=ACENTO, edgecolor=TARJETA, linewidth=2, zorder=3)
    rango = tramo.max() - tramo.min() or 1
    ax.set_ylim(tramo.min() - rango * 0.15, tramo.max() + rango * 0.12)
    ax.set_xlim(tramo.index[0], tramo.index[-1] + (tramo.index[-1] - tramo.index[0]) * 0.03)
    ax.axis("off")


def main():
    series = _series.cargar()
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor=FONDO)
    fig.text(0.04, 0.925, "datoschile", color=TEXTO, fontsize=38, family=FUENTE, weight="bold", va="center")
    fig.text(0.04, 0.862, "Datos públicos de Chile, limpios y en un DataFrame, en una línea de Python",
             color=TEXTO_2, fontsize=16, family=FUENTE, va="center")
    fig.patches.append(FancyBboxPatch((0.655, 0.875), 0.305, 0.07, boxstyle="round,pad=0,rounding_size=0.01",
                                      transform=fig.transFigure, facecolor=TARJETA, edgecolor=BORDE, lw=1,
                                      zorder=-1))
    fig.text(0.672, 0.927, "import datoschile as dc", color=TEXTO_2, fontsize=13, family=MONO, va="center")
    fig.text(0.672, 0.893, "dc.resumen()", color=TEXTO, fontsize=13, family=MONO, va="center")

    gx, gy, h = 0.0125, 0.025, 0.33
    w = (0.92 - 3 * gx) / 4
    for i, (clave, etiqueta, formato, tipo, fuente) in enumerate(TARJETAS):
        if clave not in series:
            continue
        col, fila = i % 4, i // 4
        x = 0.04 + col * (w + gx)
        y = 0.455 - fila * (h + gy)
        tarjeta(fig, x, y, w, h, series[clave], etiqueta, formato, tipo, fuente, clave)

    fig.text(0.04, 0.04, "SII · Cochilco · CMF · Banco Central (BCCh) · INE · Superintendencia de Pensiones   ·   "
             "curvas: últimos 2 años   ·   fuentes verificadas cada semana",
             color=TEXTO_3, fontsize=11, family=FUENTE, va="center")
    fig.text(0.96, 0.04, "github.com/Rxyxs/datoschile", color=TEXTO_2, fontsize=11, family=FUENTE,
             va="center", ha="right")
    salida = Path(__file__).resolve().parents[1] / "docs" / "portada.png"
    fig.savefig(salida, dpi=150, facecolor=FONDO)
    print(f"-> {salida}")


if __name__ == "__main__":
    main()
