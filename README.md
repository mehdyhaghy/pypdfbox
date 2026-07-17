# pypdfbox

[![PyPI](https://img.shields.io/pypi/v/pypdfbox)](https://pypi.org/project/pypdfbox/)
[![Downloads](https://img.shields.io/pypi/dm/pypdfbox)](https://pypistats.org/packages/pypdfbox)
[![License](https://img.shields.io/pypi/l/pypdfbox)](https://github.com/mehdyhaghy/pypdfbox/blob/main/LICENSE)

**Source, issues, and documentation: [github.com/mehdyhaghy/pypdfbox](https://github.com/mehdyhaghy/pypdfbox)**

`pypdfbox` is a pure-Python PDF library and command-line toolbox. It
reads, writes, and edits PDF files: split, merge, extract text and
images, render pages to images, fill forms, add and verify digital
signatures, encrypt and decrypt, create tagged/accessible PDFs, and
generate PDFs from text or images — with no JVM, no external
binaries, and permissively licensed (Apache 2.0) dependencies only.

It is a Python-native port of [Apache PDFBox](https://pdfbox.apache.org/)
3.0.x, which means you get a battle-tested API surface: the same
classes (`PDDocument`, `PDPage`, `PDFRenderer`, `PDFTextStripper`, …)
and the same behavior, with Java `camelCase` mapped to Python
`snake_case`. Answers written for PDFBox usually translate directly.
This project is a community port, not an official Apache release.

## Install

```sh
pip install pypdfbox
```

Using it only from the command line? Install it as an isolated tool
instead — same package, and it keeps the `pypdfbox` command out of
your project environments:

```sh
uv tool install pypdfbox    # or: pipx install pypdfbox
```

Wheels cover CPython 3.12–3.14 on macOS (x86_64 + arm64), Linux/glibc
(x86_64 + aarch64), and Windows (x86_64). See
[`docs/install.md`](docs/install.md) for source builds, the optional
`pypdfbox[cjk]` extra (opt-in CJK font auto-download), and
troubleshooting.

## Command line: the 10 most common operations

Installing the package puts a `pypdfbox` command on your `PATH`.
Every command below is copy-paste runnable; use
`pypdfbox <command> --help` for all options.

**1. Split a PDF** — one file per page by default; `-split N` makes
N-page chunks; `-startPage`/`-endPage` limit the range:

```sh
pypdfbox split -i report.pdf
pypdfbox split -i report.pdf -split 10 -outputPrefix chunk
```

**2. Merge PDFs** — pages are concatenated in the order given
(bookmarks, forms, and links are carried over):

```sh
pypdfbox merge -i part-a.pdf part-b.pdf part-c.pdf -o combined.pdf
```

**3. Extract text** — writes `report.txt` next to the input; `-console`
prints to stdout, `-html`/`-md` switch the output format, `-sort`
orders text by position on the page:

```sh
pypdfbox extracttext -i report.pdf
pypdfbox extracttext -i report.pdf -console -startPage 2 -endPage 5
```

**4. Inspect a PDF** — page count, PDF version, encryption status, and
the document info (title, author, dates); `-output json` for scripts:

```sh
pypdfbox info report.pdf
pypdfbox info report.pdf -metadata -output json
```

**5. Convert pages to images** — one image per page (JPEG by default;
`-format png` for PNG), at the DPI you choose:

```sh
python -m pypdfbox.tools.pdf_to_image -i report.pdf -dpi 150 -format png
```

**6. Extract embedded images** — pulls every image out of the PDF into
separate files:

```sh
python -m pypdfbox.tools.extract_images -i report.pdf -prefix figure
```

**7. Encrypt (password-protect)** — set an owner password and an
optional user password; `-can*` flags tune permissions like printing:

```sh
pypdfbox encrypt -i report.pdf -o locked.pdf -O ownerpass -U userpass
pypdfbox encrypt -i report.pdf -o locked.pdf -O ownerpass --no-canPrint
```

**8. Decrypt** — remove password protection (requires a password that
unlocks the document):

```sh
pypdfbox decrypt -i locked.pdf -o unlocked.pdf -password ownerpass
```

**9. Images to PDF** — one page per image, sized to the image or a
standard page:

```sh
pypdfbox imagetopdf -i scan-1.png scan-2.png -o scans.pdf
```

**10. Text file to PDF** — plain text in, paginated PDF out:

```sh
pypdfbox texttopdf -i notes.txt -o notes.pdf
```

More tools: `listbookmarks` (print the outline tree), `pdfdebugger`
(interactive structure viewer), `writedecodedstream` (decompress all
streams for inspection), `version`. The full CLI reference lives in
[`docs/guides/cli.md`](docs/guides/cli.md).

## Python quick start

```python
from pypdfbox import PDDocument

with PDDocument.load("input.pdf") as doc:
    info = doc.get_document_information()
    info.set_title("Annual Report")
    info.set_author("Engineering")
    print(f"{doc.get_number_of_pages()} pages")
    doc.save("output.pdf")
```

Extract text:

```python
from pypdfbox import PDDocument
from pypdfbox.text import PDFTextStripper

with PDDocument.load("input.pdf") as doc:
    text = PDFTextStripper().get_text(doc)
```

Task-oriented guides with complete examples:

- [Text extraction](docs/guides/text-extraction.md)
- [Merging and splitting](docs/guides/merging-splitting.md)
- [Rendering pages to images](docs/guides/rendering.md)
- [Forms (AcroForm)](docs/guides/forms.md)
- [Encryption and passwords](docs/guides/encryption.md)
- [Digital signatures](docs/guides/signing.md)
- [Tagged PDF and accessibility](docs/guides/tagged-pdf.md)
- [Embedded files and attachments](docs/guides/embedded-files.md)

Coming from Java PDFBox, or from `pypdf` / `pdfminer.six` /
`reportlab`? [`docs/migration.md`](docs/migration.md) maps the idioms
side by side.

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

## Support

Use the GitHub
[issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues) for
bug reports and feature requests. If you have found a clear bug
(crash, wrong output, parity mismatch with PDFBox), please attach a
minimal PDF that reproduces it.

Because the API mirrors Apache PDFBox, general "how do I do X with
PDFBox" answers — the
[PDFBox users mailing list](https://pdfbox.apache.org/mailinglists.html)
archives and Stack Overflow's
[`pdfbox` tag](https://stackoverflow.com/questions/tagged/pdfbox) —
usually translate directly (rename `camelCase` methods to
`snake_case`). pypdfbox is a community port, so please don't file
pypdfbox bugs with the Apache project. See
[`docs/support.md`](docs/support.md) for the full breakdown.

## Contributing and development

PRs are welcome. Source builds use
[`uv`](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/mehdyhaghy/pypdfbox.git
cd pypdfbox
uv sync --all-groups
.venv/bin/pytest -q --no-cov   # run the test suite
```

[`docs/build.md`](docs/build.md) covers the developer workflow (lint,
coverage, pre-push checks), and [`CONTRIBUTING.md`](CONTRIBUTING.md)
covers the contribution rules — in particular that changes must match
upstream PDFBox naming and behavior, and how ported code is tracked
in [`PROVENANCE.md`](PROVENANCE.md) and behavioral deviations in
[`CHANGES.md`](CHANGES.md).

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
