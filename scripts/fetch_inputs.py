# SPDX-License-Identifier: Apache-2.0
"""Fetch only pinned public font inputs into the ignored build cache."""
from pathlib import Path
import hashlib,json,subprocess,sys
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]


def fetch():
    source=json.loads((ROOT/'sources/inputs.json').read_text(encoding='utf-8'))
    for item in source['inputs']:
        path=(ROOT/item['path']).resolve();path.relative_to(ROOT/'build/inputs')
        if not path.exists():
            assert urlparse(item['url']).scheme=='https'
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix(path.suffix+'.download');assert not temporary.exists()
            command=['curl.exe' if sys.platform=='win32' else 'curl','--fail','--location','--silent','--show-error','--output',str(temporary),item['url']]
            subprocess.run(command,check=True)
            raw=temporary.read_bytes();assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
            temporary.replace(path)
        raw=path.read_bytes();assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
        print(item['path']+' '+item['sha256'])


if __name__=='__main__':fetch()
