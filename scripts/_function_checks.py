# SPDX-License-Identifier: Apache-2.0
"""Finite serialized-function checks against source-reviewed input requirements."""
from fontTools.pens.boundsPen import BoundsPen
from _shaping import shape
from _j_caron_checks import check_j_caron


def runs(font,data,text,features=None,language=None):
    return [(font.getGlyphName(g),xa,ya,xo,yo) for g,c,xa,ya,xo,yo in shape(data,text,language,None,features)]


def ink(font,run):
    glyphs=font.getGlyphSet();x=y=0;boxes=[]
    for name,xa,ya,xo,yo in run:
        pen=BoundsPen(glyphs);glyphs[name].draw(pen)
        if pen.bounds:
            a,b,c,d=pen.bounds;boxes.append([x+xo+a,y+yo+b,x+xo+c,y+yo+d])
        x+=xa;y+=ya
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None


def attachment_entries(font,base,mark):
    rows=[]
    for lookup in font['GPOS'].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            typ=lookup.LookupType
            if typ==9:typ,sub=sub.ExtensionLookupType,sub.ExtSubTable
            if typ!=4 or base not in sub.BaseCoverage.glyphs or mark not in sub.MarkCoverage.glyphs:continue
            mr=sub.MarkArray.MarkRecord[sub.MarkCoverage.glyphs.index(mark)];ba=sub.BaseArray.BaseRecord[sub.BaseCoverage.glyphs.index(base)].BaseAnchor[mr.Class]
            if ba:rows.append(([ba.XCoordinate,ba.YCoordinate],[mr.MarkAnchor.XCoordinate,mr.MarkAnchor.YCoordinate]))
    return rows


def check_functions(font,data,old,old_data,role,style,fixture,check,label):
    cmap=font.getBestCmap();cases=fixture[role][style]
    if role=='screen':
        check_j_caron(font,data,old,old_data,cases,check,label,runs)
        for text,features in [('\u1e0a',{'c2sc':1}),('D\u0307',{'c2sc':1}),('\u1e0b',{'smcp':1}),('d\u0307',{'smcp':1}),('\u1e0a',{'aalt':1}),('\u1e0b',{'aalt':1})]:
            run=runs(font,data,text,features);check(len(run)==1 and run[0][0]=='uni1E0A.sc' and run[0][1]==cases['dDotAboveSmallcap'],label+'-d-dot-above-'+text.encode('unicode_escape').decode()+'-'+str(features),actual=run)
        for text,features in [('\u1e2a',{'c2sc':1}),('\u1e2b',{'smcp':1})]:
            run=runs(font,data,text,features);check(len(run)==1 and run[0][0]=='uni1E2A.sc' and run[0][1]==cases['hBreveSmallcap'],label+'-h-breve-smallcap-'+text.encode('unicode_escape').decode(),actual=run)
        for base in 'AEIOUaeiou':
            text=base+'\u1dc5';run=runs(font,data,text);check(all(r[0]!='.notdef' for r in run),label+'-compound-above-'+base+'-nominal')
            if 'compoundAboveMarkAnchor' in cases:
                check(len(run)==2 and run[0][0]==cmap[0x131 if base=='i' else ord(base)],label+'-compound-above-'+base+'-base',actual=run)
                entries=attachment_entries(font,run[0][0],run[1][0]);ma=cases['compoundAboveMarkAnchor']
                check(any(m==ma and [b[0]-m[0]-run[0][1],b[1]-m[1]]==[run[1][3],run[1][4]] for b,m in entries),label+'-compound-above-'+base+'-actual-attachment',actual=run)
            else:check(run==runs(old,old_data,text),label+'-compound-above-'+base+'-retained-italic',actual=run)
        for row in cases['doubleMacronPairs']:
            plain=row['text'];text=plain[0]+'\u035f'+plain[1];run=runs(font,data,text);native=runs(old,old_data,plain)
            alternate='uni035F.upperPair' if plain=='TH' else 'uni035F.lowerPair'
            check([r[0] for r in run]==[cmap[ord(plain[0])],alternate,cmap[ord(plain[1])]] and sum(r[1] for r in run)==sum(r[1] for r in native),label+'-double-macron-'+plain+'-native-spacing',actual=run)
            mark=next(r for r in run if r[0]==alternate);box=ink(font,[mark]);origin=run[0][1]
            start,end=box[0]+origin,box[2]+origin
            check(abs(start-row['start'])<=.5 and abs(end-row['end'])<=.5,label+'-double-macron-'+plain+'-two-base-span',actual=[start,end],expected=[row['start'],row['end']])
    else:
        for row in cases['scopedVowels']:
            mark=cmap[int(row['mark'][2:],16)];expected=(row['baseAnchor'],row['markAnchor']);entries=attachment_entries(font,row['base'],mark)
            check(expected in entries,label+'-scoped-anchor-'+row['base']+'-'+row['mark'],actual=entries)
        for cp in [0x61,0x65,0x69,0x6f,0x75,0x254,0x25b,0x272]:
            for tone in ['', '\u0300','\u0301']:
                text=chr(cp)+'\u0329'+tone;run=runs(font,data,text);bounds=ink(font,run)
                check(all(r[0]!='.notdef' for r in run) and any(r[0]==cmap[0x329] and r[1]==0 for r in run),label+'-vertical-line-below-'+text.encode('unicode_escape').decode(),actual=run)
                check(bounds is not None and bounds[3]<=font['OS/2'].usWinAscent and -bounds[1]<=font['OS/2'].usWinDescent,label+'-vertical-line-below-'+text.encode('unicode_escape').decode()+'-finite-win-envelope',bounds=bounds)
        for text in ['\u1ecb','\u1ecb\u0304']:
            check(runs(font,data,text)==runs(old,old_data,text),label+'-soft-dot-negative-'+text.encode('unicode_escape').decode())
