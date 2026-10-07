"""Pruebas contra las fuentes reales. No corren por defecto: pytest -m red"""
import pytest

import datoschile as dc

pytestmark = pytest.mark.red


def test_uf_real_corrige_la_fuga_del_dolar_de_2014():
    df = dc.indicadores.uf(desde="2014-12-20", hasta="2015-01-05")
    assert [str(d) for d in df.attrs["informe"]["descartados"]] == ["2014-12-29", "2014-12-30"]
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
