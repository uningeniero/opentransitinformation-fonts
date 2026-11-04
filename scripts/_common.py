# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import hashlib,json
from fontTools.pens.boundsPen import BoundsPen
ROOT=Path(__file__).resolve().parents[1]
def rec(path):
    p=Path(path).resolve();p.relative_to(ROOT)
    raw=p.read_bytes()
    return {'path':p.relative_to(ROOT).as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
def stored_bound(font,name):
    glyph=font['glyf'][name]
    return [glyph.xMin,glyph.yMin,glyph.xMax,glyph.yMax] if glyph.numberOfContours else None
def bound(font, name):
    glyphs = font.getGlyphSet()
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    return list(pen.bounds) if pen.bounds else None
