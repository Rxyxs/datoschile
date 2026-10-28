"""Territorio: DPA incluida (sin red) y agregación del censo con una base sintética."""
import io
import zipfile

import pytest

from datoschile import territorio


def test_dpa_oficial_completa():
    c = territorio.comunas()
    assert len(c) == 346 and c["cut"].is_unique
    assert c["cod_provincia"].nunique() == 56 and c["cod_region"].nunique() == 16
    assert c.loc[c["cut"] == 13119, "comuna"].item() == "MAIPÚ"
    assert territorio.regiones()["comunas"].sum() == 346


@pytest.mark.parametrize("nombre,cut", [("Ñuñoa", 13120), ("NUNOA", 13120), ("Llay-Llay", 5703),
                                        ("santiago centro", 13101), ("Aisén", 11201), ("Marchigüe", 6204),
                                        ("  Puente   Alto ", 13201), ("O'Higgins", 11302)])
def test_buscar_cut_tolera_variantes(nombre, cut):
    assert territorio.buscar_cut(nombre) == cut


def test_todos_los_alias_apuntan_a_una_comuna():
    nombres = set(territorio.comunas()["comuna"].map(territorio.normalizar))
    assert all(v in nombres for v in territorio.ALIAS.values())


def test_buscar_cut_avisa_los_que_no_encuentra():
    with pytest.warns(UserWarning, match="Narnia"):
        assert territorio.buscar_cut(["Ñuñoa", "Narnia"]) == [13120, None]
    assert territorio.buscar_cut("Santiago", region=5) is None  # no hay Santiago en Valparaíso


def _zip_sintetico(filas):
    cols = ["CUT", "n_per", "n_hombres", "n_hog", "prom_edad", "prom_escolaridad18",
            "n_edad_18_24", "n_edad_25_44", "n_edad_45_59", "n_edad_60_mas"]
    texto = ";".join(cols) + "\n" + "\n".join(";".join(map(str, f)) for f in filas)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Base_zona_localidad_CPV24.csv", ("﻿" + texto).encode("utf-8"))
    return buf.getvalue()


@pytest.fixture
def censo_falso(monkeypatch):
    cuts = territorio.comunas()["cut"].tolist()
    filas = [(c, 100, 50, 40, "30,0", "12,0", 10, 30, 20, 10) for c in cuts]
    filas[0] = (cuts[0], 100, "*", 40, "40,0", "10,0", 10, 30, 20, 10)   # celda reservada
    filas.append((cuts[0], 300, 150, 100, "20,0", "14,0", 30, 90, 60, 30))  # segunda zona
    total = sum(f[1] for f in filas)
    monkeypatch.setattr(territorio, "POBLACION_CENSO_2024", total)
    monkeypatch.setattr(territorio._red, "descargar", lambda url: _zip_sintetico(filas))
    return cuts[0]


def test_censo_suma_zonas_y_pondera_promedios(censo_falso):
    c = territorio.censo(cache=False).set_index("cut")
    f = c.loc[censo_falso]
    assert f["n_per"] == 400 and f["n_hombres"] == 150 and f["celdas_reservadas"] == 1
    assert f["prom_edad"] == pytest.approx((40 * 100 + 20 * 300) / 400)
    assert f["prom_escolaridad18"] == pytest.approx((10 * 70 + 14 * 210) / 280)
    assert f["prom_per_hog"] == pytest.approx(400 / 140, abs=0.01)


def test_censo_por_region_y_validacion_del_total(censo_falso, monkeypatch):
    r = territorio.censo("region", cache=False)
    assert len(r) == 16 and r["n_per"].sum() == territorio.POBLACION_CENSO_2024
    monkeypatch.setattr(territorio, "POBLACION_CENSO_2024", 1)
    with pytest.raises(ValueError, match="cambió"):
        territorio.censo(cache=False)
    with pytest.raises(ValueError, match="nivel"):
        territorio.censo("barrio")
