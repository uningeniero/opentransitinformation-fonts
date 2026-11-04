# SPDX-License-Identifier: Apache-2.0
"""Build the two source-specific families without changing retained drawings."""
from pathlib import Path
from io import BytesIO
import argparse,copy,hashlib,json,math,os,unicodedata
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.pens.recordingPen import replayRecording
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.misc.roundTools import otRound
from fontTools.misc.xmlWriter import XMLWriter
from fontTools.otlLib.builder import buildAnchor,buildLookup,buildLigatureSubstSubtable,buildMarkBasePosSubtable,buildCoverage
from fontTools.otlLib.maxContextCalc import maxCtxFont
from _common import ROOT,rec,read,stored_bound
from _sign_baseline import append_feature_lookup
from _geometry import placed


def xml(value,font):
    out=BytesIO();value.toXML(XMLWriter(out),font)
    return out.getvalue()


def map_names(value,mapping,visited=None):
    """Map exact glyph identifiers throughout decompiled OpenType objects."""
    if isinstance(value,str):return mapping.get(value,value)
    if value is None or isinstance(value,(int,float,bool,bytes)):return value
    if visited is None:visited=set()
    if id(value) in visited:return value
    visited.add(id(value))
    if isinstance(value,list):
        for i,item in enumerate(value):value[i]=map_names(item,mapping,visited)
    elif isinstance(value,tuple):return tuple(map_names(x,mapping,visited) for x in value)
    elif isinstance(value,dict):
        items=[(map_names(k,mapping,visited),map_names(v,mapping,visited)) for k,v in value.items()]
        value.clear();value.update(items)
    elif hasattr(value,'__dict__'):
        for key,item in list(vars(value).items()):setattr(value,key,map_names(item,mapping,visited))
    else:raise TypeError(type(value))
    return value


def source_art_policy(font,role):
    if role!='screen':return {'removed':[],'aliases':{}}
    policy=read(ROOT/'sources/screen/public-artwork-exclusions.json')
    excluded=policy['glyph'];mapping=policy['sourceGlyphAliases']
    order=font.getGlyphOrder()
    assert excluded in order and not any(excluded in t.cmap.values() for t in font['cmap'].tables if hasattr(t,'cmap'))
    assert set(mapping).issubset(order) and not set(mapping.values())&set(order)
    # Expand composites and layout before changing the GID order.
    for name in order:
        g=font['glyf'][name]
        if g.isComposite():assert excluded not in [c.glyphName for c in g.components]
    for tag in ['GSUB','GPOS','GDEF']:
        table=font[tag].table
        if tag=='GDEF' and excluded in table.GlyphClassDef.classDefs:
            assert table.GlyphClassDef.classDefs[excluded]==0
            del table.GlyphClassDef.classDefs[excluded]
        assert ('"'+excluded+'"').encode() not in xml(font[tag],font)
        map_names(table,mapping)
    glyf=font['glyf']
    for name in order:
        g=glyf[name]
        if g.isComposite():
            for component in g.components:component.glyphName=mapping.get(component.glyphName,component.glyphName)
    glyf.glyphs={mapping.get(n,n):g for n,g in glyf.glyphs.items() if n!=excluded}
    font['hmtx'].metrics={mapping.get(n,n):v for n,v in font['hmtx'].metrics.items() if n!=excluded}
    for table in font['cmap'].tables:
        if hasattr(table,'cmap'):table.cmap={cp:mapping.get(n,n) for cp,n in table.cmap.items()}
    post=font['post']
    if hasattr(post,'extraNames'):post.extraNames=[mapping.get(n,n) for n in post.extraNames if n!=excluded]
    if hasattr(post,'mapping'):post.mapping={mapping.get(k,k):mapping.get(v,v) for k,v in post.mapping.items() if k!=excluded}
    font.setGlyphOrder([mapping.get(n,n) for n in order if n!=excluded])
    return {'removed':[excluded],'aliases':mapping}


