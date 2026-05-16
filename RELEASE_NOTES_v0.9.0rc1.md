# pypdfbox 0.9.0rc1 — Release Notes

**First public release candidate of pypdfbox — a Python-native port of Apache PDFBox 3.0.x.**

---

## What it is

`pypdfbox` is a direct port of [Apache PDFBox](https://pdfbox.apache.org/) to pure Python. No JVM, no JPype, no shell-out to a Java process — the COS object model, parser, writer, content-stream engine, font subsystem, renderer, tagged-PDF accessibility model, signature pipeline, and CLI tools are all reimplemented in Python while preserving PDFBox's package layout, class names, inheritance hierarchies, and method semantics. A developer experienced with PDFBox should recognise pypdfbox at roughly 85–90% conceptual familiarity. The one consistent translation is naming: Java `camelCase` becomes Python `snake_case`. Everything else — `COSDictionary`, `PDDocument`, `PDFParser`, `PDFRenderer`, `PDStructureTreeRoot`, lazy COS loading, incremental save with xref preservation, object streams, ToUnicode mapping, Type0/CID font handling — is the same shape upstream PDFBox developers already know.

---

## What works

Numbers from `.parity/snapshot.txt` against upstream Apache PDFBox 3.0 HEAD:

- **Class parity: 1,116 / 1,222 — 100% of the in-scope surface.** The unmapped remainder is `org.apache.pdfbox.preflight.*`, removed from PDFBox 4.0 and intentionally out of scope. PDF/A / PDF/UA conformance validation is similarly out of scope — pypdfbox ships permissive-license components only and stays validator-agnostic; downstream users wire up whichever validator they choose.
- **Method parity: 99.0%** (8,725 / 8,817 matched).
- **Tests: 30,958+ passing, 14 skipped** (each skip carries a one-line documented reason in the test source).
- **Line coverage: 90.22% global**, ~99% on the stable parser + writer + pdmodel + contentstream + text + fontbox + rendering + xmpbox + tools core.
- **All 14 Standard 14 fonts substitute properly** out of the box via bundled Liberation Sans/Serif/Mono (regular, bold, italic, bold-italic) and DejaVuSans for symbolic glyph coverage.
- **Tkinter debugger fully ported.** The Swing `PDFDebugger` UI (tree model, page pane, stream pane, hex viewer) ships as a Python-native widget toolkit equivalent.
- **PDF parsing** — `BaseParser → COSParser → PDFParser`, `PDFStreamParser`, xref streams, hybrid-reference recovery, lenient malformed-input handling.
- **PDF writing** — full save, incremental save with byte-range preservation, xref streams, object streams, `ContentStreamWriter`.
- **Encryption** — Standard Security Handler r2–r6 (RC4 40/128-bit, AES-128/256 CBC), public-key handler, crypt filters.
- **Digital signatures** — `PDSignature` write-side, ByteRange placeholder pipeline, PKCS#7 verification surface, seed values, external signing, PAdES helpers.
- **Content streams** — text-state, graphics-state, path, color, shading, marked-content, inline images, including the `sh` shading operator.
- **Text extraction** — `PDFTextStripper`, `PDFTextStripperByArea`, marked-content extractor, `/Differences`-aware decode, width-based word spacing.
- **Rendering** — `PDFRenderer` page rasterisation, text, form XObjects, clip regions, inline images, patterns, shadings, soft masks, blend modes, Type1/Type1C glyphs (Pillow + aggdraw backend).
- **qpdf integration scaffold** (Apache 2.0) in place for downstream `qpdf --check` / `qpdf --qdf` validation pipelines. No PDF/A / PDF/UA validator is bundled — that choice is intentionally left to the downstream user.

---

## What's known to be incomplete

These are the substantive gaps you should know about before depending on this RC. See `CHANGES.md` "Project status" for the live picture.

- **ICC color-conversion math** — ICC profiles parse, but full ICC-to-device colorimetric transforms are not yet implemented; rendering paths fall back to device-RGB approximations.
- **Full PDF/A conformance from the writer** — the writer can produce structurally valid tagged PDFs, but does not yet guarantee a clean conformance report across all PDF/A-1/2/3/4 levels without manual remediation. Choice of external conformance validator is left to the user (pypdfbox itself stays validator-agnostic per the permissive-license rule).
- **ICC v4 chunked profile parsing** — v2 profiles round-trip; v4 chunked profiles are partially supported.

For everything else, refer to the **Project status** block at the top of `CHANGES.md` — that is the canonical, wave-by-wave updated view.

---

## Installation

This is a **pre-release**, so pip needs `--pre`:

```sh
pip install --pre pypdfbox==0.9.0rc1
```

Or pin the exact version:

```sh
pip install pypdfbox==0.9.0rc1
```

Python 3.14+ is required. Runtime dependencies (all permissive — Apache 2.0 / BSD / MIT / HPND):

- `cryptography>=42`
- `Pillow>=12.2.0`
- `fontTools>=4`
- `aggdraw>=1.3`
- `jbig2-parser`

---

## Migration from upstream PDFBox

The only translation rule is mechanical: **Java `camelCase` becomes Python `snake_case`.** Class names, package paths, inheritance, and behaviour are preserved verbatim.

| PDFBox (Java) | pypdfbox (Python) |
|---|---|
| `org.apache.pdfbox.cos.COSDictionary` | `pypdfbox.cos.COSDictionary` |
| `org.apache.pdfbox.pdmodel.PDDocument` | `pypdfbox.pdmodel.PDDocument` |
| `org.apache.fontbox.ttf.TrueTypeFont` | `pypdfbox.fontbox.ttf.TrueTypeFont` |
| `doc.saveIncremental(out)` | `doc.save_incremental(out)` |
| `catalog.getDocumentCatalog()` | `catalog.get_document_catalog()` |
| `Loader.loadPDF(file)` | `Loader.load_pdf(file)` *(or `PDDocument.load(file)`)* |

Inheritance hierarchies are intact (`BaseParser → COSParser → PDFParser`), so subclass-based extensions ported from Java keep working. The `ICOSVisitor` protocol exposes `visit_from_object` from the start (a PDFBox 4.0 alignment).

A typical port of a PDFBox snippet:

```java
// Java / PDFBox
try (PDDocument doc = Loader.loadPDF(new File("in.pdf"))) {
    PDDocumentInformation info = doc.getDocumentInformation();
    info.setTitle("Annual Report 2025");
    doc.save("out.pdf");
}
```

```python
# Python / pypdfbox
from pypdfbox import PDDocument

with PDDocument.load("in.pdf") as doc:
    info = doc.get_document_information()
    info.set_title("Annual Report 2025")
    doc.save("out.pdf")
```

---

## Acknowledgements

`pypdfbox` exists because of work by:

- **The Apache PDFBox project** — the source code we ported under Apache 2.0. See `NOTICE` and `PROVENANCE.md` for per-file attribution.
- **Liberation Fonts** (Red Hat) — bundled Sans/Serif/Mono families that substitute for the Standard 14.
- **DejaVu Fonts** — bundled `DejaVuSans` for extended Unicode and symbolic glyph coverage.
- **fontTools** — TTF/CFF/OTF/Type 1 table parsing.
- **Pillow** (and `aggdraw`) — the rasterisation canvas backing `PDFRenderer`.
- **cryptography** — primitives for `StandardSecurityHandler`, public-key handler, and PKCS#7 signature verification.

Full license texts ship under `LICENSE` and in `pypdfbox/resources/ttf/`.

---

## Reporting issues

Please file bugs, parity gaps, and questions at the GitHub issue tracker:

**https://github.com/mehdyhaghy/pypdfbox/issues**

When reporting a parity issue, include:

1. The minimal PDF that reproduces the problem (or the exact PDFBox Java snippet whose output you expect to match).
2. The Java PDFBox version you're comparing against.
3. The pypdfbox version (`python -c "import pypdfbox; print(pypdfbox.__version__)"`).

---

## What to expect before 0.9.0 final

This RC exists to surface integration issues against real-world PDF corpora. Between `0.9.0rc1` and `0.9.0` final we expect to:

- Close the ICC color-math gap so rendered raster output matches PDFBox at pixel parity on color-managed inputs.
- Tighten writer output so a clean PDF/A round-trip is achievable without external remediation for the common conformance levels.
- Drive method parity from 99.0% toward 100% on the remaining debugger inner-helper surface.

No public API breakage is planned between this RC and `0.9.0`.
