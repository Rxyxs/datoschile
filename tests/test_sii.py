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