def add_language_records(font,rows):
    order=font.getGlyphOrder();cmap=font.getBestCmap();added=[]
    names=[r['glyph'] for r in rows]
    assert not set(order)&set(names) and len(names)==len(set(names))
    font.setGlyphOrder(order+names)
    for row in rows:
        assert row['unicode'] not in cmap
        digest=hashlib.sha256(json.dumps(row['recording'],separators=(',',':')).encode()).hexdigest()
        assert digest==row['sourceDecision']['recordingSha256']
        assert all(op in ['moveTo','lineTo','qCurveTo','closePath','endPath'] for op,_ in row['recording'])
        pen=TTGlyphPen(None);replayRecording(row['recording'],pen);glyph=pen.glyph()
        if glyph.numberOfContours:
            glyph.coordinates.toInt(round=otRound);glyph.recalcBounds(None)
        assert not hasattr(glyph,'program') or not glyph.program.getBytecode()
        name=row['glyph'];font['glyf'][name]=glyph
        font['hmtx'][name]=(otRound(row['advance']),glyph.xMin if glyph.numberOfContours else 0)
        for table in font['cmap'].tables:
            if table.isUnicode() and table.format in [4,12,13]:table.cmap[row['unicode']]=name
        if not unicodedata.category(chr(row['unicode'])).startswith(('Z','C')):
            font['GDEF'].table.GlyphClassDef.classDefs[name]=3 if unicodedata.category(chr(row['unicode'])).startswith('M') else 1
        added.append({'unicode':row['unicode'],'glyph':name,'recordingSHA256':digest,'bounds':stored_bound(font,name),'advance':font['hmtx'][name][0]})
    routes={tuple(r['sourceDecision']['nfdCompositionRoute']):r['glyph'] for r in rows if 'nfdCompositionRoute' in r['sourceDecision']}
    if routes:append_feature_lookup(font,'GSUB','ccmp',buildLookup([buildLigatureSubstSubtable(routes)],table='GSUB'))
    return added


def append_lth_context(font,cut):
    table=font['GSUB'].table;gm=font.getReverseGlyphMap()
    helper=buildLookup([buildLigatureSubstSubtable({('iogonek','uni0307.case'):'iogonek'})],table='GSUB')
    helper_index=len(table.LookupList.Lookup);table.LookupList.Lookup.append(helper)
    sub=otTables.ChainContextSubst();sub.Format=3
    sub.BacktrackGlyphCount=0;sub.BacktrackCoverage=[]
    sub.InputGlyphCount=2;sub.InputCoverage=[buildCoverage([n],gm) for n in ['iogonek','uni0307.case']]
    sub.LookAheadGlyphCount=1;sub.LookAheadCoverage=[buildCoverage(['acutecomb.case'],gm)]
    r=otTables.SubstLookupRecord();r.SequenceIndex=0;r.LookupListIndex=helper_index
    sub.SubstCount=1;sub.SubstLookupRecord=[r]
    context_index=len(table.LookupList.Lookup);table.LookupList.Lookup.append(buildLookup([sub],table='GSUB'))
    table.LookupList.LookupCount=len(table.LookupList.Lookup)
    latn=next(s.Script for s in table.ScriptList.ScriptRecord if s.ScriptTag=='latn')
    assert not any(l.LangSysTag=='LTH ' for l in latn.LangSysRecord)
    inherited=copy.deepcopy(latn.DefaultLangSys)
    old_ccmp=next(i for i in inherited.FeatureIndex if table.FeatureList.FeatureRecord[i].FeatureTag=='ccmp')
    feature=copy.deepcopy(table.FeatureList.FeatureRecord[old_ccmp])
    feature.Feature.LookupListIndex.append(context_index);feature.Feature.LookupCount=len(feature.Feature.LookupListIndex)
    insert=max(i for i,f in enumerate(table.FeatureList.FeatureRecord) if f.FeatureTag=='ccmp')+1
    for script in table.ScriptList.ScriptRecord:
        for lang in ([script.Script.DefaultLangSys] if script.Script.DefaultLangSys else [])+[l.LangSys for l in script.Script.LangSysRecord]:
            lang.FeatureIndex=[i+1 if i>=insert else i for i in lang.FeatureIndex]
            if lang.ReqFeatureIndex!=0xFFFF and lang.ReqFeatureIndex>=insert:lang.ReqFeatureIndex+=1
    inherited.FeatureIndex=[insert if i==old_ccmp else i+1 if i>=insert else i for i in inherited.FeatureIndex]
    inherited.FeatureIndex.sort();inherited.FeatureCount=len(inherited.FeatureIndex)
    if inherited.ReqFeatureIndex!=0xFFFF and inherited.ReqFeatureIndex>=insert:inherited.ReqFeatureIndex+=1
    table.FeatureList.FeatureRecord.insert(insert,feature);table.FeatureList.FeatureCount=len(table.FeatureList.FeatureRecord)
    record=otTables.LangSysRecord();record.LangSysTag='LTH ';record.LangSys=inherited
    latn.LangSysRecord.append(record);latn.LangSysRecord.sort(key=lambda r:r.LangSysTag);latn.LangSysCount=len(latn.LangSysRecord)
    marks={r['glyph']:(0,buildAnchor(*r['anchor'])) for r in cut['markCoverage']}
    bases={r['glyph']:{0:buildAnchor(*r['anchor'])} for r in cut['baseCoverage']}
    mark_index=append_feature_lookup(font,'GPOS','mark',buildLookup([buildMarkBasePosSubtable(marks,bases,gm)],table='GPOS'))
    return {'GSUBhelper':helper_index,'GSUBcontext':context_index,'GPOSmark':mark_index,'language':'LTH '}


