import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pytest
import pandas as pd
import pipeline

CALENDAR = '''<table class="wikitable"><tr><th>Round</th><th>Grand Prix</th><th>Circuit</th><th>Race date</th></tr><tr><th>1</th><td><a href="/wiki/2025_Australian_Grand_Prix">Australian Grand Prix</a></td><td><a href="/wiki/Albert_Park_Circuit">Albert Park Circuit</a>, Melbourne</td><td>16 March<sup>[1]</sup></td></tr><tr><th>22</th><td><a href="/wiki/2025_Las_Vegas_Grand_Prix">Las Vegas Grand Prix</a></td><td><a href="./Las_Vegas_Strip_Circuit">Las Vegas Strip Circuit</a></td><td>22 November</td></tr></table>'''

def test_calendar_extracts_local_dates_and_circuit_links():
    result = pipeline.parse_calendar(CALENDAR, expected_races=None)
    assert result['race_date'].tolist() == ['2025-03-16', '2025-11-22']
    assert result.iloc[1]['circuit_url'] == 'https://en.wikipedia.org/wiki/Las_Vegas_Strip_Circuit'
    assert result.iloc[0]['race_name'] == 'Australian Grand Prix'

def test_calendar_rejects_incomplete_season():
    with pytest.raises(ValueError, match='24'):
        pipeline.parse_calendar(CALENDAR)

def test_coordinates_decimal_and_signed_dms():
    assert pipeline.parse_coordinates('<span class="geo">-37.8497; 144.968</span>') == (-37.8497,144.968)
    assert pipeline.parse_coordinates('<span class="latitude">37°50′58.9″S</span><span class="longitude">144°58′4.8″E</span>') == pytest.approx((-37.8496944444,144.968))

def test_coordinates_fail_loudly_when_unavailable():
    with pytest.raises(ValueError,match='coordinate'):
        pipeline.parse_coordinates('<p>No coordinates</p>')

def test_dst_hours_and_vegas_local_day():
    assert len(pipeline.expected_hours('2025-11-02','America/New_York')) == 25
    assert len(pipeline.expected_hours('2025-03-09','America/New_York')) == 23
    vegas=pipeline.expected_hours('2025-11-22','America/Los_Angeles')
    assert len(vegas)==24
    assert str(vegas[0])=='2025-11-22 08:00:00+00:00'

def payload():
    ts=pipeline.expected_hours('2025-11-22','America/Los_Angeles')
    ts=ts.append(pd.DatetimeIndex([ts[-1]+pd.Timedelta(hours=1)]))
    return {'timezone':'America/Los_Angeles','latitude':36.1,'longitude':-115.2,
            'hourly_units':{'time':'unixtime','temperature_2m':'°C','relative_humidity_2m':'%','precipitation':'mm','wind_speed_10m':'km/h'},
            'hourly':{'time':[int(t.timestamp()) for t in ts], 'temperature_2m':[10.0]*25, 'relative_humidity_2m':[50]*25,'precipitation':[0.0]*25,'wind_speed_10m':[4.0]*25}}

def row():
    return {'round':22,'race_name':'Las Vegas Grand Prix','circuit':'Las Vegas Strip Circuit','race_date':'2025-11-22','latitude':36.1,'longitude':-115.2,'circuit_url':'https://en.wikipedia.org/wiki/Las_Vegas_Strip_Circuit'}

def test_weather_uses_local_dates_and_valid_units():
    df=pipeline.clean_weather(payload(),row())
    assert len(df)==24
    assert df['local_date'].unique().tolist()==['2025-11-22']
    assert df['hour_local'].tolist()==list(range(24))
    assert df['precipitation_mm'].sum()==0

def test_weather_rejects_missing_and_negative_values():
    p=payload(); p['hourly']['temperature_2m'][0]=None
    with pytest.raises(ValueError,match='missing'):
        pipeline.clean_weather(p,row())
    p=payload();p['hourly']['precipitation'][1]=-1
    with pytest.raises(ValueError,match='range'):
        pipeline.clean_weather(p,row())

def test_weather_rejects_duplicate_or_wrong_date():
    p=payload();p['hourly']['time'][1]=p['hourly']['time'][0]
    with pytest.raises(ValueError,match='duplicate'):
        pipeline.clean_weather(p,row())
    p=payload();p['hourly']['time'][0]+=172800
    with pytest.raises(ValueError,match='coverage'):
        pipeline.clean_weather(p,row())

def test_daily_aggregation_precip_sum_and_other_means():
    p=payload();p['hourly']['precipitation'][1]=2.0
    df=pipeline.clean_weather(p,row())
    daily=pipeline.aggregate_daily(df)
    assert len(daily)==1
    assert daily.iloc[0]['precipitation_total_mm']==2.0
    assert daily.iloc[0]['wet_hours']==1
    assert daily.iloc[0]['temperature_mean_c']==10.0


def test_precipitation_aligns_to_interval_start_without_shifting_instant_values():
    p=payload()
    p['hourly']['precipitation'][0]=99.0 # belongs to previous day
    p['hourly']['precipitation'][1]=2.0 # interval starting race-day midnight
    p['hourly']['precipitation'][-1]=3.0 # last race-day interval
    p['hourly']['temperature_2m'][0]=7.0
    df=pipeline.clean_weather(p,row())
    assert df.iloc[0]['temperature_c']==7.0
    assert df.iloc[0]['precipitation_mm']==2.0
    assert df.iloc[-1]['precipitation_mm']==3.0
    assert df['precipitation_mm'].sum()==5.0
    assert df.iloc[-1]['precipitation_interval_end_local'].startswith('2025-11-23T00:00')

def test_missing_precipitation_boundary_rejected():
    p=payload()
    p['hourly']={k:v[:-1] for k,v in p['hourly'].items()}
    with pytest.raises(ValueError,match='boundary'):
        pipeline.clean_weather(p,row())

def test_calendar_ignores_country_flag_links_before_circuit():
    html=CALENDAR.replace('<a href="/wiki/Albert_Park_Circuit">','<a href="/wiki/Australia"><img alt="Australia"/></a> <a href="/wiki/Albert_Park_Circuit">')
    result=pipeline.parse_calendar(html,expected_races=None)
    assert result.iloc[0]['circuit']=='Albert Park Circuit'
    assert result.iloc[0]['circuit_url'].endswith('/Albert_Park_Circuit')
