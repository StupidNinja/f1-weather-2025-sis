"""Gentle HTTP acquisition and SHA-256-verified raw provenance cache."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
import requests

USER_AGENT='F1WeatherStudentProject/1.0 (educational research; requests)'

class SourceStore:
    def __init__(self, root: Path, offline: bool=True):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.offline=offline
        self.manifest_path=self.root/'manifest.json'
        self.manifest=json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}
        self.session=requests.Session();self.session.headers.update({'User-Agent':USER_AGENT})
        self.last_request=0.0

    def save(self, name, content, url, kind='source', parameters=None, **metadata):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        self.manifest[name]={'url':url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                             'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),
                             'kind':kind,'parameters':parameters or {},**metadata}
        self.manifest_path.write_text(json.dumps(self.manifest,indent=2,ensure_ascii=False)+'\n')
        return content

    def read(self,name):
        content=(self.root/name).read_bytes()
        if name not in self.manifest or hashlib.sha256(content).hexdigest()!=self.manifest[name]['sha256']:
            raise ValueError(f'Raw source hash mismatch or missing provenance: {name}')
        return content

    def get(self,name,url,params=None,kind='source'):
        if (self.root/name).exists():
            if params is not None and self.manifest.get(name,{}).get('parameters') != params:
                raise ValueError(f'Cached request parameters differ from this run: {name}')
            return self.read(name)
        if self.offline:
            raise FileNotFoundError(f'{name} missing in offline cache. Acquire sources explicitly first.')
        wait=max(0,1.2-(time.monotonic()-self.last_request))
        time.sleep(wait)
        response=self.session.get(url,params=params,timeout=90)
        self.last_request=time.monotonic()
        response.raise_for_status() # no retries around access denial or rate limiting
        return self.save(name,response.content,response.url,kind=kind,parameters=params,
                         status_code=response.status_code,last_modified=response.headers.get('Last-Modified'))

    def wikipedia_allowed(self,url):
        if urlparse(url).netloc!='en.wikipedia.org':
            raise ValueError('Only approved English Wikipedia source links are supported')
        body=self.get('wikipedia_robots.txt','https://en.wikipedia.org/robots.txt',kind='robots')
        parser=RobotFileParser();parser.parse(body.decode('utf-8-sig').splitlines())
        return parser.can_fetch(USER_AGENT,url)

    def wikipedia(self,name,url):
        if not self.wikipedia_allowed(url):
            raise PermissionError(f'robots.txt disallows Wikipedia source: {url}')
        return self.get(name,url,kind='wikipedia_html').decode('utf-8')
