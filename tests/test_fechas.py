import pandas as pd

from cordillera._fechas import rango


def test_rango_entiende_anio_mes_y_fecha():
    assert rango(2020, 2020, minimo=2000) == (pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"))
    assert rango("2020-02", "2020-02", minimo=2000) == (pd.Timestamp("2020-02-01"), pd.Timestamp("2020-02-29"))
    assert rango("2020-02-10", "2020-02-11", minimo=2000) == (pd.Timestamp("2020-02-10"), pd.Timestamp("2020-02-11"))


def test_rango_respeta_el_minimo_y_hoy():
    ini, fin = rango(1990, None, minimo=2002)
    assert ini == pd.Timestamp("2002-01-01") and fin == pd.Timestamp.today().normalize()
