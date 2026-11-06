# SPDX-License-Identifier: Apache-2.0
"""Compile all current editable UFO sources with the pinned open toolchain."""
from pathlib import Path
import argparse,hashlib,json,os,sys,importlib.metadata
from fontTools.ttLib import TTFont
from fontmake.font_project import FontProject
from ufoLib2 import Font
from ufo2ft.filters.decomposeTransformedComponents import DecomposeTransformedComponentsFilter
import ttfautohint
from _common import ROOT,read,rec
from _ufo_features import refresh_anchors


def source_tree(path):
    rows=[rec(p) for p in sorted(path.rglob('*'),key=lambda p:p.relative_to(path).as_posix()) if p.is_file()]
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'path':path.relative_to(ROOT).as_posix(),'files':len(rows),'sha256':digest}


def compile_source(path,target,epoch):
    ufo=Font.open(path);refresh_anchors(ufo)
    # Imported native assembly remains editable in the source. Component
    # normalisation can reorder points, so output instructions are regenerated.
    ufo.lib.pop('public.truetype.instructions',None)
    for glyph in ufo:glyph.lib.pop('public.truetype.instructions',None)
    FontProject().run_from_ufos([ufo],output=['ttf'],output_path=str(target),
        use_production_names=False,remove_overlaps=False,reverse_direction=False,
        feature_writers=[],auto_use_my_metrics=False,flatten_components=True,
        filters=[DecomposeTransformedComponentsFilter()])
    unhinted=TTFont(target,recalcTimestamp=False)
    snapshot={tag:unhinted.getTableData(tag) for tag in ['cmap','hmtx','GSUB','GPOS','GDEF']}
    unhinted.close()
    target.write_bytes(ttfautohint.ttfautohint(in_buffer=target.read_bytes(),no_info=True,epoch=epoch))
    hinted=TTFont(target,recalcTimestamp=False)
    assert all(hinted.getTableData(tag)==data for tag,data in snapshot.items())
    assert all(tag in hinted for tag in ['fpgm','prep','cvt '])
    hinted.close()


def production_environment():
    policy=read(ROOT/'tools/production.json');assert '.'.join(map(str,sys.version_info[:3]))==policy['python']
    versions={}
    for line in (ROOT/'requirements-build.lock').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith((' ','#')) and '==' in line:
            name,version=line.split('==',1);version=version.split()[0]
            actual=importlib.metadata.version(name);assert actual==version,(name,version,actual);versions[name]=actual
    engine=Path(ttfautohint._executable_path());raw=engine.read_bytes()
    version=ttfautohint.run(['--version'],capture_output=True).stdout.decode().splitlines()[0]
    assert version==policy['hinting']['engineVersion'],version
    return {'python':policy['python'],'distributions':versions,'externalHinter':{'name':engine.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'version':version}}


def main(output):
    os.chdir(ROOT);policy=read(ROOT/'release.json');environment=production_environment();os.environ['SOURCE_DATE_EPOCH']=str(policy['sourceDateEpoch'])
    output=output.resolve();output.relative_to(ROOT/'build');assert not output.exists();output.mkdir(parents=True)
    cuts=[];licenses=[]
    for role in ['screen','sign']:
        family=policy['families'][role];prefix=family.replace(' ','')
        license_source=ROOT/'licenses'/('traveller-'+role)/'OFL.txt';license_data=license_source.read_bytes()
        assert b'SIL OPEN FONT LICENSE Version 1.1' in license_data
        folder=output/'fonts'/prefix.lower();folder.mkdir(parents=True,exist_ok=True)
        license_target=folder/'OFL.txt';license_target.write_bytes(license_data);licenses.append({'role':role,'source':rec(license_source),'file':rec(license_target)})
        styles=['Regular','Medium','SemiBold','Bold']+(['Italic','MediumItalic','SemiBoldItalic','BoldItalic'] if role=='screen' else [])
        for style in styles:
            path=ROOT/'sources/ufo'/(prefix+'-'+style+'.ufo');source=Font.open(path,lazy=True)
            assert source.info.familyName==family
            assert (source.info.versionMajor,source.info.versionMinor)==tuple(map(int,policy['fontVersion'].split('.')))
            assert source.info.copyright==license_data.decode('utf-8').splitlines()[0]
            source.close()
            target=folder/(prefix+'-'+style+'.ttf');compile_source(path,target,policy['sourceDateEpoch'])
            font=TTFont(target,recalcTimestamp=False,recalcBBoxes=False)
            assert font['name'].getBestFamilyName()==family and font['name'].getDebugName(5)=='Version '+policy['fontVersion']
            assert all(n.toUnicode()==license_data.decode('utf-8').splitlines()[0] for n in font['name'].names if n.nameID==0)
            font['head'].created=policy['sourceDateEpoch']+2082844800;font['head'].modified=font['head'].created
            font.save(target,reorderTables=False);font.close()
            font=TTFont(target,recalcTimestamp=False,recalcBBoxes=False);font.flavor='woff2';font.save(target.with_suffix('.woff2'),reorderTables=False);font.close()
            cuts.append({'role':role,'style':style,'ufo':source_tree(path),'ttf':rec(target),'woff2':rec(target.with_suffix('.woff2'))})
            print(json.dumps({'compiled':prefix+'-'+style,'ttf':cuts[-1]['ttf']}),flush=True)
    companions=[];provenance=read(ROOT/'companions/source-sans-3/provenance.json')
    for record in provenance['fonts']:
        source=ROOT/record['path'];assert rec(source)['sha256']==record['sha256']
        web=next(x for x in provenance['webFonts'] if Path(x['path']).name==source.name+'.woff2')
        web_source=ROOT/web['path'];assert rec(web_source)['sha256']==web['sha256']
        folder=output/'companions';folder.mkdir(exist_ok=True);target=folder/source.name;target.write_bytes(source.read_bytes());web_target=folder/web_source.name;web_target.write_bytes(web_source.read_bytes())
        companions.append({'ttf':rec(target),'woff2':rec(web_target),'unchangedOfficialResources':True})
    manifest={'spdxLicense':'CC-BY-4.0','version':policy['version'],'fontVersion':policy['fontVersion'],'releasePolicy':rec(ROOT/'release.json'),'environment':environment,
              'production':'Editable UFO contours, components, GLIF anchors and text features compiled with Fontmake/ufo2ft; external ttfautohint regenerates output instructions after component normalisation.',
              'hinting':{'wrapperVersion':importlib.metadata.version('ttfautohint-py'),'engineVersion':ttfautohint.run(['--version'],capture_output=True).stdout.decode().splitlines()[0],'options':{'no_info':True,'epoch':policy['sourceDateEpoch']},'retainedSourceAssembly':'Imported native TrueType instructions remain in the UFO sources and are not carried into the normalised output.'},
              'cuts':cuts,'companions':companions,'familyLicenses':licenses}
    destination=output/'build-manifest.json';destination.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'manifest':rec(destination),'cuts':len(cuts),'companionFiles':8}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'build'/('production-'+read(ROOT/'release.json')['version']))
    main(p.parse_args().output_dir)
