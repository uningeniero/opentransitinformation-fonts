# SPDX-License-Identifier: Apache-2.0
"""Compare a fresh build with the exact published font file digests."""
from pathlib import Path
import argparse,hashlib,json,sys
from _common import ROOT,read

def main(folder):
    expected=read(ROOT/'fonts/checksums.json')['files']
    manifest=read(folder/'build-manifest.json')
    built={Path(c[k]['path']).name:c[k] for c in manifest['cuts']+manifest['companions'] for k in ['ttf','woff2']}
    failures=[]
    for row in expected:
        name=Path(row['path']).name;actual=built.get(name)
        if actual is None or row['bytes']!=actual['bytes'] or row['sha256']!=actual['sha256']:failures.append(name)
        elif hashlib.sha256((ROOT/actual['path']).read_bytes()).hexdigest()!=row['sha256']:failures.append(name)
    assert set(built)=={Path(r['path']).name for r in expected}
    print(json.dumps({'fontFiles':len(expected),'byteIdentical':not failures,'mismatches':failures}))
    return not failures

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);args=p.parse_args();sys.exit(0 if main(args.folder.resolve()) else 1)
