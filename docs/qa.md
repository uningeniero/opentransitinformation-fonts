<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Release 1.1.0 engineering checks

Traveller Sign and Traveller Screen use font software version 1.100. The release contains twelve primary cuts in TTF and WOFF2 formats and eight unchanged official Source Sans 3 resources. Screen encodes 1,775 Unicode scalars in each cut; Sign encodes 821. All twelve cuts contain the 319 characters in the pinned Google Fonts Latin Core list.

## Source and production

The editable UFOs contain contours, components, advances, anchors, source bindings and text OpenType rules. CPython 3.12.14 and the hash-pinned dependency lock produce the fonts through Fontmake 3.12.2 and ufo2ft 3.11.0. The separate ttfautohint 1.8.4.16-eb64 executable regenerates instructions after component normalisation. `tools/production.json` records the options. The builder checks that hinting preserves cmap, metrics and layout tables.

The source-edit probe changed one actual Screen Regular GLIF anchor by two units and recompiled it. HarfBuzz measured the corresponding two-unit change in the attached mark position; outlines, horizontal metrics and hint programs stayed unchanged. The original source tree was preserved.

## Serialized functions and native use

The corrected candidate passed 2,379 baseline checks and 520 finite function checks. These cover source and binary bindings, retained drawings and metrics, the selected language profile, canonical composition, Lithuanian positioning, optional Sign tabular figures, Screen small capitals and the source-reviewed mark constructions. The final j-caron successor passed a further 264 targeted checks, including all retained Screen contours and metrics, genuine native small-cap construction, NFC/NFD substitution, unchanged default shaping and inherited pair spacing. Sign and the companion resources are byte-identical to the corrected candidate. The underlying receipts preserve these separate executions and their exact input hashes.

The Windows GDI probe privately selected the twelve actual cuts and matched nine serialized tables for each selected face: name, glyf, OS/2, hmtx, GSUB, GPOS, fpgm, prep and cvt. Temporary font and drawing resources were removed. The fifteen Sign glyphs affected by component normalisation were also drawn at 12, 14, 16, 18, 20 and 24 px in Regular and Bold, alongside the immutable predecessor. The four native images were inspected for missing shapes, clipping, counters, carons and direction changes.

The offline example was checked in Windows Edge 156.0.4314.58 at 390 and 1440 px. The browser's actual font records identified all sixteen intended styles, including the separate Source Sans 3 resource for complete Greek and Cyrillic rows. The checks recorded no external network requests, page errors or horizontal overflow. Sign's `tnum` and Screen's `ss20` declarations were active. These are finite software and rendering checks.

## Fontspector 1.9.0

The full Google Fonts profile includes the real family OFL files. Raw results are retained in [the release QA directory](qa/1.1.0/summary.json), including every severity and the exact reported glyph records.

| Family | Pass | Warn | Fail | Skip | Info |
|---|---:|---:|---:|---:|---:|
| Traveller Screen | 694 | 163 | 24 | 442 | 40 |
| Traveller Sign | 365 | 68 | 0 | 242 | 20 |

Screen's 24 failing subresults comprise eight missing-`smcp` records, eight missing-`c2sc` records and eight language-shaping records. Each language-shaping record includes Church Slavic (`cu_Cyrl`); the SemiBold upright record also includes three Latin orthographies. These are subresult counts, rather than counts of languages or causes. The small-cap lists include phonetic characters and case-linked Latin and Cyrillic letters; the raw metadata identifies each glyph. The genuine native U+01F0 j-caron route is included in this release. The remaining repertoire is partial: no identity substitutions or scaled capitals were added to suppress the findings.

The Church Slavic finding names eighteen missing historical Cyrillic scalars: U+047A-U+0481, U+A640-U+A643, U+A64A-U+A64D and U+A656-U+A657.

The SemiBold upright language record also names Mango (`mge_Latn`), Nateni (`ntm_Latn`) and Longto (`wok_Latn`). It reports attachment failures between Latin small letter open e (U+025B) and combining tilde below (U+0330): the sequence U+025B U+0330 in all three, with grave or acute variants for Nateni and Longto and a macron variant for Longto.

The saved Fontspector 1.9.0 reports use Shaperglot 1.2.2 with Harfrust 0.13.3. An additional read-only diagnostic used HarfBuzz 14.2.1 to trace those four strings in all eight released Screen cuts, without rerunning Fontspector. All 32 runs executed the compiled mark-to-base lookup and ended with coincident base and mark anchors. In SemiBold, the 473-unit base advance, base anchor (260, 0) and mark anchor (-213, 0) require a final mark offset of (0, 0). The [pinned Shaperglot check](https://github.com/googlefonts/shaperglot/blob/357b5d978d9b112d6c460b51becd9bfa4b605a63/shaperglot-lib/src/checks/no_orphaned_marks.rs#L90) classifies a nonspacing mark with both final offsets zero as an orphan. The current binary traces therefore indicate a zero-offset reporting ambiguity for this exact base/mark combination. The original FAIL statuses remain in the full profile.

The full profile also retains separate warnings, including auxiliary-language characters and other attachment cases. The raw reports provide their exact input sequences and statuses.

An additional j-caron plus acute/dot diagnostic is preserved in [the finite diagnostic record](qa/1.1.0/j-caron-diagnostic.json). It recorded sixteen failed comparisons with plain j, whose native shaping selects a different dotless base. Both observed Regular acute runs also select `acutecomb.sc` with a 300-unit advance and zero offset. This spacing-mark result remains an unsupported extra-stack case; the bounded j-caron construction and pair-spacing checks are recorded separately in [the successor checks](qa/1.1.0/j-caron-validation.json).

Family licence, font copyright, OFL copyright/body, licence URL and trailing-space checks pass. The catalogue `METADATA.pb` licence check is skipped because this independent source distribution has no catalogue metadata file.

The QA command preserves FAIL, ERROR and FATAL severities and returns a nonzero status for the unresolved Screen findings. No exclusions or severity overrides apply. Google Fonts curation and contributor requirements remain a separate [catalogue route](google-fonts-route.md).
