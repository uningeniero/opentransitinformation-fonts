<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OTI Traveller font bundle 1.0.1

OTI Traveller Sign and OTI Traveller Screen are transport typeface adaptations from [Open Transit Information](https://opentransitinformation.org). The font software version is 1.001.

Install the required TTF files from `fonts/otitravellersign/` or `fonts/otitravellerscreen/` using your operating system's font installer. OTI Traveller Sign has four upright weights; OTI Traveller Screen has four upright weights and their genuine italics. Select the actual style in your application.

For a website, serve the WOFF2 files and use the declarations in `examples/fonts.css`. Open `examples/index.html` for the included specimens. The `ss20` feature enables the optional Screen numeral profile.

For Greek and Cyrillic sign rows, explicitly select the separate Source Sans 3 resource for the complete intended script run, including its figures, punctuation and marks. Use `companions/source-sans-3/fonts/`. Preserve deliberate Latin versus Cyrillic and mixed-script choices; a missing-glyph fallback stack does not provide the same resource selection.

The Source Sans 3 files retain their original name and version 3.052. The TTF files and unhinted WOFF2 web builds are separately verified, unchanged official upstream resources. The companion provenance record identifies their exact source and digests.

The font software uses the SIL Open Font License 1.1. Keep the original Fira, Cabin and Adobe notices in `licenses/` and `companions/source-sans-3/LICENSE.md` with redistribution. The included CSS code is Apache-2.0 and original documentation is CC-BY-4.0. Typeface sources, build instructions and release records are in the [technical font repository](https://github.com/uningeniero/opentransitinformation-fonts).

Source-specific adaptations and release engineering: Open Transit Information, coordinated by Álvaro Marín Abril. The source families and their contributors retain the authorship and notices recorded in the accompanying licences. Exact file digests are in `fonts/checksums.json`; the selected repertoire and source boundaries are described in `docs/qa.md`.
