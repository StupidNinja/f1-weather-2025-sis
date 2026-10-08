"""Generate the readable notebook source; execute separately to verify all outputs."""
from pathlib import Path
import nbformat as nbf

root=Path(__file__).resolve().parents[1]
nb=nbf.v4.new_notebook()
nb.metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
             'language_info':{'name':'python','version':'3.12.12'}}
cells=[]
def md(text): cells.append(nbf.v4.new_markdown_cell(text.strip()))
def code(text): cells.append(nbf.v4.new_code_cell(text.strip()))
md('''# Weather Conditions Across the 2025 Formula 1 Season

**Authors:** Temirkhan Adilet and Bertayev Azat  
**Professor:** Koishiyeva

## Research question
How did air temperature, precipitation, relative humidity and wind differ between Formula 1 circuits **on the local race days of the 2025 season**?

This notebook combines a static-HTML Wikipedia scrape with Open-Meteo's Historical Weather API. The analysis contains 24 race days and 576 hourly rows. Each race contributes its local civil day, not its practice/qualifying days and not just the race-session hours. Las Vegas therefore uses **22 November 2025**, its Saturday local date.

**Data meaning:** ERA5 atmospheric reanalysis estimates near each circuit. These are not on-track measurements, track-surface temperatures, race-control observations or evidence about driver performance.''')
md('''## 1. Reproducible setup

Run this notebook from the project folder after installing `requirements.txt`. By default, the notebook uses the included raw cache and makes **no network requests**. It verifies each cached file against its acquisition-time SHA-256 hash, reparses the HTML, re-cleans the JSON and regenerates all CSVs and charts.

To acquire missing sources deliberately, run `python src/build_data.py --online` before rerunning the notebook. That command checks Wikipedia's robots.txt, identifies the educational client, spaces requests by at least 1.2 seconds and stops on HTTP errors. It does not bypass access denial. Existing cached sources are kept for an exact reproducible snapshot.''')
code('''from pathlib import Path
import os, sys, json
ROOT = Path.cwd()
if not (ROOT / 'src').exists():
    raise RuntimeError('Start this notebook in the extracted f1_weather_project folder')
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.jupyter' / 'matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.jupyter' / 'cache'))
sys.path.insert(0, str(ROOT / 'src'))
import requests
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
get_ipython().run_line_magic('matplotlib', 'inline')
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import display, Markdown, Image
from pipeline import parse_calendar, parse_coordinates, clean_weather, expected_hours, VARIABLES
from sources import SourceStore
from build_data import build_dataset
from analysis import analyze, create_figures, DAILY_VARS, LABELS, CODES, SHORT
pd.set_option('display.max_columns', 16)
pd.set_option('display.float_format', lambda x: f'{x:.3f}')
print('Working folder:', ROOT.name)
print('pandas', pd.__version__, '| NumPy', np.__version__, '| Seaborn', sns.__version__)''')
md('''## 2. Sources, ethical collection and provenance

1. [Wikipedia: 2025 Formula One World Championship](https://en.wikipedia.org/wiki/2025_Formula_One_World_Championship): calendar table, race names, circuit links and dates
2. The corresponding 24 Wikipedia circuit pages: latitude and longitude from their geographic markup; exact article URLs are preserved in `calendar.csv`
3. [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api): hourly temperature at 2 m, relative humidity at 2 m, precipitation and wind speed at 10 m, with `models=era5`, `timezone=auto`, °C, %, mm and km/h

Raw HTML, the robots response, JSON payloads, request parameters, URLs, retrieval times and hashes are retained in `data/raw/`. Wikipedia text is credited to its contributors under [CC BY-SA](https://en.wikipedia.org/wiki/Wikipedia:Copyrights). Open-Meteo data are credited under [CC BY 4.0](https://open-meteo.com/en/licence); underlying ERA5 is from ECMWF/Copernicus. See the README for full reuse notes.''')
code('''store = SourceStore(ROOT / 'data/raw', offline=True)
manifest = pd.DataFrame.from_dict(store.manifest, orient='index').rename_axis('cache_file')
for filename in store.manifest:
    store.read(filename)  # raises on a changed or undocumented raw file
print(f'Verified {len(manifest)} raw source files')
display(manifest[['kind','retrieved_at_utc','bytes','url']].head(6))
print('First retrieval:', manifest.retrieved_at_utc.min())
print('Last retrieval: ', manifest.retrieved_at_utc.max())''')
md('''### Static-HTML scraping approach

BeautifulSoup locates the calendar using its column headings rather than a fragile table number. It removes citation markers and ignores country-flag image links before selecting each circuit's textual article link. Coordinates are parsed from the `.geo` decimal field, with a degrees/minutes/seconds fallback. Missing coordinates, an incomplete calendar or an unexpected Las Vegas date trigger an error instead of guessed data.

The next cell exposes the actual scraper implementation. The full reusable functions are in `src/pipeline.py`.''')
code('''import inspect
print(inspect.getsource(parse_calendar))
print(inspect.getsource(parse_coordinates))''')
md('''## 3. Define a race day correctly

The API returns UNIX instants; they are interpreted as UTC and converted to each returned IANA timezone. A race day runs from local midnight to the next local midnight. Expected coverage is calculated with timezone-aware boundaries, so a daylight-saving transition could produce 23 or 25 hours. The 24 selected 2025 dates each have 24 hours. The raw Las Vegas response contains a scalar UTC offset that differs from its historical race-date offset; the code deliberately uses the IANA timezone and UTC instants instead, recovering UTC−08:00 for 22 November.

**Precipitation requires a separate time alignment.** Open-Meteo labels precipitation by the end of its preceding one-hour accumulation. To measure rainfall over the actual civil race day, the row at hour *t* contains precipitation ending at *t + 1 hour*. Temperature, humidity and wind remain instantaneous values at *t*. The final 23:00 row therefore uses the precipitation endpoint at the following midnight.

The archive endpoint uses date-level bounds, so raw requests include the race date and the following date. Only the race-day instants plus that one necessary precipitation boundary contribute to the analysis. No next-day temperature, humidity or wind enters the final table. `precipitation_interval_end_utc` and `precipitation_interval_end_local` make this alignment auditable.''')
code('''calendar, hourly, daily, quality = build_dataset(ROOT, offline=True)
display(calendar[['round','race_name','circuit','race_date','latitude','longitude']])
print(json.dumps(quality, indent=2))''')
md('''## 4. Cleaning and data-quality checks

- Names use snake_case and units appear in weather column names
- Dates, integer rounds/hours and numeric weather values are parsed explicitly
- Coordinates are scraped rather than manually invented; requested and returned grid coordinates remain separate
- The key `(round, timestamp_utc)` must be unique; duplicates fail loudly rather than being arbitrarily kept
- Missing or nonnumeric weather values are detected; **no imputation** and no replacement of unknown rain with zero
- Humidity must lie within 0–100%; precipitation and wind must be nonnegative; conservative physical bounds flag implausible temperatures/winds
- Every expected local race-day hour and each precipitation boundary must be present

These rules produced no missing weather values or duplicate hourly keys in this snapshot.''')
code('''checks = pd.DataFrame({
    'check': ['Calendar races', 'Clean hourly rows', 'Expected hourly rows', 'Duplicate race/hour keys',
              'Missing weather cells', 'Imputed weather cells', 'Rows outside local race date'],
    'value': [len(calendar), len(hourly), quality['expected_hourly_rows'],
              hourly.duplicated(['round','timestamp_utc']).sum(),
              hourly[list(VARIABLES.values())].isna().sum().sum(), 0,
              (hourly.local_date != hourly.race_date).sum()]
})
display(checks)
assert len(calendar) == len(daily) == 24
assert len(hourly) == quality['expected_hourly_rows'] == 576
assert not hourly.duplicated(['round','timestamp_utc']).any()
assert hourly[list(VARIABLES.values())].notna().all().all()
assert (hourly.local_date == hourly.race_date).all()
assert hourly[hourly.race_name.str.contains('Las Vegas')].timestamp_local.str.endswith('-08:00').all()
print('DST control examples:', len(expected_hours('2025-03-09','America/New_York')),
      'hours in spring;', len(expected_hours('2025-11-02','America/New_York')), 'hours in autumn')
vegas = hourly[hourly.race_name.str.contains('Las Vegas')]
display(vegas[['race_date','timestamp_local','timestamp_utc','precipitation_interval_end_local']].iloc[[0,-1]])''')
code('''display(hourly[['round','race_name','timestamp_local','temperature_c','relative_humidity_pct',
                'precipitation_mm','wind_speed_kmh','latitude','longitude','grid_latitude','grid_longitude']].head())
display(hourly[['round','hour_local','temperature_c','relative_humidity_pct','precipitation_mm','wind_speed_kmh']].dtypes.to_frame('dtype'))
print('Grid coordinates can differ from circuit coordinates because ERA5 represents a surrounding grid cell.')''')
md('''## 5. Descriptive statistics and aggregation

Each race day contributes hourly means for temperature, humidity and wind; minimum and maximum temperature; total interval-aligned precipitation; the number of hours with positive precipitation; and maximum hourly wind. Wind is wind speed, not gust speed. A positive modeled precipitation amount does not prove that the race session was wet.

The primary comparison and correlations use **24 race-day rows**. The 576 hourly rows are repeated, temporally dependent samples and must not be treated as 576 independent race events.''')
code('''descriptive, pearson, spearman, results = analyze(hourly, daily, ROOT)
display(daily[['round','race_name','temperature_mean_c','temperature_min_c','temperature_max_c',
               'relative_humidity_mean_pct','precipitation_total_mm','wet_hours','wind_speed_mean_kmh']])
display(descriptive.rename(index=LABELS))''')
md('''## 6. Visual comparisons

Figures use the same ERA5 model, variable heights, units and full-local-day scope. Three-letter race codes in the first two charts map to the calendar below.''')
code('''display(pd.DataFrame({'Round': range(1,25), 'Code': CODES, 'Grand Prix': SHORT}).set_index('Round').T)
figure_paths = create_figures(hourly, daily, ROOT, show=True)
print('Saved', len(figure_paths), 'labeled figures to figures/')''')
md('''### Interpretation of the figures

The temperature ranges show both cross-location differences and within-day variation. Precipitation is uneven and many totals are zero, so a few wet dates can dominate simple summaries. Humidity and wind need separate scales because they have different units. The hourly heatmap shows why race-day averages cannot be read as race-session weather, especially for evening/night Grands Prix.''')
md('''## 7. Associations, not causes

Pearson's correlation measures linear association among the 24 daily aggregates. Spearman's rank correlation is included because precipitation is skewed and contains many zeros. These coefficients describe this selected season only. They do not isolate weather effects from latitude, elevation, season, geography or each race's scheduling.

No p-values, causal claims or driver/team performance conclusions are made. A supplemental pooled-hour correlation CSV is saved for transparency, but is **descriptive only** because adjacent hours from the same race are not independent.''')
code('''display(pearson.rename(index=LABELS, columns=LABELS).round(3))
display(spearman.rename(index=LABELS, columns=LABELS).round(3))
print('Comparison units for these matrices:', len(daily), 'race-day aggregates')''')
md('''## 8. Results summary''')
code('''warm = results['warmest_day_mean']; cool = results['coolest_day_mean']
wet = results['wettest_day']; windy = results['windiest_day_mean']
r_th = pearson.loc['temperature_mean_c','relative_humidity_mean_pct']
r_hp = pearson.loc['relative_humidity_mean_pct','precipitation_total_mm']
text = f"""
- Warmest local race-day mean: **{warm['race_name']}**, **{warm['value']:.2f} °C**
- Coolest local race-day mean: **{cool['race_name']}**, **{cool['value']:.2f} °C**
- Largest full-day precipitation total: **{wet['race_name']}**, **{wet['value']:.1f} mm**
- Highest mean 10 m wind speed: **{windy['race_name']}**, **{windy['value']:.2f} km/h**
- **{results['days_with_any_precipitation']} of 24** race days have any positive modeled precipitation; **{results['days_with_at_least_1mm']}** reach at least 1 mm
- Race-level temperature–humidity Pearson correlation: **r = {r_th:.3f}**
- Race-level humidity–precipitation Pearson correlation: **r = {r_hp:.3f}**

These values characterize whole local days and ERA5 grid estimates, not race-session conditions.
"""
display(Markdown(text))''')
md('''## 9. Limitations and conclusion

**Spatial resolution.** ERA5 is an approximately 0.25° (about 25 km) atmospheric reanalysis. Open-Meteo selects a nearby land grid cell and applies elevation handling; results can miss circuit-scale showers, coastal effects and local wind. Latitude/longitude in the raw response are grid coordinates, not necessarily the requested circuit point.

**Temporal scope.** Entire local civil race days were intentionally selected. The conclusions do not describe only the Grand Prix's start/end window. Precipitation intervals are explicitly aligned to the day, but temperature/humidity/wind are hourly instants rather than continuous measurements.

**Selection and sample size.** This is one 24-race season. Circuit geography, latitude, elevation, time of year and scheduling are confounded. Cross-race associations are descriptive, and an hour-level sample-size claim would overstate independent information.

**Source uncertainty.** Wikipedia pages can change, APIs may revise historical data and reanalysis is modeled. The included raw snapshot, hashes and exact parameters preserve the evidence used here. Amounts are limited by API precision; a tiny positive precipitation estimate is not proof of rain during the race.

**Conclusion.** A static web source and a public API can be integrated into an auditable race-day weather dataset. The largest analytical risks are incorrect local dates, confusing modeled grid weather with on-track observations, and misaligning precipitation accumulation timestamps. The validation rules address the first and third; the interpretation acknowledges the second.''')
md('''## 10. Reproduce and inspect the deliverables

- `data/processed/calendar.csv`: 24 scraped race/circuit/date/coordinate records
- `data/processed/f1_weather_hourly.csv`: 576 clean, merged race-day rows
- `data/processed/f1_weather_daily.csv`: 24 daily aggregates
- `data/processed/quality_report.json`: validation counts and scope
- `data/processed/results_summary.json`: machine-readable findings
- `data/raw/manifest.json`: URLs, acquisition times, parameters and SHA-256 hashes
- `figures/`: five chart PNGs
- `src/`: documented source parsing, HTTP cache, cleaning and analysis functions
- `tests/`: parser, boundary alignment, DST, missingness, range, duplicate and cache tests

Run `python -m pytest tests -q` for validation, and `python scripts/execute_notebook.py` for a fresh end-to-end offline execution of every notebook cell in IPython (the tested path). Use `--engine kernel` for a standard separate Jupyter kernel when available. The assignment requires a GitHub repository link for submission. The project is prepared locally; remote repository creation/publication remains pending the owners’ choice and approval.

### References
- Wikipedia contributors. [2025 Formula One World Championship](https://en.wikipedia.org/wiki/2025_Formula_One_World_Championship), and the 24 circuit articles listed in `calendar.csv`; snapshot retrieval times are recorded in the manifest
- Open-Meteo. [Historical Weather API documentation](https://open-meteo.com/en/docs/historical-weather-api) and [data licence](https://open-meteo.com/en/licence)
- ECMWF/Copernicus Climate Change Service. [ERA5 hourly data on single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)

Code can be inspected and adapted. Review and understand the notebook and follow the institution's rules on attribution and assisted work before submitting.''')
nb.cells=cells
nbf.write(nb,root/'f1_weather_2025.ipynb')
print(f'Created notebook with {len(cells)} cells')
