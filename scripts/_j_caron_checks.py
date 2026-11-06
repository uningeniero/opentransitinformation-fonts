# SPDX-License-Identifier: Apache-2.0
"""Check the native j-small-cap and zero-width caron construction."""
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen


def check_j_caron(font,data,old,old_data,cases,check,label,runs):
    expected=cases['jCaronSmallcap'];name='uni01F0.sc';glyphs=font.getGlyphSet()
    actual=DecomposingRecordingPen(glyphs);glyphs[name].draw(actual)
    native=DecomposingRecordingPen(glyphs);glyphs['j.sc'].draw(native)
    glyphs['uni030C.case'].draw(TransformPen(native,(1,0,0,1,*expected['componentTranslate'])))
    check(actual.value==native.value,label+'-j-caron-native-component-geometry')
    check(font['hmtx'][name][0]==expected['advance']==font['hmtx']['j.sc'][0] and font['hmtx']['uni030C.case'][0]==0,label+'-j-caron-native-advances')
    for text in ['\u01f0','j\u030c']:
        run=runs(font,data,text,{'smcp':1})
        check(run==[(name,expected['advance'],0,0,0)],label+'-j-caron-smcp-'+text.encode('unicode_escape').decode(),actual=run)
        check(runs(font,data,text)==runs(old,old_data,text),label+'-j-caron-retained-default-'+text.encode('unicode_escape').decode())
    for following in ['A','V','T','a','v','t']:
        new=runs(font,data,'\u01f0'+following,{'smcp':1});reference=runs(font,data,'j'+following,{'smcp':1})
        check(len(new)==len(reference) and new[0][0]==name and reference[0][0]=='j.sc' and new[0][1:]==reference[0][1:] and new[1:]==reference[1:],label+'-j-caron-inherited-pair-spacing-'+following,actual=new,reference=reference)
