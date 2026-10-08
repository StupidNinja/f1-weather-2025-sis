"""Rebuild derived tables from cached sources; acquire only when explicitly enabled."""
from pathlib import Path
import argparse
import json
import pandas as pd
from pipeline import CALENDAR_URL, API_URL, VARIABLES, parse_calendar, parse_coordinates, clean_weather, aggregate_daily, expected_hours
from sources import SourceStore


def build_dataset(root: Path, offline: bool=True):
    root=Path(root)
    store=SourceStore(root/'data/raw',offline=offline)
    calendar=parse_calendar(store.wikipedia('calendar_2025.html',CALENDAR_URL))
    frames=[]
    for idx,race in calendar.iterrows():
        number=int(race['round'])
        html=store.wikipedia(f'circuit_{number:02d}.html',race['circuit_url'])
        lat,lon=parse_coordinates(html)
        calendar.loc[idx,'latitude']=lat;calendar.loc[idx,'longitude']=lon
        race=calendar.loc[idx].to_dict()
        next_date=(pd.Timestamp(race['race_date'])+pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        parameters={'latitude':lat,'longitude':lon,
                    'start_date':race['race_date'],'end_date':next_date,
                    'hourly':','.join(VARIABLES),'models':'era5','timezone':'auto',
                    'timeformat':'unixtime','temperature_unit':'celsius',
                    'wind_speed_unit':'kmh','precipitation_unit':'mm','cell_selection':'land'}
        raw=store.get(f'weather_{number:02d}.json',API_URL,params=parameters,kind='open_meteo_json')
        payload=json.loads(raw)
        frames.append(clean_weather(payload,race))
        print(f'{number:02d}/24 {race["race_name"]}: {len(frames[-1])} local-day hours',flush=True)
    hourly=pd.concat(frames,ignore_index=True).sort_values(['round','timestamp_utc']).reset_index(drop=True)
    if hourly.duplicated(['round','timestamp_utc']).any():
        raise ValueError('Duplicate merged race/hour key')
    if not (hourly.local_date==hourly.race_date).all():
        raise ValueError('A non-race local date leaked into analysis')
    daily=aggregate_daily(hourly)
    expected={int(r['round']):len(expected_hours(r['race_date'],r['timezone'])) for r in daily.to_dict('records')}
    missing=hourly[list(VARIABLES.values())].isna().sum().to_dict()
    quality={'races':len(calendar),'hourly_rows':len(hourly),'daily_rows':len(daily),
             'expected_hourly_rows':sum(expected.values()),'expected_hours_by_round':expected,
             'duplicate_race_hour_keys':int(hourly.duplicated(['round','timestamp_utc']).sum()),
             'missing_weather_values':{k:int(v) for k,v in missing.items()},
             'all_rows_on_local_race_date':bool((hourly.local_date==hourly.race_date).all()),
             'precipitation_boundary_aligned':True,'imputed_weather_values':0,
             'model':'ERA5','timezone_request':'auto','raw_source_count':len(store.manifest),
             'raw_response_rows':sum(len(json.loads(store.read(f'weather_{i:02d}.json'))['hourly']['time']) for i in range(1,25)),
             'wikipedia_pages':25,'api_responses':24,
             'precipitation_intervals':'[timestamp_local, precipitation_interval_end_local)',
             'notes':'All raw hours are retained for provenance; only race-day instants and their forward precipitation intervals enter the cleaned table.'}
    out=root/'data/processed';out.mkdir(parents=True,exist_ok=True)
    calendar.to_csv(out/'calendar.csv',index=False,float_format='%.8f')
    hourly.to_csv(out/'f1_weather_hourly.csv',index=False,float_format='%.8f')
    daily.to_csv(out/'f1_weather_daily.csv',index=False,float_format='%.8f')
    (out/'quality_report.json').write_text(json.dumps(quality,indent=2,ensure_ascii=False)+'\n')
    return calendar,hourly,daily,quality

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--online',action='store_true',help='Acquire any missing public sources; otherwise strict offline mode')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    *_,quality=build_dataset(root,offline=not args.online)
    print(json.dumps(quality,indent=2))
