<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Traveller font bundle 1.1.0

Traveller Sign and Traveller Screen are transport typeface families from [Open Transit Information](https://opentransitinformation.org). The font software version is 1.100.

Install the required TTF files from `fonts/ttf/travellersign/` or `fonts/ttf/travellerscreen/` using the operating system font installer. Sign has four upright weights; Screen has four upright weights and their genuine italics. Select the actual style in the application.

For a website, serve the WOFF2 files and use `examples/fonts.css`. Open `examples/index.html` for the included specimens. Sign offers optional `tnum` tabular figures and `pnum` proportional figures. Screen offers the optional `ss20` numeral profile.

For the selected Greek and Cyrillic sign rows, explicitly select the separate Source Sans 3 resource for the complete script run, including figures, punctuation and marks. Its files are in `companions/source-sans-3/fonts/`. The native name and version 3.052 remain unchanged. The TTF files and unhinted WOFF2 builds are separate, unchanged official upstream resources.

Keep the family `OFL.txt` files and the original Fira, Cabin, Lato and Adobe notices in `licenses/` and `companions/source-sans-3/LICENSE.md` with redistribution. Font software uses OFL 1.1; CSS code uses Apache-2.0; first-party documentation uses CC-BY-4.0.

Source construction and release engineering: Open Transit Information, coordinated by Álvaro Marín Abril. The original source families and contributors retain the authorship and notices recorded in the accompanying licences. Editable UFOs and the one-command build are in the [technical font repository](https://github.com/uningeniero/opentransitinformation-fonts). Exact font digests are in `fonts/checksums.json`; finite checks and residuals are in `docs/qa.md`.
