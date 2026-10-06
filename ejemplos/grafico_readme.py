"""Genera docs/ejemplo.png: tres series bajadas con datoschile, cada una en una línea de código.

    python ejemplos/grafico_readme.py
"""
from pathlib import Path

import matplotlib.pyplot as plt

import datoschile as dc

indice = dc.pensiones.indice(fondos="AE", desde=2008, real=True)
mora = dc.cmf.morosidad(solo_sistema=True)
cobre = dc.indicadores.cobre(desde=2013)

TINTA, GRIS, A, E = "#1f2328", "#8c959f", "#1a7f37", "#0969da"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": GRIS, "axes.labelcolor": TINTA, "xtick.color": TINTA,
                     "ytick.color": TINTA, "axes.titlesize": 11, "axes.titleweight": "bold",
                     "axes.titlelocation": "left"})
fig, ejes = plt.subplots(1, 3, figsize=(13, 3.6))

ax = ejes[0]
for fondo, color in (("A", A), ("E", E)):
    s = indice[indice.fondo == fondo]
    ax.plot(s.fecha, s.indice, color=color, lw=1.3)
    ax.annotate(f"Fondo {fondo}", (s.fecha.iloc[-1], s.indice.iloc[-1]), xytext=(4, 0),
                textcoords="offset points", color=color, va="center", fontsize=9)
ax.axhline(100, color=GRIS, lw=0.8, ls=":")
ax.set_title("Fondos A y E, en UF")
ax.set_ylabel("índice real (ene-2008 = 100)")
ax.text(0, -0.2, "pensiones.indice(fondos=\"AE\", desde=2008, real=True)", transform=ax.transAxes,
        family="monospace", fontsize=8, color=GRIS)

ax = ejes[1]
ax.plot(mora.fecha, mora.total, color=TINTA, lw=1.4)
ax.set_title("Morosidad bancaria 90+ días")
ax.set_ylabel("% de la cartera")
ax.text(0, -0.2, "cmf.morosidad(solo_sistema=True)", transform=ax.transAxes,
        family="monospace", fontsize=8, color=GRIS)

ax = ejes[2]
ax.plot(cobre.fecha, cobre.libra_cobre, color="#bc4c00", lw=1)
ax.set_title("Precio del cobre")
ax.set_ylabel("dólares por libra")
ax.text(0, -0.2, "indicadores.cobre(desde=2013)", transform=ax.transAxes,
        family="monospace", fontsize=8, color=GRIS)

import matplotlib.dates as mdates

for ax in ejes:
    ax.xaxis.set_major_locator(mdates.YearLocator(4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ejes[1].annotate("2023-07: la CMF no publicó\nel total del sistema",(mora.fecha[mora.total.isna()].iloc[0], 2.0),
                 xytext=(-112, 18), textcoords="offset points", fontsize=8, color=GRIS,
                 arrowprops={"arrowstyle": "-", "color": GRIS, "lw": 0.8})
fig.tight_layout(w_pad=3)
salida = Path(__file__).resolve().parents[1] / "docs" / "ejemplo.png"
fig.savefig(salida, dpi=150, bbox_inches="tight", facecolor="white")
print(f"-> {salida}")
