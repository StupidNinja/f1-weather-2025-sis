# Weather Conditions Across the 2025 Formula 1 Season

## Project scope
Authors: Temirkhan Adilet and Bertayev Azat. Professor: Koishiyeva.
Compare temperature, precipitation, relative humidity and wind at circuits on the local race date only. Scrape the 2025 calendar and circuit coordinates from static Wikipedia HTML. Retrieve hourly ERA5 historical reanalysis from Open-Meteo. Preserve raw sources, provenance and reproducible code.

## Implementation plan
1. Test and implement calendar/coordinate parsing, explicit local date handling, robots-aware cached requests and strict weather cleaning.
2. Acquire the 24 calendar rows and circuit pages; make one gentle request per race day; retain raw response hashes, URLs, parameters and acquisition times.
3. Test clean merged hourly data, timezone/DST coverage, missing values, duplicate keys and metadata. Aggregate race days without inventing values.
4. Execute an explanatory notebook from the cache with descriptive statistics, race-day correlations and at least three labeled charts. Include limitations and source attribution.
5. Verify complete offline rerun, test suite, artifact quality and package with README and pinned environment.

## Review focus
- Wikipedia tables, citations, unusual links and coordinates must be parsed from actual markup
- Las Vegas is 22 November locally, even if a source exposes 23 November UTC
- Hourly coverage must use local timezone day boundaries; daylight-saving days may have 23/25 hours
- Unknown missing values are not filled with zero; incomplete/invalid records trigger a clear error
- Small-sample, geography-confounded correlations and reanalysis limitations must be explicit
