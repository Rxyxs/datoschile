"""resumen(): una fila por indicador, y una fuente caída no tumba el panel (sin red)."""
import pandas as pd
import pytest

import datoschile as dc
from datoschile import panel


def _diaria(col, inicio, valores):
    return pd.DataFrame({"fecha": pd.date_range(inicio, periods=len(valores), freq="D"), col: valores})


@pytest.fixture
def fuentes(monkeypatch):
    llamadas = {"mindicador": 0}
    hoy = pd.Timestamp.today().normalize()
    hace_un_anio = hoy - pd.DateOffset(years=1)

    def sii_diaria(codigo, desde, cache):
        return pd.Series([100.0, 110.0], index=[hace_un_anio, hoy])

    def serie(codigo, desde=None, cache=True):
        llamadas["mindicador"] += 1
        raise ConnectionError("timeout")

    meses = pd.date_range(hoy - pd.DateOffset(months=13), periods=13, freq="MS")
    monkeypatch.setattr(panel, "_diaria_sii", sii_diaria)
    monkeypatch.setattr(panel.indicadores, "serie", serie)
    monkeypatch.setattr(panel.indicadores, "dolar", lambda desde, cache: pd.DataFrame(
        {"fecha": [hace_un_anio, hoy], "dolar": [900.0, 990.0]}))
    monkeypatch.setattr(panel.cochilco, "cobre", lambda desde, cache: _diaria("cobre", hace_un_anio, [4.0, 5.0]))
    monkeypatch.setattr(panel.sii, "utm_ipc", lambda desde, cache: pd.DataFrame(
        {"fecha": meses, "utm": 60000.0, "ipc_empalmado": [100.0] + [100.0] * 11 + [104.0]}))
    monkeypatch.setattr(panel.cmf, "morosidad", lambda desde, solo_sistema, cache: pd.DataFrame(
        {"fecha": [hace_un_anio, hoy], "total": [2.0, 2.5]}))
    return llamadas


def test_resumen(fuentes):
    df = dc.resumen()
    assert list(df.columns) == panel.COLUMNAS
    fila = df.set_index("indicador")
    assert fila.loc["UF", "var_12m"] == pytest.approx(10.0)
    assert fila.loc["Dólar observado", "valor"] == 990.0
    assert fila.loc["Inflación (IPC, 12 meses)", "valor"] == pytest.approx(4.0)
    assert fila.loc["Morosidad bancaria 90+ días", "var_12m"] == pytest.approx(0.5)  # puntos, no %
    # mindicador caído: sus tres filas quedan vacías con el motivo, y se intentó una sola vez
    caidas = df[df["fuente"].str.contains("no disponible")]
    assert len(caidas) == 3 and caidas["valor"].isna().all()
    assert fuentes["mindicador"] == 1
