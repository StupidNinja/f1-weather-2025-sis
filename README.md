# Weather Conditions Across the 2025 Formula 1 Season

**Authors:** Temirkhan Adilet and Bertayev Azat  
**Professor:** Koishiyeva

A reproducible Python/Jupyter project comparing **air temperature, precipitation, relative humidity and wind on the local race days only** at all 24 circuits in the 2025 Formula 1 season.

## Main files

- `f1_weather_2025.ipynb` — executed notebook, explanations, tables and five embedded charts
- `data/processed/f1_weather_hourly.csv` — **576** merged hourly records
- `data/processed/f1_weather_daily.csv` — **24** race-day aggregates
- `data/processed/calendar.csv` — scraped race calendar, circuit article URLs and coordinates
- `data/processed/quality_report.json` — completeness, missingness and duplicate checks
- `data/processed/results_summary.json` — findings and correlation matrices
- `data/raw/` — original Wikipedia HTML, robots.txt, Open-Meteo JSON and a SHA-256 provenance manifest
- `figures/` — five labeled PNG charts
- `src/` — reusable acquisition, parsing, cleaning and analysis code
- `tests/` — automated correctness and provenance tests
- `report/report_Temirkhan_Bertayev.pdf` — public PDF (student IDs omitted): cover followed by the complete two-page report (3 pages total)
- `report/cover_Temirkhan_Bertayev.docx` — editable cover source
- `report/report_Temirkhan_Bertayev.docx` — editable two-page report source

## Quick start

