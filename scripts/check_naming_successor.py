# SPDX-License-Identifier: Apache-2.0
"""Compare the naming-only successor with the immutable published predecessor."""
from io import BytesIO
from pathlib import Path
import argparse, hashlib, json, urllib.request, zipfile
from fontTools.ttLib import TTFont
from _common import ROOT, read, rec


def main(folder, previous_archive=None):
    folder=folder.resolve();folder.relative_to(ROOT/'build')
    policy=read(ROOT/'release.json');prior=read(ROOT/'tests/naming-predecessor.json')
    if previous_archive is None:
        previous_archive=ROOT/'build/inputs/naming-predecessor-1.0.0.zip'
        if not previous_archive.exists():
            with urllib.request.urlopen(prior['url'],timeout=60) as response:data=response.read()
            assert len(data)==prior['bytes'] and hashlib.sha256(data).hexdigest()==prior['sha256']
            previous_archive.parent.mkdir(parents=True,exist_ok=True);previous_archive.write_bytes(data)
    data=previous_archive.read_bytes()
    assert len(data)==prior['bytes'] and hashlib.sha256(data).hexdigest()==prior['sha256']
    manifest=read(folder/'build-manifest.json');results=[];ps_names=set();companions=[]
    changed_names={1,3,4,5,6,16,17,18}
    with zipfile.ZipFile(BytesIO(data)) as previous:
        font_paths={Path(n).name:n for n in previous.namelist() if n.endswith(('.ttf','.woff2'))}
        assert len(font_paths)==32
        for cut in manifest['cuts']:
            role,style=cut['role'],cut['style'];family=policy['families'][role]
            italic=style.endswith('Italic');weight=style.removesuffix('Italic') or 'Regular'
            legacy=family if weight in ['Regular','Bold'] else family+' '+weight
            typo='Italic' if weight=='Regular' and italic else weight+(' Italic' if italic else '')
            subfamily=('Bold Italic' if italic else 'Bold') if weight=='Bold' else ('Italic' if italic else 'Regular')
            ps=family.replace(' ','')+'-'+style
            assert ps not in ps_names and ps.isascii() and ' ' not in ps and len(ps)<=63 and len(legacy)<32
            ps_names.add(ps)
            expected={1:legacy,2:subfamily,3:policy['fontVersion']+';OTI;'+ps,4:family+' '+typo,
                      5:'Version '+policy['fontVersion'],6:ps,18:family+' '+typo}
            if weight not in ['Regular','Bold']:expected.update({16:family,17:typo})
            for kind in ['ttf','woff2']:
                path=ROOT/cut[kind]['path'];new_bytes=path.read_bytes()
                previous_name=prior['families'][role].replace(' ','')+'-'+style+'.'+kind
                old=TTFont(BytesIO(previous.read(font_paths[previous_name])),recalcTimestamp=False)
                new=TTFont(BytesIO(new_bytes),recalcTimestamp=False)
                assert set(old.keys())==set(new.keys()),(path.name,'table-set')
                stable=set(old.keys())-{'GlyphOrder','name','head'}
                assert all(old.getTableData(t)==new.getTableData(t) for t in stable),(path.name,'stable-tables')
                assert old.getGlyphOrder()==new.getGlyphOrder() and old.getBestCmap()==new.getBestCmap()
                head_keys=set(vars(old['head']))|set(vars(new['head']))
                assert all(getattr(old['head'],k)==getattr(new['head'],k) for k in head_keys-{'fontRevision','modified','checkSumAdjustment'}),(path.name,'stable-head')
                assert new['head'].fontRevision==round(float(policy['fontVersion'])*65536)/65536
                assert new['head'].modified==policy['sourceDateEpoch']+2082844800
                def retained_names(font):
                    return sorted((n.nameID,n.platformID,n.platEncID,n.langID,n.toUnicode()) for n in font['name'].names if n.nameID not in changed_names)
                assert retained_names(old)==retained_names(new),(path.name,'retained-notices-and-names')
                for number,value in expected.items():
                    records=[n for n in new['name'].names if n.nameID==number]
                    assert records and all(n.toUnicode()==value for n in records),(path.name,'name',number)
                assert not any(n.nameID in {19,21,22,25} for n in new['name'].names)
                if weight in ['Regular','Bold']:assert not any(n.nameID in {16,17} for n in new['name'].names)
                assert new['name'].getBestFamilyName()==family
                results.append({'font':rec(path),'previousFile':font_paths[previous_name],
                                'unchangedTables':sorted(stable),'family':family,'postScriptName':ps,
                                'namesVersionStyleAndSemanticEquality':True})
                old.close();new.close()
        for cut in manifest['companions']:
            for kind in ['ttf','woff2']:
                path=ROOT/cut[kind]['path'];raw=path.read_bytes()
                assert raw==previous.read(font_paths[path.name]),path.name
                companions.append(rec(path))
    assert len(results)==24 and len(ps_names)==12 and len(companions)==8
    result={'spdxLicense':'CC-BY-4.0','version':policy['version'],'fontVersion':policy['fontVersion'],
            'predecessor':prior,'manifest':rec(folder/'build-manifest.json'),'ownFontFiles':24,
            'cuts':12,'unchangedCompanionFiles':8,'results':results,'companions':companions,
            'allNamesStyleVersionsAndSemanticComparisonsPassed':True}
    output=folder/'naming-successor.json';output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'receipt':rec(output),'ownFontFiles':24,'cuts':12,'unchangedCompanionFiles':8,'passed':True}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--previous-archive',type=Path)
    args=p.parse_args();main(args.folder,args.previous_archive)
