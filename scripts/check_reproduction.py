# SPDX-License-Identifier: Apache-2.0
"""Compare a fresh build with the exact published font file digests."""
from pathlib import Path
import argparse,hashlib,json,sys
from _common import ROOT,read,rec

def main(folder,comparison_folder=None):
    if comparison_folder is not None:
        original=read(folder/'build-manifest.json');fresh=read(comparison_folder/'build-manifest.json')
        assert original['version']==fresh['version'] and original['fontVersion']==fresh['fontVersion']
        assert original.get('selectedFamilies',['screen','sign'])==fresh.get('selectedFamilies',['screen','sign'])
        assert [(c['role'],c['style'],c['ufo']) for c in original['cuts']]==[(c['role'],c['style'],c['ufo']) for c in fresh['cuts']]
        assert original['implementationSources']==fresh['implementationSources'] and original['releasePolicy']==fresh['releasePolicy']
        left={Path(c[k]['path']).name:c[k] for c in original['cuts']+original['companions'] for k in ['ttf','woff2']}
        right={Path(c[k]['path']).name:c[k] for c in fresh['cuts']+fresh['companions'] for k in ['ttf','woff2']}
        assert set(left)==set(right)
        failures=[]
        for name,pin in left.items():
            other=right[name]
            assert rec(ROOT/pin['path'])==pin and rec(ROOT/other['path'])==other
            if (pin['bytes'],pin['sha256'])!=(other['bytes'],other['sha256']):failures.append(name)
        result={'spdxLicense':'CC-BY-4.0','firstBuild':rec(folder/'build-manifest.json'),'freshBuild':rec(comparison_folder/'build-manifest.json'),'fontFiles':len(left),'byteIdentical':not failures,'mismatches':failures,'method':'Independent current-source builds with fixed dependency lock, epoch and PYTHONHASHSEED0; complete TTF/WOFF2 bytes and exact source/implementation bindings compared.'}
        output=folder/'reproduction.json';assert not output.exists();output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result));return not failures
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
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--comparison-folder',type=Path);args=p.parse_args();sys.exit(0 if main(args.folder.resolve(),args.comparison_folder.resolve() if args.comparison_folder else None) else 1)
