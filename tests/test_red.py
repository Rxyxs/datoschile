"""Pruebas contra las fuentes reales. No corren por defecto: pytest -m red"""
import warnings

import pandas as pd
import pytest

import datoschile as dc

pytestmark = pytest.mark.red


def test_uf_real_corrige_la_fuga_del_dolar_de_2014():
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        df = dc.indicadores.uf(desde="2014-12-20", hasta="2015-01-05")
    vino_del_sii = any("SII" in str(a.message) for a in avisos)
    # mindicador trae el dólar en esos dos días y la limpieza los descarta; si mindicador
    # estaba caído, el respaldo del SII ya trae la UF correcta y no hay nada que descartar.
    esperados = [] if vino_del_sii else ["2014-12-29", "2014-12-30"]
    assert [str(d) for d in df.attrs["informe"]["descartados"]] == esperados
    assert df["uf"].between(24500, 24700).all()
    # Valor publicado por el SII para el 31-12-2008
    assert dc.indicadores.uf(desde="2008-12-31", hasta="2008-12-31")["uf"].iloc[0] == pytest.approx(21452.57, abs=0.01)


def test_indice_fondo_a_cae_en_la_crisis_de_2008():
    idx = dc.pensiones.indice("A", desde="2008-01-01", hasta="2008-12-31")
    caida = idx["indice"].min() / idx["indice"].cummax().max() - 1
    assert -0.45 < caida < -0.20


def test_morosidad_del_sistema_en_febrero_2020():
    df = dc.cmf.morosidad(desde="2020-02", hasta="2020-02", solo_sistema=True)
    assert df["total"].iloc[0] == pytest.approx(2.04, abs=0.01)


def test_cobre_real():
    df = dc.indicadores.cobre(desde="2024-01-01", hasta="2024-01-31")
    assert 15 <= len(df) <= 23 and df["libra_cobre"].between(3, 5).all()


def test_sii_publica_la_uf_correcta_donde_mindicador_falla():
    filas = {f["fecha"]: f["valor"] for f in dc.sii.descargar_anio("uf", 2014)}
    # mindicador entrega 608,15 y 607,38 (el dólar) para estos dos días.
    assert filas["2014-12-29"] == pytest.approx(24627.10, abs=0.01)
    assert filas["2014-12-30"] == pytest.approx(24627.10, abs=0.01)
    dolar = {f["fecha"]: f["valor"] for f in dc.sii.descargar_anio("dolar", 2014)}
    assert dolar["2014-01-02"] == pytest.approx(524.61, abs=0.01)


def test_sii_historico_coincide_con_el_valor_publicado_de_2008():
    filas = {f["fecha"]: f["valor"] for f in dc.sii.descargar_anio("uf", 2008)}
    assert filas["2008-12-31"] == pytest.approx(21452.57, abs=0.01)
    assert len(filas) == 366


def test_cochilco_cobre_lme_real():
    df = dc.cochilco.cobre(desde="2025-01-02", hasta="2025-01-03")
    assert df["cobre"].tolist() == pytest.approx([3.9397, 3.9467])  # 393,97 y 394,67 ¢/lb


def test_cochilco_metales_base_al_dia():
    hoy = pd.Timestamp.today().normalize()
    df = dc.cochilco.precio("zinc", desde=str((hoy - pd.Timedelta(days=20)).date()))
    assert len(df) >= 5 and df["zinc"].between(0.3, 5).all()


def test_utm_ipc_real_y_empalme():
    df = dc.sii.utm_ipc(desde=2024, hasta=2025)
    enero = df.set_index("fecha").loc["2025-01-01"]
    assert enero["utm"] == 67429 and enero["ipc"] == pytest.approx(106.74)
    assert [str(d) for d in df.attrs["cambios_de_base"]] == ["2010-01-01", "2014-01-01", "2019-01-01", "2024-01-01"]
    e = df.set_index("fecha")["ipc_empalmado"]
    # El SII publica 4,9% de inflación a 12 meses en enero de 2025, a través del cambio de base.
    assert (e["2025-01-01"] / e["2024-01-01"] - 1) * 100 == pytest.approx(4.9, abs=0.1)


def test_bcentral_series_reales():
    tpm = dc.bcentral.serie("tpm", desde="2024-01-02", hasta="2024-01-02")
    assert tpm["tpm"].tolist() == [8.25]
    imacec = dc.bcentral.serie("imacec", desde="2020-04", hasta="2020-04")
    assert imacec["imacec"].iloc[0] < -10            # el peor mes de la pandemia
    pib = dc.bcentral.serie("pib", desde=1996, hasta=1996)
    assert len(pib) == 4 and pib["pib"].iloc[0] == pytest.approx(20265, rel=0.05)
    dolar = dc.bcentral.serie("dolar", desde="2014-01-02", hasta="2014-01-02")
    assert dolar["dolar"].iloc[0] == pytest.approx(524.61, abs=0.01)   # el mismo valor del SII


def test_censo_2024_real():
    c = dc.territorio.poblacion()
    assert len(c) == 346 and c["poblacion"].sum() == 18_480_432
    assert c.loc[c["cut"] == 13201, "poblacion"].item() == 568_086   # Puente Alto, la más poblada
    r = dc.territorio.poblacion("region").set_index("cod_region")
    assert r.loc[13, "poblacion"] == 7_400_741
