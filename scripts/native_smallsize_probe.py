# SPDX-License-Identifier: Apache-2.0
"""Capture exact privately loaded GDI glyph rasters at finite small pixel sizes."""
from pathlib import Path
import argparse,ctypes as C,hashlib,json
from ctypes import wintypes as W
from fontTools.ttLib import TTFont
from native_windows_probe import api,LOGFONTW,BITMAPINFOHEADER,FR_PRIVATE,GDI_ERROR,png
from _common import ROOT,rec


def main(source,output,glyph_names=None):
    output.relative_to(ROOT/'build');assert not output.exists() and not output.with_suffix('.png').exists()
    output.parent.mkdir(parents=True,exist_ok=True)
    font=TTFont(source);cmap=font.getBestCmap();g=api();registered=g.AddFontResourceExW(str(source),FR_PRIVATE,None);assert registered>0
    dc=bitmap=old_bitmap=None;faces=[];records=[];cleanup={}
    sizes=[12,14,16,18,20,24]
    scalars=[0x49,0x6C,0x31,*range(0x30,0x3A),0x41,0x56,0x40,0x26,0x1E1A,0x1E8B,0xA7CB,0xA7DC,0x1DC5,0x032E,0x035F,0x1C89,0x1C8A]
    if glyph_names:
        assert all(name in font.getGlyphOrder() for name in glyph_names)
        scalars=[None]*len(glyph_names)
    tile=48;width=tile*len(scalars);height=tile*len(sizes)
    try:
        dc=g.CreateCompatibleDC(None);assert dc
        info=BITMAPINFOHEADER();info.biSize=C.sizeof(info);info.biWidth=width;info.biHeight=-height;info.biPlanes=1;info.biBitCount=32
        bits=C.c_void_p();bitmap=g.CreateDIBSection(dc,C.byref(info),0,C.byref(bits),None,0);assert bitmap and bits.value
        old_bitmap=g.SelectObject(dc,bitmap);C.memset(bits,255,width*height*4)
        g.SetTextAlign(dc,24);g.SetTextColor(dc,0);g.SetBkMode(dc,1)
        for row,size in enumerate(sizes):
            lf=LOGFONTW();lf.lfHeight=-size;lf.lfWeight=font['OS/2'].usWeightClass;lf.lfItalic=int(bool(font['OS/2'].fsSelection&1))
            lf.lfCharSet=1;lf.lfOutPrecision=7;lf.lfQuality=4;lf.lfFaceName=font['name'].getDebugName(1)
            handle=g.CreateFontIndirectW(C.byref(lf));assert handle;old_font=g.SelectObject(dc,handle)
            try:
                selected=C.create_unicode_buffer(256);assert g.GetTextFaceW(dc,len(selected),selected)
                selected_tables={}
                for tag in ['name','glyf','OS/2',*[t for t in ['fpgm','prep','cvt '] if t in font]]:
                    numeric=int.from_bytes(tag.encode(),'little');length=g.GetFontData(dc,numeric,0,None,0);assert length!=GDI_ERROR
                    buffer=C.create_string_buffer(length);assert g.GetFontData(dc,numeric,0,buffer,length)==length
                    assert buffer.raw==font.reader[tag], 'The actual selected font differs from the requested file.'
                    selected_tables[tag]=hashlib.sha256(buffer.raw).hexdigest()
                faces.append({'pixelSize':size,'actualFace':selected.value,'exactTableSha256':selected_tables})
                for col,cp in enumerate(scalars):
                    glyph=glyph_names[col] if glyph_names else cmap.get(cp);ids=(W.WORD*1)()
                    if glyph_names:ids[0]=font.getGlyphID(glyph);present=True
                    else:
                        assert g.GetGlyphIndicesW(dc,chr(cp),1,ids,1)!=GDI_ERROR
                        present=ids[0]!=0xFFFF;assert present==bool(glyph)
                    if present:
                        assert ids[0]==font.getGlyphID(glyph)
                        assert g.ExtTextOutW(dc,col*tile+12,row*tile+34,0x10,None,C.cast(ids,C.c_void_p),1,None)
                    records.append({'size':size,'scalar':cp,'glyph':glyph,'present':present,'tile':[col,row]})
            finally:
                g.SelectObject(dc,old_font);assert g.DeleteObject(handle)
        assert g.GdiFlush();raw=C.string_at(bits,width*height*4);rgb=bytearray(width*height*3)
        rgb[0::3],rgb[1::3],rgb[2::3]=raw[2::4],raw[1::4],raw[0::4]
        for record in records:
            col,row=record['tile'];pixels=[]
            for y in range(row*tile,(row+1)*tile):
                for x in range(col*tile,(col+1)*tile):
                    if min(rgb[(y*width+x)*3:(y*width+x)*3+3])<240:pixels.append((x-col*tile,y-row*tile))
            record['darkPixels']=len(pixels)
            record['pixelBounds']=[min(x for x,y in pixels),min(y for x,y in pixels),max(x for x,y in pixels)+1,max(y for x,y in pixels)+1] if pixels else None
            if record['present']:assert pixels, 'An outlined diagnostic glyph produced an empty raster.'
            if pixels:assert 0<min(x for x,y in pixels) and max(x for x,y in pixels)<tile-1 and 0<min(y for x,y in pixels) and max(y for x,y in pixels)<tile-1
        picture=output.with_suffix('.png');png(picture,width,height,rgb)
    finally:
        if dc and old_bitmap:g.SelectObject(dc,old_bitmap)
        if bitmap:cleanup['bitmapDeleted']=bool(g.DeleteObject(bitmap))
        if dc:cleanup['deviceContextDeleted']=bool(g.DeleteDC(dc))
        cleanup['privateFontRemoved']=bool(g.RemoveFontResourceExW(str(source),FR_PRIVATE,None));font.close()
    assert all(cleanup.values())
    result={'spdxLicense':'CC-BY-4.0','font':rec(source),'program':rec(Path(__file__)),'sizes':sizes,'scalarColumns':scalars,'glyphNameColumns':glyph_names,'tilePixels':tile,
            'exactSelectedFonts':faces,'rasters':records,'image':rec(picture),'cleanup':cleanup,
            'scope':'Finite native Windows GDI software raster observations. ETO_GLYPH_INDEX avoids fallback; these isolated glyphs do not establish text shaping, reading performance, physical calibration or universal renderer behaviour.'}
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'report':rec(output),'image':rec(picture),'glyphCases':len(records)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--font',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--glyph-names',nargs='+');a=p.parse_args();main(a.font.resolve(),a.output.resolve(),a.glyph_names)
