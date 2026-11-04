<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Google Fonts source and catalogue route

Google Fonts catalogue inclusion is separate from this public font distribution.

The current [onboarding guide](https://googlefonts.github.io/gf-guide/onboarding.html) describes a curated route for original new families and a separate upgrade route for existing catalogue families. Renaming a derivative of Fira Sans or Cabin does not establish eligibility as an original new family. An upgrade proposal must be accepted in the relevant upstream source and retain the requirements of that route.

This release provides an editable, deterministic FontTools recipe, source contour records and TTX table sources. It uses the released Fira Sans 4.301 and Cabin 3.001 TTF carriers. It does not provide recovered native Fira 4.301 design masters or establish the source format and Fontmake production requirements of the catalogue route.

The current [QA guidance](https://googlefonts.github.io/gf-guide/qa.html) identifies Fontspector as the primary tool. This release runs its pinned 1.9.0 Google Fonts profile and records actual results, including inherited source features and catalogue-specific findings. A completed tool run does not mean every check passes or that the catalogue has accepted a family.

An eligible upstream proposal would identify the exact retained source revision, original author and notice obligations, editable additions, native language rules and before/after regressions. Upstream acceptance, the applicable source workflow, curation and any actual rights-holder contributor agreement remain separate requirements. No contributor agreement is signed on behalf of a rights holder by this build.

The [OFL modification guidance](https://openfontlicense.org/how-to-modify-ofl-fonts/) and [Google Fonts licence guidance](https://googlefonts.github.io/gf-guide/license-file.html) apply to their respective distribution contexts. The renamed derivatives retain the original OFL notices and inherited Reserved Font Names. Existing source notices are not erased to satisfy a catalogue metadata pattern.
