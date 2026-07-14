# pypdfbox

**Source, issues, and documentation: [github.com/mehdyhaghy/pypdfbox](https://github.com/mehdyhaghy/pypdfbox)**

`pypdfbox` is an Apache 2.0-licensed, Python-native port of
[Apache PDFBox](https://pdfbox.apache.org/) 3.0.x. It mirrors PDFBox's
package layout (`org.apache.pdfbox.cos` → `pypdfbox.cos`), preserves
class names verbatim (`COSDictionary`, `PDDocument`, `PDFParser`,
`PDFRenderer`, `PDStructureTreeRoot`, …), keeps inheritance hierarchies
intact, and maps Java `camelCase` methods one-for-one to Python
`snake_case` — so the API a PDFBox developer already knows is the API
you call here. No JVM, no JPype, no Java subprocess: parser, writer,
content-stream engine, font subsystem, renderer, tagged-PDF model,
signature pipeline, XMP, and CLI tools are all reimplemented in pure
Python. This project is a community port, not an official Apache
release; the underlying design and the test corpus that drives it are
the work of the Apache PDFBox project, tracked centrally in
[`PROVENANCE.md`](PROVENANCE.md).

## Quick start

```sh
pip install pypdfbox
```

```python
from pypdfbox import PDDocument

with PDDocument.load("input.pdf") as doc:
    info = doc.get_document_information()
    info.set_title("Annual Report")
    info.set_author("Engineering")
    print(f"{doc.get_number_of_pages()} pages")
    doc.save("output.pdf")
```

The CLI dispatcher (`pypdfbox info|merge|split|decrypt|version|...`,
mirroring upstream's `org.apache.pdfbox.tools.PDFBox` suite) is
installed alongside.

## Installation

From PyPI:

```sh
pip install pypdfbox
```

Extras:

- `pypdfbox[cjk]` — opt-in marker that consents to network fetches of
  Noto Sans CJK (SIL OFL 1.1) as a last-resort fallback for PDFs that
  reference an unembedded CJK font. The extra carries no Python deps;
  it is only the consent gate. Auto-download is still inert unless you
  also export `PYPDFBOX_CJK_AUTODOWNLOAD=1`. See
  [`docs/install.md`](docs/install.md) for the full matrix.

Native wheels are published for CPython 3.12–3.14 on macOS (x86_64 +
arm64), Linux/glibc (x86_64 + aarch64), and Windows (x86_64). Source
installs require a working C / Rust toolchain for the transitive deps
(`cryptography`, `Pillow`, `skia-python`, `imagecodecs`, `numpy`).
JBIG2 decoding (`/JBIG2Decode`) is supported by a first-party
pure-Python decoder (ported from the Apache-2.0 `apache/pdfbox-jbig2`),
which replaced the GPL-licensed `jbig2-parser` under the
permissive-license policy — no dependency, no native code. See
[`docs/install.md`](docs/install.md) for platform-specific
troubleshooting.

## Build

Source builds use [`uv`](https://docs.astral.sh/uv/) as the package
manager.

```sh
git clone https://github.com/mehdyhaghy/pypdfbox.git
cd pypdfbox
uv sync --all-groups
```

Run the test suite:

```sh
.venv/bin/pytest -q --no-cov
```

(`--no-cov` is the fast pass; drop it to refresh coverage at
`coverage.json`.)

The full developer workflow (lint, coverage, checks that run before
a push) is documented in [`docs/build.md`](docs/build.md).

## Contribute

PRs are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
contribution workflow, the parity test layering (hand-written +
ported upstream tests), and the bookkeeping rules around
[`PROVENANCE.md`](PROVENANCE.md) and [`CHANGES.md`](CHANGES.md).

In short, every change should:

- Match upstream PDFBox class names, package layout, and inheritance.
- Translate `camelCase` to `snake_case`. Nothing else moves.
- For ported files, add a row to `PROVENANCE.md` (pypdfbox path →
  upstream version → upstream Java path).
- For behavioural deviation, add a one-line entry to `CHANGES.md`.
- Ship parity tests in `tests/<module>/test_<class>.py` plus, where
  applicable, ported upstream tests in
  `tests/<module>/upstream/test_<class>.py`.

## Support

This is a community fork-style port, not the upstream Apache project,
so the Apache Jira issue tracker and PDFBox mailing lists are not
appropriate for pypdfbox-specific questions or bugs. Use:

- The GitHub
  [issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues) for
  bug reports and feature requests against pypdfbox.
- The upstream
  [Apache PDFBox project](https://pdfbox.apache.org/) for questions
  about PDF / PDFBox concepts in general, including the
  [PDFBox users mailing list](https://pdfbox.apache.org/mailinglists.html)
  and Stack Overflow's
  [`pdfbox` tag](https://stackoverflow.com/questions/tagged/pdfbox)
  for design-level Q&A — pypdfbox's surface is close enough that
  PDFBox answers usually translate directly.

If you have found a clear pypdfbox-specific bug (parity mismatch,
crash, byte-level divergence), please open a GitHub issue and include
a minimal PDF that reproduces it.

See [`docs/support.md`](docs/support.md) for a longer breakdown of
where to ask which kind of question.

## Known Limitations and Problems

See the
[issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues) for the
full list. The most common stable-state divergences and gaps are:

1. **Symbol / ZapfDingbats glyph coverage is partial.** Non-embedded
   Standard 14 `/Symbol` and `/ZapfDingbats` references substitute
   through the bundled `DejaVuSans.ttf` (Bitstream Vera + DejaVu
   public-domain — permissive). Coverage is roughly 100% of the
   Zapf Dingbats Unicode block and ~84% of the Adobe Symbol glyph
   set (Greek + math operators). The remaining 16% of Symbol glyphs
   render as `.notdef`. Bundling a true Symbol replacement would
   require pulling in a non-permissively-licensed font; we do not.

2. **ICU bidi reordering is not ported.** Text extraction uses
   Python's stdlib `unicodedata.bidirectional` for RTL detection and
   paragraph reversal. Pure-RTL and pure-LTR runs reorder correctly;
   mixed-LTR+RTL Unicode bidi paragraph reordering can differ from
   what Acrobat (or upstream PDFBox, which uses ICU) produces. This
   is a deliberate divergence — adding ICU as a runtime dependency
   would conflict with the permissive-license-only policy.

3. **Renderer pixel-exact parity is not portable.** Upstream's JUnit
   tests compare rendered output to bundled TIFF / PNG reference
   images produced by Java AWT. pypdfbox renders through Pillow plus a
   Skia-backed `_aggdraw_compat` rasteriser, so byte-equivalent
   output is unachievable. Parity is enforced *structurally* (page
   count, MediaBox, Rotation, Contents shape, Resources keys,
   save-reload round-trip) rather than pixel-by-pixel. See
   [`CHANGES.md`](CHANGES.md) → "Active divergences".

4. **Standard 14 fallback fonts are bundled.** When a PDF references
   a Standard 14 face (`Helvetica`, `Times-Roman`, `Courier`, …)
   without embedding the program, pypdfbox substitutes via Liberation
   TTFs bundled in `pypdfbox/pdmodel/font/resources/` (~4 MB on
   install). Liberation is permissively licensed; this matches
   upstream's behaviour of serving Standard 14 via a bundled fallback
   when the host system lacks the font.

5. **CJK auto-download is opt-in.** PDFs referencing an unembedded
   CJK font produce `.notdef` glyphs unless the user both installs
   `pypdfbox[cjk]` and sets `PYPDFBOX_CJK_AUTODOWNLOAD=1`. With both
   set, the fontbox CJK loader downloads Noto Sans CJK (pinned to
   release `Sans2.004`, SIL OFL 1.1) from the upstream GitHub
   releases on first use, verifies the SHA-256, and caches per-user.

6. **No PDF/A or PDF/UA conformance validation.** Apache PDFBox 4.0
   removes the Preflight module; pypdfbox follows that decision.
   Validation is out of scope and not bundled. Downstream users who
   need it wire in whichever external validator they choose
   (pypdfbox stays validator-agnostic, in keeping with the
   permissive-license-only rule).

The full active-divergences list lives in
[`CHANGES.md` → Active divergences](CHANGES.md#active-divergences-vs-upstream).
Open in-flight gaps that are *fixable but not yet done* are tracked on
the [issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues).

## License

Apache License, Version 2.0 — same as upstream PDFBox. See
[`LICENSE`](LICENSE) for the full text and [`NOTICE`](NOTICE) for the
required attribution that downstream redistributors must propagate.

All runtime dependencies are permissively licensed (Apache-2.0 /
MIT / BSD family).

Ported files are tracked centrally in [`PROVENANCE.md`](PROVENANCE.md)
(pypdfbox path → upstream PDFBox version → upstream Java path), which
satisfies Apache 2.0 §4(b) ("notices stating that You changed the
files") in one place. Source files carry no per-file license headers.

Substantive behavioural deviations from upstream are recorded in
[`CHANGES.md`](CHANGES.md).

## Export control

This distribution includes cryptographic software. The country in
which you currently reside may have restrictions on the import,
possession, use, and/or re-export to another country of encryption
software. BEFORE using any encryption software, please check your
country's laws, regulations and policies concerning the import,
possession, or use, and re-export of encryption software, to see if
this is permitted. See <https://www.wassenaar.org/> for more
information.

The U.S. Government Department of Commerce, Bureau of Industry and
Security (BIS) has classified this software as Export Commodity
Control Number (ECCN) 5D002.C.1, which includes information security
software using or performing cryptographic functions with asymmetric
algorithms. The form and manner of this open-source distribution
makes it eligible for export under the License Exception ENC
Technology Software Unrestricted (TSU) exception (see the BIS Export
Administration Regulations, Section 740.13) for both object code and
source code.

The cryptographic surfaces in pypdfbox are:

- PDF Standard Security Handlers (r2–r6: RC4 40/128, AES-128/256
  CBC) and the public-key security handler, implemented in
  `pypdfbox.pdmodel.encryption` on top of the
  [`cryptography`](https://pypi.org/project/cryptography/) library
  (Apache-2.0 / BSD).
- Digital signature read + write (PKCS#7 / CAdES / PAdES, RFC 3161
  timestamps, PAdES-LTV `/DSS`+`/VRI` revocation-info bundling),
  implemented in `pypdfbox.pdmodel.interactive.digitalsignature` on
  top of `cryptography`'s PKCS#7 builders.

Upstream PDFBox uses the Java Cryptography Architecture (JCA) and
Bouncy Castle for the same surfaces; pypdfbox uses PyCA
`cryptography`. Functionally equivalent; the export classification is
unchanged.

## Acknowledgement of upstream

pypdfbox is a port of [Apache PDFBox](https://pdfbox.apache.org/),
maintained by the Apache Software Foundation. The COS model, parser
architecture, content-stream operators, accessibility model, font
subsystem, signature pipeline, and rendering design that this project
mirrors are the cumulative work of the PDFBox maintainers and
contributors. Per-file porting attribution lives in
[`PROVENANCE.md`](PROVENANCE.md) (one entry per ported source file
and per ported test file, recording the upstream PDFBox version and
Java path). The project-level attribution that must propagate to
downstream redistributors lives in [`NOTICE`](NOTICE).

This is a community port. It is not endorsed by, affiliated with, or
released by the Apache Software Foundation. Bugs in pypdfbox are
bugs in pypdfbox, not in Apache PDFBox.
