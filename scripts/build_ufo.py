# SPDX-License-Identifier: Apache-2.0
"""Compile all current editable UFO sources with the pinned open toolchain."""
from pathlib import Path
import argparse,hashlib,json,os,sys,importlib.metadata
from fontTools.ttLib import TTFont
from fontTools.otlLib.builder import buildStatTable
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


def static_stat_axes(font,metadata):
    """Retain family axis definitions and only this static face's values."""
    actual={'wght':font['OS/2'].usWeightClass,'ital':int(bool(font['OS/2'].fsSelection & 1))}
    axes=[]
    for definition in metadata['statAxes']:
        axis={key:value for key,value in definition.items() if key!='values'}
        axis['values']=[dict(row) for row in definition['values'] if row['value']==actual[axis['tag']]]
        assert len(axis['values'])==1,(font['name'].getBestFamilyName(),axis)
        axes.append(axis)
    return axes


def finalize_compiled(target,web_target,policy,metadata,family,license_data):
    """Serialize shared static metadata and the equivalent webfont."""
    font=TTFont(target,recalcTimestamp=False,recalcBBoxes=False)
    buildStatTable(font,static_stat_axes(font,metadata),elidedFallbackName='Regular')
    assert font['name'].getBestFamilyName()==family and font['name'].getDebugName(5)=='Version '+policy['fontVersion']
    assert all(n.toUnicode()==license_data.decode('utf-8').splitlines()[0] for n in font['name'].names if n.nameID==0)
    assert font['OS/2'].fsSelection & (1<<8)
    postscript_name=font['name'].getDebugName(6)
    assert 0<len(postscript_name)<=63 and all(33<=ord(c)<=126 and c not in '[](){}<>/%' for c in postscript_name)
    assert font['meta'].data=={'dlng':','.join(metadata['designedScripts']),'slng':','.join(metadata['supportedScripts'])}
    font['head'].created=policy['sourceDateEpoch']+2082844800;font['head'].modified=font['head'].created
    font.save(target,reorderTables=False);font.close()
    font=TTFont(target,recalcTimestamp=False,recalcBBoxes=False);font.flavor='woff2';font.save(web_target,reorderTables=False);font.close()


def main(output,selected_family='all'):
    os.chdir(ROOT);policy=read(ROOT/'release.json');configuration=read(ROOT/'sources/config.json');environment=production_environment();os.environ['SOURCE_DATE_EPOCH']=str(policy['sourceDateEpoch'])
    output=output.resolve();output.relative_to(ROOT/'build');assert not output.exists();output.mkdir(parents=True)
    cuts=[];licenses=[]
    roles=['screen','sign'] if selected_family=='all' else [selected_family]
    for role in roles:
        family=policy['families'][role];prefix=family.replace(' ','')
        license_source=ROOT/'licenses'/('traveller-'+role)/'OFL.txt';license_data=license_source.read_bytes()
        assert b'SIL OPEN FONT LICENSE Version 1.1' in license_data
        folder=output/'fonts'/'ttf'/('traveller'+role);folder.mkdir(parents=True,exist_ok=True)
        web_folder=output/'fonts'/'woff2'/('traveller'+role);web_folder.mkdir(parents=True,exist_ok=True)
        license_target=folder/'OFL.txt';license_target.write_bytes(license_data);licenses.append({'role':role,'source':rec(license_source),'file':rec(license_target)})
        styles=['Regular','Medium','SemiBold','Bold']+(['Italic','MediumItalic','SemiBoldItalic','BoldItalic'] if role=='screen' else [])
        for style in styles:
            path=ROOT/'sources/ufo'/(prefix+'-'+style+'.ufo');source=Font.open(path,lazy=True)
            assert source.info.familyName==family
            assert (source.info.versionMajor,source.info.versionMinor)==tuple(map(int,policy['fontVersion'].split('.')))
            assert source.info.copyright==license_data.decode('utf-8').splitlines()[0]
            metadata=configuration['families'][role]
            assert source.lib['public.openTypeMeta']=={'dlng':metadata['designedScripts'],'slng':metadata['supportedScripts']}
            source.close()
            target=folder/(prefix+'-'+style+'.ttf');compile_source(path,target,policy['sourceDateEpoch'])
            web_target=web_folder/(prefix+'-'+style+'.woff2')
            finalize_compiled(target,web_target,policy,metadata,family,license_data)
            cuts.append({'role':role,'style':style,'ufo':source_tree(path),'ttf':rec(target),'woff2':rec(web_target)})
            print(json.dumps({'compiled':prefix+'-'+style,'ttf':cuts[-1]['ttf']}),flush=True)
    companions=[];provenance=read(ROOT/'companions/source-sans-3/provenance.json')
    for record in provenance['fonts']:
        source=ROOT/record['path'];assert rec(source)['sha256']==record['sha256']
        web=next(x for x in provenance['webFonts'] if Path(x['path']).name==source.name+'.woff2')
        web_source=ROOT/web['path'];assert rec(web_source)['sha256']==web['sha256']
        folder=output/'companions';folder.mkdir(exist_ok=True);target=folder/source.name;target.write_bytes(source.read_bytes());web_target=folder/web_source.name;web_target.write_bytes(web_source.read_bytes())
        companions.append({'ttf':rec(target),'woff2':rec(web_target),'unchangedOfficialResources':True})
    implementation=[rec(ROOT/path) for path in ['scripts/build_ufo.py','scripts/_ufo_features.py','scripts/_ufo_io.py','scripts/_common.py','build.py','sources/build.sh','sources/config.json','tools/production.json','requirements-build.lock']]
    manifest={'spdxLicense':'CC-BY-4.0','version':policy['version'],'fontVersion':policy['fontVersion'],'selectedFamilies':roles,'releasePolicy':rec(ROOT/'release.json'),'environment':environment,'implementationSources':implementation,
              'production':'Editable UFO contours, components, GLIF anchors and text features compiled with Fontmake/ufo2ft; external ttfautohint regenerates output instructions after component normalisation.',
              'hinting':{'wrapperVersion':importlib.metadata.version('ttfautohint-py'),'engineVersion':ttfautohint.run(['--version'],capture_output=True).stdout.decode().splitlines()[0],'options':{'no_info':True,'epoch':policy['sourceDateEpoch']},'retainedSourceAssembly':'Imported native TrueType instructions remain in the UFO sources and are not carried into the normalised output.'},
              'cuts':cuts,'companions':companions,'familyLicenses':licenses}
    destination=output/'build-manifest.json';destination.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'manifest':rec(destination),'cuts':len(cuts),'companionFiles':8}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'build'/('production-'+read(ROOT/'release.json')['version']))
    p.add_argument('--family',choices=['all','sign','screen'],default='all');args=p.parse_args()
    main(args.output_dir,args.family)
