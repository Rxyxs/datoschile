"""Parser del SII y respaldo cuando mindicador no responde (sin red)."""
import warnings

import pytest

from datoschile import indicadores, sii

HTML_UF = """
<div class='meses' id='mes_enero'><table><tbody>
<tr><th colspan='6'><h2>Enero</h2></th></tr>
<tr><th width='40'><strong>1</strong></th><td width='200'>24.561,84</td>
<th width='40'><strong>11</strong></th><td width='200'></td></tr>
</tbody></table></div>
<div class='meses' id='mes_febrero'><table><tbody>
<tr><th width='40'><strong>2</strong></th><td width='200'>24.600,00</td></tr>
</tbody></table></div>
"""

HTML_DOLAR = """<div class='meses' id='mes_enero'><h3>Enero</h3><table><tbody>
<tr><th width='40'><strong>2</strong></th><td width='200'>524.61</td></tr></tbody></table></div>"""


def test_parsea_uf_con_coma_decimal_y_omite_dias_vacios():
    filas = sii.parsear_pagina(HTML_UF, 2014)
    assert filas == [{"fecha": "2014-01-01", "valor": 24561.84}, {"fecha": "2014-02-02", "valor": 24600.0}]


def test_parsea_dolar_con_punto_decimal():
    assert sii.parsear_pagina(HTML_DOLAR, 2014) == [{"fecha": "2014-01-02", "valor": 524.61}]


HTML_HISTORICO = """<table class="tabla"><thead><tr><th>Día</th><th>Ene</th><th>Feb</th></tr></thead>
<tbody>
<tr>
  <th style='text-align:center;'>1</th>
  <td>19.627,70</td><td>19.741,03</td><td>19.766,45</td><td></td><td></td><td></td>
  <td></td><td></td><td></td><td></td><td></td><td></td>
</tr>
<tr>
  <th style='text-align:center;'>30</th>
  <td>19.700,00</td><td>&nbsp;</td><td>19.800,00</td><td></td><td></td><td></td>
  <td></td><td></td><td></td><td></td><td></td><td></td>
</tr>
</tbody></table>"""


def test_parsea_el_formato_historico_un_mes_por_columna():
    filas = sii.parsear_pagina(HTML_HISTORICO, 2008)
    assert filas[:2] == [{"fecha": "2008-01-01", "valor": 19627.70}, {"fecha": "2008-01-30", "valor": 19700.0}]
    assert {"fecha": "2008-03-30", "valor": 19800.0} in filas
    assert not any(f["fecha"] == "2008-02-30" for f in filas)


def test_parsea_paginas_antiguas_con_el_dia_en_td():
    html = """<table><tbody><tr onmouseover='x();' onmouseout='y();'>
      <td>1</td>
      <td align="right">11.535,39</td><td align="right">11.578,93</td>
    </tr></tbody></table>"""
    assert sii.parsear_pagina(html, 1995) == [
        {"fecha": "1995-01-01", "valor": 11535.39}, {"fecha": "1995-02-01", "valor": 11578.93}]


def test_rechaza_series_que_el_sii_no_publica():
    with pytest.raises(ValueError):
        sii.descargar_anio("libra_cobre", 2014)


@pytest.fixture(autouse=True)
def mindicador_disponible(monkeypatch):
    monkeypatch.setattr(indicadores, "_mindicador_caido", False)


def test_despues_de_una_caida_no_vuelve_a_esperar_a_mindicador(monkeypatch):
    llamadas = []

    def caido(*args, **kwargs):
        llamadas.append(1)
        raise ConnectionError("timeout")

    monkeypatch.setattr(indicadores._red, "con_cache", caido)
    monkeypatch.setattr(sii, "descargar_anio", lambda codigo, anio, cache=True: [])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for anio in range(2010, 2015):
            indicadores.descargar_anio("uf", anio)
    assert len(llamadas) == 1


