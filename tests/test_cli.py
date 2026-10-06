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
