"""Source parsing, strict validation, and aggregation for the F1 weather project.

The analytic unit is an hourly ERA5 reanalysis grid estimate on a local race date.
No missing weather observations are imputed.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urljoin
import re
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

CALENDAR_URL = 'https://en.wikipedia.org/wiki/2025_Formula_One_World_Championship'
API_URL = 'https://archive-api.open-meteo.com/v1/archive'
VARIABLES = {
    'temperature_2m': 'temperature_c',
    'relative_humidity_2m': 'relative_humidity_pct',
    'precipitation': 'precipitation_mm',
    'wind_speed_10m': 'wind_speed_kmh',
}
UNITS = {'temperature_2m':'°C','relative_humidity_2m':'%','precipitation':'mm','wind_speed_10m':'km/h'}


def _text(tag):
    return re.sub(r'\s+', ' ', tag.get_text(' ', strip=True)).strip()


def parse_calendar(html: str, expected_races: int | None = 24) -> pd.DataFrame:
    """Locate the calendar by its headers; extract names/links and local dates."""
    soup = BeautifulSoup(html, 'html.parser')
    for extra in soup.select('sup, .sortkey'):
        extra.decompose()
    records = []
    for table in soup.select('table'):
        first = table.find('tr')
        if first is None:
            continue
        headers = [_text(c).lower() for c in first.find_all(['th','td'], recursive=False)]
        if not all(any(term in h for h in headers) for term in ('round','grand prix','circuit','date')):
            continue
        indices = {term:next(i for i,h in enumerate(headers) if term in h) for term in ('round','grand prix','circuit','date')}
        for tr in table.find_all('tr')[1:]:
            cells=tr.find_all(['th','td'],recursive=False)
            if len(cells)<=max(indices.values()):
                continue
            number=re.fullmatch(r'\d+', _text(cells[indices['round']]))
            if not number:
                continue
            gp=cells[indices['grand prix']]
            circuit=cells[indices['circuit']]
            links=[a for a in circuit.find_all('a',href=True) if _text(a) and ('/wiki/' in a['href'] or a['href'].startswith('./'))]
            if not links:
                raise ValueError(f'No Wikipedia circuit link for round {number.group()}')
            link=links[0]
            href=link['href']
            if href.startswith('./'):
                href='/wiki/'+href[2:]
            date_text=_text(cells[indices['date']])
            match=re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\b', date_text)
            if not match:
                raise ValueError(f'Unrecognized race date: {date_text}')
            date=datetime.strptime(f'{match.group(1)} {match.group(2)} 2025','%d %B %Y').date()
            records.append({'round':int(number.group()),'race_name':_text(gp),
                            'circuit':_text(link),'race_date':date.isoformat(),
                            'circuit_url':urljoin(CALENDAR_URL,href),
                            'calendar_source_url':CALENDAR_URL})
        break
    df=pd.DataFrame(records)
    if expected_races is not None and len(df)!=expected_races:
        raise ValueError(f'Expected {expected_races} calendar races; found {len(df)}')
    if df.empty:
        raise ValueError('No calendar rows found')
    if df['round'].duplicated().any():
        raise ValueError('Duplicate calendar round')
    if expected_races is not None and set(df['round'])!=set(range(1,expected_races+1)):
        raise ValueError('Calendar rounds are not contiguous')
    vegas=df['race_name'].str.contains('Las Vegas',case=False)
    if vegas.any() and not (df.loc[vegas,'race_date']=='2025-11-22').all():
        raise ValueError('Las Vegas must use the local race date 2025-11-22; investigate source instead of silently changing it')
    return df.sort_values('round').reset_index(drop=True)


def parse_coordinates(html: str) -> tuple[float,float]:
    """Read the article's first geographic coordinate, preferring machine decimals."""
    soup=BeautifulSoup(html,'html.parser')
    for geo in soup.select('.geo'):
        match=re.search(r'([+-]?\d+(?:\.\d+)?)\s*;\s*([+-]?\d+(?:\.\d+)?)',_text(geo))
        if match:
            lat,lon=map(float,match.groups())
            if -90<=lat<=90 and -180<=lon<=180:
                return lat,lon
    lat=soup.select_one('.latitude');lon=soup.select_one('.longitude')
    if lat is not None and lon is not None:
        def dms(s):
            nums=[float(n) for n in re.findall(r'\d+(?:\.\d+)?',s)]
            if not nums:
                raise ValueError('Invalid coordinate')
            result=sum(v/divisor for v,divisor in zip(nums,[1,60,3600]))
            return -result if re.search('[SW]',s,re.I) else result
        a,b=dms(_text(lat)),dms(_text(lon))
        if -90<=a<=90 and -180<=b<=180:
            return a,b
    raise ValueError('Wikipedia circuit coordinate unavailable')


