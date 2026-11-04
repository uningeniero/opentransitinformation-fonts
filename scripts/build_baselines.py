# SPDX-License-Identifier: Apache-2.0
"""Reproduce the qualified carrier baseline from relative pinned inputs.

These intermediate working-name files are source comparisons, not public
release artifacts. The publication build consumes them and applies its
explicit source, repertoire, metadata and artwork policies.
"""
from pathlib import Path
import argparse,json,os
from fontTools.ttLib import TTFont
from fontTools.misc.roundTools import otRound
from _common import rec,read
from _fence_geometry import compile_geometry
import _screen_profile
import _sign_baseline
from fetch_inputs import fetch

ROOT=Path(__file__).resolve().parents[1]


def screen_fence(style,source,target,projection):
    row=next(r for r in projection['rows'] if r['style']==style)
    glyph=compile_geometry(row['contours'])
    font=TTFont(source,lazy=True,recalcBBoxes=False,recalcTimestamp=False)
    order=list(font.getGlyphOrder());font['hmtx'];font['post']
    assert 'dottedFence' not in order and 0x2999 not in font.getBestCmap()
    font['glyf']['dottedFence']=glyph; font.setGlyphOrder(order+['dottedFence'])
    font['hmtx']['dottedFence']=(otRound(row['advance']),glyph.xMin)
    for table in font['cmap'].tables:
        if table.isUnicode() and table.format in [4,12,13]:table.cmap[0x2999]='dottedFence'
    font['OS/2'].usWinAscent,font['OS/2'].usWinDescent=projection['stageWin'][style]
    font['head'].yMax=max(font['head'].yMax,glyph.yMax)
    font['head'].yMin=min(font['head'].yMin,glyph.yMin)
    font['head'].fontRevision=0.011
    font['maxp'].numGlyphs=len(order)+1
    font['maxp'].maxPoints=max(font['maxp'].maxPoints,len(glyph.coordinates))
    font['maxp'].maxContours=max(font['maxp'].maxContours,glyph.numberOfContours)
    for n in font['name'].names:
        if n.nameID==3:n.string=('OTI-ReferenceScreenFull-0.011-'+style).encode(n.getEncoding())
        elif n.nameID==5:n.string='Version 0.011; source U2999 and measured-Win engineering proposal'.encode(n.getEncoding())
    font.save(target,reorderTables=False);font.close()


def finalize(source,target,role,style):
    font=TTFont(source,lazy=True,recalcBBoxes=False,recalcTimestamp=False)
    if role=='screen':
        font['OS/2'].usWinAscent,font['OS/2'].usWinDescent=1265,355
        font['head'].fontRevision=0.012
        for n in font['name'].names:
            if n.nameID==3:n.string=('OTI-ReferenceScreenFull-0.012-'+style).encode(n.getEncoding())
            elif n.nameID==5:n.string='Version 0.012; source fence and common Windows metrics'.encode(n.getEncoding())
    else:font['OS/2'].recalcUnicodeRanges(font)
    font['OS/2'].recalcAvgCharWidth(font)
    font.save(target,reorderTables=False);font.close()
    font=TTFont(target,lazy=True,recalcBBoxes=False,recalcTimestamp=False);font.flavor='woff2'
    font.save(target.with_suffix('.woff2'),reorderTables=False);font.close()


def main(output):
    os.chdir(ROOT);output=output.resolve();output.relative_to(ROOT/'build')
    assert not output.exists();fetch();output.mkdir(parents=True)
    screen=output/'screen';screen.mkdir()
    stages=output/'stages';stages.mkdir()
    projection=read(ROOT/'sources/screen/fence.json');expected=read(ROOT/'sources/baseline-checksums.json')
    records=[]
    for c in [c for c in expected['cuts'] if c['family']=='screen']:
        style=c['style'];first=stages/('profile-'+style+'.ttf');second=stages/('fence-'+style+'.ttf')
        _screen_profile.build(style,first);screen_fence(style,first,second,projection)
        target=screen/c['ttf']['filename'];finalize(second,target,'screen',style)
        records.append({'family':'screen','style':style,'ttf':rec(target),'woff2':rec(target.with_suffix('.woff2'))})
    sign_stage=stages/'sign';_sign_baseline.main(sign_stage)
    sign=output/'sign';sign.mkdir()
    for c in [c for c in expected['cuts'] if c['family']=='sign']:
        source=sign_stage/c['ttf']['filename'];target=sign/source.name;finalize(source,target,'sign',c['style'])
        records.append({'family':'sign','style':c['style'],'ttf':rec(target),'woff2':rec(target.with_suffix('.woff2'))})
    comparisons=[]
    for row in records:
        old=next(c for c in expected['cuts'] if (c['family'],c['style'])==(row['family'],row['style']))
        for ext in ['ttf','woff2']:
            passed=row[ext]['sha256']==old[ext]['sha256'] and row[ext]['bytes']==old[ext]['bytes']
            comparisons.append({'family':row['family'],'style':row['style'],'format':ext,'expected':old[ext]['sha256'],'actual':row[ext]['sha256'],'passed':passed})
    manifest={'schema':1,'portableRootIndependentInputs':True,'cuts':records,'baselineByteComparisons':comparisons,'all24BaselineFilesByteIdentical':all(c['passed'] for c in comparisons)}
    (output/'baseline-build.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'manifest':rec(output/'baseline-build.json'),'all24BaselineFilesByteIdentical':manifest['all24BaselineFilesByteIdentical'],'mismatches':[c for c in comparisons if not c['passed']]}))
    assert manifest['all24BaselineFilesByteIdentical'],'Portable baseline differs; inspect table-level causes before publication.'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'build/baselines');main(p.parse_args().output_dir)
