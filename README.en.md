[English ] | [[Español](README.md) ]

# datoschile

[![tests](https://github.com/Rxyxs/datoschile/actions/workflows/tests.yml/badge.svg)](https://github.com/Rxyxs/datoschile/actions/workflows/tests.yml)
[![sources](https://github.com/Rxyxs/datoschile/actions/workflows/fuentes.yml/badge.svg)](https://github.com/Rxyxs/datoschile/actions/workflows/fuentes.yml)
[![dashboard](https://github.com/Rxyxs/datoschile/actions/workflows/panel.yml/badge.svg)](https://rxyxs.github.io/datoschile/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**Chilean public data, clean and in a DataFrame, in one line.** UF (Chile's inflation-indexed unit), dollar, euro, UTM, CPI, policy rate, IMACEC, GDP, unemployment and international reserves from the Central Bank, no key needed; daily copper and other metal prices from Cochilco; pension fund unit values; bank delinquency from the CMF, the financial regulator; the 346 communes with their CUT code and the 2024 Census; legal holidays and business days; and conversions between pesos, UF and pesos of another date.

[![Dashboard with UF, dollar, copper, inflation, policy rate, IMACEC, unemployment and bank delinquency, downloaded with datoschile](docs/portada.png)](https://rxyxs.github.io/datoschile/)

**[Open the interactive dashboard →](https://rxyxs.github.io/datoschile/)** (in Spanish). It is rebuilt every week with this same library: charts with time ranges and hover detail, pension funds A to E in UF, upcoming holidays and a "what is it worth today?" calculator.

```python
import datoschile as dc

dc.resumen()                                          # latest value of 9 indicators, with source
dc.indicadores.uf(desde=2020)                         # daily UF, corrected
dc.bcentral.serie("imacec")                           # official Central Bank series
dc.cochilco.cobre(desde=2024)                         # same-day LME copper, US$/lb
dc.sii.utm_ipc(desde=2010)                            # UTM, UTA and chain-linked CPI
dc.convertir.deflactar(1_000_000, "2015-01-15")       # those pesos, in today's pesos
dc.calendario.dias_habiles("2026-09-01", "2026-09-30")
dc.territorio.buscar_cut(["Ñuñoa", "Llay-Llay"])      # [13120, 5703], offline
dc.territorio.poblacion()                             # 2024 Census by commune
dc.pensiones.indice(fondos="A", desde=2008, real=True)  # fund index in UF
dc.cmf.morosidad(desde="2020-01")                     # monthly panel by bank
```

The API is in Spanish, like the sources: `desde`/`hasta` mean from/to.

## Why it exists

These sources are public and need no key, but none of them can be used as published. Each problem below came up while working with real data, and the library solves it once so nobody else has to find it:

| Source | Real problem | What datoschile does |
|---|---|---|
| UF (mindicador.cl) | On 29 and 30 December 2014 the "UF" is **608.15 and 607.38**: the US dollar leaked into the series. A deflated index jumps ×40 and back. | Drops any day that moves more than 1% from the last valid value (the UF never does) and fills it in. If mindicador is down, it uses the SII. |
| UF (mindicador.cl) | 2015-07-11 appears five times; 2015-12-12 and 2015-12-31 are missing. | Collapses identical copies, **fails if two copies disagree**, and interpolates geometrically, which is how the UF is computed. |
| CPI (SII) | The CPI index **changes base four times** (January 2010, 2014, 2019 and 2024: from 134.10 to 101.72 in 2024). Twelve-month inflation computed on the published index is off by up to **25.8 points**. | Detects each base change because the jump does not match the official monthly change, and chain-links the series. Against official 12-month inflation over 213 months, the largest gap is 0.075 points (rounding). |
| CPI (SII) | December 2011 has the monthly change as `0.6` (with a point) and February 1992 as `(-0,6)`. | Reads both; each has a test. |
| Copper (Central Bank and mindicador.cl) | The "copper per pound" the Central Bank publishes (and mindicador copies: identical on 99.7% of days) is not that day's LME price: it matches Cochilco to the cent on only **9%** of days in 2013–2025 and, at the best lag (1–2 days), ~20%, with a 2-cent mean error. | `cochilco.cobre()` returns the official same-day LME price. |
| IMACEC and unemployment (mindicador.cl) | mindicador keeps the **first published figure** and never revises it: April 2020 IMACEC shows −14.1% while the Central Bank's current figure is −15.1%. Only **3.8%** of months in 2013–2025 match (gaps up to 2.8 points). Unemployment is identical since 2020, but 2013–2019 are figures from before INE's revision (gaps up to 0.55 points). | `bcentral.serie("imacec")` and `bcentral.serie("desempleo")` return the current series; `resumen()` and the dashboard use them. These two do not fall back to mindicador when the Central Bank is down, so vintages are never mixed. |
| Metals (Cochilco) | Gold and silver stopped updating (London until Nov 2025, COMEX until Mar 2026), with no notice on the page. | `cochilco.precio()` warns when a series has had no data for more than 30 days. |
| Holidays | Common lists miss 17 and 20 September 2010 (Law 20,450, the Bicentennial); one puts the 2009 election on Friday the 11th when it was Sunday the 13th. Indigenous Peoples' Day falls on the solstice **in Chilean time**: in 2025 it was the 20th although the solstice was on the 21st in UTC. | Computes holidays from the law and checks them against two independent sources (below). |
| Unit values (pension regulator) | The header saying which AFP sits in each column **changes 31 times** in Fund C's file. Read with a single header, columns silently misalign. | Re-reads the header every time it appears. `indice()` weights each AFP's return by its previous-day assets and, with `real=True`, deflates by the corrected UF. |
| Delinquency (CMF) | 128 Excel files in **three layouts** between 2016 and 2026, and banks that merge or get renamed. In the 2023-07 file the system row is `---`. | Detects each file's layout, joins mergers into one series, fails on unknown layouts, and leaves `---` as `NaN`: it does not make up a value. |

Every cleaning rule has a test that reproduces the original problem.

## Installation

```bash
pip install git+https://github.com/Rxyxs/datoschile
```

Requires Python 3.10+. Depends only on pandas, requests and openpyxl.

## What's inside

**`resumen()`**: one row per indicator (UF, dollar, LME copper, UTM, 12-month inflation, policy rate, IMACEC, unemployment and bank delinquency) with its latest value, the date of the data point, the 12-month change and the source. Each comes from its official source (Central Bank, SII, Cochilco, CMF); if a source is down, that row is left empty with the reason and the rest is returned anyway.

**`bcentral`**: 17 official series from the [Central Bank](https://si3.bcentral.cl/Indicadoressiete/secure/Indicadoresdiarios.aspx), no user or key. Its API requires registration, but the public "Indicadores diarios" page publishes each series' full history; daily series come one year per page and the library requests each year through the same selector the page uses.

| Function | Returns |
|---|---|
| `serie(codigo, desde, hasta)` | Daily: `dolar`, `euro`, `uf`, `ivp`, `tpm` (policy rate), `cobre`, `oro`, `plata`, `tcm` (multilateral exchange rate), `euro_por_dolar`, `yen_por_dolar`, from 1997. Monthly: `imacec` (from 1997), `ipc` (from 1928), `desempleo` (from 2010), `utm` (from 1990), `reservas` (from 1982). Quarterly: `pib` (GDP, from 1996). Details and units in `bcentral.SERIES`. |

**`indicadores`**: any series from [mindicador.cl](https://mindicador.cl), which mirrors Central Bank, INE and SII series. If mindicador does not respond, the UF and the dollar are fetched from the SII, and policy rate, CPI, UTM and euro from the Central Bank (with a `warning`). IMACEC and unemployment have no automatic fallback because mindicador's figures are not the current ones (see above): use `bcentral.serie()` for those two.

| Function | Returns |
|---|---|
| `uf(desde, hasta)` | Corrected daily UF (one value per calendar day). What was corrected is in `df.attrs["informe"]`. |
| `dolar(...)` | Observed dollar, business days. |
| `serie(codigo, desde, hasta)` | Any of: `uf`, `ivp`, `dolar`, `euro`, `utm`, `ipc`, `tpm`, `imacec`, `tasa_desempleo`, `libra_cobre`, `bitcoin` (details in `indicadores.SERIES`). |

**`sii`**: the official tables of the [SII](https://www.sii.cl/valores_y_fechas/), the tax authority, no key needed, from 1990 on.

| Function | Returns |
|---|---|
| `descargar_anio("uf" \| "dolar", anio)` | One year of UF or observed dollar (the SII uses three page layouts depending on the period, and all three are parsed). They match mindicador on every day of 2014 and 2024, except 29 and 30 December 2014, where the SII has the correct UF. |
| `utm_ipc(desde, hasta)` | Monthly: `utm`, `uta`, `ipc` (as published), `ipc_var_mensual` (the official INE change) and `ipc_empalmado` (on a single base: the one to deflate with). Detected base changes are in `df.attrs["cambios_de_base"]`. |

**`cochilco`**: daily prices from the [Chilean Copper Commission](https://boletin.cochilco.cl/estadisticas/grafico.asp).

| Function | Returns |
|---|---|
| `cobre(desde, hasta, bolsa="LME")` | Copper in dollars per pound, LME from 1996 or COMEX from 2005. |
| `precio(metal, desde, hasta, bolsa)` | `cobre`, `oro`, `plata`, `zinc`, `aluminio`, `niquel`, `plomo` or `estanio` (copper, gold, silver, zinc, aluminium, nickel, lead, tin), from 2001. Base metals in US$/lb (Cochilco publishes cents), gold and silver in US$/troy ounce. |

**`calendario`**: Chilean legal holidays from 2008, computed from the law and offline (it works for future years; elections and one-off laws are loaded through 2027).

| Function | Returns |
|---|---|
| `feriados(desde, hasta, regionales)` | `fecha`, `nombre`, `irrenunciable` (shops must close), `ley` and `alcance` (scope). `feriados(2026)` is all of 2026. `regionales=True` adds Arica (7 June) and Chillán (20 August). |
| `es_feriado(fecha)`, `es_habil(fecha, bancario)` | With `bancario=True`, 31 December is not a business day either (bank holiday). |
| `dias_habiles(desde, hasta)`, `sumar_habiles(fecha, n)` | Business days in a range; the date `n` business days after (or before). |

**`territorio`**: regions, provinces and communes (Chile's municipalities) with their CUT code, and the aggregates of INE's [2024 Census](https://censo2024.ine.gob.cl/).

| Function | Returns |
|---|---|
| `comunas()`, `regiones()` | The 2024 Census administrative division (346 communes, 56 provinces, 16 regions). Ships with the library: offline. |
| `buscar_cut(nombres, region)` | The CUT code of each name, tolerating accents, case, hyphens and old spellings ("NUNOA", "Llay-Llay", "Aisén", "Marchigüe"). The CUT code is the key to join data by commune; the name is not. |
| `poblacion(nivel)` | By commune, province or region: population, sex, mean age and schooling, % aged 0–13, % aged 60+, % immigrants, % indigenous peoples, households, persons per household, dwellings and % overcrowded dwellings. |
| `censo(nivel)` | The ~190 aggregate variables INE publishes (employment, industry, commuting, housing materials, water, electricity...). |

INE's file comes by census zone and locality; the library sums it by commune and checks that the total is exactly the published census count (18,480,432). Two source details: averages use a decimal comma (`32,8`), and some counts for very small zones are suppressed with `*`. Those are summed as zero and the `celdas_reservadas` column says how many each row has, so those totals are a lower bound. Mean age and schooling are recomputed weighted by population; averaging the zones' averages would be wrong.

**`convertir`**: to compare amounts over time. They take a number and a date, or whole columns.

| Function | Returns |
|---|---|
| `pesos_a_uf(montos, fechas)`, `uf_a_pesos(montos, fechas)` | Using each date's corrected UF. |
| `deflactar(montos, fechas, a=None)` | Pesos of each date in pesos of month `a` (by default, the latest published CPI), using the chain-linked CPI. |

**`pensiones`**: daily unit values and assets since 2002, multi-funds A–E.

| Function | Returns |
|---|---|
| `valor_cuota(fondos, desde, hasta, afps)` | One row per date, fund and AFP: `valor_cuota` and `valor_patrimonio`. |
| `indice(fondos, desde, hasta, real)` | Fund index (all AFPs weighted by assets), base 100. |

**`cmf`**: 90+ day delinquency, monthly, since 2016.

| Function | Returns |
|---|---|
| `morosidad(desde, hasta, solo_sistema)` | One row per month and bank: % delinquent in `total`, `clientes`, `comercial`, `personas`, `consumo`, `vivienda`, and the delinquent amount in millions of pesos. |

`desde` and `hasta` take a year (`2020`), a month (`"2020-03"`) or a date (`"2020-03-15"`).

### From the terminal

```bash
datoschile resumen
datoschile bcentral imacec --desde 2015 -o imacec.csv
datoschile uf --desde 2020 -o uf.csv
datoschile metal cobre --desde 2024 --bolsa COMEX
datoschile utm-ipc --desde 2010 -o cpi.csv
datoschile feriados --desde 2026 --hasta 2027 --regionales
datoschile censo --nivel region -o census_regions.csv
datoschile indice --fondos A --desde 2008 --real -o fund_a_real.csv
datoschile morosidad --desde 2020-01 --solo-sistema
```

## Cache

A year that has ended doesn't change, so it is stored in `~/.cache/datoschile` and never requested again; the current year (and the CMF's last three months, which can be revised) is always downloaded again. The first full UF download takes about 2 minutes because mindicador is slow, and Cochilco takes about 9 seconds per year; after that, closed years load from disk in hundredths of a second. To use another folder: `DATOSCHILE_CACHE=/path`. To skip the cache: `cache=False` or `--sin-cache`.

## Verified against the sources

Offline tests run on every change (Python 3.10 to 3.13). Two of them check the holidays against independent sources:

- **The yearly holiday table of feriados.cl, 2009 to 2027** (archive.org snapshots of each year): every year matches except the two differences explained above (2009 and the 2010 Bicentennial).
- **The days with no observed dollar in the SII tables, 2008 to 2026**: the dollar is published every business day, so a weekday without one is a holiday. All 208 days match the computed holidays, both ways.

Another set downloads real data and checks known values. It runs **every week** on GitHub Actions, to find out a source changed its format before a user does:

- UF on 2008-12-31 = 21,452.57, the value published by the SII; the 2014 dollar leak is detected and fixed.
- Central Bank: policy rate on 2024-01-02 = 8.25%; April 2020 IMACEC below −10%; 1996 GDP in four quarters; dollar on 2014-01-02 = 524.61, the same value as the SII.
- LME copper on 2025-01-02 = 3.9397 US$/lb at Cochilco, and base metals are still current.
- UTM in January 2025 = $67,429; all four CPI base changes are detected, and chain-linked 12-month inflation for January 2025 is the one the SII publishes (4.9%).
- 2024 Census: 346 communes adding up to 18,480,432 people; Puente Alto 568,086; Metropolitan Region 7,400,741.
- Fund A falls between 20% and 45% in 2008; system delinquency in February 2020 is 2.04%.

```bash
pip install -e ".[dev]"
pytest                 # offline
pytest -m red          # against the real sources
```

With the full history, the library reproduces the figures of the projects it came from: Fund A falls 24.6% and Fund E 3.7% between 20 February and 23 March 2020, and system delinquency goes from 2.04% (Feb 2020) to 1.26% (Dec 2021) and 2.44% (Aug 2026).

## Dashboard and cover image

- [`ejemplos/sitio.py`](ejemplos/sitio.py) builds the [web dashboard](https://rxyxs.github.io/datoschile/): a single HTML page with no dependencies and the data embedded. The `panel` workflow rebuilds it every Monday and publishes it on GitHub Pages.
- [`ejemplos/portada.py`](ejemplos/portada.py) builds the image above.

## Sources and caveats

- **mindicador.cl** is a third-party aggregator, not the official publisher, and it goes down: in October 2026 it returned 500 errors for several days. The UF and the dollar fall back to the SII automatically, and policy rate, CPI, UTM and euro to the Central Bank. For IMACEC and unemployment, use `bcentral.serie()` directly.
- **Central Bank**: [Indicadores diarios](https://si3.bcentral.cl/Indicadoressiete/secure/Indicadoresdiarios.aspx). The pages carry an opaque parameter that the library reads from the index each session; if the Central Bank changes the layout, the weekly test catches it.
- **SII**: [UF](https://www.sii.cl/valores_y_fechas/uf/uf2026.htm), [dollar](https://www.sii.cl/valores_y_fechas/dolar/dolar2026.htm) and [UTM, UTA and CPI](https://www.sii.cl/valores_y_fechas/utm/utm2026.htm). The current month's dollar table is sometimes loaded days late; `resumen()` takes the dollar from mindicador and falls back to the SII only if mindicador is down.
- **Cochilco**: [metal price bulletin](https://boletin.cochilco.cl/estadisticas/grafico.asp).
- **Pension regulator**: [unit values and assets](https://www.spensiones.cl/apps/valoresCuotaFondo/vcfAFP.php). The series includes weekends with nearly flat values; for volatility models, keep business days only.
- **INE, 2024 Census**: [aggregate file by zone and locality](https://storage.googleapis.com/bktdescargascenso2024/Datos_agregados/Base_zona_localidad_CPV24.zip) and variable dictionary, under [INE's open data license](https://www.ine.gob.cl/terminos-de-uso-y-licencia-de-datos-abiertos).
- **CMF**: [delinquency statistics](https://www.cmfchile.cl/portal/estadisticas/626/w4-propertyvalue-28914.html).
- **Holidays**: the text of each law at the [National Congress Library](https://www.bcn.cl/leychile). One-off regional holidays (for example, the Pope's visit in 2018) are not included.

The library downloads at a moderate pace (a pause between requests) and caches what doesn't change, so as not to load public services.

## License

MIT — see [LICENSE](LICENSE).

## Author

**Pablo Reyes** — [github.com/Rxyxs](https://github.com/Rxyxs)
