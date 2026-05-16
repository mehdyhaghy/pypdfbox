# pypdfbox

**Apache 2.0**-licensed, Python-native port of Apache PDFBox 3.0.x.

> **Status:** approaching 0.9.0 release candidate. 1,116 of 1,222 upstream Java classes mapped (100% of the in-scope surface — the unmapped remainder is `preflight.*`, which PDFBox 4.0 removes). Method parity 97.3%. Line coverage 90.22% global / ~99% on the parser-writer-pdmodel-contentstream-text-fontbox-rendering-xmpbox-tools core. 30,134 tests passing, 12 documented skips, 0 local TODOs.

## What this is

`pypdfbox` is a direct port of [Apache PDFBox](https://pdfbox.apache.org/) to pure Python. No JVM, no JPype, no shell-out to a Java process — the COS object model, parser, writer, content-stream engine, font subsystem, renderer, tagged-PDF accessibility model, signature pipeline, and CLI tools are all reimplemented in Python while preserving PDFBox's package layout, class names, inheritance hierarchies, and method semantics. A developer experienced with PDFBox should recognise pypdfbox at roughly 85–90% conceptual familiarity. The one consistent translation is naming: Java `camelCase` becomes Python `snake_case`. Everything else — `COSDictionary`, `PDDocument`, `PDFParser`, `PDFRenderer`, `PDStructureTreeRoot`, lazy COS loading, incremental save with xref preservation, object streams, ToUnicode mapping, Type0/CID font handling — is the same shape upstream PDFBox developers already know.

It exists because Python projects that want PDFBox-level capabilities currently have three bad options: ship a JVM with their app, depend on a Java microservice, or stitch together half a dozen narrower libraries (`pypdf` for parsing, `reportlab` for writing, `pdfminer.six` for text, `pdfplumber` for layout, etc.) that don't share an object model. `pypdfbox` gives you one library with PDFBox's surface area.

## Quick start

```sh
pip install pypdfbox
```

```python
from pypdfbox import PDDocument

# Read a PDF, edit its metadata, and save under a new path.
with PDDocument.load("input.pdf") as doc:
    info = doc.get_document_information()
    info.set_title("Annual Report 2025")
    info.set_author("Engineering")
    print(f"{doc.get_number_of_pages()} pages")
    doc.save("output.pdf")
```

Rotate every page 90° clockwise:

```python
from pypdfbox import PDDocument

with PDDocument.load("input.pdf") as doc:
    for page in doc.get_pages():
        page.set_rotation((page.get_rotation() + 90) % 360)
    doc.save("rotated.pdf")
```

Extract text:

```python
import io
from pypdfbox import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

with PDDocument.load("input.pdf") as doc:
    buf = io.StringIO()
    PDFTextStripper().write_text(doc, buf)
    print(buf.getvalue())
```

The CLI dispatcher (`pypdfbox info|merge|split|decrypt|version|…`, plus the rest of the upstream `pdfbox` command suite) is installed alongside.

## API compatibility

The translation rule is mechanical and the only one: Java `camelCase` becomes Python `snake_case`. Class names, package paths, inheritance, and behaviour are preserved verbatim.

| PDFBox (Java) | pypdfbox (Python) |
|---|---|
| `org.apache.pdfbox.cos.COSDictionary` | `pypdfbox.cos.COSDictionary` |
| `org.apache.pdfbox.pdmodel.PDDocument` | `pypdfbox.pdmodel.PDDocument` |
| `org.apache.fontbox.ttf.TrueTypeFont` | `pypdfbox.fontbox.ttf.TrueTypeFont` |
| `doc.saveIncremental(out)` | `doc.save_incremental(out)` |
| `catalog.getDocumentCatalog()` | `catalog.get_document_catalog()` |
| `Loader.loadPDF(file)` | `Loader.load_pdf(file)` *(or `PDDocument.load(file)`)* |

Inheritance hierarchies are intact (`BaseParser → COSParser → PDFParser`), so subclass-based extensions ported from Java keep working. The `ICOSVisitor` protocol exposes `visit_from_object` from the start (a 4.0 alignment — see [§ Differences from upstream](#differences-from-upstream)).

## Feature matrix

Everything in scope ships. The only `planned` rows are subsystems whose underlying codec choice is awaiting an explicit user decision (see PRD §3.7.1).

| Area | Status | Notes |
|---|---|---|
| COS object model (`COSDictionary`, `COSArray`, `COSStream`, `COSDocument`, …) | done | Full lazy graph; visitor `visit_from_object` from day one. |
| `io` random-access (file, mmap, buffer, view, scratch) | done | Thin stdlib adapters over `io.BytesIO`, `BufferedReader`, `mmap`, `SpooledTemporaryFile`. |
| Parser (`BaseParser → COSParser → PDFParser`, `PDFStreamParser`, xref-stream + hybrid-reference, malformed recovery) | done | Lenient parsing matches upstream recovery paths. |
| Writer (full save, incremental save, xref streams, object streams, `ContentStreamWriter`) | done | Incremental save preserves original byte ranges. |
| Filters (`FlateDecode`, `ASCIIHexDecode`, `ASCII85Decode`, `RunLengthDecode`, `LZWDecode`, `DCTDecode`, `CCITTFaxDecode`, `JPXDecode`, `JBIG2Decode`) | done | DCT/JPX/JBIG2 decode wired; encode for non-Flate raster filters intentionally upstream-parity (PDFBox itself defers most encodes). |
| `pdmodel` document / catalog / page tree / resources / info / viewer prefs / page labels / outlines / destinations / actions | done | |
| Annotations (widget, link, file-attachment, line, square/circle, free-text, ink, popup, polygon, stamp, …) | done | Appearance streams emitted and parsed. |
| Interactive forms (AcroForm, fields, choice, text, checkbox, signature, flattening) | done | Cyclic `/Kids` graphs guarded. |
| Tagged PDF / structure tree (`PDStructureTreeRoot`, `PDStructureElement`, MCID, role map, attribute objects) | done | Direct kid append/remove keeps `/P` parent pointers consistent. |
| Content-stream engine + operators (text-state, graphics-state, path, color, shading, marked-content, inline images) | done | `PDFGraphicsStreamEngine` registers the `sh` shading operator. |
| Text extraction (`PDFTextStripper`, `PDFTextStripperByArea`, marked-content extractor) | done | `/Differences`-aware decode; width-based word spacing. |
| Fonts (`fontbox`: TTF tables, CFF, Type1/Type1C, Type3, MMType1, CID, GSUB/GPOS, CMap, ToUnicode, encodings, AFM, Standard 14, subsetting) | done | Type 1 / CFF parsing layered on `fontTools` (MIT). No external font library for table semantics — ported from upstream `org.apache.fontbox.*`. |
| Rendering (`PDFRenderer`: page rasterisation, text, form XObjects, clip, inline images, patterns, shadings, soft masks, blend modes, Type1/Type1C glyphs) | done | Pillow + aggdraw backend. |
| Encryption (Standard Security Handler r2–r6: RC4 40/128, AES-128/256 CBC; public-key handler; crypt filters) | done | `cryptography` library for primitives only. |
| Digital signatures (`PDSignature` write-side, ByteRange placeholder pipeline, PKCS#7 verification surface, seed values, external signing) | done | PKCS#7 via `cryptography`. PAdES profile helpers ported. |
| `multipdf` (`Splitter`, `Merger`, page import + intra-source link remap) | done | |
| XMP metadata (`xmpbox`: parser, schemas, structured types, PDF 2.0 schemas) | done | `xml.etree` with hardened entity rejection. No `defusedxml` dependency. |
| Tools / CLI (`info`, `merge`, `split`, `decrypt`, `version`, `texttopdf`, `overlay`, `extract`, …) | done | Mirrors upstream `org.apache.pdfbox.tools.PDFBox` dispatcher. |
| Debugger (PDFDebugger UI port: tree model, page pane, stream pane, hex viewer) | done | Swing-equivalent UI ported on a Python-native widget toolkit. |
| PDF/A & PDF/UA validation | out of scope | Per PRD §13 and PDFBox 4.0 alignment: no `preflight` module ships. Downstream users wire up whichever external validator they choose — pypdfbox itself stays permissive-license-only and ships no scaffolding for any specific validator. |
| JBIG2 / JPEG 2000 / advanced JPEG decode-quality knobs | partial / planned | Awaiting explicit user decision on which Python codec backend to depend on (see PRD §3.7.1 "Pending user decision"). Default decode paths work today. |

## Status

All numbers below come from `.parity/snapshot.txt` (recomputed every wave against the PDFBox 3.0 HEAD clone at `/tmp/pdfbox`):

- **Class coverage:** 1,116 / 1,222 mapped → **100% of the in-scope surface** (the 106 unmapped classes are all `preflight.*`, intentionally excluded).
- **Method parity:** **97.3%** — 8,548 of 8,788 upstream methods matched.
- **Line coverage:** **90.22%** globally, ≈99% on the core (parser, writer, pdmodel, contentstream, text, fontbox, rendering, xmpbox, tools). The global delta is debugger-only and being closed in flight.
- **Tests:** **30,134 passing**, 12 skipped (each with a documented reason — most are upstream Java-plumbing tests that don't apply to Python).
- **Local TODOs:** **0**.
- **Path to RC:** approximately 3–5 more waves to close the remaining debugger-coverage delta and stabilise the in-flight test failures.

## Differences from upstream

A handful of behavioural divergences are intentional. The full list lives in [`CHANGES.md`](CHANGES.md); the high-level ones are:

- **No `preflight` module.** Apache PDFBox 4.0 removes Preflight; we follow that decision. PDF/A and PDF/UA conformance validation is out of scope — pypdfbox ships permissive-license components only, so the choice of external validator is left to the downstream user.
- **No commons-logging / log4j.** Python `logging` (stdlib) is used throughout.
- **Method naming.** Java `camelCase` → Python `snake_case` across the entire API surface. Semantics unchanged.
- **AWT-free rendering.** `java.awt.Color` is represented as a tuple of floats; `BufferedImage` returns are Pillow `Image` instances. `Matrix`, `Vector`, `GeneralPath`, `BoundingBox` widen to `Any` on font protocols.
- **Stdlib-first I/O.** `RandomAccessReadBuffer` / `RandomAccessReadBufferedFile` / `ScratchFile` are thin adapters over `io.BytesIO`, `BufferedReader`, and `tempfile.SpooledTemporaryFile`. Observable behaviour is identical; implementation is dramatically smaller. Spill-to-disk threshold defaults to 16 MiB.
- **`PDIndexed`.** No no-arg constructor; the two methods removed in PDFBox 4.0 are not ported.

See [`CHANGES.md` § Project-wide deviations vs upstream](CHANGES.md#project-wide-deviations-vs-upstream) and the per-file deviation list immediately below it.

## Compatibility goals (verbatim)

- Package layout mirrors `org.apache.pdfbox.*` → `pypdfbox.*` and `org.apache.fontbox.*` → `pypdfbox.fontbox.*`.
- Class names preserved: `COSDictionary`, `PDDocument`, `PDFParser`, `PDStructureTreeRoot`, `PDFRenderer`, …
- Method names: Java `camelCase` → Python `snake_case`; semantics unchanged.
- Inheritance hierarchies preserved.
- Behavioural compatibility (lazy loading, incremental save, xref preservation, object streams, force-parsing semantics) takes priority over Pythonic simplification.

The full product requirements are in [`pypdfbox_full_prd_v_1.md`](pypdfbox_full_prd_v_1.md). AI-assistant rules (for contributors using Claude Code or similar) are in [`CLAUDE.md`](CLAUDE.md).

## Development

Requires **Python 3.14+** (chosen so we can use the free-threaded build for parallel parsing/rendering work). Package management is [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync                                                    # creates .venv from uv.lock
uv run pytest -q                                           # run the test suite
uv run pytest -q tests/cos                                 # one module
uv run ruff check .                                        # lint
uv run mypy pypdfbox                                       # type-check
```

To recompute parity against an upstream PDFBox clone:

```sh
git clone --branch 3.0 --depth 1 https://github.com/apache/pdfbox.git /tmp/pdfbox
uv run python scripts/parity.py /tmp/pdfbox                # class + method parity report
uv run python scripts/parity.py /tmp/pdfbox --missing     # show unmapped Java methods
```

Add a dependency (runtime deps need explicit user approval per PRD §3.7.1):

```sh
uv add <pkg>                  # runtime
uv add --group dev <pkg>      # dev only
```

### Contributing

PRs require:

- For ported files: an entry in [`PROVENANCE.md`](PROVENANCE.md) (pypdfbox path → upstream PDFBox version → upstream Java path).
- Parity / oracle tests (PRD §12) — no class is complete without them. Layer hand-written tests in `tests/<module>/test_<class>.py` plus ported upstream tests in `tests/<module>/upstream/test_<class>.py`.
- Class-cluster scoped changes (PRD §11) — do not port whole modules in one change.
- For ported files whose behaviour deviates from upstream: a one-line entry in [`CHANGES.md`](CHANGES.md).

## Licensing

- **Source: Apache License 2.0** — same as upstream PDFBox. See [`LICENSE`](LICENSE).
- Required attribution lives in [`NOTICE`](NOTICE); downstream redistributors must propagate it.
- **Dependency policy:** Apache-2.0 / MIT / BSD only. GPL / LGPL / AGPL / MPL / EPL / CDDL / SSPL / BUSL are forbidden, and CI hard-fails on any.
- **No per-file license headers.** Ported files are tracked centrally in [`PROVENANCE.md`](PROVENANCE.md) (file → upstream PDFBox version + Java path), which satisfies Apache 2.0 §4(b) in one place. Source files stay clean.
- Substantive deviations from upstream are recorded in [`CHANGES.md`](CHANGES.md).

## Acknowledgements

pypdfbox is a port of [Apache PDFBox](https://pdfbox.apache.org/), maintained by the Apache Software Foundation. The COS model, parser architecture, content-stream operators, accessibility model, font subsystem, and rendering pipeline that this project mirrors are the result of decades of work by the PDFBox maintainers and contributors. Full attribution is in [`NOTICE`](NOTICE). Where upstream relies on `org.apache.fontbox.*` for font handling and `org.apache.pdfbox.filter.ccitt.*` for fax filters, pypdfbox carries those ports too rather than reach for separate Python libraries — see PRD §3.7.1 for the parity-over-convenience rationale.