def test_usa_el_sii_cuando_mindicador_falla(monkeypatch):
    def caido(*args, **kwargs):
        raise ConnectionError("500 Server Error")

    monkeypatch.setattr(indicadores._red, "con_cache", caido)
    monkeypatch.setattr(sii, "descargar_anio", lambda codigo, anio, cache=True: [{"fecha": f"{anio}-01-02", "valor": 1.0}])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        filas = indicadores.descargar_anio("uf", 2014)
    assert filas == [{"fecha": "2014-01-02", "valor": 1.0}]
    assert any("SII" in str(x.message) for x in w)


def test_sin_respaldo_para_series_que_el_sii_no_publica(monkeypatch):
    def caido(*args, **kwargs):
        raise ConnectionError("500 Server Error")

    monkeypatch.setattr(indicadores._red, "con_cache", caido)
    with pytest.raises(ConnectionError):
        indicadores.descargar_anio("libra_cobre", 2024)


# --- UTM, UTA e IPC ---------------------------------------------------------------------------

def test_utm_formato_actual_de_seis_columnas():
    html = """<tr>
       <th>Enero</th>
       <td>69.751</td>
       <td>837.012</td>
       <td align='center'>109,71</td>
       <td align='center'>0,4</td>
       <td align='center'>0,4</td>
       <td align='center'>2,8</td>
     </tr>
     <tr><th>Diciembre</th><td>39.021</td><td>468.252</td><td>107,02</td><td>0.6</td><td>4,4</td><td>4,4</td></tr>
     <tr><th>Noviembre</th><td>72.151</td><td>865.812</td><td></td><td></td><td></td><td></td></tr>"""
    filas = sii.parsear_utm(html, 2026)
    assert filas[0] == {"fecha": "2026-01-01", "utm": 69751.0, "uta": 837012.0, "ipc": 109.71, "ipc_var_mensual": 0.4}
    assert filas[1]["ipc_var_mensual"] == 0.6           # "0.6" con punto, como en dic-2011
    assert filas[2]["utm"] == 72151.0 and filas[2]["ipc"] != filas[2]["ipc"]  # IPC aún no publicado


def test_utm_formatos_historicos_de_tres_y_cuatro_columnas():
    tres = "<tr><th align='left'>Febrero</th><td>14.745</td><td>(-0,6)</td><td>39,69</td></tr>"
    cuatro = "<tr><th align='left'>Enero</th><td>30.399</td><td>364.788</td><td>-0,3</td><td>81,192</td></tr>"
    assert sii.parsear_utm(tres, 1992) == [{"fecha": "1992-02-01", "utm": 14745.0, "uta": 14745.0 * 12,
                                           "ipc": 39.69, "ipc_var_mensual": -0.6}]
    assert sii.parsear_utm(cuatro, 2005)[0] == {"fecha": "2005-01-01", "utm": 30399.0, "uta": 364788.0,
                                                "ipc": 81.192, "ipc_var_mensual": -0.3}


def test_utm_formato_desconocido_falla():
    with pytest.raises(ValueError, match="desconocido"):
        sii.parsear_utm("<tr><th>Enero</th><td>1</td><td>2</td></tr>", 2020)


def test_empalme_detecta_el_cambio_de_base_y_reescala_lo_anterior():
    import pandas as pd
    df = pd.DataFrame({
        "fecha": pd.to_datetime(["2023-11-01", "2023-12-01", "2024-01-01", "2024-02-01"]),
        "ipc": [134.77, 134.10, 101.72, 102.33],
        "ipc_var_mensual": [0.7, -0.5, 0.7, 0.6],
    })
    out = sii.empalmar_ipc(df)
    assert [str(d) for d in out.attrs["cambios_de_base"]] == ["2024-01-01"]
    e = out["ipc_empalmado"]
    assert e.iloc[2] == 101.72 and e.iloc[3] == 102.33          # la base nueva no se toca
    assert e.iloc[2] / e.iloc[1] == pytest.approx(1.007)       # el salto es la variación oficial
    assert e.iloc[1] / e.iloc[0] == pytest.approx(134.10 / 134.77)  # el tramo viejo conserva su forma
