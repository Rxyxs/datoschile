"""Descargas HTTP con reintentos y una caché en disco para los periodos cerrados.

Un año que ya terminó no cambia, así que se guarda en disco y no se vuelve a pedir.
El año en curso (y los últimos meses de la CMF) siempre se descargan de nuevo.
La carpeta de caché es ``~/.cache/datoschile`` o la que indique ``DATOSCHILE_CACHE``.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from . import __version__

USER_AGENT = f"datoschile/{__version__} (+https://github.com/Rxyxs/datoschile)"
_session: requests.Session | None = None


def carpeta_cache() -> Path:
    """Carpeta donde se guardan las descargas de periodos cerrados."""
    base = os.environ.get("DATOSCHILE_CACHE")
    return Path(base) if base else Path.home() / ".cache" / "datoschile"


def _sesion() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = USER_AGENT
    return _session


def descargar(url: str, params: dict | None = None, reintentos: int = 3, timeout: int = 60) -> bytes:
    """GET con reintentos y espera creciente. Devuelve el cuerpo en bytes."""
    ultimo_error: Exception | None = None
    for intento in range(1, reintentos + 1):
        try:
            resp = _sesion().get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:  # red caída, 5xx, timeout
            ultimo_error = e
            time.sleep(0.5 * 2**intento)
    raise ConnectionError(f"No se pudo descargar {url} ({params}): {ultimo_error}")


def con_cache(clave: str, obtener, usar_cache: bool) -> bytes:
    """Devuelve el contenido guardado bajo ``clave`` o lo obtiene y lo guarda.

    ``usar_cache=False`` siempre descarga y no escribe nada (para periodos abiertos).
    """
    ruta = carpeta_cache() / clave
    if usar_cache and ruta.exists() and ruta.stat().st_size > 0:
        return ruta.read_bytes()
    contenido = obtener()
    if usar_cache:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_suffix(ruta.suffix + ".tmp")
        tmp.write_bytes(contenido)
        tmp.replace(ruta)
    return contenido
