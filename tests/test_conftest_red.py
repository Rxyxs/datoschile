"""El hook de conftest convierte una fuente caída en 'omitida' solo en las pruebas de red."""
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]


def test_fuente_caida_se_omite_y_formato_roto_falla(pytester):
    pytester.makeconftest((Path(__file__).parent / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.red
        def test_caida():
            raise ConnectionError("Read timed out")

        @pytest.mark.red
        def test_formato():
            assert 608.15 == 24627.10

        def test_offline_caida():
            raise ConnectionError("sin red")
        """
    )
    pytester.makeini("[pytest]\nmarkers = red: red")
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(passed=0, skipped=1, failed=2)
