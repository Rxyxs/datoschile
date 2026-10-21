"""UF y dólar observado desde el SII, la fuente oficial que publica ambas tablas.

`mindicador.cl` es un agregador de terceros: cuando se cae (devolvió 500 durante días en
octubre de 2026) la librería no tenía de dónde más sacar la UF. El SII publica una página
por año con la UF y el dólar observado de cada día, sin clave ni registro:

- desde 2013: https://www.sii.cl/valores_y_fechas/uf/uf2014.htm, con un bloque por mes
  (``id='mes_enero'`` ...) y pares día/valor;
- hasta 2012: https://www.sii.cl/pagina/valores/uf/uf2008.htm, una sola tabla con un día
  por fila y un mes por columna.

El dólar sigue las mismas dos rutas (``dolar/dolar2014.htm``). Ojo con el formato: la UF
usa coma decimal (``24.627,10``) y el dólar punto (``541.59``).

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
URLS_HISTORICAS = {
    "uf": "https://www.sii.cl/pagina/valores/uf/uf{anio}.htm",
    "dolar": "https://www.sii.cl/pagina/valores/dolar/dolar{anio}.htm",
}
PRIMER_ANIO_FORMATO_NUEVO = 2013
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
_BLOQUE_MES = re.compile(r"id=['\"]mes_(" + "|".join(MESES) + r")['\"](.*?)</table>", re.S)
_PAR_DIA_VALOR = re.compile(r"<strong>\s*(\d{1,2})\s*</strong>\s*</th>\s*<td[^>]*>\s*([^<]*?)\s*</td>", re.S)
# El día va en <th> o en <td> según la época, y algunas filas traen atributos (onmouseover).
_FILA_HISTORICA = re.compile(r"<tr[^>]*>\s*<t[hd][^>]*>\s*(\d{1,2})\s*</t[hd]>(.*?)</tr>", re.S)
_CELDA = re.compile(r"<td[^>]*>\s*([^<]*?)\s*</td>", re.S)


def _numero(texto: str) -> float:
    """``24.627,10`` -> 24627.10 y ``541.59`` -> 541.59."""
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def _parsear_historica(html: str, anio: int) -> list[dict]:
    filas = []
    for dia, celdas in _FILA_HISTORICA.findall(html):
        for numero_mes, valor in enumerate(_CELDA.findall(celdas)[:12], start=1):
            valor = valor.replace("&nbsp;", "").strip()
            if not valor:
                continue
            filas.append({"fecha": f"{anio:04d}-{numero_mes:02d}-{int(dia):02d}", "valor": _numero(valor)})
    return sorted(filas, key=lambda f: f["fecha"])


def parsear_pagina(html: str, anio: int) -> list[dict]:
    """Pares fecha/valor de una página anual del SII (cualquiera de los dos formatos);
    los días sin valor se omiten."""
    if "id='mes_" not in html and 'id="mes_' not in html:
        return _parsear_historica(html, anio)
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
        lambda: _red.descargar((URLS if anio >= PRIMER_ANIO_FORMATO_NUEVO else URLS_HISTORICAS)[codigo].format(anio=anio)),
        usar_cache=cache and es_periodo_cerrado(anio),
    )
    return parsear_pagina(contenido.decode("latin-1"), anio)
