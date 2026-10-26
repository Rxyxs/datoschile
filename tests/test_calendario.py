"""Feriados y días hábiles, contra dos fuentes independientes (sin red)."""
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from datoschile import calendario

DATOS = Path(__file__).parent / "datos"


def _json(nombre):
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


@pytest.mark.parametrize("anio,esperada", [(2008, date(2008, 3, 23)), (2019, date(2019, 4, 21)),
                                           (2025, date(2025, 4, 20)), (2027, date(2027, 3, 28))])
def test_pascua(anio, esperada):
    assert calendario.pascua(anio) == esperada


@pytest.mark.parametrize("anio,utc", [(2021, "2021-06-21 03:32"), (2024, "2024-06-20 20:51"),
                                      (2025, "2025-06-21 02:42"), (2026, "2026-06-21 08:24")])
def test_solsticio_con_error_de_minutos(anio, utc):
    calculado = pd.Timestamp(calendario.solsticio_de_junio(anio)).tz_convert(None)
    assert abs(calculado - pd.Timestamp(utc)) < pd.Timedelta(minutes=5)


def test_pueblos_indigenas_usa_la_hora_de_chile():
    # 2025: solsticio el 21 a las 02:42 UTC, el 20 a las 22:42 en Chile; el feriado fue el 20.
    assert calendario.es_feriado("2025-06-20") and not calendario.es_feriado("2025-06-21")
    # 2021: la propia ley fijó el 21 (en Chile el solsticio fue el 20 a las 23:32).
    assert calendario.es_feriado("2021-06-21")


# Diferencias conocidas con la tabla de referencia, cada una con su explicación:
# - feriados.cl puso la elección presidencial de 2009 el viernes 11 de diciembre; fue el
#   domingo 13 (y el 11 hubo dólar observado, ver el otro test).
# - La única captura de 2010 es de febrero, antes de la Ley 20.450 que declaró feriados el
#   17 y el 20 de septiembre (Bicentenario); esos días no hubo dólar observado.
DIFERENCIAS_CONOCIDAS = {"2009": ({"2009-12-11"}, {"2009-12-13"}),
                         "2010": (set(), {"2010-09-17", "2010-09-20"})}


def test_coincide_con_la_tabla_anual_de_feriados_2009_2027():
    referencia = _json("feriados_referencia.json")["feriados"]
    for anio, filas in referencia.items():
        esperados = {f for f, _ in filas}
        calculados = {str(d.date()) for d in calendario.feriados(int(anio))["fecha"]}
        solo_ref, solo_lib = DIFERENCIAS_CONOCIDAS.get(anio, (set(), set()))
        assert esperados - calculados == solo_ref, anio
        assert calculados - esperados == solo_lib, anio


def test_coincide_con_los_dias_sin_dolar_observado_2008_2026():
    """El dólar observado se publica todos los días hábiles: un día de semana sin dólar es
    feriado, y un feriado de semana no tiene dólar."""
    dias = _json("dias_sin_dolar.json")["dias"]
    for anio, sin_dolar in dias.items():
        sin_dolar = {date.fromisoformat(d) for d in sin_dolar}
        fin = max(sin_dolar | {date(int(anio), 1, 1)}) if anio == "2026" else date(int(anio), 12, 31)
        feriados_de_semana = {d.date() for d in calendario.feriados(int(anio))["fecha"]
                              if d.weekday() < 5 and d.date() <= fin}
        assert sin_dolar == feriados_de_semana, anio


def test_traslados_de_la_ley_19668_y_20299():
    assert calendario.es_feriado("2012-07-02")      # 29-jun viernes -> lunes siguiente
    assert calendario.es_feriado("2027-06-28")      # 29-jun martes -> lunes anterior
    assert calendario.es_feriado("2023-10-27")      # 31-oct martes -> viernes anterior
    assert calendario.es_feriado("2012-11-02")      # 31-oct miércoles -> viernes siguiente
    assert calendario.es_feriado("2026-10-31")      # sábado: se queda


def test_sandwich_de_fiestas_patrias_y_2_de_enero():
    assert calendario.es_feriado("2018-09-17")      # lunes (Ley 20.215)
    assert calendario.es_feriado("2024-09-20")      # viernes (Ley 20.215)
    assert calendario.es_feriado("2027-09-17")      # viernes con 18 sábado (Ley 20.983)
    assert not calendario.es_feriado("2010-01-02")  # sábado
    assert calendario.es_feriado("2023-01-02")      # lunes desde 2017 (Ley 20.983)
    assert not calendario.es_feriado("2012-01-02")  # antes de la ley


def test_tabla_del_anio():
    df = calendario.feriados(2025)
    assert list(df.columns) == ["fecha", "nombre", "irrenunciable", "ley", "alcance"]
    fila = df[df["fecha"] == "2025-06-29"].iloc[0]
    assert "San Pedro" in fila["nombre"] and "Primarias" in fila["nombre"]  # dos motivos, una fila
    assert fila["irrenunciable"]
    assert not df[df["fecha"] == "2025-04-18"]["irrenunciable"].iloc[0]


def test_regionales_solo_si_se_piden():
    assert len(calendario.feriados(2026, regionales=True)) == len(calendario.feriados(2026)) + 2
    assert not calendario.es_feriado("2026-06-08")


def test_dias_habiles_y_sumar():
    assert len(calendario.dias_habiles("2026-09-01", "2026-09-30")) == 21
    assert calendario.sumar_habiles("2026-09-17", 1) == pd.Timestamp("2026-09-21")
    assert calendario.sumar_habiles("2026-09-21", -1) == pd.Timestamp("2026-09-17")
    assert calendario.sumar_habiles("2026-09-19", 0) == pd.Timestamp("2026-09-21")


def test_31_de_diciembre_es_feriado_bancario():
    assert calendario.es_habil("2026-12-31") and not calendario.es_habil("2026-12-31", bancario=True)


def test_rechaza_anios_sin_validar():
    with pytest.raises(ValueError, match="2008"):
        calendario.feriados(2005)
