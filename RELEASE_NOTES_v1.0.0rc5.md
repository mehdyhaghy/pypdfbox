# pypdfbox 1.0.0rc5 — Release Notes

Fifth release candidate. Delta over
[1.0.0rc4](RELEASE_NOTES_v1.0.0rc4.md) — packaging-metadata only. No
source, API, or behavioral change; the library is identical to rc4.

## Changed (packaging metadata)

- **PEP 639 license metadata.** `pyproject.toml` now declares
  `license = "Apache-2.0"` (an SPDX expression) with
  `license-files = ["LICENSE", "NOTICE"]`, replacing the older
  file-based `license = { file = "LICENSE" }` form. The published
  distribution now carries a clean `License-Expression: Apache-2.0`
  (Metadata-Version 2.4) instead of embedding the full license text in
  the `License` field. `LICENSE` and `NOTICE` are still bundled under
  `.dist-info/licenses/`. The now-redundant, PEP-639-incompatible
  `License :: OSI Approved :: Apache Software License` classifier is
  removed. The build backend floor is raised to `hatchling>=1.27` for
  PEP 639 support.
- **Maintainer email removed from published metadata.** The
  `project.authors` entry keeps the name but drops the email address,
  so it no longer appears in the distribution's `Author-email` field
  (a spam-scrape vector). Attribution is unchanged in `LICENSE` /
  `NOTICE` / `PROVENANCE.md`.
