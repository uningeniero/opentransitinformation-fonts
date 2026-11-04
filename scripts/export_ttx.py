# SPDX-License-Identifier: Apache-2.0
"""Export editable public-successor tables, including instructions and layout."""
from pathlib import Path
import argparse
from fontTools.ttLib import TTFont
from _common import ROOT,read

def main(folder):
    destination=ROOT/'sources/ttx';assert not destination.exists();destination.mkdir(parents=True)
    for cut in read(folder/'build-manifest.json')['cuts']:
        path=ROOT/cut['ttf']['path'];font=TTFont(path,recalcBBoxes=False,recalcTimestamp=False)
        assert 'uniF8FF' not in font.getGlyphOrder()
        font.saveXML(destination/(path.stem+'.ttx'));font.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);args=p.parse_args();main(args.folder.resolve())
