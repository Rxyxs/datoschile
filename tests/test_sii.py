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
