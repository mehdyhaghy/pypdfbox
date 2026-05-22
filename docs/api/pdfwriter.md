# pypdfbox.pdfwriter — PDF writing pipeline

`COSWriter` is the canonical `ICOSVisitor` implementation: it walks the
`COSDocument` graph and emits a byte-for-byte PDF file. Three save modes are
supported — full rewrite, incremental append, and incremental in a separate
output stream — and three xref encodings — classic xref table, xref stream,
and hybrid. Compression policy is configured through `CompressParameters`,
and an `ICOSVisitor`-shaped `COSWriter.visit_from_stream` keeps stream
encryption transparent.

## Public surface

| Class | Purpose |
| --- | --- |
| `COSWriter` | The visitor + driver. Handles full save (`write(doc)`), incremental save (`write(doc, signature_interface=None)` with a prior loaded `COSDocument`), object-stream packing, xref emission, encryption attachment. |
| `COSStandardOutputStream` | The buffered byte sink with offset tracking. Tracks every `\n`/`\r` for the cross-reference table; keeps a 10-byte rolling tail used by linearization repair. |
| `ContentStreamWriter` | Helper for writing PDF content-stream operators (`Tj`, `q`, `re`, …) with PDFBox-compatible operand spacing and decimal formatting. Used by `PDPageContentStream` and the appearance generator. |
| `COSWriterXRefEntry` | One (object key, byte offset, generation, free flag) record collected during the walk and serialised into the xref. |
| `CompressParameters` | Configures whether object streams are emitted (`set_compression_level`, `set_object_stream_count`). Default is `CompressParameters.no_compression()`. |

## Save modes

The `PDDocument` save surface dispatches into `COSWriter` like this:

```python
doc.save(path_or_stream)
doc.save(path_or_stream, compress_parameters=CompressParameters.default_compression())
doc.save_incremental(stream)
doc.save_incremental(stream, signature_interface=signer)
doc.save_incremental_for_external_signing(stream)  # returns ExternalSigningSupport
```

`save_incremental` always appends a new xref section starting at the current
end-of-file; the existing object graph is untouched on disk, so a previously
signed PDF's `byte range` digest remains valid.

## Xref encoding

`COSWriter` selects xref encoding from the loaded document's
`get_xref_table_type()`:

| Source xref type | Default emission | Override via |
| --- | --- | --- |
| `TABLE` | Classic `xref`/`trailer` block | `set_xref_stream_compression(...)` |
| `STREAM` | `/Type /XRef` stream with predictor 12 | `set_classic_xref_table()` |
| `HYBRID` | Hybrid (classic + stream) | (kept as-is) |
| `REPAIRED` | Classic | (kept as-is) |

New documents (`PDDocument()` with no loaded source) default to a classic
xref table.

## Object-stream packing

When `CompressParameters` requests compression, `COSWriter` packs eligible
indirect objects into `/Type /ObjStm` streams. Excluded from packing:
encrypted streams, the trailer/catalog/info/encrypt dictionary, anything
flagged via `cos_object.set_compressed(False)`. Packing batch size defaults
to 100 objects (`PDFBox.MAX_OBJECT_STREAM_COUNT`).

## Encryption attachment

If the loaded `COSDocument` has a `Encryption` dictionary, `COSWriter`
re-runs the existing `SecurityHandler.encrypt` over every stream and string
on its way out. If you want to add encryption to a previously unencrypted
document, call `doc.protect(protection_policy)` before saving — that
attaches the right handler and the writer picks it up.

## Typical usage

```python
from pypdfbox import PDDocument
from pypdfbox.pdfwriter import CompressParameters

with PDDocument() as doc:
    doc.add_page(...)
    doc.save("out.pdf", compress_parameters=CompressParameters.default_compression())

# Incremental append on a previously loaded document:
with Loader.load_pdf("existing.pdf") as doc:
    doc.get_document_catalog().get_acro_form().get_field("Name").set_value("Ada")
    with open("existing.pdf", "ab") as f:
        doc.save_incremental(f)
```

## Direct visitor use

`COSWriter` is itself an `ICOSVisitor`, so any custom traversal can reuse
its per-token output routines. The visit methods (`visit_from_array`,
`visit_from_dictionary`, `visit_from_stream`, etc.) match the protocol in
[cos.md](cos.md).

## PDFBox divergence

- `save(File)` overloads collapse into one `save(path_or_stream, *,
  compress_parameters=..., security_handler=...)`. Pass a `pathlib.Path`,
  `str`, or any binary stream.
- `saveIncremental(OutputStream, ...)` → `save_incremental(stream, ...)`.
- `saveIncrementalForExternalSigning` → `save_incremental_for_external_signing`.
  Returns a `pypdfbox.pdmodel.interactive.digitalsignature.ExternalSigningSupport`
  (Python-named) handle.
- `CompressParameters.setCompressionLevel(level)` →
  `set_compression_level(level)`. Levels mirror `zlib`'s `0`–`9`.

## See also

- [cos.md](cos.md) — the `ICOSVisitor` protocol and the object graph the
  writer walks.
- [pdmodel.md](pdmodel.md) — `PDDocument.save(...)` is the typical entry.
- [pdmodel-interactive.md](pdmodel-interactive.md) — incremental save with
  signatures.
- [guides/incremental-update.md](../guides/incremental-update.md) — when to
  use `save_incremental` vs `save`.
- [guides/encryption.md](../guides/encryption.md) — adding encryption
  before save.