Python **3.12** was used. Create and activate a virtual environment:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/execute_notebook.py
```

The last command runs **every notebook code cell in a fresh IPython process**, captures real tables/charts, validates the notebook format and writes the executed notebook. It uses the included raw cache only; no API key or internet is needed after installation. This is the verified execution route in the supplied cloud environment.

For the normal interactive Jupyter interface:

```bash
python -m pip install -r requirements-ui.txt
jupyter lab f1_weather_2025.ipynb
```

Open the notebook and choose **Restart Kernel and Run All Cells**. Alternatively, `python scripts/execute_notebook.py --engine kernel` uses nbclient with a separate Jupyter kernel. This optional route could not be verified in the restricted cloud environment because ZeroMQ socket/interface operations are blocked. The notebook's cells were actually executed in IPython; no outputs were fabricated. The default runner avoids that local-socket requirement.

The direct dependencies in `requirements.txt` are pinned to tested versions; `requirements-lock.txt` also records their resolved dependency versions. `requirements-ui.txt` is an optional UI installation and is not needed for the verified command-line execution.

## Research question and units of analysis

How did race-day weather vary across the 2025 Formula 1 calendar?

- Calendar/circuit metadata: **24 rows**
- Hourly analytic unit: one hour on a circuit's **local civil race date**
- Clean hourly data: **24 × 24 = 576 rows**
- Main comparison/correlation unit: **24 race-day aggregates**
- No practice, qualifying or full-weekend analysis
- Full local days, not the race-session start/end window
- Las Vegas: **22 November 2025 locally**, not its 23 November UTC date

## Sources and acquisition

1. Static HTML from [Wikipedia's 2025 Formula One World Championship calendar](https://en.wikipedia.org/wiki/2025_Formula_One_World_Championship)
2. Geographic coordinate markup on the corresponding 24 Wikipedia circuit articles, linked in `calendar.csv`
3. [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api), with `models=era5`, `timezone=auto`, `timeformat=unixtime` and explicit units:
   - temperature at 2 m: °C
   - relative humidity at 2 m: %
   - precipitation: mm
   - wind speed at 10 m: km/h

The public-data snapshot was acquired on **7 October 2026 UTC**. Exact per-file timestamps, source URLs, request parameters, response byte counts and SHA-256 hashes are in `data/raw/manifest.json`. There are **50 original source files**: one robots response, 25 HTML pages and 24 JSON API responses.

`SourceStore` checks Wikipedia's robots.txt, sends a descriptive educational User-Agent, makes serial requests separated by at least 1.2 seconds, caches successful responses and stops on HTTP errors. There is no access-control bypass. No credentials, private accounts or personal data are used.

To collect any **missing** sources deliberately, run:

```bash
python src/build_data.py --online
```

Existing raw cache files are reused and hash-checked, and a changed parameter set is rejected rather than silently mixed with a prior response. The default command without `--online` is strictly offline. Keep the supplied raw snapshot unchanged; create a separate project copy if you want to compare a future source refresh. Check the applicable current robots policy before refreshing Wikipedia.

## Important time alignment

Open-Meteo's temperature, humidity and wind are instantaneous values at timestamp **t**. Its precipitation is the sum for the **preceding hour**, labeled by that interval's ending timestamp.

To describe the same civil race day correctly:

- Each cleaned row is labeled by its local hour/start instant **t**
- Temperature, humidity and wind retain their values at **t**
- Precipitation is taken from the raw endpoint **t + 1 hour**
- The final local 23:00 row uses precipitation ending at the next midnight

The API has date-level start/end bounds, so each cached response includes the race date and the next date (**1,152 raw hourly records** in total). The cleaner retains only race-day instants and their matching forward precipitation intervals. The next-day context is not part of the analysis. Both interval-end timestamps are retained in the CSV.

UNIX timestamps are converted with the returned **IANA timezone**, not by adding a single scalar offset. This matters in the Las Vegas response, whose scalar `utc_offset_seconds` differs from the historical race-date offset. Correct conversion produces **UTC−08:00** on 22 November. Timezone-aware civil-day boundaries account for 23/25-hour daylight-saving days; all 24 selected race dates have 24 hours.

## Cleaning and validation

- Calendar table identified from headings; citations and flag-image links excluded
- Circuit coordinates parsed from actual `.geo` markup, with a DMS fallback
- Snake_case columns, numeric weather dtypes and explicit time conversions
- Unique `(round, timestamp_utc)` key; duplicates trigger an error
- Missing/nonnumeric values trigger an error; **no imputation**
- Conservative physical bounds and exact API-unit checks
- Every expected local-day hour and precipitation boundary required
- Cached bytes checked against acquisition hashes and request parameters

This snapshot has **0 missing weather values, 0 duplicate keys and 0 imputed values**.

## Main results

- Warmest race-day mean: **Saudi Arabian Grand Prix, 32.07 °C**
- Coolest race-day mean: **Japanese Grand Prix, 13.74 °C**
- Largest civil-day precipitation total: **Miami Grand Prix, 24.2 mm**
- Highest mean wind speed: **Azerbaijan Grand Prix, 34.33 km/h**
- Any positive modeled precipitation: **11 of 24 days**; at least 1 mm: **7 days**
- Pearson temperature–humidity correlation: **−0.354**
- Pearson humidity–precipitation correlation: **0.512**

The correlation sample is **n = 24** race-day aggregates. Spearman correlations and descriptive statistics are also saved. Pooled-hour correlations are labeled descriptive-only; hourly readings from the same day are dependent. No significance or causality claim is made.

## Figures

1. Mean temperature and hourly minimum–maximum by race
2. Midnight-to-midnight precipitation totals
3. Humidity and wind comparisons on separate scales
4. Race-day Pearson correlation heatmap
5. Hourly local-day temperature heatmap

Three-letter chart codes are mapped to all 24 race names in the notebook.

## Limitations

ERA5 is modeled atmospheric reanalysis on a roughly **0.25° (~25 km) grid**, not a circuit weather station. Requested coordinates and selected grid coordinates differ; Open-Meteo also handles elevation. Fine-scale showers and local wind can be missed. Air temperature at 2 m is **not track temperature**, and wind speed is **not a gust measurement**.

The analysis covers entire local days, so a wet day does not prove a wet race. Circuit geography, elevation, latitude, season and scheduling are confounded. One 24-race season cannot establish general causal relationships or effects on drivers/results. Source pages and historical API data can change; the preserved raw snapshot makes this version auditable.

## Attribution and data reuse

- Calendar and circuit-page HTML: **Wikipedia contributors**, articles listed in `calendar.csv`, under Wikipedia's applicable [Creative Commons Attribution-ShareAlike terms](https://en.wikipedia.org/wiki/Wikipedia:Copyrights). The raw pages preserve source attribution/history links. Treat derived calendar metadata consistently with those terms
- Weather: **Open-Meteo**, [CC BY 4.0](https://open-meteo.com/en/licence), based on **ECMWF / Copernicus Climate Change Service ERA5**. The hourly precipitation column is time-aligned and daily summaries are derived from the supplied API data
- ERA5 reference: [Copernicus ERA5 hourly data on single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)

These source licences cover their respective data; this project does not assert ownership over third-party content.

## Submission checklist

- Review and understand the notebook and report; follow institutional rules for attribution and assisted work
- This public copy omits student IDs. The separate submission copy retains them.
- Include this repository URL with the submission.
- Submit the executed notebook, report and repository link according to the assignment instructions
- The working deadline is **9 October 2026**; confirm the exact institutional cutoff

