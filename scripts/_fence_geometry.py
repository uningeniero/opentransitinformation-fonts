# SPDX-License-Identifier: Apache-2.0
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
def compile_geometry(contours):
    target = TTGlyphPen(None)
    points = PointToSegmentPen(Cu2QuPen(target, max_err=1, reverse_direction=False))
    for contour in contours:
        assert contour["closed"]
        points.beginPath()
        for node in contour["nodes"]:
            segment = {"offcurve": None, "curve": "curve", "line": "line", "qcurve": "qcurve"}[node["type"]]
            points.addPoint((node["x"], node["y"]), segmentType=segment, smooth=node["smooth"])
        points.endPath()
    glyph = target.glyph()
    glyph.recalcBounds(None)
    return glyph