def inherit_native_kerning(font,style):
    policy=read(ROOT/'sources/language/native-composite-kerning-roles.json')
    rows=[r for r in policy['roles'] if r['style']==style];assert len(rows)==18
    gm=font.getReverseGlyphMap();aliases={}
    for r in rows:aliases.setdefault(r['sourceBaseGlyph'],[]).append(r['newGlyph'])
    counts=[];table=font['GPOS'].table
    declared=sorted({(m['lookupIndex'],m['subtableIndex']) for r in rows for m in r['kernMembership']})
    for lookup_index,sub_index in declared:
        lookup=table.LookupList.Lookup[lookup_index];sub=lookup.SubTable[sub_index]
        if lookup.LookupType==9:
            assert sub.ExtensionLookupType==2;sub=sub.ExtSubTable
        else:assert lookup.LookupType==2
        old_coverage=list(sub.Coverage.glyphs);before_count=len(old_coverage)
        coverage=old_coverage+[name for base,names in aliases.items() if base in old_coverage for name in names]
        if sub.Format==1:
            old_sets={n:copy.deepcopy(s) for n,s in zip(old_coverage,sub.PairSet)};new_sets={}
            for old_first,pairs in old_sets.items():
                for first in [old_first]+aliases.get(old_first,[]):
                    records=[]
                    for pair in pairs.PairValueRecord:
                        records.append(copy.deepcopy(pair))
                        for name in aliases.get(pair.SecondGlyph,[]):
                            clone=copy.deepcopy(pair);clone.SecondGlyph=name;records.append(clone)
                    records.sort(key=lambda r:gm[r.SecondGlyph]);assert len(records)==len({r.SecondGlyph for r in records})
                    new=copy.deepcopy(pairs);new.PairValueRecord=records;new.PairValueCount=len(records);new_sets[first]=new
            sub.Coverage=buildCoverage(coverage,gm);sub.PairSet=[new_sets[n] for n in sub.Coverage.glyphs];sub.PairSetCount=len(sub.PairSet)
        else:
            assert sub.Format==2
            for classdef in [sub.ClassDef1.classDefs,sub.ClassDef2.classDefs]:
                old=dict(classdef)
                for base,names in aliases.items():
                    if base in old:
                        for name in names:assert name not in classdef;classdef[name]=old[base]
                assert all(classdef[k]==v for k,v in old.items())
            sub.Coverage=buildCoverage(coverage,gm)
        counts.append({'lookup':lookup_index,'subtable':sub_index,'format':sub.Format,'oldFirstCoverageCount':before_count,'newFirstCoverageCount':len(sub.Coverage.glyphs)})
    return {'policy':rec(ROOT/'sources/language/native-composite-kerning-roles.json'),'newGlyphCount':len(rows),'extendedSubtables':counts}


def append_yoruba_marks(font,style):
    policy=read(ROOT/'sources/language/yoruba-routes.json')
    cut=next(c for c in policy['cuts'] if c['style']==style);gm=font.getReverseGlyphMap()
    marks={r['glyph']:(0,buildAnchor(*r['anchor'])) for r in cut['markCoverage']}
    bases={r['glyph']:{0:buildAnchor(*r['anchor'])} for r in cut['baseCoverage']}
    index=append_feature_lookup(font,'GPOS','mark',buildLookup([buildMarkBasePosSubtable(marks,bases,gm)],table='GPOS'))
    return {'policy':rec(ROOT/'sources/language/yoruba-routes.json'),'GPOSmark':index}


