# SPDX-License-Identifier: Apache-2.0
"""Check serialized UFO production against immutable predecessor and source data."""
from io import BytesIO
from pathlib import Path
import argparse,hashlib,json,sys,urllib.request,zipfile
import unicodedata2 as ud
from fontTools.ttLib import TTFont
from fontTools.misc.roundTools import otRound
from fontTools.misc.xmlWriter import XMLWriter
from ufoLib2 import Font
from _common import ROOT,read,rec
from _shaping import shape
from build_ufo import source_tree
from _function_checks import check_functions
from _successor_checks import check_successor


def contours(font,name):
    coordinates,ends,flags=font['glyf'][name].getCoordinates(font['glyf']);rows=[];start=0
    for end in ends:
        ring=[(otRound(x),otRound(y),int(flag)&1) for (x,y),flag in zip(coordinates[start:end+1],flags[start:end+1])];start=end+1
        candidates=[]
        for sequence in [ring,list(reversed(ring))]:
            first=min(sequence)
            candidates.extend(tuple(sequence[i:]+sequence[:i]) for i,p in enumerate(sequence) if p==first)
        rows.append(min(candidates))
    return sorted(rows)


def xml(glyph,font):
    out=BytesIO();glyph.toXML(XMLWriter(out),font);return out.getvalue()


def normalized(font,data,text,language='en',script='Latn',features=None):
    return [(font.getGlyphName(gid),xa,ya,xo,yo) for gid,cluster,xa,ya,xo,yo in shape(data,text,language,script,features)]


def predecessor():
    policy=read(ROOT/'tests/source-predecessor.json');local=ROOT/policy['localArchive']
    if local.is_file():raw=local.read_bytes()
    else:
        with urllib.request.urlopen(policy['url']) as response:raw=response.read()
    assert len(raw)==policy['bytes'] and hashlib.sha256(raw).hexdigest()==policy['sha256']
    return zipfile.ZipFile(BytesIO(raw)),policy


