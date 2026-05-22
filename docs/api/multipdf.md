# pypdfbox.multipdf — merge, split, clone, overlay, layer

`multipdf` mirrors `org.apache.pdfbox.multipdf`: utilities that operate on
two or more `PDDocument`s, or carve one `PDDocument` into pieces. These
sit on top of `pdmodel` and use the parser + writer end-to-end. The
package is small but its three workhorse classes — `PDFMergerUtility`,
`PDFCloneUtility`, `Splitter` — are the foundation of every multi-document
operation.

## Public surface

| Class | Purpose |
| --- | --- |
| `PDFMergerUtility` | Concatenate two or more PDFs. `add_source(path_or_stream_or_doc)`, `set_destination_file_name(path)`, `set_destination_stream(stream)`, `set_document_merge_mode(mode)`, `set_acro_form_merge_mode(mode)`, `merge_documents(memory_usage_setting=None)`. |
| `PDFCloneUtility` | Deep-clone a `COSBase` graph from one document into another, deduplicating indirect references via an identity map. `clone_for_new_document(cos_base) -> COSBase`. Used internally by the merger, the layer utility, the page extractor, and any cross-document import. |
| `KCloner` | Lighter-weight clone that knows about specific object types (annotations, fields, form X-objects). Optimised for the AcroForm merge path. |
| `Splitter` | Split one `PDDocument` into several. `set_split_at_page(n)`, `set_start_page(n)`, `set_end_page(n)`, `set_memory_usage_setting(setting)`, `split(source) -> list[PDDocument]`. The caller is responsible for `close()`ing each returned document. |
| `PageExtractor` | Extract a subset of pages into a new `PDDocument`. `extract() -> PDDocument`. Lighter-weight than `Splitter` when you only want one output. |
| `LayerUtility` | Embed one PDF (or one page from one) as a Form X-object on another. `append_form_as_layer(target_page, form_xobject, transform, layer_name)`. Optionally creates an Optional Content Group for toggling. |
| `Overlay` | Stamp one PDF on top of another. `set_input_pdf(path)`, `set_default_overlay_pdf(path)`, `set_specific_page_overlay(page_index, path)`, `set_overlay_position(Position)`, `overlay(specific_overlays_dict) -> PDDocument`. |
| `Position` | `enum.Enum` — `FOREGROUND`, `BACKGROUND`. The `BACKGROUND` mode places the overlay underneath existing content. |
| `DocumentMergeMode` | `enum.Enum` — `OPTIMIZE_RESOURCES_MODE`, `PDFBOX_LEGACY_MODE`. Determines whether identical fonts/X-objects/color-spaces from different sources are merged into one resource entry. |
| `AcroFormMergeMode` | `enum.Enum` — `JOIN_FORM_FIELDS_MODE` (default; merge form field trees and de-duplicate field names), `PDFBOX_LEGACY_MODE` (preserve every field tree independently). |

## Typical usage

### Merge

```python
from pypdfbox.multipdf import PDFMergerUtility, DocumentMergeMode

merger = PDFMergerUtility()
merger.add_source("intro.pdf")
merger.add_source("body.pdf")
merger.add_source("appendix.pdf")
merger.set_destination_file_name("book.pdf")
merger.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
merger.merge_documents()
```

### Split

```python
from pypdfbox import Loader
from pypdfbox.multipdf import Splitter

with Loader.load_pdf("book.pdf") as src:
    splitter = Splitter()
    splitter.set_split_at_page(1)        # one page per output
    for i, part in enumerate(splitter.split(src)):
        part.save(f"page-{i+1:03d}.pdf")
        part.close()
```

### Extract a range

```python
from pypdfbox.multipdf import PageExtractor

with Loader.load_pdf("book.pdf") as src:
    extractor = PageExtractor(src, start_page=10, end_page=20)
    with extractor.extract() as dst:
        dst.save("chapter-2.pdf")
```

### Overlay (watermark / stamp)

```python
from pypdfbox.multipdf import Overlay, Position

overlay = Overlay()
overlay.set_input_pdf("doc.pdf")
overlay.set_default_overlay_pdf("watermark.pdf")
overlay.set_overlay_position(Position.FOREGROUND)
with overlay.overlay({}) as out:
    out.save("doc-watermarked.pdf")
```

### Insert as layer

```python
from pypdfbox.multipdf import LayerUtility
from pypdfbox.util import Matrix

with Loader.load_pdf("base.pdf") as base, Loader.load_pdf("logo.pdf") as logo:
    util = LayerUtility(base)
    form = util.import_page_as_form(logo, 0)
    util.append_form_as_layer(base.get_page(0), form, Matrix.identity(), "Logo")
    base.save("with-logo.pdf")
```

## Merge modes

`DocumentMergeMode.OPTIMIZE_RESOURCES_MODE` (default) walks every page's
`/Resources` dictionary on the way in and de-duplicates fonts, color
spaces, ExtGStates, X-objects, patterns, and shadings by content
hash. The output PDF is typically 10-30 % smaller than the
`PDFBOX_LEGACY_MODE` equivalent on real-world inputs.

`AcroFormMergeMode.JOIN_FORM_FIELDS_MODE` (default) merges field trees
across source documents, renaming colliding fully-qualified names with a
numeric suffix; widgets are re-parented to the merged field.

## PDFBox divergence

- `PDFMergerUtility.addSource(File|InputStream|PDDocument)` collapses
  into one `add_source(path_or_stream_or_doc)`.
- `mergeDocuments(MemoryUsageSetting)` → `merge_documents(memory_usage_setting=None)`.
- `Splitter.split(PDDocument)` returns a `list[PDDocument]` (Python list)
  rather than the Java `List<PDDocument>`.
- `Overlay.overlay(Map<Integer, String> specificOverlays)` →
  `overlay(specific_overlays_dict: dict[int, str | pathlib.Path])`.

## See also

- [pdmodel.md](pdmodel.md) — the underlying document model.
- [pdfwriter.md](pdfwriter.md) — every merge/split path ends in a
  `COSWriter` save.
- [tools.md](tools.md) — `pypdfbox merge`, `pypdfbox split`,
  `pypdfbox overlay` wrap these classes.
- [guides/merge-and-split.md](../guides/merge-and-split.md).
