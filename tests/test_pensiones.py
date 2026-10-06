import pandas as pd
import pytest

from cordillera import pensiones

# Dos encabezados: a mitad del archivo entra una AFP nueva (como Modelo en 2010) y las
# columnas se corren. Un parser con un solo encabezado asignaría mal los valores.
ARCHIVO = """
Valores Confirmados

Fecha;CAPITAL;;HABITAT
;Valor Cuota;Valor Patrimonio;Valor Cuota;Valor Patrimonio
2010-01-01;20.000,00;1000;30.000,00;3000
2010-01-02;20.200,00;1010;30.000,00;3000
Fecha;CAPITAL;;MODELO;;HABITAT
;Valor Cuota;Valor Patrimonio;Valor Cuota;Valor Patrimonio;Valor Cuota;Valor Patrimonio
2010-01-03;20.200,00;1010;10.000,00;50;30.300,00;3030
2010-01-04;;;10.100,00;51;30.300,00;3030
"""


def test_parsear_reancla_columnas_cuando_cambia_el_encabezado():
    df = pensiones.parsear_archivo(ARCHIVO, "A")
    hab = df[df.afp == "HABITAT"].set_index("fecha")["valor_cuota"]
    assert hab.loc["2010-01-03"] == 30300.0  # no 10.000 (que es de MODELO)
    assert df[df.afp == "MODELO"]["valor_cuota"].tolist() == [10000.0, 10100.0]
    # CAPITAL sin dato el 04: la fila se omite, no queda en cero
    assert df[(df.afp == "CAPITAL") & (df.fecha == "2010-01-04")].empty
    assert set(df.columns) == {"fecha", "fondo", "afp", "valor_cuota", "valor_patrimonio"}
    assert df["fondo"].unique().tolist() == ["A"]


def test_numero_clp():
    assert pensiones._numero_clp("96.092,23") == 96092.23
    assert pensiones._numero_clp("5957005569484") == 5957005569484.0
    assert pensiones._numero_clp("  ") is None


def test_indice_pondera_por_patrimonio_del_dia_anterior():
    valores = pd.DataFrame({
        "fecha": pd.to_datetime(["2020-01-01", "2020-01-02"] * 2),
        "fondo": "A",
        "afp": ["X", "X", "Y", "Y"],
        "valor_cuota": [100.0, 110.0, 50.0, 50.0],   # X +10%, Y 0%
        "valor_patrimonio": [300.0, 999.0, 100.0, 999.0],  # pesos del día anterior: 3 a 1
    })
    out = pensiones.indice_ponderado(valores)
    assert out["retorno"].iloc[0] == pytest.approx(0.075)  # (10%*300 + 0%*100) / 400
    assert out["indice"].iloc[0] == 100.0


def test_fondos_invalidos():
    with pytest.raises(ValueError):
        pensiones.valor_cuota(fondos="AZ")


def test_valor_cuota_usa_cache_en_anios_cerrados(monkeypatch):
    llamadas = []

    def falso(url, params=None, **kw):
        llamadas.append(params["aaaaini"])
        return ARCHIVO.encode("latin-1")

    monkeypatch.setattr(pensiones._red, "descargar", falso)
    a = pensiones.valor_cuota("A", desde=2010, hasta=2010, pausa=0)
    b = pensiones.valor_cuota("A", desde=2010, hasta=2010, pausa=0)
    assert llamadas == [2010]  # la segunda vez sale de la caché
    pd.testing.assert_frame_equal(a, b)
    assert len(pensiones.valor_cuota("A", desde="2010-01-03", hasta="2010-01-03", pausa=0)) == 3


def test_indice_parte_en_base_el_dia_pedido(monkeypatch):
    dias = pd.date_range("2020-02-15", "2020-02-25")
    valores = pd.DataFrame({"fecha": dias, "fondo": "A", "afp": "X",
                            "valor_cuota": [100.0 + i for i in range(len(dias))], "valor_patrimonio": 1.0})
    pedido = {}

    def falso(fondos, desde, hasta, cache):
        pedido.update(desde=desde)
        return valores

    monkeypatch.setattr(pensiones, "valor_cuota", falso)
    out = pensiones.indice("A", desde="2020-02-20", hasta="2020-02-25")
    assert pedido["desde"] == "2020-02-10"  # baja días antes para tener el retorno del primero
    assert out["fecha"].iloc[0] == pd.Timestamp("2020-02-20")
    assert out["indice"].iloc[0] == 100.0
    assert out["retorno"].iloc[0] == pytest.approx(105 / 104 - 1)
