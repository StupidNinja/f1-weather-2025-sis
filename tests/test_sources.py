from pathlib import Path
import sys, json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pytest
import sources

def test_cache_rejects_tampered_bytes(tmp_path):
    store=sources.SourceStore(tmp_path,offline=True)
    store.save('test.txt',b'original','https://example.org/public',kind='test')
    assert store.read('test.txt')==b'original'
    (tmp_path/'test.txt').write_text('changed')
    with pytest.raises(ValueError,match='hash'):
        store.read('test.txt')

def test_offline_never_silently_fetches_missing_data(tmp_path):
    store=sources.SourceStore(tmp_path,offline=True)
    with pytest.raises(FileNotFoundError,match='offline'):
        store.get('missing.txt','https://example.org/public')

def test_robots_denial_is_respected(tmp_path):
    store=sources.SourceStore(tmp_path,offline=True)
    store.save('wikipedia_robots.txt',b'User-agent: *\nDisallow: /wiki/Forbidden\n','https://en.wikipedia.org/robots.txt',kind='robots')
    assert store.wikipedia_allowed('https://en.wikipedia.org/wiki/Allowed')
    assert not store.wikipedia_allowed('https://en.wikipedia.org/wiki/Forbidden')

def test_cache_rejects_parameter_mismatch(tmp_path):
    store=sources.SourceStore(tmp_path,offline=True)
    store.save('weather.json',b'{}','https://archive-api.open-meteo.com/v1/archive?models=era5',kind='open_meteo_json',parameters={'models':'era5'})
    with pytest.raises(ValueError,match='parameters'):
        store.get('weather.json','https://archive-api.open-meteo.com/v1/archive',params={'models':'era5_land'})
