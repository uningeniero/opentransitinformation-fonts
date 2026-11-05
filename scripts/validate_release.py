# SPDX-License-Identifier: Apache-2.0
"""Validate serialized fonts, retained source records and scoped language routes."""
from pathlib import Path
from io import BytesIO
import argparse,copy,hashlib,json,sys,unicodedata
from fontTools.ttLib import TTFont
from fontTools.misc.xmlWriter import XMLWriter
from _common import ROOT,read,rec
from _shaping import shape
from _geometry import placed


def xml(value,font):
    out=BytesIO();value.toXML(XMLWriter(out),font);return out.getvalue()


def normalized(data,font,text,language='en',script='Latn',features=None):
    return [(font.getGlyphName(gid),xa,ya,xo,yo) for gid,cluster,xa,ya,xo,yo in shape(data,text,language,script,features)]


def retained_lookup(lookup,allowed_names):
    result=copy.deepcopy(lookup)
    for sub in result.SubTable:
        typ=result.LookupType
        if typ==9:typ,sub=sub.ExtensionLookupType,sub.ExtSubTable
        if typ!=2:continue
        if sub.Format==1:
            sets={n:s for n,s in zip(sub.Coverage.glyphs,sub.PairSet) if n in allowed_names}
            sub.Coverage.glyphs=[n for n in sub.Coverage.glyphs if n in allowed_names]
            sub.PairSet=[sets[n] for n in sub.Coverage.glyphs];sub.PairSetCount=len(sub.PairSet)
            for pairs in sub.PairSet:
                pairs.PairValueRecord=[p for p in pairs.PairValueRecord if p.SecondGlyph in allowed_names];pairs.PairValueCount=len(pairs.PairValueRecord)
        elif sub.Format==2:
            sub.Coverage.glyphs=[n for n in sub.Coverage.glyphs if n in allowed_names]
            for classdef in [sub.ClassDef1,sub.ClassDef2]:classdef.classDefs={n:v for n,v in classdef.classDefs.items() if n in allowed_names}
    return result


