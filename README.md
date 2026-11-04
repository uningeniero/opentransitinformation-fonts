<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Tavrenel Sign and Tavrenel Screen

Two transport typeface families from [Open Transit Information](https://opentransitinformation.org).

Tavrenel Sign uses Cabin 3.001 as its principal source, with selected Fira Sans supplements and source-specific additions. It contains four upright weights: Regular, Medium, SemiBold and Bold. Tavrenel Screen uses Fira Sans 4.301 as its principal source, with four upright weights and their genuine italics.

The release includes TTF and WOFF2 files. The font software is licensed under the SIL Open Font License 1.1. The original copyright notices, Reserved Font Names and contributor records are retained in `licenses/`. Build code is Apache-2.0; original documentation is CC-BY-4.0.

## Use

Install the TTF files for desktop applications, or serve the WOFF2 files with your application. Set the document language and use a shaping engine that applies the native OpenType language, composition, kerning and mark features. The `ss20` feature in Tavrenel Screen selects its transport numeral profile; the default source numerals remain available.

For Greek and Cyrillic sign text, use the separately bundled, unchanged **Source Sans 3 version 3.052**. Select that resource for the complete script run, including its figures, punctuation and marks. Its native family name, genuine four weights and Adobe licence remain separate from Tavrenel Sign. Selecting individual missing glyphs from a fallback stack can mix the partial Greek repertoire inherited from Cabin with a different resource.

The selected release profile contains 1,730 encoded scalars in each Tavrenel Screen cut and 791 in each Tavrenel Sign cut. The native Sign companion covers the 238 scalars required by the selected Greek and Cyrillic profile. These counts describe this repertoire and its software checks; the locale requirements and exact function cases are in `tests/validation-spec.json`.

## Build

Use Python 3.12.14 and the hash-pinned dependencies:

```sh
python -m venv .venv
# Activate the environment using your shell's activation command.
python -m pip install --require-hashes --only-binary=:all: -r requirements-build.lock
python scripts/build_baselines.py --output-dir build/baselines
python scripts/build_release.py --baselines build/baselines --output-dir build/release
python scripts/validate_release.py build/release
```

The first step downloads the exact pinned upstream TTF carriers into an ignored cache and verifies their byte counts and SHA-256 digests. It reproduces 24 comparison files before the public successor build proceeds. All paths used by the build are relative to this repository. `release.json` fixes the numeric version and deterministic font timestamp.

The source records in `sources/` define the numeral profile, mathematical fence, additive contours, canonical composition routes and separate scoped Lithuanian and Yoruba attachment rules. Retained glyph drawings, advances and instructions are checked against the exact carriers. The public Screen successor excludes one unencoded source artwork glyph and explicitly aliases four nonconforming source glyph identifiers. Reordered composite GIDs are compared through named logical records.

This source recipe uses the released Fira 4.301 and Cabin 3.001 TTF carriers. It does not represent recovered native Fira 4.301 drawing masters. The mathematical fence comes from the pinned editable Fira 4.202 source. The Source Sans 3 TTF and WOFF2 files are unchanged official upstream resources. Its web builds omit the TTF hinting programs; the outline, spacing and layout comparisons are recorded separately from binary and hint identity.

## Sources and attribution

- Fira Sans: Mozilla Foundation, Telefonica S.A., Carrois Corporate GbR and bBox Type GmbH. Preserve the original notices under `licenses/fira/`.
- Cabin: the Cabin Project Authors. Preserve the original author, contributor, trademark and OFL records under `licenses/cabin/`.
- Source Sans 3: Adobe and the upstream contributors. Preserve `companions/source-sans-3/LICENSE.md` and its native font metadata.
- CLDR and Unicode character data: the pinned public sources and applicable data terms are identified in `tests/validation-spec.json`. Character reference material supplies identities and language requirements, rather than copied reference-font outlines.
- Source-specific adaptations and release engineering: Open Transit Information, coordinated by Álvaro Marín Abril. Project: [opentransitinformation.org](https://opentransitinformation.org).

The source revisions and exact input digests are recorded in `sources/inputs.json` and the companion provenance record. Google Fonts catalogue submission has separate source and curation requirements; this repository is the independent font distribution.
