"""Conversiones UF/pesos y deflactor (sin red)."""
import pandas as pd
import pytest

from datoschile import convertir


@pytest.fixture(autouse=True)
def fuentes_falsas(monkeypatch):
    def uf(desde, hasta, cache=True):
        dias = pd.date_range(desde, hasta, freq="D")
        return pd.DataFrame({"fecha": dias, "uf": 30000.0 + (dias - pd.Timestamp("2020-01-01")).days})

    def utm_ipc(cache=True):
        return pd.DataFrame({"fecha": pd.to_datetime(["2015-01-01", "2020-01-01", "2026-09-01", "2026-10-01"]),
                             "ipc_empalmado": [50.0, 80.0, 100.0, float("nan")]})

    monkeypatch.setattr(convertir.indicadores, "uf", uf)
    monkeypatch.setattr(convertir.sii, "utm_ipc", utm_ipc)


def test_pesos_y_uf_ida_y_vuelta():
    assert convertir.pesos_a_uf(30010.0, "2020-01-11") == pytest.approx(1.0)
    assert convertir.uf_a_pesos(2, "2020-01-01") == 60000.0


def test_columnas_conservan_el_indice():
    montos = pd.Series([30000.0, 60020.0], index=["a", "b"])
    out = convertir.pesos_a_uf(montos, ["2020-01-01", "2020-01-11"])
    assert list(out.index) == ["a", "b"] and out.tolist() == pytest.approx([1.0, 2.0])


def test_deflactar_al_ultimo_ipc_publicado_por_omision():
    assert convertir.deflactar(1000, "2015-01-20") == pytest.approx(2000.0)
    assert convertir.deflactar(1000, "2015-01-20", a="2020-01") == pytest.approx(1600.0)
    assert convertir.deflactar([1000, 1000], ["2020-01-05", "2026-09-30"]).tolist() == pytest.approx([1250.0, 1000.0])


def test_deflactar_a_un_mes_sin_ipc_falla_y_un_origen_sin_ipc_da_nan():
    with pytest.raises(ValueError, match="No hay IPC"):
        convertir.deflactar(1000, "2015-01-01", a="2026-10")
    assert pd.isna(convertir.deflactar(1000, "2018-06-01"))


def test_largos_distintos_fallan():
    with pytest.raises(ValueError, match="mismo largo"):
        convertir.pesos_a_uf([1, 2, 3], ["2020-01-01", "2020-01-02"])
