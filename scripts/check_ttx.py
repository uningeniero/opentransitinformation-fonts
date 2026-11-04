# SPDX-License-Identifier: Apache-2.0
"""Verify the editable table exports against the distributed font records."""
from io import BytesIO
from pathlib import Path
import json,sys
from fontTools.ttLib import TTFont
from fontTools.misc.xmlWriter import XMLWriter
from _common import ROOT,read

def xml(value,font):
    b=BytesIO();value.toXML(XMLWriter(b),font);return b.getvalue()

def main():
    results=[]
    for cut in read(ROOT/'fonts/manifest.json')['cuts']:
        path=ROOT/cut['ttf']['path'];source=ROOT/'sources/ttx'/(path.stem+'.ttx')
        original=TTFont(path,recalcBBoxes=False,recalcTimestamp=False);rebuilt=TTFont(recalcBBoxes=False,recalcTimestamp=False);rebuilt.importXML(source)
        assert original.getGlyphOrder()==rebuilt.getGlyphOrder() and original.getBestCmap()==rebuilt.getBestCmap()
        assert all(xml(original['glyf'][n],original)==xml(rebuilt['glyf'][n],rebuilt) and original['hmtx'][n]==rebuilt['hmtx'][n] for n in original.getGlyphOrder())
        for tag in ['GSUB','GPOS','GDEF','name','OS/2','maxp','hhea','fpgm','prep','cvt ']:
            if tag in original:assert original.getTableData(tag)==rebuilt.getTableData(tag),(path.name,tag)
        results.append(path.name);original.close();rebuilt.close()
    print(json.dumps({'editableTtxFiles':len(results),'glyphsMetricsHintsLayoutNamesMatched':True}))

if __name__=='__main__':main()