def naming(font,role,style,policy):
    family=policy['families'][role];style=style.replace('Semibold','SemiBold').replace('RegularItalic','Italic')
    italic=style.endswith('Italic');weight=style.removesuffix('Italic')
    if weight=='':weight='Regular'
    legacy=family if weight in ['Regular','Bold'] else family+' '+weight
    subfamily=('Bold Italic' if italic else 'Bold') if weight=='Bold' else ('Italic' if italic else 'Regular')
    typographic=weight+(' Italic' if italic else '')
    if weight=='Regular' and italic:typographic='Italic'
    full=family+' '+typographic;ps=family.replace(' ','')+'-'+style
    values={1:legacy,2:subfamily,3:policy['fontVersion']+';OTI;'+ps,4:full,5:'Version '+policy['fontVersion'],6:ps,
            8:'Open Transit Information',10:'A source-specific transport typeface adaptation by Open Transit Information.',
            11:policy['canonicalOrigin'],16:family if weight not in ['Regular','Bold'] else None,
            17:typographic if weight not in ['Regular','Bold'] else None,18:full,19:None,25:None}
    retained=[]
    for n in font['name'].names:
        if n.nameID in [21,22,25]:continue
        if n.nameID in values:
            value=values[n.nameID]
            if value is None:continue
            n.string=value.encode(n.getEncoding())
        elif n.nameID==0:n.string=' '.join(n.toUnicode().split()).encode(n.getEncoding())
        retained.append(n)
    font['name'].names=retained
    for key,value in values.items():
        if value is not None:font['name'].setName(value,key,3,1,0x409)
    font['head'].fontRevision=float(policy['fontVersion'])
    font['head'].modified=int(policy['sourceDateEpoch'])+2082844800
    # Request integer PPEM scaler math, as recommended for hinted fonts by
    # the OpenType head specification. Raster effects are platform-specific.
    font['head'].flags|=1<<3
    font['head'].macStyle=(font['head'].macStyle&~3)|(1 if weight=='Bold' else 0)|(2 if italic else 0)
    fs=font['OS/2'].fsSelection&~(1|32|64)
    font['OS/2'].fsSelection=fs|(1 if italic else 0)|(32 if weight=='Bold' else 0)|(64 if not italic and weight!='Bold' else 0)
    if 'DSIG' in font:del font['DSIG']
    return ps,style


def metadata(font):
    boxes=[stored_bound(font,n) for n in font.getGlyphOrder()];boxes=[b for b in boxes if b]
    head=font['head'];head.xMin=min(b[0] for b in boxes);head.yMin=min(b[1] for b in boxes)
    head.xMax=max(b[2] for b in boxes);head.yMax=max(b[3] for b in boxes)
    font['maxp'].recalc(font);font['hhea'].recalc(font)
    os2=font['OS/2'];os2.recalcAvgCharWidth(font);os2.recalcUnicodeRanges(font)
    cps=font.getBestCmap();os2.usFirstCharIndex=min(cps);os2.usLastCharIndex=min(max(cps),0xFFFF)
    os2.usMaxContext=maxCtxFont(font)
    return [max(os2.usWinAscent,head.yMax),max(os2.usWinDescent,-head.yMin)]


