# API reference

`pypdfbox` mirrors the Apache PDFBox package layout one-for-one so a developer
familiar with the Java library can navigate the Python codebase without
re-learning concepts. Class names are preserved verbatim (`COSDictionary`,
`PDPageTree`, `PDFRenderer`, …); only method names are translated from
`camelCase` to `snake_case`. Inheritance hierarchies (`BaseParser` →
`COSParser` → `PDFParser`) are preserved. Behavioural semantics — lazy
loading, force-parsing, incremental append, xref preservation, object-stream
packing — match upstream.

## Top-level entry points

The root `pypdfbox` package re-exports the small set of names every program
needs:

```python
from pypdfbox import (
    Loader,
    PDDocument,
    PDDocumentCatalog,
    PDPage,
    PDPageTree,
    PDRectangle,
    PDResources,
)
```

`Loader.load_pdf(path_or_bytes)` is the canonical reader. Direct
`PDDocument()` construction creates an empty document for writing.

## Module map (PDFBox-compatible layout)

| Module | PDFBox package | Reference |
| --- | --- | --- |
| `pypdfbox.io` | `org.apache.pdfbox.io` | [io.md](io.md) |
| `pypdfbox.cos` | `org.apache.pdfbox.cos` | [cos.md](cos.md) |
| `pypdfbox.pdfparser` | `org.apache.pdfbox.pdfparser` | [pdfparser.md](pdfparser.md) |
| `pypdfbox.pdfwriter` | `org.apache.pdfbox.pdfwriter` | [pdfwriter.md](pdfwriter.md) |
| `pypdfbox.pdmodel` | `org.apache.pdfbox.pdmodel` | [pdmodel.md](pdmodel.md) |
| `pypdfbox.pdmodel.font` | `org.apache.pdfbox.pdmodel.font` | [pdmodel-font.md](pdmodel-font.md) |
| `pypdfbox.pdmodel.graphics` | `org.apache.pdfbox.pdmodel.graphics` | [pdmodel-graphics.md](pdmodel-graphics.md) |
| `pypdfbox.pdmodel.interactive` | `org.apache.pdfbox.pdmodel.interactive` | [pdmodel-interactive.md](pdmodel-interactive.md) |
| `pypdfbox.contentstream` | `org.apache.pdfbox.contentstream` | [contentstream.md](contentstream.md) |
| `pypdfbox.text` | `org.apache.pdfbox.text` | [text.md](text.md) |
| `pypdfbox.fontbox` | `org.apache.fontbox` | [fontbox.md](fontbox.md) |
| `pypdfbox.rendering` | `org.apache.pdfbox.rendering` | [rendering.md](rendering.md) |
| `pypdfbox.xmpbox` | `org.apache.xmpbox` | [xmpbox.md](xmpbox.md) |
| `pypdfbox.tools` | `org.apache.pdfbox.tools` | [tools.md](tools.md) |
| `pypdfbox.multipdf` | `org.apache.pdfbox.multipdf` | [multipdf.md](multipdf.md) |

Auxiliary packages — `pypdfbox.filter` (Flate, LZW, ASCII85, ASCIIHex,
RunLength, CCITTFax, DCT, JBIG2, JPX, Crypt, predictor pipeline),
`pypdfbox.util` (Matrix, Vector, hex helpers, small-map, file-type detector),
`pypdfbox.debugger` (Tkinter `PDFDebugger`), `pypdfbox.printing`,
`pypdfbox.examples` and `pypdfbox.benchmark` — are documented inline in their
own `__init__.py` docstrings and follow the same naming rules.

## Dependency-ordered implementation

The PRD locks the build order:

```
io  ->  cos  ->  pdfparser  ->  pdfwriter  ->  pdmodel
              ->  contentstream  ->  text  ->  fontbox  ->  rendering
```

Each layer depends only on the layers above it. This is enforced through
imports and through the test suite (a `pypdfbox.text` change cannot reach
into `pypdfbox.rendering`, and a `pypdfbox.cos` change must not import any
PD-prefixed class). When you read the API pages below in order, you are
reading the same flow.

## PDFBox-divergence reminders

The diverges from the Java API are deliberate and documented per class:

- Method names are always `snake_case`. There are no `camelCase` aliases —
  use `get_document_catalog()`, not `getDocumentCatalog()`.
- Java `byte[]` parameters become `bytes` / `bytearray`. Returns that were
  arrays in Java become `tuple`s when the value is immutable, `list`s when
  callers mutate them.
- Where Java relied on `@FunctionalInterface` SAM types, pypdfbox uses
  `typing.Protocol` (e.g. `StreamCacheCreateFunction`,
  `ResourceCacheCreateFunction`, `ICOSVisitor`).
- Java enums become module-level `enum.Enum` subclasses (`StorageMode`,
  `XrefType`, `PageLayout`, `PageMode`, `OpenMode`, `RenderDestination`,
  `ImageType`, `FontFormat`).
- `IOException` maps to `OSError` in generic I/O contexts and to
  `PDFParseError` (defined in `pypdfbox.pdfparser`) when the issue is parser
  state. `IllegalArgumentException` maps to `ValueError`,
  `IllegalStateException` to `RuntimeError`.
- Java `null`-returning getters typically return `Optional[T]` annotations,
  but the actual runtime value is `None` — `Optional` is documentation, not
  a wrapper.

## See also

- [migration.md](../migration.md) — Java-to-Python translation cheat-sheet for
  developers porting an existing PDFBox project.
- [guides/getting-started.md](../guides/getting-started.md) — first-program
  walkthrough.
- [guides/text-extraction.md](../guides/text-extraction.md),
  [guides/rendering.md](../guides/rendering.md),
  [guides/forms.md](../guides/forms.md),
  [guides/signing.md](../guides/signing.md) — task-oriented recipes.
- `PROVENANCE.md` — per-file provenance against upstream PDFBox.
- `CHANGES.md` — substantive behavioural divergences from upstream.
