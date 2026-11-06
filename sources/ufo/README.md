<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Editable font sources

The twelve UFO 3 directories contain the current Traveller Sign and Traveller Screen sources. Each glyph has editable contours or named components, an advance and any applicable Unicode mappings and anchors. `features.fea` contains the OpenType rules. The `public.glyphOrder` and `public.openTypeCategories` records preserve explicit production order and glyph classes.

Attachment coordinates belong to the GLIF anchors. The attachment-policy records in each UFO's `lib.plist` identify the contextual lookup and anchor class. `scripts/_ufo_features.py` regenerates the corresponding text rules from those anchors before compilation. Explicit `kerningSourceGlyphs` records identify native pair-positioning roles for added canonical compositions; their inherited rules are also present in `features.fea`.

The initial editable contours and native instruction assembly were imported from the pinned 1.0.1 fonts. Per-font import records retain the exact input digest and original metadata. Subsequent constructions retain their source bindings in the affected glyph's library.

Production uses Fontmake/ufo2ft to flatten nested components and decompose transformed components. It then invokes the separate pinned ttfautohint executable to regenerate output instructions. Imported native assembly remains in the UFO as source history; programs tied to the old point order are not copied into the normalised output. The build asserts that hinting leaves cmap, horizontal metrics and layout tables unchanged.

Use the one-command build in the repository README. The source fonts and their derivative drawings use OFL 1.1 with the accompanying original notices. Build code uses Apache-2.0. First-party documentation uses CC-BY-4.0.
