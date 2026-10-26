import pandas as pd

from datoschile import __main__ as cli


def test_cli_escribe_csv(tmp_path, monkeypatch):
    llamado = {}

    def falso_uf(desde, hasta, cache):
        llamado.update(desde=desde, hasta=hasta, cache=cache)
        return pd.DataFrame({"fecha": pd.to_datetime(["2020-01-01"]), "uf": [28310.86]})

    monkeypatch.setattr(cli.indicadores, "uf", falso_uf)
    salida = tmp_path / "uf.csv"
    assert cli.main(["uf", "--desde", "2020", "--hasta", "2020-01-01", "-o", str(salida), "--sin-cache"]) == 0
    assert llamado == {"desde": 2020, "hasta": "2020-01-01", "cache": False}
    assert pd.read_csv(salida)["uf"].tolist() == [28310.86]


def test_cli_feriados_sin_conexion(tmp_path):
    salida = tmp_path / "feriados.csv"
    assert cli.main(["feriados", "--desde", "2026", "-o", str(salida)]) == 0
    df = pd.read_csv(salida)
    assert len(df) == 16 and "2026-09-18" in df["fecha"].tolist()


def test_cli_metal_pasa_la_bolsa(tmp_path, monkeypatch):
    llamado = {}

    def falso(metal, desde, hasta, bolsa=None, cache=True):
        llamado.update(metal=metal, desde=desde, bolsa=bolsa)
        return pd.DataFrame({"fecha": pd.to_datetime(["2025-01-02"]), "cobre": [3.9885]})

    monkeypatch.setattr(cli.cochilco, "precio", falso)
    assert cli.main(["metal", "cobre", "--desde", "2025", "--bolsa", "COMEX", "-o", str(tmp_path / "c.csv")]) == 0
    assert llamado == {"metal": "cobre", "desde": 2025, "bolsa": "COMEX"}
