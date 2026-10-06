import pytest


@pytest.fixture(autouse=True)
def cache_temporal(tmp_path, monkeypatch):
    """Cada test usa su propia carpeta de caché: nunca la del usuario."""
    monkeypatch.setenv("CORDILLERA_CACHE", str(tmp_path / "cache"))
    yield tmp_path / "cache"
