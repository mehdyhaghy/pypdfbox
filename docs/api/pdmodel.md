# pypdfbox.pdmodel — high-level document model

`pdmodel` is the PDFBox-shaped abstraction over the COS object graph. Where
`cos` deals in dictionaries and arrays, `pdmodel` exposes typed wrappers —
`PDDocument`, `PDPage`, `PDPageTree`, `PDDocumentCatalog`, `PDResources` —
that match upstream method-for-method (with `snake_case` renaming) and hide
the underlying COS lookups behind named accessors.

Most application code lives here. Drop into `cos` only when you need to
inspect or build something `pdmodel` does not surface yet.

## Public surface (top-level)

| Class | Purpose |
| --- | --- |
| `PDDocument` | The document. Owns the `COSDocument`, the document catalog, the page tree, the resource cache, the signing/encryption state. `save`, `save_incremental`, `close`, `get_number_of_pages`, `get_pages`, `add_page`, `import_page`, `protect`, `is_encrypted`, `get_signature_dictionaries`. |
| `PDDocumentCatalog` | The `/Catalog` dictionary. Owns page tree, outlines, metadata, AcroForm, OC properties, names dictionary, document language, page mode, page layout. |
| `PDDocumentInformation` | The `/Info` dictionary: title, author, subject, keywords, creator, producer, creation/mod date, custom properties. |
| `PDDocumentNameDictionary` | `/Names` lookup. Backs `Dests`, `EmbeddedFiles`, `JavaScript`, `Pages`, `IDS`, `URLS`, `Renditions`, `Templates`, `AlternatePresentations`. |
| `PDDocumentNameDestinationDictionary` | Legacy `/Dests` named-destination dictionary. |
| `PDPage` | One page. `get_resources`, `get_media_box`, `get_crop_box`, `get_bleed_box`, `get_trim_box`, `get_art_box`, `get_rotation`, `set_rotation`, `get_annotations`, `set_annotations`, `get_thumbnail`, `get_contents`, `get_actions`. |
| `PDPageTree` | The `/Pages` tree. `iter`, `__len__`, `__iter__`, `__getitem__`, `add`, `insert_before`, `insert_after`, `remove`. Supports random access by page index. |
| `PDPageLabels` | `/PageLabels` number tree wrapper (range-based labels: roman / arabic / letters / prefix). |
| `PDPageLabelRange` | One contiguous label range. |
| `PDRectangle` | `[lower_x, lower_y, upper_x, upper_y]` box. Provides `get_width`, `get_height`, `contains`, `as_matrix`, `transform(matrix)`. |
| `PDResources` | `/Resources` dictionary view: fonts, color spaces, X-objects, patterns, shadings, properties, ExtGState. `get_font`, `add_font`, `get_x_object`, `add_x_object`, `get_color_space`, etc. Backed by a `ResourceCache` to avoid re-parsing across pages. |
| `PDAbstractContentStream` | Base class for both `PDPageContentStream` and `PDAppearanceContentStream`. Writes content-stream operators with PDFBox-compatible decimal formatting. |
| `PDViewerPreferences` | `/ViewerPreferences` dictionary (HideToolbar, HideMenubar, FitWindow, Direction, etc.). |
| `PDDeveloperExtension` | A `/Extensions` developer-prefix entry. |
| `PageMode` / `PageLayout` | `enum.Enum` for `/PageMode` and `/PageLayout` catalog entries. |
| `PageIterator` | Lazy iterator over `PDPageTree` that resolves indirect references on demand. |
| `SearchContext` | Shared state used by recursive page-tree walkers. |
| `ResourceCache` | Protocol — `get(key) -> PDFontLike / PDXObject / …`. |
| `ResourceCacheCreateFunction` | Protocol — `() -> ResourceCache`. |
| `ResourceCacheFactory` | Convenience: `default()`, `none()`. |
| `DefaultResourceCacheCreateImpl` | Per-document LRU resource cache. |
| `MissingResourceException` | Raised when a referenced font/X-object is not present in the active resource chain. |

## Sub-packages

These have dedicated reference pages:

- [pdmodel-font.md](pdmodel-font.md) — `PDFont`, `PDType0Font`,
  `PDType1Font`, `PDType3Font`, `PDTrueTypeFont`, `PDCIDFont*`,
  `Standard14Fonts`, the font mapper.
- [pdmodel-graphics.md](pdmodel-graphics.md) — color spaces, shadings, blend
  modes, transparency groups, patterns.
- [pdmodel-interactive.md](pdmodel-interactive.md) — annotations, forms,
  actions, digital signatures, outlines.

Other in-module packages:

| Package | Notable contents |
| --- | --- |
| `pypdfbox.pdmodel.common` | `PDStream`, `PDNumberTreeNode`, `PDNameTreeNode`, `COSObjectable`, `COSArrayList`, `PDDestination`, `PDPropertyList`. |
| `pypdfbox.pdmodel.encryption` | `PDEncryption`, `ProtectionPolicy`, `StandardProtectionPolicy`, `PublicKeyProtectionPolicy`, `AccessPermission`, `SecurityHandler`. |
| `pypdfbox.pdmodel.fdf` | `FDFDocument`, FDF field types. |
| `pypdfbox.pdmodel.fixup` | Document-level fix-up passes (`PDAcroFormFixup`, `PDAnnotationFixup`). |
| `pypdfbox.pdmodel.documentinterchange` | Structure tree (`PDStructureTreeRoot`, `PDStructureElement`), marked-content references, role-mapping, tagged-PDF accessibility. |

## Typical usage

```python
from pypdfbox import Loader, PDDocument, PDPage, PDRectangle

# Read
with Loader.load_pdf("in.pdf") as src:
    title = src.get_document_information().get_title()
    page = src.get_page(0)
    rect = page.get_media_box()
    print(title, rect.get_width(), rect.get_height())

# Build from scratch
with PDDocument() as dst:
    page = PDPage(PDRectangle.A4)
    dst.add_page(page)
    dst.get_document_information().set_title("Hello")
    dst.save("out.pdf")
```

## PDFBox divergence

- `PDDocument.load(path)` → `Loader.load_pdf(path)` (the static `load`
  factory moved into the dedicated `Loader` class so the parsing surface is
  searchable; `PDDocument` no longer carries multiple `load` overloads).
- `PDPageTree.iterator()` → `iter(tree)` / `__iter__`. Random-access
  `getNumberOfPages()` → `len(tree)` and `get_number_of_pages()` (both
  retained).
- `PDDocument.getNumberOfPages()` is preserved as
  `get_number_of_pages()` and also via `len(doc)`.
- `PDPage.getMediaBox()` returns a new `PDRectangle` (Java returned a
  shared one; pypdfbox copies to avoid alias bugs).
- `PDResources` accessors take an optional `default=None` second argument
  where Java returned `null`. The fallback `MissingResourceException` is
  only raised by `get_font` / `get_x_object` when the name is present in
  the dictionary but the value is broken — never on a missing key.

## See also

- [cos.md](cos.md) — the underlying object model.
- [pdfparser.md](pdfparser.md) — how `PDDocument` is built from bytes.
- [pdfwriter.md](pdfwriter.md) — how it is saved.
- [contentstream.md](contentstream.md) — `PDPageContentStream` lives here
  and writes via the content-stream operator set documented there.
- [migration.md](../migration.md) — class-by-class Java-to-Python mapping.
