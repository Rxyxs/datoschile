"""Datos públicos de Chile, limpios y en un DataFrame.

    >>> import cordillera as co
    >>> co.indicadores.uf(desde=2020)
    >>> co.pensiones.valor_cuota(fondos="A", desde=2024)
    >>> co.cmf.morosidad(desde="2020-01")
"""
__version__ = "0.1.0"

from . import cmf, indicadores, pensiones  # noqa: E402

__all__ = ["cmf", "indicadores", "pensiones", "__version__"]
