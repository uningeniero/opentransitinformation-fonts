<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Release 1.0.1 engineering checks

OTI Traveller Sign and OTI Traveller Screen are the naming-only successors to the 1.0.0 families. All 24 primary TTF and WOFF2 files were compared with the immutable predecessor archive. Glyph order and all font tables except the name table and the declared version, timestamp and checksum fields in the font header remain identical. Original copyright and licence records remain unchanged. The eight Source Sans 3 files are byte-identical to the predecessor.

The serialized release was checked against the selected repertoire and source rules. The local validation contains 2,520 passing assertions, including retained drawings, metrics and instructions, layout definitions, canonical sequences, 108 Lithuanian cases, 32 Yoruba cases and 216 native-composite word/pair fixtures. Original Source Sans 3 web resources are compared with their corresponding TTF outlines, spacing, language layout and notices; their upstream hinting difference is retained.

The twelve renamed TTF cuts were loaded privately through Windows GDI. The actual selected name, glyph and OS/2 tables matched the requested files, and the temporary font and drawing resources were removed. The offline web specimens loaded all sixteen declared faces at widths of 390 and 1440 px, including the unchanged Source Sans 3 resources for the complete selected Greek and Cyrillic rows. These are software checks rather than measurements of reading performance or a manufactured sign.

The Screen `head.flags` bit 3 requests integer PPEM scaler mathematics, following the [OpenType recommendation for hinted fonts](https://learn.microsoft.com/en-us/typography/opentype/spec/head). The predecessor's Windows Edge 156.0.4314.58 Canvas comparison used eight cuts, eight sizes from 12 to 24.25 px and three finite code/diacritic/fence strings. Its 192 flag-on/flag-off comparisons had equal advances; 144 raster masks differed. That flag comparison was not repeated for the naming-only successor. The flag and hint instructions are unchanged between these two releases.

## Fontspector 1.9.0

The full Google Fonts profile completed for both families. Counts below are tool subresults, not independent outline defects or a catalogue admission result.

| Family | Pass | Warn | Fail | Skip | Info |
|---|---:|---:|---:|---:|---:|
| OTI Traveller Screen | 665 | 159 | 72 | 460 | 39 |
| OTI Traveller Sign | 332 | 72 | 84 | 252 | 21 |

The remaining failing check categories have explicit source or repertoire dispositions:

| Check | Disposition |
|---|---|
| `googlefonts/family_name_compliance` | The adopted OTI prefix is reported as an abbreviation under the Google Fonts family-name rules. This independent distribution retains its project prefix and records the finding. It does not claim an exception or catalogue acceptance. |
| `case_mapping` | Some inherited extra characters have missing case counterparts. The selected profile is checked independently; Sign uses a separate native resource for whole selected Greek and Cyrillic rows. |
| `missing_small_caps_glyphs` | Screen retains the original partial small-cap feature repertoire. It does not add artificial small capitals for every inherited phonetic character. |
| `nested_components` | Retained source composites are checked through their logical names and actual recursion metadata. They are not decomposed automatically to satisfy a production preference. The [OpenType maximum profile](https://learn.microsoft.com/en-us/typography/opentype/spec/maxp) records component recursion. |
| `transformed_components` | Sign retains native transformed component constructions and their instructions. These include inverted punctuation and source letter constructions. |
| `googlefonts/font_copyright` | Screen preserves the inherited Fira copyright and Reserved Font Name notice instead of replacing it with a catalogue-specific notice pattern. |
| `googlefonts/glyphsets/shape_languages` | The tool tests additional orthographies beyond the selected profile. Screen's failing orthographies are outside that profile. Sign's remaining Yoruba finding concerns U+0329, an alternative below-line input outside the selected CLDR 49 dot-below profile; the selected dot-below plus tone cases are checked separately. The other failing Sign orthographies are outside the profile. |

The CI policy retains these named findings and rejects unexpected failing categories or new selected-language attachment failures. This is a source-preserving build policy; it does not turn the full Google Fonts profile into a clean pass. Numeric repertoire, software shaping, native rendering, participant reading and physical sign measurements remain different kinds of evidence.
