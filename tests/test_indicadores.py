import json

import pandas as pd
import pytest

from datoschile import indicadores


def _uf(pares):
    return pd.DataFrame({"fecha": pd.to_datetime([p[0] for p in pares]), "uf": [p[1] for p in pares]})


def test_limpiar_uf_descarta_el_dolar_filtrado_y_lo_interpola():
    # Lo que pasó el 29 y 30 de diciembre de 2014: el dólar observado en lugar de la UF.
    df = _uf([("2014-12-27", 24620.0), ("2014-12-28", 24622.0), ("2014-12-29", 608.15),
              ("2014-12-30", 607.38), ("2014-12-31", 24627.1)])
    limpio, informe = indicadores.limpiar_uf(df)
    assert [str(d) for d in informe["descartados"]] == ["2014-12-29", "2014-12-30"]
    assert limpio["uf"].between(24620, 24628).all()
    assert len(limpio) == 5


def test_limpiar_uf_interpola_geometricamente_y_colapsa_duplicados():
    df = _uf([("2015-12-10", 25000.0), ("2015-12-10", 25000.0), ("2015-12-12", 25010.0)])
    limpio, informe = indicadores.limpiar_uf(df)
    assert informe["duplicados"] == 1
    assert [str(d) for d in informe["interpolados"]] == ["2015-12-11"]
    # media geométrica de los vecinos (la UF crece a tasa diaria constante), no aritmética
    assert limpio["uf"].iloc[1] == pytest.approx((25000.0 * 25010.0) ** 0.5, rel=1e-12)


def test_limpiar_uf_rechaza_huecos_largos():
    df = _uf([("2015-01-01", 100.0), ("2015-01-10", 100.1)])
    with pytest.raises(ValueError, match="Hueco"):
        indicadores.limpiar_uf(df)


def test_serie_rechaza_dos_valores_distintos_el_mismo_dia(monkeypatch):
    cuerpo = {"serie": [{"fecha": "2020-01-02T03:00:00.000Z", "valor": 1.0},
                        {"fecha": "2020-01-02T03:00:00.000Z", "valor": 2.0}]}
    monkeypatch.setattr(indicadores._red, "descargar", lambda url, **kw: json.dumps(cuerpo).encode())
    with pytest.raises(ValueError, match="Valores distintos"):
        indicadores.serie("dolar", desde=2020, hasta=2020, pausa=0)


def test_serie_filtra_rango_y_usa_cache(monkeypatch):
    pedidos = []

    def falso(url, **kw):
        pedidos.append(url)
        anio = int(url.rstrip("/").split("/")[-1])
        return json.dumps({"serie": [
            {"fecha": f"{anio}-12-31T03:00:00.000Z", "valor": float(anio)},
            {"fecha": f"{anio}-01-02T03:00:00.000Z", "valor": float(anio) - 0.5},
        ]}).encode()

    monkeypatch.setattr(indicadores._red, "descargar", falso)
    df = indicadores.serie("libra_cobre", desde="2019-06-01", hasta=2020, pausa=0)
    assert df["fecha"].dt.strftime("%Y-%m-%d").tolist() == ["2019-12-31", "2020-01-02", "2020-12-31"]
    assert list(df.columns) == ["fecha", "libra_cobre"]
    indicadores.serie("libra_cobre", desde=2019, hasta=2020, pausa=0)
    assert len(pedidos) == 2  # la segunda llamada sale entera de la caché


def test_codigo_desconocido():
    with pytest.raises(ValueError, match="Serie desconocida"):
        indicadores.serie("peso_argentino")
