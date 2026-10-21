import pytest


@pytest.fixture(autouse=True)
def cache_temporal(tmp_path, monkeypatch):
    """Cada test usa su propia carpeta de caché: nunca la del usuario."""
    monkeypatch.setenv("DATOSCHILE_CACHE", str(tmp_path / "cache"))
    yield tmp_path / "cache"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """En las pruebas contra fuentes reales, una fuente caída no es un cambio de formato.

    El workflow semanal ``fuentes`` existe para avisar cuando una fuente cambia su formato
    o sus valores. Si la fuente simplemente no responde (timeout, 5xx), la prueba se marca
    como omitida con el motivo, en vez de pintar de rojo algo que no es un error de la
    librería. Un valor o un formato distinto sigue fallando.
    """
    outcome = yield
    if item.get_closest_marker("red") is None or outcome.excinfo is None:
        return
    if issubclass(outcome.excinfo[0], ConnectionError):
        outcome.force_exception(pytest.skip.Exception(f"fuente no disponible: {outcome.excinfo[1]}", _use_item_location=True))
