"""UF y dólar observado desde el SII, la fuente oficial que publica ambas tablas.

`mindicador.cl` es un agregador de terceros: cuando se cae (devolvió 500 durante días en
octubre de 2026) la librería no tenía de dónde más sacar la UF. El SII publica una página
por año con la UF y el dólar observado de cada día, sin clave ni registro:

- https://www.sii.cl/valores_y_fechas/uf/uf2014.htm
- https://www.sii.cl/valores_y_fechas/dolar/dolar2014.htm

Cada página tiene un bloque por mes (``id='mes_enero'`` ...) con pares día/valor. Ojo con
el formato: la UF usa coma decimal (``24.627,10``) y el dólar punto (``541.59``).

    >>> from datoschile import sii
    >>> sii.descargar_anio("uf", 2014)[:2]
"""
from __future__ import annotations

import re

from . import _red
from ._fechas import es_periodo_cerrado

URLS = {
    "uf": "https://www.sii.cl/valores_y_fechas/uf/uf{anio}.htm",
    "dolar": "https://www.sii.cl/valores_y_fechas/dolar/dolar{anio}.htm",
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
_BLOQUE_MES = re.compile(r"id=['\"]mes_(" + "|".join(MESES) + r")['\"](.*?)</table>", re.S)
_PAR_DIA_VALOR = re.compile(r"<strong>\s*(\d{1,2})\s*</strong>\s*</th>\s*<td[^>]*>\s*([^<]*?)\s*</td>", re.S)


def _numero(texto: str) -> float:
    """``24.627,10`` -> 24627.10 y ``541.59`` -> 541.59."""
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def parsear_pagina(html: str, anio: int) -> list[dict]:
    """Pares fecha/valor de una página anual del SII; los días sin valor se omiten."""
    filas = []
    for mes, bloque in _BLOQUE_MES.findall(html):
        numero_mes = MESES.index(mes) + 1
        for dia, valor in _PAR_DIA_VALOR.findall(bloque):
            if not valor.strip():
                continue
            filas.append({"fecha": f"{anio:04d}-{numero_mes:02d}-{int(dia):02d}", "valor": _numero(valor)})
    return sorted(filas, key=lambda f: f["fecha"])


def descargar_anio(codigo: str, anio: int, cache: bool = True) -> list[dict]:
    """UF (``"uf"``) o dólar observado (``"dolar"``) de un año, desde el SII."""
    if codigo not in URLS:
        raise ValueError(f"El SII solo publica {', '.join(URLS)}; pedido: '{codigo}'")
    contenido = _red.con_cache(
        f"sii/{codigo}/{anio}.htm",
        lambda: _red.descargar(URLS[codigo].format(anio=anio)),
        usar_cache=cache and es_periodo_cerrado(anio),
    )
    return parsear_pagina(contenido.decode("latin-1"), anio)
