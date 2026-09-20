# Compatibility matrix

What pypdfbox can do, and how to reach it from Python or the command
line. Runnable end-to-end examples live in
[`pypdfbox/examples/`](../pypdfbox/examples/) (ported from upstream's
examples module); task-oriented walkthroughs live in
[`docs/guides/`](guides/).

| Task | Python entry point | CLI |
|---|---|---|
| Load / edit / save | `PDDocument.load(...)` → `.save(...)` | — |
| Extract text | `PDFTextStripper().get_text(doc)` | `pypdfbox extracttext` |
| Split / merge | `Splitter`, `PDFMergerUtility` | `pypdfbox split` / `merge` |
| Render pages to images | `PDFRenderer(doc).render_image_with_dpi(i, 150)` | `python -m pypdfbox.tools.pdf_to_image` |
| Extract embedded images | — | `python -m pypdfbox.tools.extract_images` |
| Inspect / metadata | `doc.get_document_information()` | `pypdfbox info` |
| Fill forms (AcroForm) | `catalog.get_acro_form()` | — |
| Encrypt / decrypt | `StandardProtectionPolicy`; `PDDocument.load(..., password=...)` | `pypdfbox encrypt` / `decrypt` |
| Digital signatures | `PDSignature` (sign + verify) | — |
| Tagged / accessible PDF | `PDStructureTreeRoot`, `PDMarkedContent` | — |
| Create PDFs | `PDPageContentStream` | `pypdfbox imagetopdf` / `texttopdf` |

## API compatibility with Apache PDFBox

pypdfbox is a Python-native port of Apache PDFBox 3.0.x. It preserves
the upstream package layout, class names, and inheritance hierarchies;
the only systematic change is method naming, where Java `camelCase`
becomes Python `snake_case`:

| Apache PDFBox (Java) | pypdfbox (Python) |
|---|---|
| `org.apache.pdfbox.cos.COSDictionary` | `pypdfbox.cos.COSDictionary` |
| `org.apache.fontbox.ttf.TrueTypeFont` | `pypdfbox.fontbox.ttf.TrueTypeFont` |
| `document.getDocumentCatalog()` | `document.get_document_catalog()` |
| `document.saveIncremental(...)` | `document.save_incremental(...)` |

PDFBox answers — javadoc, mailing-list archives, Stack Overflow —
usually translate directly. Coming from Java PDFBox, or from `pypdf` /
`pdfminer.six` / `reportlab`? [`migration.md`](migration.md) maps the
idioms side by side.

Behavioural deviations from upstream are recorded in
[`CHANGES.md`](../CHANGES.md); known gaps are in
[`limitations.md`](limitations.md).

## Platforms

Wheels cover CPython 3.14 on macOS (x86_64 + arm64), Linux/glibc
(x86_64 + aarch64), and Windows (x86_64).

Not supported: Alpine/musl and Windows ARM64 — upstream wheels for two
dependencies do not cover them. See [`install.md`](install.md) for
source builds and troubleshooting.