def expected_hours(date: str, timezone: str) -> pd.DatetimeIndex:
    """UTC instants between successive LOCAL midnights (handles DST honestly)."""
    start=pd.Timestamp(date).tz_localize(timezone)
    next_date=pd.Timestamp(date)+pd.Timedelta(days=1)
    stop=next_date.tz_localize(timezone)
    return pd.date_range(start,stop,freq='h',inclusive='left').tz_convert('UTC')


def clean_weather(payload: dict, race: dict) -> pd.DataFrame:
    """Type, validate and merge one raw hourly response with circuit metadata."""
    if payload.get('error'):
        raise ValueError(f'Open-Meteo error: {payload.get("reason")}')
    units=payload.get('hourly_units',{})
    if any(units.get(k)!=u for k,u in UNITS.items()) or units.get('time')!='unixtime':
        raise ValueError(f'Unexpected API units: {units}')
    frame=pd.DataFrame(payload['hourly']).rename(columns=VARIABLES)
    times=pd.to_datetime(frame.pop('time'),unit='s',utc=True,errors='raise')
    if times.duplicated().any():
        raise ValueError('duplicate hourly UTC timestamps')
    zone=payload['timezone']
    expected=expected_hours(race['race_date'],zone)
    if not set(expected).issubset(set(times)):
        raise ValueError(f'Hourly coverage does not match local date {race["race_date"]} in {zone}')
    boundary=expected[-1]+pd.Timedelta(hours=1)
    if boundary not in set(times):
        raise ValueError('Missing next-midnight precipitation boundary')
    frame.index=pd.DatetimeIndex(times)
    precipitation=frame['precipitation_mm'].reindex(expected+pd.Timedelta(hours=1)).to_numpy()
    frame=frame.reindex(expected).reset_index(drop=True)
    frame['precipitation_mm']=precipitation
    times=pd.Series(expected)
    frame['timestamp_utc']=times
    frame['precipitation_interval_end_utc']=times+pd.Timedelta(hours=1)
    frame['precipitation_interval_end_local']=(times+pd.Timedelta(hours=1)).dt.tz_convert(zone).map(lambda x:x.isoformat())
    local=times.dt.tz_convert(zone)
    frame['timestamp_local']=local.map(lambda x:x.isoformat())
    frame['local_date']=local.dt.strftime('%Y-%m-%d')
    frame['hour_local']=local.dt.hour.astype('int64')
    frame['timezone']=zone
    for name in VARIABLES.values():
        frame[name]=pd.to_numeric(frame[name],errors='coerce').astype(float)
    weather=frame[list(VARIABLES.values())]
    if weather.isna().any().any():
        raise ValueError('missing or nonnumeric weather values; no imputation permitted')
    if not np.isfinite(weather.to_numpy()).all():
        raise ValueError('Weather values outside finite range')
    valid=(frame.temperature_c.between(-90,65) & frame.relative_humidity_pct.between(0,100)
           & frame.precipitation_mm.ge(0) & frame.wind_speed_kmh.between(0,500))
    if not valid.all():
        raise ValueError('Weather values outside physical range')
    for key,value in dict(race).items():
        frame[key]=value
    frame['grid_latitude']=float(payload['latitude'])
    frame['grid_longitude']=float(payload['longitude'])
    frame['model']='ERA5'
    return frame.sort_values('timestamp_utc').reset_index(drop=True)


def aggregate_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """One row per race: full-local-day means/ranges and precipitation sums."""
    keys=['round','race_name','circuit','race_date','timezone','latitude','longitude']
    return hourly.groupby(keys,as_index=False,dropna=False).agg(
        hours=('temperature_c','size'),temperature_mean_c=('temperature_c','mean'),
        temperature_min_c=('temperature_c','min'),temperature_max_c=('temperature_c','max'),
        relative_humidity_mean_pct=('relative_humidity_pct','mean'),
        precipitation_total_mm=('precipitation_mm','sum'),
        wet_hours=('precipitation_mm',lambda s:int((s>0).sum())),
        wind_speed_mean_kmh=('wind_speed_kmh','mean'),wind_speed_max_kmh=('wind_speed_kmh','max'),
    ).sort_values('round').reset_index(drop=True)
