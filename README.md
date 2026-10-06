🇨🇱 **Español** · 🇺🇸 [English](README.en.md)

# datoschile

[![tests](https://github.com/Rxyxs/datoschile/actions/workflows/tests.yml/badge.svg)](https://github.com/Rxyxs/datoschile/actions/workflows/tests.yml)
[![fuentes](https://github.com/Rxyxs/datoschile/actions/workflows/fuentes.yml/badge.svg)](https://github.com/Rxyxs/datoschile/actions/workflows/fuentes.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licencia](https://img.shields.io/badge/licencia-MIT-lightgrey)

**Datos públicos de Chile, limpios y en un DataFrame, en una línea.** UF, dólar, cobre, IPC, TPM, IMACEC y desempleo; valores cuota y patrimonio de las AFP por fondo; y morosidad bancaria por banco desde la CMF.

```python
import datoschile as dc

dc.indicadores.uf(desde=2020)                         # UF diaria, corregida
dc.indicadores.cobre(desde=2024)                      # precio de la libra de cobre
dc.pensiones.valor_cuota(fondos="AE", desde=2020)     # por día, fondo y AFP
dc.pensiones.indice(fondos="A", desde=2008, real=True)  # índice del fondo en UF
dc.cmf.morosidad(desde="2020-01")                     # panel mensual por banco
```

![Fondos A y E en UF, morosidad bancaria y precio del cobre, bajados con datoschile](docs/ejemplo.png)

## Por qué existe

Estas fuentes son públicas y no piden clave, pero ninguna se puede usar tal como viene. Cada problema de abajo apareció trabajando con datos reales en otros proyectos ([pensiones](https://github.com/Rxyxs/chile-pension-fund-switching-cost), [morosidad bancaria](https://github.com/Rxyxs/chile-banking-delinquency-cmf)), y la librería lo resuelve una vez para que nadie más tenga que encontrarlo:

| Fuente | Problema real | Qué hace datoschile |
|---|---|---|
| UF (mindicador.cl) | El 29 y 30 de diciembre de 2014 la "UF" vale **608,15 y 607,38**: es el dólar filtrado en la serie. Un índice deflactado salta ×40 y vuelve. | Descarta todo día que se mueva más de 1% respecto del último valor válido (la UF nunca lo hace) y lo rellena. |
| UF (mindicador.cl) | El 11-07-2015 aparece cinco veces; faltan el 12-12-2015 y el 31-12-2015. | Colapsa copias idénticas, **falla si dos copias no coinciden**, e interpola geométricamente, que es como se calcula la UF. |
| Valores cuota (Superintendencia de Pensiones) | El encabezado que dice qué AFP va en cada columna **cambia 31 veces** en el archivo del fondo C. Leído con un solo encabezado, las columnas se desalinean en silencio. | Vuelve a leer el encabezado cada vez que aparece. |
| Valores cuota | El valor cuota de cada AFP parte en un nivel distinto: promediarlos no tiene sentido. | `indice()` pondera el retorno de cada AFP por su patrimonio del día anterior y, con `real=True`, lo deflacta por la UF corregida. |
| Morosidad (CMF) | 128 archivos Excel en **tres formatos** distintos entre 2016 y 2026, y bancos que se fusionan o cambian de nombre. | Detecta el formato de cada archivo, une las fusiones en una sola serie y falla si el formato no es ninguno de los conocidos. |
| Morosidad (CMF) | En el archivo de 2023-07 la fila del sistema viene en `---`. | La deja en `NaN`: no inventa un valor. |

Todas las reglas de limpieza tienen un test que reproduce el problema original.

## Instalación

```bash
pip install git+https://github.com/Rxyxs/datoschile
```

Requiere Python 3.10 o superior. Depende solo de pandas, requests y openpyxl.

## Qué trae

**`indicadores`**: cualquier serie de [mindicador.cl](https://mindicador.cl), que replica series del Banco Central, el INE y el SII.

| Función | Devuelve |
|---|---|
| `uf(desde, hasta)` | UF diaria (un valor por día calendario) corregida. Lo corregido queda en `df.attrs["informe"]`. |
| `dolar(...)`, `cobre(...)` | Dólar observado y libra de cobre, días hábiles. |
| `serie(codigo, desde, hasta)` | Cualquiera de: `uf`, `ivp`, `dolar`, `euro`, `utm`, `ipc`, `tpm`, `imacec`, `tasa_desempleo`, `libra_cobre`, `bitcoin` (detalle en `indicadores.SERIES`). |

**`pensiones`**: valores cuota y patrimonio diarios desde 2002, multifondos A–E.

| Función | Devuelve |
|---|---|
| `valor_cuota(fondos, desde, hasta, afps)` | Una fila por fecha, fondo y AFP: `valor_cuota` y `valor_patrimonio`. |
| `indice(fondos, desde, hasta, real)` | Índice del fondo (todas las AFP ponderadas por patrimonio), base 100. |

**`cmf`**: morosidad de 90 días o más, mensual, desde 2016.

| Función | Devuelve |
|---|---|
| `morosidad(desde, hasta, solo_sistema)` | Una fila por mes y banco: % moroso en `total`, `clientes`, `comercial`, `personas`, `consumo`, `vivienda`, y el monto moroso en MM$. |

`desde` y `hasta` aceptan un año (`2020`), un mes (`"2020-03"`) o una fecha (`"2020-03-15"`).

### Desde la terminal

```bash
datoschile uf --desde 2020 -o uf.csv
datoschile serie libra_cobre --desde 2024
datoschile indice --fondos A --desde 2008 --real -o fondo_a_real.csv
datoschile morosidad --desde 2020-01 --solo-sistema
```

## Caché

Un año que ya terminó no cambia, así que se guarda en `~/.cache/datoschile` y no se vuelve a pedir; el año en curso (y los últimos tres meses de la CMF, que pueden corregirse) siempre se descarga de nuevo. La primera descarga de la UF completa toma cerca de 2 minutos porque mindicador es lento; después, los años cerrados salen del disco en centésimas de segundo y solo se vuelve a pedir el año en curso (unos segundos). Para usar otra carpeta: `DATOSCHILE_CACHE=/ruta`. Para no usar caché: `cache=False` o `--sin-cache`.

## Verificado contra las fuentes

Además de los tests sin conexión (corren en cada cambio), hay un conjunto que descarga datos reales y comprueba valores conocidos. Corre **cada semana** en GitHub Actions, para enterarse si una fuente cambió su formato antes que quien la use:

- UF del 31-12-2008 = 21.452,57, el valor publicado por el SII.
- La fuga del dólar de 2014 se detecta y se corrige.
- El fondo A cae entre 20% y 45% en 2008.
- La morosidad del sistema en febrero de 2020 es 2,04%.

```bash
pip install -e ".[dev]"
pytest                 # sin conexión
pytest -m red          # contra las fuentes reales
```

Con todo el historial, la librería reproduce las cifras de los proyectos de donde salió: el fondo A cae 24,6% y el E 3,7% entre el 20 de febrero y el 23 de marzo de 2020, y la morosidad del sistema pasa de 2,04% (feb-2020) a 1,26% (dic-2021) y a 2,44% (ago-2026).

## Fuentes y advertencias

- **mindicador.cl** es un agregador de terceros, no el publicador oficial. Para usos regulatorios, contrasta con el [Banco Central](https://si3.bcentral.cl/siete) o el [SII](https://www.sii.cl/valores_y_fechas/).
- **Superintendencia de Pensiones**: [valores cuota y patrimonio](https://www.spensiones.cl/apps/valoresCuotaFondo/vcfAFP.php). La serie incluye fines de semana con valores casi planos; para modelos de volatilidad conviene quedarse con días hábiles.
- **CMF**: [estadísticas de morosidad](https://www.cmfchile.cl/portal/estadisticas/626/w4-propertyvalue-28914.html).

La librería descarga a un ritmo moderado (una pausa entre pedidos) y guarda en caché lo que no cambia, para no cargar servicios públicos.

## Licencia

MIT — ver [LICENSE](LICENSE).

## Autor

**Pablo Reyes** — [github.com/Rxyxs](https://github.com/Rxyxs)