def validate(folder):
    manifest=read(folder/'build-manifest.json');spec=read(ROOT/'tests/validation-spec.json');policy=read(ROOT/'release.json')
    additions=read(ROOT/'sources/language/additions.json')['additions'];lt=read(ROOT/'sources/language/lithuanian-routes.json')
    checks=[]
    def check(condition,case,**detail):checks.append({'case':case,'passed':bool(condition),**detail})
    fonts={}
    for cut in manifest['cuts']:
        role,style=cut['role'],cut['style'];p=ROOT/cut['ttf']['path'];data=p.read_bytes();font=TTFont(p)
        fonts[(role,style)]=(font,data,cut)
        check(rec(p)==cut['ttf'],role+'-'+style+'-ttf-binding')
        woff=ROOT/cut['woff2']['path'];wf=TTFont(woff);wf.flavor=None
        check(rec(woff)==cut['woff2'],role+'-'+style+'-woff-binding')
        same=[tag for tag in font.keys()[1:] if tag!='head' and font.getTableData(tag)!=wf.getTableData(tag)]
        # WOFF2 can rewrite the legal glyf/loca encoding. Compare logical glyphs below.
        check(not [t for t in same if t not in ['glyf','loca']],role+'-'+style+'-woff-tables',different=same)
        check(font.getGlyphOrder()==wf.getGlyphOrder() and font.getBestCmap()==wf.getBestCmap(),role+'-'+style+'-woff-order-cmap')
        check(all(xml(font['glyf'][n],font)==xml(wf['glyf'][n],wf) and font['hmtx'][n]==wf['hmtx'][n] for n in font.getGlyphOrder()),role+'-'+style+'-woff-glyphs')
        check(wf['head'].fontRevision==font['head'].fontRevision and wf['head'].flags==(font['head'].flags|0x800),role+'-'+style+'-woff-head-flags')
        resource='screen-primary' if role=='screen' else 'sign-latin'
        required=set(spec['resourceRequirements'][resource]['requiredScalars'])
        check(required==set(font.getBestCmap()),role+'-'+style+'-exact-repertoire',expected=len(required),actual=len(font.getBestCmap()))
        check(font['name'].getBestFamilyName()==policy['families'][role] and font['name'].getDebugName(5)=='Version '+policy['fontVersion'],role+'-'+style+'-names-version')
        check('uniF8FF' not in font.getGlyphOrder() if role=='screen' else True,role+'-'+style+'-art-exclusion')
        check(not any('-' in n for n in font.getGlyphOrder()),role+'-'+style+'-glyphname-aliases')
        # Read back every retained serialized glyph, hint and horizontal metric.
        baseline_path=ROOT/manifest.get('baselineManifest',{'path':'build/baselines-second/baseline-build.json'})['path']
        old_cut=next(c for c in read(baseline_path)['cuts'] if c['family']==role and c['style']==cut['baselineStyle'])
        old=TTFont(ROOT/old_cut['ttf']['path']);aliases=cut['artPolicy']['aliases'];removed=cut['artPolicy']['removed'];differing=[]
        for name in old.getGlyphOrder():
            if name in removed:continue
            target=aliases.get(name,name);expected=xml(old['glyf'][name],old)
            for source,dest in aliases.items():expected=expected.replace(('"'+source+'"').encode(),('"'+dest+'"').encode())
            if expected!=xml(font['glyf'][target],font) or font['hmtx'][target]!=old['hmtx'][name]:differing.append(name)
        check(not differing,role+'-'+style+'-serialized-source-conservation',differing=differing)
        check(all(font.getTableData(t)==old.getTableData(t) for t in ['fpgm','prep','cvt '] if t in old),role+'-'+style+'-native-hint-tables')
        allowed_names=set(old.getGlyphOrder())-set(removed)
        for tag in ['GSUB','GPOS']:
            original=old[tag].table.LookupList.Lookup;successor=font[tag].table.LookupList.Lookup;differing=[]
            for i,lookup in enumerate(original):
                expected=xml(lookup,old)
                for source,dest in aliases.items():expected=expected.replace(('"'+source+'"').encode(),('"'+dest+'"').encode())
                current=retained_lookup(successor[i],allowed_names) if role=='sign' else successor[i]
                if expected!=xml(current,font):differing.append(i)
            check(not differing,role+'-'+style+'-retained-'+tag+'-lookup-definitions',differing=differing)
        if role=='sign':
            old_data=(ROOT/old_cut['ttf']['path']).read_bytes()
            kern=read(ROOT/'sources/language/native-composite-kerning-roles.json')
            for row in [r for r in kern['roles'] if r['style']==cut['baselineStyle']]:
                text=chr(row['unicode']);nfd=unicodedata.normalize('NFD',text)
                for template in ['V{}A','T{}o','{}{}']:
                    old_text=template.format(nfd,nfd);new_text=template.format(text,text)
                    advances={}
                    for enabled in [0,1]:
                        previous=shape(old_data,old_text,'en','Latn',{'kern':enabled})
                        successor=shape(data,new_text,'en','Latn',{'kern':enabled})
                        decomposed=shape(data,template.format(nfd,nfd),'en','Latn',{'kern':enabled})
                        advances[str(enabled)]=[sum(r[2] for r in previous),sum(r[2] for r in successor),sum(r[2] for r in decomposed)]
                    check(all(a==b==c for a,b,c in advances.values()),style+'-kern-'+format(row['unicode'],'04X')+'-'+template,advances=advances)
        old.close()
        for row in [r for r in additions if r['family']==('digital' if role=='screen' else 'physical') and r['style']==cut['baselineStyle']]:
            g=font['glyf'][row['glyph']]
            check(not hasattr(g,'program') or not g.program.getBytecode(),role+'-'+style+'-new-unhinted-'+format(row['unicode'],'04X'))
            text=chr(row['unicode']);nfd=unicodedata.normalize('NFD',text)
            if text!=nfd:
                check(normalized(data,font,text)==normalized(data,font,nfd),role+'-'+style+'-new-canonical-'+format(row['unicode'],'04X'))
        for locale in spec['localeRequirements']:
            if role=='sign' and locale['signRole']!='sign-latin':continue
            chars=' '.join(chr(cp) for cp in locale['requiredScalars'])
            for form in ['NFC','NFD']:
                text=unicodedata.normalize(form,chars)
                result=shape(data,text,locale['locale'],locale['script'])
                check(all(r[0]!=0 for r in result),role+'-'+style+'-'+locale['locale']+'-'+form+'-nominal',missing=[r[1] for r in result if r[0]==0])
        if role=='sign':
            source=next(c for c in lt['cuts'] if c['style']==cut['baselineStyle'])
            for case in source['cases']:
                run,_=placed(font,data,case['text'],{},'lt','Latn');mark=next((r for r in run['positions'] if r['glyph']==case['markGlyph']),None)
                check(mark is not None and mark['origin']==case['proposedMarkOrigin'],style+'-'+case['caseId']+'-anchor',expected=case['proposedMarkOrigin'],actual=mark['origin'] if mark else None)
                check(normalized(data,font,case['text'],'lt')==normalized(data,font,case['nfd'],'lt'),style+'-'+case['caseId']+'-canonical')
            for case in source['dotRetentionCases']:
                run,_=placed(font,data,case['text'],{},'lt','Latn')
                if 'contextInputGlyphs' in case:
                    check([r['glyph'] for r in run['positions']]==case['outputGlyphSequence'],style+'-'+case['caseId']+'-glyphs',actual=[r['glyph'] for r in run['positions']])
                    mark=next((r for r in run['positions'] if r['glyph']=='acutecomb.case'),None)
                    check(mark is not None and mark['origin']==case['proposedMarkOrigin'],style+'-'+case['caseId']+'-anchor',expected=case['proposedMarkOrigin'],actual=mark['origin'] if mark else None)
                    other=normalized(data,font,case['text'],'en')
                    check([r[0] for r in other]==[r['glyph'] for r in case['beforeGlyphs']],style+'-'+case['caseId']+'-GSUB-language-scope',englishPositionedGlyphs=other)
                else:
                    before=[(r['glyph'],r['advance'],0,r['xOffset'],r['yOffset']) for r in case['beforeGlyphs']]
                    check(normalized(data,font,case['text'],'lt')==before,style+'-'+case['caseId']+'-retained-native')
            for case in source['negativeControls']:
                if case['text']=='\u012f\u0307\u0301':continue
                before=[(r['glyph'],r['advance'],0,r['xOffset'],r['yOffset']) for r in case['beforeGlyphs']]
                check(normalized(data,font,case['text'],'lt')==before,style+'-negative-'+case['text'].encode('unicode_escape').decode())
            yo=next(c for c in read(ROOT/'sources/language/yoruba-routes.json')['cuts'] if c['style']==cut['baselineStyle'])
            for case in yo['cases']:
                run,_=placed(font,data,case['text'],{},'yo','Latn');mark=next((r for r in run['positions'] if r['glyph']==case['markGlyph']),None)
                check(mark is not None and mark['origin']==case['proposedMarkOrigin'],style+'-'+case['caseId']+'-anchor',expected=case['proposedMarkOrigin'],actual=mark['origin'] if mark else None)
                check(normalized(data,font,case['text'],'yo')==normalized(data,font,case['nfd'],'yo'),style+'-'+case['caseId']+'-canonical')
                check(not run['missingClusters'] and run['inkBounds'][3]<=font['OS/2'].usWinAscent and -run['inkBounds'][1]<=font['OS/2'].usWinDescent,style+'-'+case['caseId']+'-envelope')
            for case in yo['negativeControls']:
                before=[(r['glyph'],r['advance'],0,r['xOffset'],r['yOffset']) for r in case['beforeGlyphs']]
                check(normalized(data,font,case['text'],'yo')==before,style+'-yo-negative-'+case['text'].encode('unicode_escape').decode())
        wf.close()
    for companion in manifest['companions']:
        p=ROOT/companion['ttf']['path'];font=TTFont(p);data=p.read_bytes()
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        web_path=ROOT/companion['woff2']['path'];web=TTFont(web_path,recalcBBoxes=False,recalcTimestamp=False)
        # HarfBuzz consumes decoded SFNT. Its wheel is not a WOFF2 decoder.
        web.flavor=None;sfnt=BytesIO();web.save(sfnt,reorderTables=False);web_data=sfnt.getvalue()
        check(rec(web_path)==companion['woff2'],p.stem+'-native-web-binding')
        check(font.getGlyphOrder()==web.getGlyphOrder() and font.getBestCmap()==web.getBestCmap(),p.stem+'-native-web-order-cmap')
        differences=[];gs1=font.getGlyphSet();gs2=web.getGlyphSet()
        for name in font.getGlyphOrder():
            a=DecomposingRecordingPen(gs1);b=DecomposingRecordingPen(gs2);gs1[name].draw(a);gs2[name].draw(b)
            if a.value!=b.value or font['hmtx'][name]!=web['hmtx'][name]:differences.append(name)
        check(not differences,p.stem+'-native-web-geometry-metrics',differing=differences)
        check(all(font.getTableData(t)==web.getTableData(t) for t in ['GSUB','GPOS','GDEF','OS/2','post']),p.stem+'-native-web-layout-tables')
        check(all(font['name'].getDebugName(i)==web['name'].getDebugName(i) for i in [0,7,9,13,14]),p.stem+'-native-web-notices')
        check(web['name'].getBestFamilyName()=='Source Sans 3' and web['name'].getDebugName(5).startswith('Version 3.052'),p.stem+'-native-web-metadata')
        check(not any(t in web for t in ['fpgm','prep','cvt ']),p.stem+'-official-web-unhinted-tables')
        check(set(spec['resourceRequirements']['sign-greek-cyrillic-companion']['requiredScalars']).issubset(font.getBestCmap()),p.stem+'-repertoire')
        check(font['name'].getBestFamilyName()=='Source Sans 3' and font['name'].getDebugName(5).startswith('Version 3.052'),p.stem+'-native-metadata')
        for locale in [r for r in spec['localeRequirements'] if r['signRole']=='sign-greek-cyrillic-companion']:
            text=' '.join(chr(cp) for cp in locale['requiredScalars'])
            for form in ['NFC','NFD']:
                sample=unicodedata.normalize(form,text)
                check(all(r[0]!=0 for r in shape(data,sample,locale['locale'],locale['script'])),p.stem+'-'+locale['locale']+'-'+form)
                check(normalized(data,font,sample,locale['locale'],locale['script'])==normalized(web_data,web,sample,locale['locale'],locale['script']),p.stem+'-'+locale['locale']+'-'+form+'-native-web-positioned')
        web.close();font.close()
    for font,data,cut in fonts.values():font.close()
    output={'spdxLicense':'CC-BY-4.0','manifest':rec(folder/'build-manifest.json'),'spec':rec(ROOT/'tests/validation-spec.json'),'checks':checks,'total':len(checks),'failures':sum(not c['passed'] for c in checks)}
    dest=folder/'validation.json';dest.write_text(json.dumps(output,indent=2,ensure_ascii=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'receipt':rec(dest),'total':len(checks),'failures':[c for c in checks if not c['passed']]}))
    return output['failures']==0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);args=p.parse_args()
    sys.exit(0 if validate(args.folder.resolve()) else 1)
