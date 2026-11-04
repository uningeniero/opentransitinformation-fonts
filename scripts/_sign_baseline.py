# SPDX-License-Identifier: Apache-2.0
"""Build exact frozen additive TTF carriers; never redraw native body glyphs."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import unicodedata
from io import BytesIO
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import replayRecording
from fontTools.misc.roundTools import otRound
from fontTools.misc.xmlWriter import XMLWriter
from fontTools.otlLib.builder import buildAnchor,buildLookup,buildLigatureSubstSubtable,buildMarkBasePosSubtable,buildCoverage,buildMarkArray,buildMark2Record,buildSinglePosSubtable,buildValue
from _common import rec,read,stored_bound
from _geometry import placed

HERE=Path(__file__).resolve().parents[1]
TYPO=HERE
SNAP=HERE/'sources/sign'
SNAP_SHA='99b27a34a8f4d840d29aa76fb1bb9f425a41503597df6d8ca204b17d80b15faf'
CASES=[('q-upper','q\u0302\u0301'),('Q-upper','Q\u0302\u0301'),
       ('q-bottom-circumflex','q\u0323\u032d'),('q-bottom-tilde','q\u0323\u0330'),
       ('q-two-new-bottom','q\u032d\u0330'),('native-anchored-h-upper','h\u0306\u0301')]


def xml(value,font):
    if value is None:return None
    out=BytesIO();value.toXML(XMLWriter(out),font);return out.getvalue()


def mark_mark(marks,receivers,glyph_map):
    sub=otTables.MarkMarkPos();sub.Format=1;sub.ClassCount=1
    sub.Mark1Coverage=buildCoverage(marks,glyph_map)
    sub.Mark2Coverage=buildCoverage(receivers,glyph_map)
    sub.Mark1Array=buildMarkArray(marks,glyph_map)
    sub.Mark2Array=otTables.Mark2Array()
    sub.Mark2Array.Mark2Record=[buildMark2Record([receivers[g][0]]) for g in sub.Mark2Coverage.glyphs]
    sub.Mark2Array.Mark2Count=len(sub.Mark2Array.Mark2Record)
    return sub


def append_feature_lookup(font,tag,feature_tag,lookup):
    table=font[tag].table;index=len(table.LookupList.Lookup)
    table.LookupList.Lookup.append(lookup);table.LookupList.LookupCount=len(table.LookupList.Lookup)
    matches=[r for r in table.FeatureList.FeatureRecord if r.FeatureTag==feature_tag]
    assert matches,(tag,feature_tag)
    for record in matches:
        record.Feature.LookupListIndex.append(index)
        record.Feature.LookupCount=len(record.Feature.LookupListIndex)
    return index


def original_dot_anchor(probe,base,dot):
    for lookup in probe['GPOS'].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            typ=lookup.LookupType
            if typ==9:typ,sub=sub.ExtensionLookupType,sub.ExtSubTable
            if typ!=4 or dot not in sub.MarkCoverage.glyphs or base not in sub.BaseCoverage.glyphs:continue
            klass=sub.MarkArray.MarkRecord[sub.MarkCoverage.glyphs.index(dot)].Class
            anchors=sub.BaseArray.BaseRecord[sub.BaseCoverage.glyphs.index(base)].BaseAnchor
            if klass<len(anchors) and anchors[klass] is not None:return True
    return False


def append_contextual_dot(font,probe,boxes,metrics,mark_names,base_coverage):
    dot=probe.getBestCmap()[0x323];db=boxes[dot]
    assert db and metrics[dot][0]==0
    classes=font['GDEF'].table.GlyphClassDef.classDefs
    eligible=[];groups={};native_anchored=[]
    for base in font.getGlyphOrder():
        b=boxes[base]
        if base not in base_coverage or not b or base=='.notdef' or classes.get(base,0) in [2,3]:continue
        if base in probe.getGlyphOrder() and original_dot_anchor(probe,base,dot):
            native_anchored.append(base);continue
        desired_x=(b[0]+b[2]-db[0]-db[2])/2;desired_y=b[1]-90-db[3]
        xp,yp=otRound(desired_x-metrics[base][0]),otRound(desired_y)
        groups.setdefault((xp,yp),[]).append(base)
        eligible.append({'base':base,'baseGid':font.getGlyphID(base),'baseBounds':b,'baseAdvance':metrics[base][0],
                         'dotGlyph':dot,'dotBounds':db,'desiredDotOrigin':[desired_x,desired_y],
                         'singlePosValue':[xp,yp],'actualRoundedDotOrigin':[metrics[base][0]+xp,yp],
                         'originRoundingError':[metrics[base][0]+xp-desired_x,yp-desired_y],
                         'originalNativeDotBaseAnchorAvailable':False})
    table=font['GPOS'].table;glyph_map=font.getReverseGlyphMap();subtables=[];helpers=[]
    for (xp,yp),bases in sorted(groups.items()):
        index=len(table.LookupList.Lookup)
        helper=buildLookup([buildSinglePosSubtable({dot:buildValue({'XPlacement':xp,'YPlacement':yp})},glyph_map)],table='GPOS',extension=True)
        table.LookupList.Lookup.append(helper)
        helpers.append({'lookup':index,'singlePosValue':[xp,yp],'eligibleBases':bases,'onlyInvokedByContext':True})
        sub=otTables.ChainContextPos();sub.Format=3
        sub.BacktrackGlyphCount=1;sub.BacktrackCoverage=[buildCoverage(bases,glyph_map)]
        sub.InputGlyphCount=1;sub.InputCoverage=[buildCoverage([dot],glyph_map)]
        sub.LookAheadGlyphCount=1;sub.LookAheadCoverage=[buildCoverage(mark_names,glyph_map)]
        sub.PosCount=1;record=otTables.PosLookupRecord();record.SequenceIndex=0;record.LookupListIndex=index;sub.PosLookupRecord=[record]
        subtables.append(sub)
    table.LookupList.LookupCount=len(table.LookupList.Lookup)
    context_index=append_feature_lookup(font,'GPOS','mark',buildLookup(subtables,table='GPOS',extension=True))
    return {'contextLookup':context_index,'helperLookups':helpers,'eligibleBaseRecords':eligible,
            'nativeAnchoredBasesExcluded':native_anchored,'dotGlyph':dot,'newMarkLookahead':list(mark_names),
            'scope':'Only adjacent eligiblebase+nativedot+newbelowmark. Helpers are absent from direct featurelookup lists; no unconditional native-dot shift.'}


def construct(style,stage):
    manifest=read(SNAP/'snapshot.json')
    for binding in manifest['sourceFiles'].values():assert rec(Path(binding['frozen']['path']))==binding['frozen']
    profile=read(Path(manifest['sourceFiles']['physical-cabin-source.json']['frozen']['path']))
    sparse=read(Path(manifest['sourceFiles']['source/physical-cabin-additions-0.015-r2.json']['frozen']['path']))
    assert profile['sourceRevision']==5
    original_record=next(r['font'] for r in manifest['canonicalOriginalFonts'] if r['style']==style)
    source=Path(original_record['path']);assert rec(source)==original_record
    rows=sorted([r for r in sparse['additions'] if r['style']==style],key=lambda r:r['unicode'])
    assert len(rows)==85 and len({r['unicode'] for r in rows})==85
    # Geometry reads use a separate object. The carrier's old glyf slices stay
    # lazy/raw until serialization, avoiding unnecessary old-glyph recompiles.
    probe=TTFont(source)
    original_order=probe.getGlyphOrder()
    boxes={name:stored_bound(probe,name) for name in original_order}
    cmap=dict(probe.getBestCmap());all_metrics=dict(probe['hmtx'].metrics)
    classes=dict(probe['GDEF'].table.GlyphClassDef.classDefs)
    original_xml={tag:[xml(l,probe) for l in probe[tag].table.LookupList.Lookup] for tag in ['GSUB','GPOS']}
    # Store only source fields, not lazy reader/font caches.
    original_scripts={tag:xml(probe[tag].table.ScriptList,probe) for tag in ['GSUB','GPOS']}
    font=TTFont(source,lazy=True,recalcBBoxes=False,recalcTimestamp=False)
    assert len(original_order)==747 and len(cmap)==668
    # Initialise the original post/glyf/hmtx mappings while the original order
    # still applies. A late post decompile would replace appended source names
    # with generated glyphNNNN identifiers during serialization.
    assert font.getGlyphOrder()==original_order
    font['glyf'];font['hmtx'];font['post']
    names=[r['sourceDecision']['outputGlyph'] for r in rows]
    assert not set(names)&set(original_order)
    font.setGlyphOrder(original_order+names)
    added=[]
    for row in rows:
        cp=row['unicode'];name=row['sourceDecision']['outputGlyph']
        assert cp not in cmap and name=='oti.uni'+format(cp,'04X')
        record_hash=hashlib.sha256(json.dumps(row['recording'],separators=(',',':')).encode()).hexdigest()
        assert record_hash==row['sourceDecision']['recordingSha256']
        assert all(op in ['moveTo','lineTo','qCurveTo','closePath','endPath'] for op,_ in row['recording'])
        pen=TTGlyphPen(None);replayRecording(row['recording'],pen);glyph=pen.glyph()
        glyph.coordinates.toInt(round=otRound)
        glyph.recalcBounds(None)
        assert not glyph.program.getBytecode()
        font['glyf'][name]=glyph
        lsb=glyph.xMin if glyph.numberOfContours else 0
        width=otRound(row['advance']);font['hmtx'][name]=(width,lsb);all_metrics[name]=(width,lsb)
        box=[glyph.xMin,glyph.yMin,glyph.xMax,glyph.yMax] if glyph.numberOfContours else None
        boxes[name]=box;cmap[cp]=name
        added.append({'unicode':cp,'glyph':name,'gid':len(original_order)+len(added),'bounds':box,'advance':width,'lsb':lsb,
                      'sourceRecordSHA256':record_hash,'sourceDecisionId':'OTI-TYPE-PHYSICAL-'+style+'-'+name})
    closure=profile['canonicalCmapClosure'];assert closure['fromUnicode']==0x2126 and closure['toUnicode']==0x3a9
    assert 0x3a9 not in cmap
    cmap[0x3a9]=cmap[0x2126]
    for table in font['cmap'].tables:
        if table.isUnicode() and table.format in [4,12,13]:
            for row in rows:table.cmap[row['unicode']]=row['sourceDecision']['outputGlyph']
            table.cmap[0x3a9]=cmap[0x2126]
    assert len(cmap)==754
    routes={tuple(r['sourceDecision']['nfdCompositionRoute']):r['sourceDecision']['outputGlyph'] for r in rows if 'nfdCompositionRoute' in r['sourceDecision']}
    assert len(routes)==20
    assert set(g for route in routes for g in route).issubset(set(original_order+names))
    new_ccmp=append_feature_lookup(font,'GSUB','ccmp',buildLookup([buildLigatureSubstSubtable(routes)],table='GSUB'))
    new_marks={cmap[cp]:(0,buildAnchor(0,90)) for cp in [0x32d,0x330]}
    mark_names={name for cp,name in cmap.items() if unicodedata.category(chr(cp)).startswith('M')}
    mark_names.update(name for name,kind in classes.items() if kind==3)
    bases={name:{0:buildAnchor(otRound((b[0]+b[2])/2),b[1])} for name,b in boxes.items() if b and name not in mark_names and name!='.notdef'}
    bottom_names={name for cp,name in cmap.items() if unicodedata.combining(chr(cp)) in [202,220]}
    receivers={name:{0:buildAnchor(otRound((boxes[name][0]+boxes[name][2])/2),boxes[name][1])} for name in bottom_names if boxes[name]}
    glyph_map=font.getReverseGlyphMap()
    new_mark=append_feature_lookup(font,'GPOS','mark',buildLookup([buildMarkBasePosSubtable(new_marks,bases,glyph_map)],table='GPOS'))
    gdef=font['GDEF'].table
    assert all(gdef.GlyphClassDef.classDefs.get(n,0)==classes.get(n,0) for n in original_order)
    for row in rows:
        cp,name=row['unicode'],row['sourceDecision']['outputGlyph']
        if cp in [0x32d,0x330]:gdef.GlyphClassDef.classDefs[name]=3
        elif not unicodedata.category(chr(cp)).startswith(('Z','C')):gdef.GlyphClassDef.classDefs[name]=1
    contextual=append_contextual_dot(font,probe,boxes,all_metrics,list(new_marks),set(bases))
    new_mkmk=append_feature_lookup(font,'GPOS','mkmk',buildLookup([mark_mark(new_marks,receivers,glyph_map)],table='GPOS'))
    for tag in ['GSUB','GPOS']:
        assert [xml(l,font) for l in font[tag].table.LookupList.Lookup[:len(original_xml[tag])]]==original_xml[tag]
        assert xml(font[tag].table.ScriptList,font)==original_scripts[tag]
    for name in font['name'].names:
        if name.nameID in {1,4,6,16,18,21,22}:
            value=name.toUnicode().replace('Cabin',profile['workingFamilyName'] if name.nameID!=6 else profile['workingFamilyName'].replace(' ',''))
            name.string=value.encode(name.getEncoding())
        elif name.nameID==3:name.string=('OTI-ReferenceSignStudy-0.015-'+style).encode(name.getEncoding())
        elif name.nameID==5:name.string='Version 0.015; source-preserving four-cut carrier'.encode(name.getEncoding())
        elif name.nameID==11:name.string=profile['canonicalOrigin'].encode(name.getEncoding())
        elif name.nameID==0:
            source_fira=next(r['sourceDecision'] for r in rows if r['sourceDecision'].get('sourcePath'))
            donor=TTFont(TYPO/source_fira['sourcePath'],lazy=True)
            value=name.toUnicode()+'\n'+donor['name'].getDebugName(0)
            name.string=value.encode(name.getEncoding());donor.close()
    font['head'].fontRevision=0.015
    all_boxes=[b for b in boxes.values() if b]
    font['head'].xMin=min(b[0] for b in all_boxes);font['head'].yMin=min(b[1] for b in all_boxes)
    font['head'].xMax=max(b[2] for b in all_boxes);font['head'].yMax=max(b[3] for b in all_boxes)
    font['maxp'].numGlyphs=832
    font['maxp'].maxPoints=max([font['maxp'].maxPoints]+[len(font['glyf'][n].coordinates) for n in names])
    font['maxp'].maxContours=max([font['maxp'].maxContours]+[font['glyf'][n].numberOfContours for n in names])
    font['hhea'].advanceWidthMax=max(a for a,l in all_metrics.values())
    font['hhea'].minLeftSideBearing=min(l for a,l in all_metrics.values())
    font['hhea'].minRightSideBearing=min(all_metrics[n][0]-all_metrics[n][1]-(b[2]-b[0]) for n,b in boxes.items() if b)
    font['hhea'].xMaxExtent=max(all_metrics[n][1]+b[2]-b[0] for n,b in boxes.items() if b)
    # Stage minimum covers stored ink. The driver adds the named actual
    # positioned-case envelope across all four cuts before final output.
    stored_win=[max(2300,max(b[3] for b in all_boxes)),max(630,-min(b[1] for b in all_boxes))]
    font['OS/2'].usWinAscent,font['OS/2'].usWinDescent=stored_win
    assert not stage.exists();font.save(stage,reorderTables=False);font.close();probe.close()
    return {'style':style,'original':original_record,'stage':rec(stage),'addedGlyphs':added,
            'canonicalCompositionRoutes':{' '.join(k):v for k,v in routes.items()},
            'newLookupIndices':{'GSUBccmp':new_ccmp,'GPOSmark':new_mark,'GPOSmkmk':new_mkmk},
            'newBottomMarkNames':list(new_marks),'newBottomReceiverNames':sorted(receivers),
            'newBottomBaseCount':len(bases),'minimumStoredWin':stored_win,
            'contextualNativeDotRepair':contextual,
            'canonicalOmegaAlias':{'unicode':0x3a9,'sameExistingGlyphAs':0x2126,'glyph':cmap[0x2126]}}


def main(folder):
    assert rec(SNAP/'snapshot.json')['sha256']==SNAP_SHA
    assert HERE in folder.resolve().parents and not folder.exists()
    folder.mkdir(parents=True)
    cuts=[]
    for style in ['Regular','Medium','Semibold','Bold']:
        stage=folder/('stage-'+style+'.ttf')
        cut=construct(style,stage)
        font=TTFont(stage)
        measurements=[]
        for case,text in CASES:
            run,_=placed(font,stage.read_bytes(),text,{'ccmp':1,'kern':1,'liga':0,'clig':0,'mark':1,'mkmk':1})
            assert not run['missingClusters']
            measurements.append({'id':case,'text':text,'run':run})
        font.close();cut['metricCases']=measurements;cuts.append(cut)
    common_ascent=math.ceil(max([r['minimumStoredWin'][0] for r in cuts]+[m['run']['inkBounds'][3] for r in cuts for m in r['metricCases']]))
    common_descent=math.ceil(max([r['minimumStoredWin'][1] for r in cuts]+[-m['run']['inkBounds'][1] for r in cuts for m in r['metricCases']]))
    for cut in cuts:
        final=folder/('ReferenceSignStudy-'+cut['style']+'.ttf')
        font=TTFont(cut['stage']['path'],lazy=True,recalcBBoxes=False,recalcTimestamp=False)
        font['OS/2'].usWinAscent,font['OS/2'].usWinDescent=common_ascent,common_descent
        font.save(final,reorderTables=False);font.close()
        compressed=TTFont(final,lazy=True,recalcBBoxes=False,recalcTimestamp=False);compressed.flavor='woff2';compressed.save(final.with_suffix('.woff2'),reorderTables=False);compressed.close()
        cut['ttf']=rec(final);cut['woff2']=rec(final.with_suffix('.woff2'))
    output=folder/'construction.json'
    output.write_text(json.dumps({'$comment':'SPDX-License-Identifier: CC-BY-4.0 for original annotations; source/font terms unchanged',
        'builder':rec(Path(__file__)),'snapshot':rec(SNAP/'snapshot.json'),'commonWin':[common_ascent,common_descent],
        'finiteNamedMetricCases':[{'id':i,'text':t} for i,t in CASES],'cuts':cuts,
        'scope':'Actual frozen-R5additive carrier construction; conservation, new-record/lookup/sequence/contextualattachment readback and source-owned acceptance follow. Twenty canonical NFD outputs plus scoped native-dot/newmark contexts change intentionally; canonicalOmega gains cmapalias. No universal mark/reader claim.'},indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    print(json.dumps({'construction':rec(output),'commonWin':[common_ascent,common_descent]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    main(parser.parse_args().output_dir.resolve())
