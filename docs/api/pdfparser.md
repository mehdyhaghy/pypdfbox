# pypdfbox.pdfparser — PDF reading pipeline

The parser turns a `RandomAccessRead` into a `COSDocument`. It is layered to
match upstream PDFBox: `BaseParser` handles the COS-token grammar,
`COSParser` adds xref/trailer awareness and lazy resolution, `PDFParser` is
the top-level driver that owns the document state, runs repair, and decrypts
streams. Linearization hint tables are decoded on demand so a network-loaded
PDF can satisfy first-page-fast access patterns.

## Public surface

| Class / function | Purpose |
| --- | --- |
| `BaseParser` | Token-level COS grammar: parse name, number, boolean, string, hex string, array, dictionary, stream. Operates on a `RandomAccessRead`. |
| `COSParser` | Adds xref resolution, lazy object dictionaries, encryption hook. Subclass of `BaseParser`. |
| `PDFParser` | Top-level driver: locates startxref, validates header, drives `parse()`, owns the `COSDocument` and `XrefTrailerResolver`. |
| `BruteForceParser` | Fallback path used when the cross-reference table is broken or missing. Scans the file for `n n obj` markers and rebuilds the xref. |
| `FDFParser` | Specialised parser for FDF (Forms Data Format) — same grammar, different trailer expectations. |
| `PDFObjectStreamParser` | Decodes a `/Type /ObjStm` compressed-objects stream into its constituent indirect objects. |
| `PDFStreamParser` | Content-stream tokeniser used by both content-stream consumers (graphics engine, text stripper) and the appearance-stream embedder. |
| `Operator` | A content-stream operator token (e.g. `Tj`, `q`, `re`). Carries an optional inline-image dictionary + payload. |
| `PDFXRefStream` | Builder for `/Type /XRef` cross-reference streams (W array, Index ranges, predictor). |
| `PDFXrefStreamParser` | Decodes a PDFXRefStream back into xref entries. |
| `XrefTrailerResolver` | Merges every xref table + xref stream + repair pass into a single canonical mapping. |
| `XrefEntry` | A single `(offset, generation, is_free, is_compressed, container_obj_num, index_in_container)` row. |
| `XrefTrailerObj` | One trailer dictionary plus its xref range. |
| `XrefType` | `enum.Enum` — `TABLE`, `STREAM`, `HYBRID`, `REPAIRED`. |
| `EndstreamFilterStream` | Strips the trailing whitespace/EOL between stream contents and `endstream`. |
| `ObjectNumbers` | Tracks which object numbers have already been allocated. |
| `PDFParseError` | The parser's exception type (subclass of `OSError`). |

### Linearization hint tables

Decoding linearized PDFs uses three small parsers (page-offset,
shared-object, and thumbnail):

| Symbol | Purpose |
| --- | --- |
| `parse_page_offset_hint_header` / `parse_page_offset_hint_table` | Decodes header + entries of the page-offset hint table. |
| `parse_shared_object_hint_header` / `parse_shared_object_hint_table` | Decodes the shared-object hint table. |
| `parse_thumbnail_hint_header` / `parse_thumbnail_hint_table` | Decodes the thumbnail hint table. |
| `PageOffsetHintHeader`, `PageOffsetHintTable`, `PageOffsetEntry` | Decoded structures. |
| `SharedObjectHintHeader`, `SharedObjectHintTable`, `SharedObjectEntry` | Decoded structures. |
| `ThumbnailHintHeader`, `ThumbnailHintTable`, `ThumbnailEntry` | Decoded structures. |
| `HintTableParseError` | Raised on malformed hint tables. |

## Typical usage

The recommended entry point is `Loader.load_pdf` rather than constructing
`PDFParser` directly:

```python
from pypdfbox import Loader

with Loader.load_pdf("input.pdf", password="hunter2") as doc:
    catalog = doc.get_document_catalog()
    print(catalog.get_metadata())
```

`Loader.load_pdf` accepts:

- `bytes`, `bytearray`, `str` / `pathlib.Path`, an open binary file, or any
  pre-built `RandomAccessRead`.
- `password=` — encryption password.
- `keystore=` + `alias=` — for public-key encryption.
- `memory_usage_setting=` — see [io.md](io.md).
- `stream_cache_create_function=` — custom buffer allocator.

For direct parser use:

```python
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser

source = RandomAccessReadBuffer(open("input.pdf", "rb").read())
parser = PDFParser(source)
parser.parse()
doc = parser.get_document()  # COSDocument
```

## Repair semantics

When the xref table cannot be located or fails sanity checks, `PDFParser`
hands the source to `BruteForceParser`, which rebuilds the cross-reference
by scanning for `obj` markers. This matches upstream PDFBox behaviour:
repair is automatic, never opt-in, and produces an `XrefType.REPAIRED`
xref. Inspect `doc.get_xref_table_type()` if you need to log this.

## PDFBox divergence

- `PDFParser` does not expose a no-arg constructor — pass a
  `RandomAccessRead` (or use `Loader.load_pdf`).
- All `parseXxx()` methods are `parse_xxx()`. `forceParsing` flag becomes
  `force_parsing`.
- `Operator` carries an optional `image_data: bytes` field for inline
  images instead of the Java `byte[]` plus separate `setImageData()`.

## See also

- [io.md](io.md) — input adapters.
- [cos.md](cos.md) — the object model the parser builds.
- [pdfwriter.md](pdfwriter.md) — the inverse direction.
- [guides/linearized-pdfs.md](../guides/linearized-pdfs.md) — first-page
  fast read patterns using the hint tables.
- [migration.md](../migration.md) — `PDDocument.load(...)` →
  `Loader.load_pdf(...)`.
