<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Traveller Sign and Traveller Screen

Two transport typeface families from [Open Transit Information](https://opentransitinformation.org).

Traveller Sign has four upright weights: Regular, Medium, SemiBold and Bold. Traveller Screen has those four weights and their genuine italics. The distribution provides desktop TTFs, WOFF2 web fonts and twelve editable UFO sources.

Release 1.1.0 uses font software version 1.100. Source, binaries, checksums and the matching [GitHub release](https://github.com/uningeniero/opentransitinformation-fonts/releases/tag/v1.1.0) identify the same version. Earlier releases remain available through their immutable tags and assets.

## Use

Install the required TTF files, or serve the WOFF2 files with your application. The declarations in `examples/fonts.css` identify each real weight and style. Set the document language so the shaping engine can apply its language rules.

Sign retains proportional default figures. Its optional `tnum` feature selects tabular figures; `pnum` restores proportional figures. Screen retains its default numerals and offers the optional `ss20` numeral profile. Select an available genuine style rather than synthesising bold or italic.

For the selected Greek and Cyrillic sign rows, choose the separately bundled **Source Sans 3 version 3.052** for the complete script run, including its figures, punctuation and marks. Its native family name, four weights and Adobe notices remain separate. The companion TTF and WOFF2 resources are unchanged official upstream files.

The repertoire and finite software checks are recorded in `tests/validation-spec.json`, `fonts/manifest.json` and `docs/qa.md`.

## Build

Use CPython 3.12.14 and the complete hash-pinned dependency lock:

```sh
python -m venv .venv
# Activate the environment using your shell's activation command.
python -m pip install --require-hashes --only-binary=:all: -r requirements-build.lock
python scripts/build_ufo.py
python scripts/validate_ufo.py build/production-1.1.0
python scripts/check_reproduction.py build/production-1.1.0
```

The production command reads the editable UFO contours, components, anchors and text features. It uses Fontmake/ufo2ft, followed by the separate ttfautohint executable. `release.json` fixes the version and timestamp; `tools/production.json` identifies the tools and options. Validation separately checks the immutable 1.0.1 predecessor.

Read `sources/ufo/README.md` for the source structure, recorded conversion inputs and subsequent constructions. Component normalisation can change point order; output hints are regenerated after that step.

The full primary Google Fonts profile runs without check exclusions or severity overrides. Raw FAIL, ERROR and FATAL findings retain their severity and produce a nonzero QA command status. Their exact disposition belongs in `docs/qa.md`; a recorded residual does not establish catalogue acceptance.

## Sources and licences

Font software and derivative drawings use the SIL Open Font License 1.1. Original notices, Reserved Font Names and contributor records accompany the fonts. Build code and CSS use Apache-2.0; first-party documentation uses CC-BY-4.0.

Keep the family OFL files and the copyright, Reserved Font Name and contributor notices in [NOTICE.md](NOTICE.md), `licenses/` and `companions/source-sans-3/LICENSE.md` with redistribution. Technical source and contributor records remain in [the source documentation](sources/ufo/README.md).

- The selected language data uses the pinned CLDR and Unicode sources in `tests/validation-spec.json`. The pinned Google Fonts Latin Core character list and its Apache-2.0 licence are identified in `tests/data/glyphsets-provenance.json`.
- Source construction and release engineering are coordinated by Álvaro Marín Abril for Open Transit Information. Project: [opentransitinformation.org](https://opentransitinformation.org).

AI coding tools assisted source conversion, build implementation and QA analysis. Source records identify the retained upstream material and specific additions. Their copyright and licence obligations remain in force. The [catalogue route](docs/google-fonts-route.md) has separate curation, contributor and disclosure requirements.
