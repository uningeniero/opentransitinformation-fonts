# SPDX-License-Identifier: Apache-2.0
"""Measure a single exact font in an isolated process with private GDI loading.

No font directory, registry entry, permanent installation or physical test.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import struct
import zlib
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parents[1]
FR_PRIVATE = 0x10
GDI_ERROR = 0xFFFFFFFF


class LOGFONTW(C.Structure):
    _fields_ = [(name, W.LONG) for name in ["lfHeight", "lfWidth", "lfEscapement", "lfOrientation", "lfWeight"]] + [(name, W.BYTE) for name in ["lfItalic", "lfUnderline", "lfStrikeOut", "lfCharSet", "lfOutPrecision", "lfClipPrecision", "lfQuality", "lfPitchAndFamily"]] + [("lfFaceName", W.WCHAR * 32)]


class TEXTMETRICW(C.Structure):
    _fields_ = [(name, W.LONG) for name in ["tmHeight", "tmAscent", "tmDescent", "tmInternalLeading", "tmExternalLeading", "tmAveCharWidth", "tmMaxCharWidth", "tmWeight", "tmOverhang", "tmDigitizedAspectX", "tmDigitizedAspectY"]] + [(name, W.WCHAR) for name in ["tmFirstChar", "tmLastChar", "tmDefaultChar", "tmBreakChar"]] + [(name, W.BYTE) for name in ["tmItalic", "tmUnderlined", "tmStruckOut", "tmPitchAndFamily", "tmCharSet"]]


class BITMAPINFOHEADER(C.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD), ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]


class SIZE(C.Structure):
    _fields_ = [("cx", W.LONG), ("cy", W.LONG)]


def api():
    g = C.WinDLL("gdi32", use_last_error=True)
    signatures = {
        "AddFontResourceExW": ([W.LPCWSTR, W.DWORD, C.c_void_p], C.c_int),
        "RemoveFontResourceExW": ([W.LPCWSTR, W.DWORD, C.c_void_p], W.BOOL),
        "CreateCompatibleDC": ([W.HDC], W.HDC), "DeleteDC": ([W.HDC], W.BOOL),
        "CreateFontIndirectW": ([C.POINTER(LOGFONTW)], W.HANDLE),
        "SelectObject": ([W.HDC, W.HANDLE], W.HANDLE), "DeleteObject": ([W.HANDLE], W.BOOL),
        "GetTextMetricsW": ([W.HDC, C.POINTER(TEXTMETRICW)], W.BOOL),
        "GetTextFaceW": ([W.HDC, C.c_int, W.LPWSTR], C.c_int),
        "GetFontData": ([W.HDC, W.DWORD, W.DWORD, C.c_void_p, W.DWORD], W.DWORD),
        "GetGlyphIndicesW": ([W.HDC, W.LPCWSTR, C.c_int, C.POINTER(W.WORD), W.DWORD], W.DWORD),
        "CreateDIBSection": ([W.HDC, C.POINTER(BITMAPINFOHEADER), W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD], W.HANDLE),
        "SetTextAlign": ([W.HDC, W.UINT], W.UINT), "SetTextColor": ([W.HDC, W.DWORD], W.DWORD),
        "SetBkMode": ([W.HDC, C.c_int], C.c_int),
        "ExtTextOutW": ([W.HDC, C.c_int, C.c_int, W.UINT, C.c_void_p, C.c_void_p, W.UINT, C.c_void_p], W.BOOL),
        "GetTextExtentPoint32W": ([W.HDC, W.LPCWSTR, C.c_int, C.POINTER(SIZE)], W.BOOL),
        "GdiFlush": ([], W.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(g, name)
        function.argtypes, function.restype = arguments, result
    return g


def rec(path):
    data = path.read_bytes()
    return {"path": path.resolve().relative_to(HERE).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def png(path, width, height, rgb):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag+data) & 0xFFFFFFFF)
    scan = b"".join(b"\0"+rgb[y*width*3:(y+1)*width*3] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(scan,9))+chunk(b"IEND",b""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.font.resolve(), args.output.resolve()
    assert (HERE/'build').resolve() in output.parents and not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    picture = output.with_suffix(".png")
    assert not picture.exists()
    font = TTFont(source, lazy=True)
    face = font["name"].getDebugName(1)
    assert face and len(face) < 32
    weight = font["OS/2"].usWeightClass
    italic = bool(font["OS/2"].fsSelection & 1)
    g = api()
    registered = g.AddFontResourceExW(str(source), FR_PRIVATE, None)
    assert registered > 0, "Private font loading failed."
    dc = hfont = bitmap = old_font = old_bitmap = None
    removal = False
    cleanup = {}
    result = None
    try:
        dc = g.CreateCompatibleDC(None)
        assert dc
        lf = LOGFONTW()
        lf.lfHeight, lf.lfWeight, lf.lfItalic = -96, weight, int(italic)
        lf.lfCharSet, lf.lfOutPrecision, lf.lfQuality = 1, 7, 4
        lf.lfFaceName = face
        hfont = g.CreateFontIndirectW(C.byref(lf))
        assert hfont
        old_font = g.SelectObject(dc, hfont)
        selected = C.create_unicode_buffer(256)
        assert g.GetTextFaceW(dc, len(selected), selected)
        # Identify the actual selected data, rather than trusting the requested face name.
        tables = {}
        for tag in ["name", "glyf", "OS/2"]:
            numeric_tag = int.from_bytes(tag.encode("ascii"), "little")
            length = g.GetFontData(dc, numeric_tag, 0, None, 0)
            assert length != GDI_ERROR
            buffer = C.create_string_buffer(length)
            assert g.GetFontData(dc, numeric_tag, 0, buffer, length) == length
            tables[tag] = {"bytes": length, "sha256": hashlib.sha256(buffer.raw).hexdigest()}
            assert buffer.raw == font.reader[tag], "GDI selected different font data: "+tag
        tm = TEXTMETRICW()
        assert g.GetTextMetricsW(dc, C.byref(tm))
        text_size = SIZE()
        text = "Bilbao Il1 08:45"
        assert g.GetTextExtentPoint32W(dc, text, len(text), C.byref(text_size))
        width, height, baseline = 240, 320, 230
        info = BITMAPINFOHEADER()
        info.biSize, info.biWidth, info.biHeight = C.sizeof(BITMAPINFOHEADER), width, -height
        info.biPlanes, info.biBitCount, info.biCompression = 1, 32, 0
        bits = C.c_void_p()
        bitmap = g.CreateDIBSection(dc, C.byref(info), 0, C.byref(bits), None, 0)
        assert bitmap and bits.value
        old_bitmap = g.SelectObject(dc, bitmap)
        g.SetTextAlign(dc, 24)  # TA_LEFT | TA_BASELINE, no rectangle clipping.
        g.SetTextColor(dc, 0)
        g.SetBkMode(dc, 1)
        cases = []
        panels = []
        for cp in [0x49, 0x1FA, 0x1EB2, 0x2999]:
            character = chr(cp)
            ids = (W.WORD * 1)()
            assert g.GetGlyphIndicesW(dc, character, 1, ids, 1) != GDI_ERROR
            present = ids[0] != 0xFFFF
            expected_name = font.getBestCmap().get(cp)
            assert present == bool(expected_name)
            if present:
                assert ids[0] == font.getGlyphID(expected_name)
            C.memset(bits, 255, width*height*4)
            if present:
                assert g.ExtTextOutW(dc, 40, baseline, 0x10, None, C.cast(ids,C.c_void_p), 1, None)
            assert g.GdiFlush(), "Synchronise GDI before direct DIB pixel access."
            raw = C.string_at(bits, width*height*4)
            rgb = bytearray(width*height*3)
            rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
            pixels = [i for i in range(width*height) if min(rgb[i*3:i*3+3]) < 240]
            bbox = [min(i%width for i in pixels), min(i//width for i in pixels), max(i%width for i in pixels)+1, max(i//width for i in pixels)+1] if pixels else None
            if bbox:
                assert bbox[0] > 0 and bbox[1] > 0 and bbox[2] < width and bbox[3] < height, "Offscreen canvas boundary reached; not a font-clipping test."
            cases.append({"scalar": cp, "glyphPresentInExactSelectedFont": present, "glyphIndex": int(ids[0]),
                          "glyph": expected_name, "pixelBounds": bbox, "darkPixelCount": len(pixels),
                          "drawOrigin": [40,baseline], "draw": "ExtTextOutW ETO_GLYPH_INDEX; no font linking or rectangle clip",
                          "bitmapMaskSha256": hashlib.sha256(bytes(rgb)).hexdigest()})
            panels.append(rgb)
        strip = bytearray(width*len(panels)*height*3)
        for y in range(height):
            for i, panel in enumerate(panels):
                start = (y*width*len(panels)+i*width)*3
                strip[start:start+width*3] = panel[y*width*3:(y+1)*width*3]
        png(picture,width*len(panels),height,strip)
        result = {"$comment":"SPDX-License-Identifier: CC-BY-4.0", "recordedAtUtc":datetime.now(timezone.utc).isoformat(),
                  "program":rec(Path(__file__)), "font":rec(source), "requestedFace":face, "selectedFace":selected.value,
                  "selectedExactTableData":tables, "requestedLogicalHeight":-96, "mappingMode":"MM_TEXT logical pixel units in an offscreen DIB",
                  "textMetrics":{name:getattr(tm,name) for name,_ in TEXTMETRICW._fields_},
                  "textExtent":{"text":text,"width":text_size.cx,"height":text_size.cy},
                  "fontVerticalMetrics":{"typo":[font['OS/2'].sTypoAscender,font['OS/2'].sTypoDescender,font['OS/2'].sTypoLineGap],
                      "win":[font['OS/2'].usWinAscent,font['OS/2'].usWinDescent],"selection":font['OS/2'].fsSelection},
                  "cases":cases, "image":rec(picture), "panelOrder":[c['scalar'] for c in cases],
                  "dibSynchronisation":"Explicit GdiFlush before every direct bitmap read and subsequent CPU write.",
                  "scope":"Finite actual private-process Windows GDI software measurement. Pixel bounds are observed raster output, not automatic proof of complete outline retention, universal clipping behaviour, physical calibration or reading quality. Missing baseline U2999 is not rendered through a fallback."}
    finally:
        if dc and old_font:
            g.SelectObject(dc,old_font)
        if dc and old_bitmap:
            g.SelectObject(dc,old_bitmap)
        if hfont:
            cleanup['fontObjectDeleted'] = bool(g.DeleteObject(hfont))
        if bitmap:
            cleanup['bitmapDeleted'] = bool(g.DeleteObject(bitmap))
        if dc:
            cleanup['deviceContextDeleted'] = bool(g.DeleteDC(dc))
        removal = bool(g.RemoveFontResourceExW(str(source),FR_PRIVATE,None))
        font.close()
    assert removal and all(cleanup.values()), "Private GDI resource cleanup incomplete."
    result['cleanup']={**cleanup,'privateFontExplicitlyRemoved':removal,'registeredFaces':registered,'registryOrFontDirectoryChanged':False}
    output.write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    print(json.dumps({'report':rec(output),'metrics':result['textMetrics'],'cases':[{k:c[k] for k in ['scalar','glyphPresentInExactSelectedFont','pixelBounds']} for c in result['cases']]}))


if __name__ == '__main__':
    main()
