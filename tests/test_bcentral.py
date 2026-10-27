"""Parser de las páginas públicas del Banco Central (sin red)."""
import pandas as pd
import pytest

from datoschile import bcentral

DIARIA = """<select name="DrDwnFechas" id="DrDwnFechas">
<option value="2024">2024</option><option value="2025">2025</option>
<option selected="selected" value="2026">2026</option></select>
<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc" />
<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="xyz" />
<table class="table" id="gr">
<tr><th>Día</th><th>Enero</th><th>Febrero</th><th>Marzo</th><th>Abril</th><th>Mayo</th><th>Junio</th>
<th>Julio</th><th>Agosto</th><th>Septiembre</th><th>Octubre</th><th>Noviembre</th><th>Diciembre</th></tr>
<tr><td>1</td><td></td><td>1.071,09</td><td></td><td>4,50</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>31</td><td>927,46</td><td></td><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</table>"""

MENSUAL = """<table id="gr">
<tr><th>Año</th><th>Enero</th><th>Febrero</th><th>Marzo</th><th>Abril</th><th>Mayo</th><th>Junio</th>
<th>Julio</th><th>Agosto</th><th>Septiembre</th><th>Octubre</th><th>Noviembre</th><th>Diciembre</th></tr>
<tr><td>2010</td><td></td><td></td><td>9,23</td><td>8,84</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>2026</td><td>-0,9</td><td>-0,2</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</table>"""

TRIMESTRAL = """<table id="gr"><tr><th>Año</th><th>I</th><th>II</th><th>III</th><th>IV</th></tr>
<tr><td>1996</td><td>20.265</td><td>20.369</td><td>19.581</td><td>21.421</td></tr>
<tr><td>2026</td><td>53.040</td><td>53.211</td><td></td><td></td></tr></table>"""


def test_diaria_dia_por_mes_con_miles_y_coma_decimal():
    assert bcentral.parsear_diaria(DIARIA, 2026) == [
        {"fecha": "2026-01-31", "valor": 927.46},
        {"fecha": "2026-02-01", "valor": 1071.09},
        {"fecha": "2026-04-01", "valor": 4.5},
    ]
    assert bcentral.anios_disponibles(DIARIA) == [2024, 2025, 2026]


def test_mensual_y_trimestral():
    assert bcentral.parsear_por_anio(MENSUAL, 12) == [
        {"fecha": "2010-03-01", "valor": 9.23}, {"fecha": "2010-04-01", "valor": 8.84},
        {"fecha": "2026-01-01", "valor": -0.9}, {"fecha": "2026-02-01", "valor": -0.2}]
    t = bcentral.parsear_por_anio(TRIMESTRAL, 4)
    assert [f["fecha"] for f in t[:4]] == ["1996-01-01", "1996-04-01", "1996-07-01", "1996-10-01"]
    assert t[-1] == {"fecha": "2026-04-01", "valor": 53211.0}


def test_sin_tabla_falla_en_vez_de_devolver_vacio():
    with pytest.raises(ValueError, match="tabla"):
        bcentral.parsear_por_anio("<html>mantención</html>", 12)


@pytest.fixture
def red_falsa(monkeypatch):
    pedidos = []

    def descargar(url, params=None, reintentos=3, timeout=60, datos=None):
        pedidos.append((url, datos))
        if url == bcentral.URL_INDICE:
            return (b'<a href="Serie.aspx?gcode=TPM&amp;param=XYZ">TPM</a>'
                    b'<a href="Serie.aspx?gcode=TAS_DES_INE&amp;param=D">x</a>')
        if datos is None:
            return (DIARIA if "TPM" in url else MENSUAL).encode("latin-1")
        return DIARIA.replace('selected="selected" ', "").encode("latin-1")

    monkeypatch.setattr(bcentral, "_enlaces", {})
    monkeypatch.setattr(bcentral._red, "descargar", descargar)
    return pedidos


def test_el_anio_vigente_sale_de_la_portada_sin_postback(red_falsa):
    filas = bcentral.descargar_anio("tpm", 2026, cache=False)
    assert len(filas) == 3
    assert all(datos is None for _, datos in red_falsa)
    assert red_falsa[1][0].endswith("Serie.aspx?gcode=TPM&param=XYZ")


def test_otro_anio_reenvia_el_formulario_con_el_anio(red_falsa):
    bcentral.descargar_anio("tpm", 2025, cache=False)
    datos = red_falsa[-1][1]
    assert datos["DrDwnFechas"] == "2025" and datos["__EVENTTARGET"] == "DrDwnFechas"
    assert datos["__VIEWSTATE"] == "abc" and datos["__EVENTVALIDATION"] == "xyz"


def test_anio_que_la_serie_no_tiene(red_falsa):
    assert bcentral.descargar_anio("tpm", 2001, cache=False) == []


def test_serie_mensual_filtra_por_mes(red_falsa):
    df = bcentral.serie("desempleo", desde="2010-04", hasta=2026)
    assert df["fecha"].tolist() == list(pd.to_datetime(["2010-04-01", "2026-01-01", "2026-02-01"]))
    assert df.attrs["frecuencia"] == "mensual" and df.attrs["unidad"] == "%"


def test_valida_codigo():
    with pytest.raises(ValueError, match="desconocida"):
        bcentral.serie("libra_cobre")
    with pytest.raises(ValueError, match="mensual"):
        bcentral.descargar_anio("imacec", 2020)
