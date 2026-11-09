# SPDX-License-Identifier: Apache-2.0
"""Execute the declared successor inputs against actual serialized fonts."""
import unicodedata2 as ud
from fontTools.pens.boundsPen import BoundsPen
from _function_checks import attachment_entries, ink as run_ink
from _shaping import shape


def check_successor(font, data, role, style, spec, check, label):
    cmap = font.getBestCmap()
    uppercase_glyphs = {name for cp, name in cmap.items() if ud.category(chr(cp)) == 'Lu'}
    glyph_set = font.getGlyphSet()
    categories = font['GDEF'].table.GlyphClassDef.classDefs

    def run(text, features=None, script=None, language='und'):
        return [(font.getGlyphName(g), xa, ya, xo, yo)
                for g, cluster, xa, ya, xo, yo in shape(data, text, language, script, features or {})]

    def ink(name):
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        return pen.bounds

    check(len(cmap) == spec['bothFamilies']['expectedEncodedScalars'][role], label + '-successor-exact-repertoire')
    check(bool(font['OS/2'].fsSelection & (1 << 8)), label + '-successor-wws')
    check('STAT' in font and [a.AxisTag for a in font['STAT'].table.DesignAxisRecord.Axis] == spec['bothFamilies']['statAxes'][role], label + '-successor-stat-axes')
    if 'STAT' in font:
        axes = font['STAT'].table.DesignAxisRecord.Axis
        values = font['STAT'].table.AxisValueArray.AxisValue
        expected = {'wght': font['OS/2'].usWeightClass}
        if role == 'screen': expected['ital'] = int(bool(font['OS/2'].fsSelection & 1))
        actual = [(axes[v.AxisIndex].AxisTag, v.Value) for v in values if v.Format == 1]
        check(len(actual) == len(expected) and dict(actual) == expected and len(values) == len(actual),
              label + '-successor-static-stat-actual-coordinates', actual=actual, expected=expected)
    scripts = 'Latn,Grek,Cyrl' if role == 'screen' else 'Latn'
    check('meta' in font and font['meta'].data == {'dlng': scripts, 'slng': scripts}, label + '-successor-script-metadata')
    postscript_name=font['name'].getDebugName(6)
    check(0<len(postscript_name)<=63 and all(33<=ord(c)<=126 and c not in '[](){}<>/%' for c in postscript_name), label + '-successor-postscript-name-length')
    for cp in spec['bothFamilies']['newSeparators']:
        name = cmap.get(cp)
        check(name is not None and ink(name) is None and font['hmtx'][name][0] == 0,
              label + '-successor-zero-ink-separator-' + f'{cp:04X}')

    circle = cmap.get(spec['bothFamilies']['dottedCircle'])
    check(circle is not None and categories.get(circle) == 1 and ink(circle) is not None,
          label + '-successor-dotted-circle-base')
    if circle is not None:
        for cp, name in sorted(cmap.items()):
            if ud.category(chr(cp)) not in ['Mn', 'Me'] or ink(name) is None:
                continue
            actual = run(chr(spec['bothFamilies']['dottedCircle']) + chr(cp))
            check(all(r[0] != '.notdef' for r in actual), label + '-successor-circle-mark-' + f'{cp:04X}' + '-nominal', actual=actual)
            # A coordinate of zero can be an active GPOS attachment. Match the
            # actual serialized base/mark anchors rather than offset heuristics.
            valid = len(actual) == 2 and actual[0][0] == circle
            entries = attachment_entries(font, circle, actual[-1][0]) if valid else []
            valid = valid and len(entries) == 1 and actual[1][1:3] == (0, 0) and any(
                [b[0] - m[0] - actual[0][1], b[1] - m[1]] == list(actual[1][3:5]) for b, m in entries)
            check(valid, label + '-successor-circle-mark-' + f'{cp:04X}' + '-actual-attachment', actual=actual, applicableAnchorPairs=entries)

    if role != 'screen':
        for tag, expected in spec['sign']['stylisticSetNames'].items():
            feature = next((r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag == tag), None)
            params = feature.FeatureParams if feature is not None else None
            check(params is not None and font['name'].getDebugName(params.UINameID) == expected,
                  label + '-successor-' + tag + '-accurate-name')
        check(run('@', {'ss01': 1})[0][0] == 'at.ss01' and run('@')[0][0] == 'at',
              label + '-successor-ss01-retained-at-sign-route')
        return

    for cp in spec['screen']['historicalCyrillic']:
        check(cp in cmap and ink(cmap[cp]) is not None, label + '-successor-historical-' + f'{cp:04X}' + '-encoded')
        if cp not in cmap:
            continue
        tag = 'c2sc' if cp % 2 == 0 else 'smcp'
        expected = 'uni' + f'{cp & ~1:04X}' + '.sc'
        actual = run(chr(cp), {tag: 1}, 'Cyrl')
        check(len(actual) == 1 and actual[0][0] == expected and expected in glyph_set,
              label + '-successor-historical-' + f'{cp:04X}' + '-' + tag, actual=actual, expected=expected)

    authentic = spec['screen']['authenticCyrillic']
    bridge = spec['screen']['cgjOverbridge']
    cgj = cmap.get(bridge['scalar'])
    check(cgj == bridge['glyph'] and ink(cgj) is None and font['hmtx'][cgj][0] == 0
          and categories.get(cgj) == bridge['gdefGlyphClass'],
          label + '-successor-cgj-nominal-zero-ink-mark')
    check(ud.category(chr(bridge['scalar'])) == bridge['generalCategory']
          and ud.combining(chr(bridge['scalar'])) == bridge['canonicalCombiningClass'],
          label + '-successor-cgj-unicode-properties')
    attachment = font['GDEF'].table.MarkAttachClassDef.classDefs
    above = attachment.get(bridge['aboveClassControl'])
    check(above is not None and above != 0 and all(attachment.get(name) == above
          for name in bridge['requiredAboveAttachmentMembers']),
          label + '-successor-above-receiver-filter-membership',
          controlClass=above, actual={name: attachment.get(name, 0)
          for name in bridge['requiredAboveAttachmentMembers']})
    check(not attachment.get(cgj, 0), label + '-successor-cgj-outside-above-filter')
    # MarkAttachmentType is the high byte of LookupFlag. It is distinct
    # from UseMarkFilteringSet and from the GDEF mark glyph category.
    receiver_lookups = []
    for lookup in font['GPOS'].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            typ = lookup.LookupType
            if typ == 9:
                typ, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if typ == 6 and 'uni0361' in sub.Mark2Coverage.glyphs:
                receiver_lookups.append(lookup)
                break
    check(len(receiver_lookups) == 1 and receiver_lookups[0].LookupFlag >> 8 == above
          and not receiver_lookups[0].LookupFlag & 0x10,
          label + '-successor-overbridge-real-filter-flag',
          flags=[lookup.LookupFlag for lookup in receiver_lookups])
    psili, iso = authentic['standaloneGlyph'], authentic['isoGlyph']
    check(cmap.get(authentic['newEncodedMark']) == psili and categories.get(psili) == 3 and font['hmtx'].metrics.get(psili, (1, 0))[0] == 0,
          label + '-successor-authentic-psili-mark')
    check(iso in glyph_set and iso not in cmap.values() and categories.get(iso) == 3 and font['hmtx'].metrics.get(iso, (1, 0))[0] == 0,
          label + '-successor-authentic-iso-unencoded-mark')
    check(not set(authentic['unsupportedNeighbouringMarks']) & set(cmap), label + '-successor-finite-cyrillic-repertoire-boundary')
    for normalization in spec['normalizations']:
        for mode in spec['featureModes']:
            for text in authentic['contexts']:
                source = ud.normalize(normalization, text)
                actual = run(source, mode['features'], 'Cyrl', 'cu')
                expected = iso if chr(authentic['newEncodedMark']) + '\u0301' in text else psili
                valid = all(r[0] != '.notdef' for r in actual) and len(actual) == 2 and actual[1][0] == expected and actual[1][1:3] == (0, 0)
                entries = attachment_entries(font, actual[0][0], expected) if valid else []
                valid = valid and any([b[0] - m[0] - actual[0][1], b[1] - m[1]] == list(actual[1][3:5]) for b, m in entries)
                check(valid, label + '-successor-authentic-' + text.encode('unicode_escape').decode() + '-' + normalization + '-' + mode['name'], actual=actual, applicableAnchorPairs=entries)
                bounds = run_ink(font, actual)
                check(bounds is not None and bounds[3] <= font['OS/2'].usWinAscent and bounds[1] >= -font['OS/2'].usWinDescent,
                      label + '-successor-authentic-linebox-' + text.encode('unicode_escape').decode() + '-' + normalization + '-' + mode['name'],
                      ink=bounds, winAscent=font['OS/2'].usWinAscent, winDescent=font['OS/2'].usWinDescent)
            for text in authentic['reverseContexts'] + ['\u047b\u0486\u0300\u0301']:
                actual = run(ud.normalize(normalization, text), mode['features'], 'Cyrl', 'cu')
                check(iso not in [r[0] for r in actual] and all(r[0] != '.notdef' for r in actual),
                      label + '-successor-iso-order-control-' + text.encode('unicode_escape').decode() + '-' + normalization + '-' + mode['name'], actual=actual)
    disabled = run(authentic['contexts'][0], {'ccmp': 0}, 'Cyrl', 'cu')
    check(iso not in [r[0] for r in disabled], label + '-successor-iso-real-ccmp-control', actual=disabled)

    for tag, inputs in spec['screen']['smallcapInputs'].items():
        unresolved = []
        for cp in inputs:
            if cp not in cmap:
                unresolved.append({'scalar': cp, 'reason': 'Missing input mapping'})
                continue
            nominal = run(chr(cp))
            active = run(chr(cp), {tag: 1})
            # This is a necessary routing check, not optical acceptance. A
            # semantic exception requires its separately recorded disposition.
            if active == nominal or any(r[0] == '.notdef' or r[0] in uppercase_glyphs for r in active):
                unresolved.append({'scalar': cp, 'default': nominal, 'active': active})
        check(not unresolved, label + '-successor-complete-' + tag + '-input-routing', unresolved=unresolved,
              criterion='Real reviewed optical forms and separate source/paint review remain required.')

    for text in spec['softDotInputs'] + spec['stackDiagnosticInputs']:
        if not all(ord(c) in cmap for c in text):
            continue
        for normalization in spec['normalizations']:
            source = ud.normalize(normalization, text)
            script = 'Cyrl' if 0x0400 <= ord(source[0]) <= 0x04FF else 'Latn'
            for mode in spec['featureModes']:
                actual = run(source, mode['features'], script, 'lt' if text == 'i\u0307\u0301' else 'und')
                valid = all(r[0] != '.notdef' for r in actual) and all(r[1:3] == (0, 0) for r in actual[1:])
                if mode['name'] in ['smcp', 'both']:
                    valid = valid and '.sc' in actual[0][0]
                check(valid, label + '-successor-context-' + text.encode('unicode_escape').decode() + '-' + normalization + '-' + mode['name'], actual=actual)
