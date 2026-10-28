"""Datos públicos de Chile, limpios y en un DataFrame.

    >>> import datoschile as dc
    >>> dc.resumen()                                   # panel con los últimos valores
    >>> dc.indicadores.uf(desde=2020)
    >>> dc.bcentral.serie("imacec")                    # serie oficial del Banco Central
    >>> dc.cochilco.cobre(desde=2024)                  # cobre LME, US$/lb
    >>> dc.sii.utm_ipc(desde=2010)                     # UTM e IPC empalmado
    >>> dc.calendario.dias_habiles("2026-09-01", "2026-09-30")
    >>> dc.convertir.deflactar(1_000_000, "2015-01-01")
    >>> dc.territorio.buscar_cut("Ñuñoa")              # 13120, sin conexión
    >>> dc.territorio.poblacion()                      # Censo 2024 por comuna
    >>> dc.pensiones.valor_cuota(fondos="A", desde=2024)
    >>> dc.cmf.morosidad(desde="2020-01")
"""
__version__ = "0.4.0"

from . import bcentral, calendario, cmf, cochilco, convertir, indicadores, pensiones, sii, territorio  # noqa: E402
from .panel import resumen  # noqa: E402

__all__ = ["bcentral", "calendario", "cmf", "cochilco", "convertir", "indicadores", "pensiones", "sii", "territorio",
           "resumen", "__version__"]
