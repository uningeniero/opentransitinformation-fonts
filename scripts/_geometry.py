# SPDX-License-Identifier: Apache-2.0
"""Actual placed curves with explicit support for compiled composite glyphs."""
import pathops
from fontTools.pens.recordingPen import DecomposingRecordingPen,replayRecording
from fontTools.pens.transformPen import TransformPen
from _shaping import shape
from _common import bound


def placed(font,data,text,features,language='en',script='Latn'):
    run=shape(data,text,language,script,features)
    positions=[];curves=[];whole=None;x=y=0;glyphs=font.getGlyphSet()
    for gid,cluster,xa,ya,xo,yo in run:
        name=font.getGlyphName(gid)
        recording=DecomposingRecordingPen(glyphs);glyphs[name].draw(recording)
        curve=pathops.Path()
        replayRecording(recording.value,TransformPen(curve.getPen(),(1,0,0,1,x+xo,y+yo)))
        local=bound(font,name)
        box=[local[0]+x+xo,local[1]+y+yo,local[2]+x+xo,local[3]+y+yo] if local else None
        if box:whole=box[:] if whole is None else [min(whole[0],box[0]),min(whole[1],box[1]),max(whole[2],box[2]),max(whole[3],box[3])]
        positions.append({'glyph':name,'gid':gid,'cluster':cluster,'advance':[xa,ya],'offset':[xo,yo],'origin':[x+xo,y+yo],'inkBounds':box})
        curves.append(curve);x+=xa;y+=ya
    return {'positions':positions,'advance':[x,y],'inkBounds':whole,'missingClusters':[r[1] for r in run if r[0]==0]},curves