def main(baselines,output):
    os.chdir(ROOT);output=output.resolve();output.relative_to(ROOT/'build')
    assert not output.exists();output.mkdir(parents=True)
    baseline=read(baselines/'baseline-build.json');assert baseline['all24BaselineFilesByteIdentical']
    policy=read(ROOT/'release.json');additions=read(ROOT/'sources/language/additions.json')['additions']
    lt=read(ROOT/'sources/language/lithuanian-routes.json');rows=[]
    for cut in baseline['cuts']:
        role,style=cut['family'],cut['style'];source=ROOT/cut['ttf']['path']
        font=TTFont(source,recalcBBoxes=False,recalcTimestamp=False)
        # Force every source table to resolve names while original GIDs still apply.
        for tag in font.keys()[1:]:font[tag]
        before_order=font.getGlyphOrder();before={n:xml(font['glyf'][n],font) for n in before_order}
        before_metrics=dict(font['hmtx'].metrics)
        hints={t:font.getTableData(t).hex() for t in ['fpgm','prep','cvt '] if t in font}
        art=source_art_policy(font,role)
        source_rows=[r for r in additions if r['family']==('digital' if role=='screen' else 'physical') and r['style']==style]
        assert len(source_rows)==(11 if role=='screen' else 37)
        added=add_language_records(font,source_rows)
        kerning=inherit_native_kerning(font,style) if role=='sign' else None
        routes=append_lth_context(font,next(c for c in lt['cuts'] if c['style']==style)) if role=='sign' else None
        yoruba=append_yoruba_marks(font,style) if role=='sign' else None
        aliases=art['aliases'];conservation=[]
        for name in before_order:
            if name in art['removed']:continue
            target=aliases.get(name,name);expected=before[name]
            for old,new in aliases.items():expected=expected.replace(('"'+old+'"').encode(),('"'+new+'"').encode())
            assert xml(font['glyf'][target],font)==expected,(role,style,name,'glyph')
            assert font['hmtx'][target]==before_metrics[name],(role,style,name,'metrics')
            conservation.append(name)
        assert all(font.getTableData(t).hex()==value for t,value in hints.items())
        ps,canonical_style=naming(font,role,style,policy);minimum=metadata(font)
        directory=output/'fonts'/policy['families'][role].replace(' ','').lower();directory.mkdir(parents=True,exist_ok=True);stage=directory/(ps+'.ttf')
        font.save(stage,reorderTables=False);font.close()
        measurements=[]
        if role=='sign':
            f=TTFont(stage);data=stage.read_bytes();lcut=next(c for c in lt['cuts'] if c['style']==style)
            for case in lcut['cases']+lcut['dotRetentionCases']:
                run,_=placed(f,data,case['text'],{'ccmp':1,'kern':1,'liga':0,'clig':0,'mark':1,'mkmk':1},'lt','Latn')
                assert not run['missingClusters']
                measurements.append({'id':case['caseId'],'text':case['text'],'run':run})
                if run['inkBounds']:
                    minimum[0]=max(minimum[0],math.ceil(run['inkBounds'][3]));minimum[1]=max(minimum[1],math.ceil(-run['inkBounds'][1]))
            f.close()
        rows.append({'role':role,'style':canonical_style,'baselineStyle':style,'baselineSHA256':cut['ttf']['sha256'],
            'ttf':rec(stage),'artPolicy':art,'added':added,'lithuanianLookups':routes,'yorubaLookup':yoruba,'nativeKerningInheritance':kerning,
            'retainedGlyphCount':len(conservation),'retainedGlyphsMetricsInstructionsVerified':True,
            'minimumWin':minimum,'lithuanianMeasurements':measurements})
    for role in ['screen','sign']:
        common=[max(c['minimumWin'][i] for c in rows if c['role']==role) for i in [0,1]]
        for cut in [c for c in rows if c['role']==role]:
            p=ROOT/cut['ttf']['path'];f=TTFont(p,recalcBBoxes=False,recalcTimestamp=False)
            f['OS/2'].usWinAscent,f['OS/2'].usWinDescent=common;f.save(p,reorderTables=False);f.close()
            f=TTFont(p,recalcBBoxes=False,recalcTimestamp=False);f.flavor='woff2';f.save(p.with_suffix('.woff2'),reorderTables=False);f.close()
            cut.update({'ttf':rec(p),'woff2':rec(p.with_suffix('.woff2')),'commonWin':common})
    companions=[]
    native=read(ROOT/'companions/source-sans-3/provenance.json')
    for source in native['fonts']:
        p=ROOT/source['path'];assert rec(p)['sha256']==source['sha256']
        target=output/'companions'/p.name;target.parent.mkdir(exist_ok=True);target.write_bytes(p.read_bytes())
        web=next(r for r in native['webFonts'] if Path(r['path']).name==p.name+'.woff2')
        web_path=ROOT/web['path'];assert rec(web_path)['sha256']==web['sha256']
        web_target=target.with_name(web_path.name);web_target.write_bytes(web_path.read_bytes())
        companions.append({'ttf':rec(target),'woff2':rec(web_target),'woff2Source':'Official upstream unhinted web build; both files retain their native names and notices.'})
    manifest={'spdxLicense':'CC-BY-4.0','version':policy['version'],'fontVersion':policy['fontVersion'],
        'releasePolicy':rec(ROOT/'release.json'),'baselineManifest':rec(baselines/'baseline-build.json'),'sourceInputs':rec(ROOT/'sources/inputs.json'),
        'sourceAdditions':rec(ROOT/'sources/language/additions.json'),'lithuanianPolicy':rec(ROOT/'sources/language/lithuanian-routes.json'),
        'yorubaPolicy':rec(ROOT/'sources/language/yoruba-routes.json'),'nativeCompanionProvenance':rec(ROOT/'companions/source-sans-3/provenance.json'),
        'cuts':rows,'companions':companions}
    path=output/'build-manifest.json';path.write_text(json.dumps(manifest,indent=2,ensure_ascii=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'manifest':rec(path),'cuts':len(rows),'companions':len(companions)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baselines',type=Path,default=ROOT/'build/baselines')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/release')
    args=parser.parse_args();main(args.baselines.resolve(),args.output_dir)
