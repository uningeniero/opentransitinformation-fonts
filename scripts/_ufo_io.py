# SPDX-License-Identifier: Apache-2.0
"""Persist selected editable UFO records without rewriting unrelated glyphs."""
from pathlib import Path
from fontTools.ufoLib import UFOWriter
from _common import ROOT, rec

def ensure_spdx(path):
    path = Path(path)
    text = path.read_text(encoding='utf-8')
    if 'SPDX-License-Identifier:' not in text:
        first, remainder = text.split('\n', 1)
        path.write_text(first + '\n<!-- SPDX-License-Identifier: OFL-1.1 -->\n' + remainder,
                        encoding='utf-8', newline='\n')

def write_selected(path, font, names=(), info=False, features=True):
    path = Path(path).resolve()
    path.relative_to(ROOT / 'sources/ufo')
    written = [path / 'metainfo.plist']
    with UFOWriter(path, formatVersion=3) as writer:
        glyphs = writer.getGlyphSet()
        for name in names:
            glyph = font[name]
            glyphs.writeGlyph(name, glyph, glyph.drawPoints, formatVersion=2)
            written.append(path / 'glyphs' / glyphs.contents[name])
        if names:
            glyphs.writeContents()
            written.append(path / 'glyphs/contents.plist')
        if info:
            writer.writeInfo(font.info)
            written.append(path / 'fontinfo.plist')
        writer.writeLib(font.lib)
        written.append(path / 'lib.plist')
        if features:
            writer.writeFeatures(font.features.text)
            written.append(path / 'features.fea')
    for target in written:
        if target.suffix in ['.plist', '.glif']:
            ensure_spdx(target)
    return [rec(target) for target in written]
