# Merging and splitting

Pypdfbox ports the upstream multi-document utilities
[`PDFMergerUtility`](../api/pdmodel.md) and
[`Splitter`](../api/pdmodel.md) under `pypdfbox.multipdf`.

## Merge PDFs

`PDFMergerUtility` concatenates input documents while reconciling
the document catalog: page tree, `/AcroForm`, `/Names`, `/Dests`,
`/Outlines`, `/PageLabels`, `/Metadata`, and `/StructTreeRoot`.

```python
from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility

merger = PDFMergerUtility()
merger.add_source("part-a.pdf")
merger.add_source("part-b.pdf")
merger.add_source("part-c.pdf")
merger.set_destination_file_name("combined.pdf")
merger.merge_documents()
```

`add_source` accepts a file path, raw `bytes`, a binary stream, an
already-opened `PDDocument`, or a `RandomAccessRead`. The merger
opens each on demand and closes it when done.

`merger.set_destination_stream(buffer)` writes the result to an
in-memory file. Default merge mode reconciles AcroForm fields by
renaming collisions; pass an alternative `AcroFormMergeMode`
through `set_acro_form_merge_mode` if you need a different
strategy. `set_document_merge_mode` switches between the
default page-append and the resource-deduplicating
`OPTIMIZE_RESOURCES_MODE`.

## Split by page chunk size

`Splitter` produces N-page slices of a source document. The
default chunk size is 1 (one output document per page).

```python
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel import PDDocument

with PDDocument.load("book.pdf") as doc:
    splitter = Splitter()
    splitter.set_split_at_page(10)              # 10 pages per output
    parts = splitter.split(doc)
    for i, part in enumerate(parts):
        with part:
            part.save(f"book-{i:03d}.pdf")
```

The setters return `self` for fluent chaining:

```python
splitter = (
    Splitter()
    .set_split_at_page(5)
    .set_start_page(11)        # 1-based inclusive
    .set_end_page(40)          # 1-based inclusive
)
```

Each `PDDocument` returned by `split()` owns its own copy of the
source pages and must be closed by the caller (the `with` statement
above handles this).

## Split by bookmark

Use the source document's outline (bookmark tree) to pick chunk
boundaries. The outline-aware split is not built into `Splitter`
directly; combine the outline walker with `Splitter`'s
`set_start_page` / `set_end_page` per chunk:

```python
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel import PDDocument

with PDDocument.load("book.pdf") as doc:
    outline = doc.get_document_catalog().get_document_outline()
    bookmarks = list(outline.children()) if outline is not None else []
    boundaries = []
    for bm in bookmarks:
        page = bm.find_destination_page(doc)
        if page is not None:
            boundaries.append(doc.get_pages().indexOf(page) + 1)  # 1-based
    boundaries.append(doc.get_number_of_pages() + 1)

    for i, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        sp = Splitter().set_start_page(start).set_end_page(end - 1)
        for j, part in enumerate(sp.split(doc)):
            with part:
                part.save(f"chapter-{i:02d}-{j:02d}.pdf")
```

The exact accessor names depend on the version of the outline port
in your tree; consult the [API reference](../api/pdmodel.md) for the
authoritative surface.

## Cross-chunk destination resolver

When a link target straddles a chunk boundary the default behaviour
is to null out the link (the target page no longer exists in the
chunk being written). Wave 1379 added a `set_cross_chunk_destination_resolver`
hook that lets you rewrite such links as `GoToR` actions pointing at
the sibling chunk file.

```python
from pypdfbox.multipdf.splitter import Splitter

def resolver(target_page_dict):
    """Return (file_name, page_index_within_file) for cross-chunk links."""
    # `target_page_dict` is the source target page COSDictionary (captured
    # before deep-copy). Look up which chunk file holds the target and
    # the 0-based page index within that file, then return the tuple.
    chunk_idx, page_in_chunk = my_chunk_index_lookup(target_page_dict)
    return (f"book-{chunk_idx:03d}.pdf", page_in_chunk)

splitter = Splitter()
splitter.set_split_at_page(20)
splitter.set_cross_chunk_destination_resolver(resolver)
parts = splitter.split(doc)
```

The resolver receives the *source* target page `COSDictionary`. Return
options:

- `None` — keep historical null-out behaviour.
- `(file_name, page_index)` — explicit `GoToR` payload (preferred).
- A bare `str` — file name only; the page index defaults to 0.

After all chunks are written you must save them with names that
match what the resolver advertised — pypdfbox does not invent the
file names for you.

## See also

- [API reference: `pypdfbox.pdmodel`](../api/pdmodel.md)
- [CLI guide](cli.md) for `pypdfbox merge` and `pypdfbox split`
- [Documentation index](../index.md)
