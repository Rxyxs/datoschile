import io

import numpy as np
import pandas as pd
import pytest

from datoschile import cmf

HTML = """
<a href="articles-113888_recurso_1.xlsx?ts=1" class="card-img" aria-label="Descargar Agosto 2026 (xlsx, 30 KB)">
<a href="articles-1_recurso_1.xlsx?ts=1" class="card-img" aria-label="Descargar Setiembre 2016 (xlsx, 30 KB)">
<a href="otra-cosa.pdf" aria-label="Descargar Memoria 2025 (pdf)">
"""


def _xlsx(filas):
    buf = io.BytesIO()
    pd.DataFrame(filas).to_excel(buf, header=False, index=False)
    return buf.getvalue()


def _antiguo():
    # 9 columnas, banco en la columna 0, encabezados de texto
    enc = ["Institución", "Colocaciones", "Clientes", "Comerciales", "Personas", "Consumo", "Vivienda", "", "MM$"]
    return _xlsx([enc,
                  ["Banco Uno", 1.5, 1.6, 1.2, 2.0, 2.5, 1.0, None, 100],
                  ["Itaú Corpbanca", 2.0, 2.1, 1.8, 2.2, 3.0, "---", None, 50],
                  ["Sistema Bancario", 1.8, 1.9, 1.5, 2.1, 2.8, 1.0, None, 150],
                  ["(1) Nota al pie", 9.9, 9.9, 9.9, 9.9, 9.9, 9.9, None, 9]])


def _nuevo_sin_encabezado():
    # 12 columnas, banco en la columna 1, sin encabezados de texto (2022-01 a 2023-03)
    return _xlsx([[None, "Banco Uno", 1.5, 1.6, 1.2, 2.0, 2.5, 1.0, None, None, 100, None],
                  [None, "Sistema Bancario", 1.8, 1.9, 1.5, 2.1, 2.8, 1.0, None, None, 150, None]])


def test_parsear_indice():
    idx = cmf.parsear_indice(HTML)
    assert list(idx) == [pd.Timestamp("2016-09-01"), pd.Timestamp("2026-08-01")]
    assert idx[pd.Timestamp("2026-08-01")] == "articles-113888_recurso_1.xlsx"


def test_parsear_mes_formato_antiguo_corta_en_el_sistema():
    df = cmf.parsear_mes(_antiguo(), pd.Timestamp("2018-05-01"))
    assert df["banco_original"].tolist() == ["Banco Uno", "Itaú Corpbanca", "Sistema Bancario"]
    assert df["formato"].unique().tolist() == ["antiguo"]
    assert np.isnan(df.loc[1, "vivienda"])  # '---' = no tiene esa cartera
    assert df.loc[2, "monto_moroso_mm"] == 150


def test_parsear_mes_formato_nuevo_sin_encabezados():
    df = cmf.parsear_mes(_nuevo_sin_encabezado(), pd.Timestamp("2022-06-01"))
    assert df["formato"].unique().tolist() == ["nuevo"]
    assert df.set_index("banco_original").loc["Sistema Bancario", "total"] == 1.8


def test_falla_si_no_hay_fila_del_sistema():
    with pytest.raises(ValueError, match="Sistema Bancario"):
        cmf.parsear_mes(_xlsx([[None, "Banco Uno", 1.5, 1.6, 1.2, 2.0, 2.5, 1.0, None, None, 100, None]]),
                        pd.Timestamp("2022-06-01"))


def test_nombre_canonico_une_fusiones_y_excluye_el_itau_previo():
    assert cmf.nombre_canonico("Itaú Corpbanca", pd.Timestamp("2018-01-01")) == "Banco Itaú Chile"
    assert cmf.nombre_canonico("Banco Itaú Chile", pd.Timestamp("2016-02-01")) is None
    assert cmf.nombre_canonico("Banco Itaú Chile", pd.Timestamp("2024-02-01")) == "Banco Itaú Chile"


def test_morosidad_arma_el_panel(monkeypatch):
    archivos = {"a.xlsx": _antiguo(), "b.xlsx": _nuevo_sin_encabezado()}
    monkeypatch.setattr(cmf, "meses_disponibles",
                        lambda: {pd.Timestamp("2018-05-01"): "a.xlsx", pd.Timestamp("2022-06-01"): "b.xlsx"})
    monkeypatch.setattr(cmf._red, "descargar", lambda url, **kw: archivos[url.rsplit("/", 1)[-1]])
    panel = cmf.morosidad(pausa=0)
    assert panel.groupby("fecha").size().tolist() == [3, 2]
    assert "Banco Itaú Chile" in set(panel["banco"])
    assert cmf.morosidad(desde="2022-01", solo_sistema=True, pausa=0)["total"].tolist() == [1.8]
