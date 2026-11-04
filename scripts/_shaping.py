# SPDX-License-Identifier: Apache-2.0
import uharfbuzz as hb
def shape(data, text, language=None, script=None, features=None):
    font = hb.Font(hb.Face(data))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    if language:
        buf.language = language
    if script:
        buf.script = script
    hb.shape(font, buf, features or {})
    return [(g.codepoint, g.cluster, p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for g, p in zip(buf.glyph_infos, buf.glyph_positions)]
