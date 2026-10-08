"""Integration checks against the preserved, genuinely acquired project snapshot."""
from pathlib import Path
import json
import sys
import pandas as pd
import nbformat
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sources import SourceStore
from pipeline import parse_calendar,parse_coordinates,clean_weather

ROOT=Path(__file__).resolve().parents[1]

def test_every_raw_file_hash_and_metadata_matches():
    store=SourceStore(ROOT/'data/raw',offline=True)
    assert len(store.manifest)==50
    for filename,meta in store.manifest.items():
        assert len(store.read(filename))==meta['bytes']
        assert meta['retrieved_at_utc'].startswith('2026-10-07')

def test_real_calendar_and_source_weather_reproduce_clean_rows():
    store=SourceStore(ROOT/'data/raw',offline=True)
    cal=parse_calendar(store.read('calendar_2025.html').decode())
    actual=pd.read_csv(ROOT/'data/processed/f1_weather_hourly.csv')
    columns=['temperature_c','relative_humidity_pct','precipitation_mm','wind_speed_kmh']
    for race in cal.to_dict('records'):
        n=race['round']
        race['latitude'],race['longitude']=parse_coordinates(store.read(f'circuit_{n:02d}.html').decode())
        rebuilt=clean_weather(json.loads(store.read(f'weather_{n:02d}.json')),race)
        saved=actual[actual['round']==n].reset_index(drop=True)
        assert len(rebuilt)==len(saved)==24
        pd.testing.assert_frame_equal(rebuilt[columns],saved[columns],check_exact=False,atol=1e-8,rtol=0)
    assert len(actual)==576
    assert actual[['round','timestamp_utc']].duplicated().sum()==0

def test_executed_notebook_contains_real_figures_and_summary():
    notebook=nbformat.read(ROOT/'f1_weather_2025.ipynb',as_version=4)
    nbformat.validate(notebook)
    code=[c for c in notebook.cells if c.cell_type=='code']
    assert len(code)==10
    assert [c.execution_count for c in code]==list(range(1,11))
    outputs=[o for c in code for o in c.outputs]
    assert not any(o.output_type=='error' for o in outputs)
    assert sum('image/png'in o.get('data',{}) for o in outputs)==5
    rendered=[o['data']['text/markdown'] for o in outputs if 'text/markdown'in o.get('data',{})]
    assert len(rendered)==1
    assert 'Saudi Arabian Grand Prix' in rendered[0]
    assert '24.2 mm' in rendered[0]