def validate(folder,selected_family='all'):
    manifest=read(folder/'build-manifest.json');spec=read(ROOT/'tests/validation-spec.json');policy=read(ROOT/'release.json')
    successor_path=spec['currentProduction'].get('successorInputs')
    successor=read(ROOT/successor_path) if successor_path else None
    prior,prior_policy=predecessor();checks=[];function_cases=read(ROOT/'tests/font-function-cases.json')
    def check(condition,case,**detail):checks.append({'case':case,'passed':bool(condition),**detail})
    check(manifest['version']==policy['version'] and manifest['fontVersion']==policy['fontVersion'],'manifest-version')
    check(bool(manifest.get('implementationSources')) and all(rec(ROOT/r['path'])==r for r in manifest['implementationSources']),'build-implementation-bindings')
    expected_roles=['screen','sign'] if selected_family=='all' else [selected_family]
    expected_cuts=sum(8 if role=='screen' else 4 for role in expected_roles)
    check(manifest.get('selectedFamilies',['screen','sign'])==expected_roles and len(manifest['cuts'])==expected_cuts and len(manifest['companions'])==4,'resource-counts')
    check(all(sum(c['role']==role for c in manifest['cuts'])==(8 if role=='screen' else 4) for role in expected_roles),'complete-selected-families')
    core_path=ROOT/'tests/data/GF_Latin_Core.nam'
    core={int(line.split()[0],16) for line in core_path.read_text(encoding='utf-8').splitlines() if line and not line.startswith('#')}
    check(len(core)==319,'pinned-latin-core-size')
    for cut in manifest['cuts']:
        role,style=cut['role'],cut['style'];prefix=policy['families'][role].replace(' ','');label=prefix+'-'+style
        path=ROOT/cut['ttf']['path'];data=path.read_bytes();font=TTFont(path,recalcTimestamp=False)
        web_path=ROOT/cut['woff2']['path'];web=TTFont(web_path,recalcTimestamp=False);web.flavor=None
        old_name='OTITraveller'+role.title()+'-'+style+'.ttf';old_data=prior.read('fonts/otitraveller'+role+'/'+old_name);old=TTFont(BytesIO(old_data))
        source=Font.open(ROOT/'sources/ufo'/(label+'.ufo'));cmap=font.getBestCmap();source_cmap={cp:g.name for g in source for cp in g.unicodes}
        check(source_tree(ROOT/'sources/ufo'/(label+'.ufo'))==cut['ufo'],label+'-exact-source-tree-binding')
        check(rec(path)==cut['ttf'] and rec(web_path)==cut['woff2'],label+'-serialized-bindings')
        check(cmap==source_cmap,label+'-source-cmap',encodedScalars=len(cmap))
        current=spec['currentProduction']['resources'][role]
        check(len(cmap)==current['exactEncodedScalarCount'] and set(cmap)-set(old.getBestCmap())==set(current['addedEncodedScalars']),label+'-finite-current-repertoire')
        required=set(spec['resourceRequirements']['screen-primary' if role=='screen' else 'sign-latin']['requiredScalars'])
        check(required.issubset(cmap) and set(old.getBestCmap()).issubset(cmap),label+'-retained-and-required-repertoire')
        check(core.issubset(cmap),label+'-latin-core',missing=sorted(core-set(cmap)))
        check(font['name'].getBestFamilyName()==policy['families'][role] and font['name'].getDebugName(5)=='Version '+policy['fontVersion'],label+'-names-version')
        check(old['name'].getDebugName(0) in font['name'].getDebugName(0),label+'-original-copyright-retained')
        check(font['name'].getDebugName(13)=='This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org' and font['name'].getDebugName(14)=='https://openfontlicense.org',label+'-canonical-license-metadata')
        check(not any('alvaromarinabril@gmail.com' in n.toUnicode().lower() for n in font['name'].names),label+'-private-account-exclusion')
        geometry=[];metrics=[]
        for name in old.getGlyphOrder():
            if font['hmtx'][name]!=old['hmtx'][name]:metrics.append(name)
            if contours(font,name)!=contours(old,name):geometry.append(name)
        check(not metrics,label+'-retained-advances-lsb',differing=metrics)
        check(not geometry,label+'-retained-contours-after-integer-direction-normalisation',differing=geometry)
        check(all(tag in font for tag in ['fpgm','prep','cvt ']),label+'-regenerated-hint-tables')
        check(font.getGlyphOrder()==web.getGlyphOrder() and cmap==web.getBestCmap(),label+'-woff-order-cmap')
        table_diff=[tag for tag in font.keys()[1:] if tag not in ['head','glyf','loca'] and font.getTableData(tag)!=web.getTableData(tag)]
        check(not table_diff,label+'-woff-tables',differing=table_diff)
        glyph_diff=[n for n in font.getGlyphOrder() if xml(font['glyf'][n],font)!=xml(web['glyf'][n],web) or font['hmtx'][n]!=web['hmtx'][n]]
        check(not glyph_diff,label+'-woff-contours-hints-metrics',differing=glyph_diff)
        for locale in spec['localeRequirements']:
            if role=='sign' and locale['signRole']!='sign-latin':continue
            text=' '.join(chr(cp) for cp in locale['requiredScalars'])
            for form in ['NFC','NFD']:
                run=shape(data,ud.normalize(form,text),locale['locale'],locale['script'])
                check(all(r[0]!=0 for r in run),label+'-'+locale['locale']+'-'+form+'-nominal')
        fixtures=[('Bilbao Il1 08:45',{},'en'),('ÁÉîỗ',{},'en'),('į\u0307\u0301',{},'lt'),('ẹ\u0301 ọ\u0300',{},'yo'),('бд',{},'bg'),('0123456789',{'ss20':1},'en'),('Abçé',{'smcp':1},'en'),('ABÇÉ',{'c2sc':1},'en')]
        for i,(text,features,lang) in enumerate(fixtures):
            check(normalized(old,old_data,text,lang,features=features)==normalized(font,data,text,lang,features=features),label+'-retained-layout-'+str(i))
        check_functions(font,data,old,old_data,role,style,function_cases,check,label)
        if successor is not None:
            check_successor(font,data,role,style,successor,check,label)
        if role=='sign':
            text='0123456789';default=normalized(font,data,text);tabular=normalized(font,data,text,features={'tnum':1});proportional=normalized(font,data,text,features={'tnum':1,'pnum':1})
            check([r[1] for r in tabular]==[1412]*10,label+'-tnum-ten-equal-advances')
            check(proportional==default,label+'-pnum-restores-default-run')
            for cp in range(48,58):
                name=cmap[cp];alt=name+'.tf';dx=otRound((1412-old['hmtx'][name][0])/2)
                shifted=contours(font,alt);original=contours(old,name)
                expected=[tuple((x+dx,y,flag) for x,y,flag in ring) for ring in original]
                check(shifted==expected,label+'-tnum-native-contour-'+chr(cp))
        else:
            for glyph in source:
                construction=glyph.lib.get('org.opentransitinformation.construction',{})
                if not glyph.unicodes or construction.get('kind')!='Canonical composition from the pinned prior font shaping':continue
                cp=glyph.unicodes[0];text=chr(cp);nfd=ud.normalize('NFD',text)
                check(normalized(font,data,text)==normalized(font,data,nfd),label+'-canonical-'+f'{cp:04X}')
                for template in ['V{}A','T{}o','{}{}']:
                    a=shape(old_data,template.format(nfd,nfd),'en','Latn',{});b=shape(data,template.format(text,text),'en','Latn',{})
                    check(sum(r[2] for r in a)==sum(r[2] for r in b),label+'-canonical-native-kern-'+f'{cp:04X}'+'-'+template)
        source.close();old.close();font.close();web.close()
    companion_source=read(ROOT/'companions/source-sans-3/provenance.json')
    expected={Path(r['path']).name:r for r in companion_source['fonts']+companion_source['webFonts']}
    for cut in manifest['companions']:
        for key in ['ttf','woff2']:
            row=cut[key];check(row['sha256']==expected[Path(row['path']).name]['sha256'] and rec(ROOT/row['path'])==row,Path(row['path']).name+'-unchanged-official-companion')
    prior.close()
    implementation=[rec(ROOT/path) for path in ['scripts/validate_ufo.py','scripts/_successor_checks.py','scripts/_function_checks.py','scripts/_j_caron_checks.py','scripts/_shaping.py']]
    output={'spdxLicense':'CC-BY-4.0','manifest':rec(folder/'build-manifest.json'),'predecessor':prior_policy,'spec':rec(ROOT/'tests/validation-spec.json'),'implementationSources':implementation,
            'checks':checks,'total':len(checks),'failures':sum(not r['passed'] for r in checks)}
    dest=folder/'validation.json';dest.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'receipt':rec(dest),'total':len(checks),'failures':[r for r in checks if not r['passed']]}))
    return output['failures']==0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--family',choices=['all','sign','screen'],default='all');args=p.parse_args();sys.exit(0 if validate(args.folder.resolve(),args.family) else 1)
