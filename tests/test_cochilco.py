"""Parser y conversión de unidades de Cochilco (sin red)."""
import warnings

import pandas as pd
import pytest

from datoschile import cochilco

HTML = """<TABLE>
    <TR><TD colspan="2">Grafico: Precio Nominal Cobre Diario (\xa2/lb)1</TD></TR>
    <TR>
    <TD>03/01/2025</TD>
    <TD>394,67</TD>
    </TR>
    <TR><TD>02/01/2025</TD><TD>393,97</TD></TR>
    <TR><TD>06/01/2025</TD><TD>1.280,26</TD></TR>
</TABLE>"""


def test_parsea_y_ordena():
    assert cochilco.parsear(HTML) == [
        {"fecha": "2025-01-02", "valor": 393.97},
        {"fecha": "2025-01-03", "valor": 394.67},
        {"fecha": "2025-01-06", "valor": 1280.26},
    ]


@pytest.fixture
def anio_falso(monkeypatch):
    pedidos = []

    def falso(metal, anio, bolsa=None, cache=True):
        pedidos.append((metal, anio, bolsa))
        return cochilco.parsear(HTML) if anio == 2025 else []

    monkeypatch.setattr(cochilco, "descargar_anio", falso)
    return pedidos


def test_centavos_a_dolares_por_libra(anio_falso):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = cochilco.cobre(desde="2025-01-01", hasta="2025-01-03")
    assert df["cobre"].tolist() == [3.9397, 3.9467]
    assert df.attrs["unidad"] == "dólares por libra" and df.attrs["bolsa"] == "LME"
    assert anio_falso == [("cobre", 2025, "LME")]


def test_oro_queda_en_dolares_por_onza(anio_falso):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = cochilco.precio("oro", desde="2025-01-01", hasta="2025-01-03")
    assert df["oro"].tolist() == [393.97, 394.67]


def test_avisa_si_la_serie_dejo_de_publicarse(anio_falso):
    with pytest.warns(UserWarning, match="no publica"):
        cochilco.precio("cobre", desde="2025-01-01", hasta="2025-03-31")


def test_valida_metal_y_bolsa():
    with pytest.raises(ValueError, match="Metal desconocido"):
        cochilco.precio("litio")
    with pytest.raises(ValueError, match="Bolsa"):
        cochilco.precio("zinc", bolsa="COMEX")


def test_primer_anio_por_bolsa():
    assert cochilco.primer_anio("cobre") == 1996
    assert cochilco.primer_anio("cobre", "COMEX") == 2005
    assert cochilco.primer_anio("zinc") == 2001


def test_formulario_pide_el_anio_completo():
    f = cochilco._formulario("Cobre", "LME", 2024)
    assert (f["dia"], f["mes"], f["anio"], f["dia1"], f["mes1"], f["anio1"]) == (1, 1, 2024, 31, 12, 2024)
    assert f["bolsa3"] == f["bolsa_excel"] == "LME" and f["tipo_metal_excel"] == "Cobre"


def test_sin_datos_devuelve_tabla_vacia(monkeypatch):
    monkeypatch.setattr(cochilco, "descargar_anio", lambda *a, **k: [])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = cochilco.precio("plomo", desde=2024, hasta=2024)
    assert df.empty and list(df.columns) == ["fecha", "plomo"]
    assert pd.api.types.is_datetime64_any_dtype(df["fecha"])
