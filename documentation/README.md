<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Sources and production

Traveller Sign and Traveller Screen are maintained by [Open Transit Information](https://opentransitinformation.org). Font sources use UFO 3; the contour, component, anchor and feature structure is documented in [the source guide](../sources/ufo/README.md). Original copyright and licence notices are retained in [the family licences](../licenses/), [AUTHORS.txt](../AUTHORS.txt) and [CONTRIBUTORS.txt](../CONTRIBUTORS.txt).

Use CPython 3.12.14 and run the open build from the repository root:

```sh
bash sources/build.sh --family sign
python build.py validate --family sign
python build.py reproduce --family sign
python build.py qa --family sign
```

Use `--family screen` for Traveller Screen, or omit the option to build both families. Builds use hash-pinned dependencies in a versioned environment. Fontmake/ufo2ft compile the editable sources; the pinned external ttfautohint executable generates output instructions. The release policy fixes the version and timestamp. A fixed Python hash seed controls hash-dependent ordering.

With `--family sign`, TTFs and the family OFL are written to `build/production-VERSION-sign/fonts/ttf/travellersign/`; use the corresponding `-screen` and `travellerscreen` paths for Screen. An all-family build uses `build/production-VERSION/`. WOFF2 files use the corresponding `fonts/woff2/` directory. `build-manifest.json` records the exact sources, tools and output digests. Reproduction performs a second independent build and compares every TTF and WOFF2 byte. The full Google Fonts profile retains all severities, without exclusions or severity overrides.

The Ubuntu workflow checks each family separately and preserves its build, validation, reproduction and raw QA results. Catalogue requests and contributor requirements are recorded in [the Google Fonts route](../docs/google-fonts-route.md).
