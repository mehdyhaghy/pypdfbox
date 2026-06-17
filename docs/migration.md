# Migrating from Apache PDFBox (Java) to pypdfbox

## Audience and premise

This guide is for developers fluent in Apache PDFBox 3.0.x who want to
use pypdfbox from Python. If you know PDFBox, you already know
pypdfbox at roughly 85-90 percent. The remaining 10-15 percent is
naming convention plus a handful of Python-idiom adjustments that
fall out of the language difference itself, not from API redesign.
This document is the bridge.

The port is deliberately conservative. Class names, package paths,
inheritance chains, lazy-loading semantics, incremental-append
behaviour, xref preservation, and object-stream handling all match
upstream. Where the Java surface had method overloads, pypdfbox
uses default arguments and keyword arguments to expose the same
shapes. Where the Java surface used `IOException`, pypdfbox raises
`OSError` (or `PDFParseError` from the parser layer) — but the
control-flow shape is identical.

If a section below contradicts something you remember from PDFBox,
the safe assumption is "pypdfbox follows upstream"; read the
section before assuming a divergence.

## The one universal translation: camelCase to snake_case

Every public method on every class went through a mechanical
camelCase-to-snake_case conversion. Semantics are unchanged. The
upstream Java spelling does not survive as an alias anywhere in
production source (with a small list of fontTools-pen exceptions
where an external library calls back into our code by camelCase
name).

Examples across the most common API surface:

| Java (PDFBox 3.0.x) | Python (pypdfbox) |
|---|---|
| `Loader.loadPDF(file)` | `Loader.load_pdf("file.pdf")` |
| `Loader.loadPDF(file, password)` | `Loader.load_pdf("file.pdf", password)` |
| `PDDocument.load(file)` | `PDDocument.load("file.pdf")` |
| `doc.getDocument()` | `doc.get_document()` |
| `doc.getDocumentCatalog()` | `doc.get_document_catalog()` |
| `doc.getDocumentInformation()` | `doc.get_document_information()` |
| `doc.getNumberOfPages()` | `doc.get_number_of_pages()` |
| `doc.getPage(0)` | `doc.get_page(0)` |
| `doc.getVersion()` | `doc.get_version()` |
| `doc.setVersion(1.7f)` | `doc.set_version(1.7)` |
| `doc.isEncrypted()` | `doc.is_encrypted()` |
| `doc.save(out)` | `doc.save(out)` |
| `doc.saveIncremental(out)` | `doc.save_incremental(out)` |
| `doc.close()` | `doc.close()` |
| `cat.getPages()` | `cat.get_pages()` |
| `cat.getDocumentOutline()` | `cat.get_document_outline()` |
| `cat.getAcroForm()` | `cat.get_acro_form()` |
| `cat.getMetadata()` | `cat.get_metadata()` |
| `cat.getPageLayout()` | `cat.get_page_layout()` |
| `cat.getPageMode()` | `cat.get_page_mode()` |
| `cat.getStructureTreeRoot()` | `cat.get_structure_tree_root()` |
| `cat.getViewerPreferences()` | `cat.get_viewer_preferences()` |
| `page.getMediaBox()` | `page.get_media_box()` |
| `page.getCropBox()` | `page.get_crop_box()` |
| `page.getRotation()` | `page.get_rotation()` |
| `page.getContents()` | `page.get_contents()` |
| `page.getResources()` | `page.get_resources()` |
| `page.getAnnotations()` | `page.get_annotations()` |
| `page.addAnnotation(a)` | `page.add_annotation(a)` |
| `info.getTitle()` | `info.get_title()` |
| `info.setTitle("...")` | `info.set_title("...")` |
| `info.getCreationDate()` | `info.get_creation_date()` |
| `info.setCreationDate(cal)` | `info.set_creation_date(dt)` |
| `tree.getCount()` | `tree.get_count()` |
| `dict.getCOSName(key)` | `dict.get_cos_name(key)` |
| `dict.getDictionaryObject(key)` | `dict.get_dictionary_object(key)` |
| `dict.setItem(key, value)` | `dict.set_item(key, value)` |
| `dict.setName(key, "foo")` | `dict.set_name(key, "foo")` |
| `dict.setInt(key, 42)` | `dict.set_int(key, 42)` |
| `dict.containsKey(key)` | `dict.contains_key(key)` |
| `dict.keySet()` | `dict.key_set()` |
| `dict.entrySet()` | `dict.entry_set()` |
| `array.add(value)` | `array.add(value)` |
| `array.get(i)` | `array.get(i)` |
| `array.size()` | `array.size()` |
| `string.getString()` | `string.get_string()` |
| `string.getBytes()` | `string.get_bytes()` |
| `parser.parse()` | `parser.parse()` |
| `parser.getDocument()` | `parser.get_document()` |
| `parser.isLenient()` | `parser.is_lenient()` |
| `parser.setLenient(true)` | `parser.set_lenient(True)` |
| `stripper.setStartPage(1)` | `stripper.set_start_page(1)` |
| `stripper.setEndPage(5)` | `stripper.set_end_page(5)` |
| `stripper.setSortByPosition(true)` | `stripper.set_sort_by_position(True)` |
| `stripper.getText(doc)` | `stripper.get_text(doc)` |
| `renderer.renderImage(0)` | `renderer.render_image(0)` |
| `renderer.renderImageWithDPI(0, 300)` | `renderer.render_image_with_dpi(0, 300.0)` |
| `font.getName()` | `font.get_name()` |
| `font.encode(...)` | `font.encode(...)` |
| `resources.add(font)` | `resources.add(font)` |
| `resources.getFont(name)` | `resources.get_font(name)` |

Acronyms remain uppercased in class names (`COSDictionary`,
`PDFParser`, `PDFRenderer`, `XMPMetadata`) but split at the
camelCase boundary in method names (`get_pdf_source`,
`get_cos_object`, `set_acro_form`). This matches Python's PEP 8
guidance for snake_case method names that contain acronyms and is
applied uniformly.

## Preserved verbatim

These are the things you should not expect to translate. They look
exactly like upstream.

- **Class names.** `COSDictionary` stays `COSDictionary` — not
  `CosDictionary`, not `Dictionary`. `COSArray`, `COSStream`,
  `COSName`, `COSInteger`, `COSFloat`, `COSBoolean`, `COSObject`,
  `COSString`, `COSDocument`. `PDDocument`, `PDPage`, `PDPageTree`,
  `PDResources`, `PDRectangle`, `PDDocumentCatalog`,
  `PDDocumentInformation`. `PDFParser`, `BaseParser`, `COSParser`,
  `PDFRenderer`, `PageDrawer`, `PDFStreamEngine`, `PDFTextStripper`,
  `PDFTextStripperByArea`, `LegacyPDFStreamEngine`, `COSWriter`,
  `ContentStreamWriter`, `XrefTrailerResolver`. Everything keeps
  its upstream identifier.
- **Package paths.** Drop the `org.apache.` prefix and lowercase
  the rest. `org.apache.pdfbox.cos.COSName` becomes
  `pypdfbox.cos.COSName`. `org.apache.pdfbox.pdmodel.PDDocument`
  becomes `pypdfbox.pdmodel.PDDocument` (the top-level
  `pypdfbox` re-exports the most-used names from `pypdfbox.pdmodel`
  as a convenience). `org.apache.fontbox.ttf.TTFParser` becomes
  `pypdfbox.fontbox.ttf.TTFParser`. The module layout is
  mirror-flat; nothing has been merged or split.
- **Inheritance hierarchies.** `BaseParser` -> `COSParser` ->
  `PDFParser` is preserved exactly. `COSBase` -> `COSDocument`,
  `COSDictionary`, `COSArray`, `COSStream` (the last via
  `COSDictionary` as upstream models it). `PDFStreamEngine` ->
  `LegacyPDFStreamEngine` -> `PDFTextStripper` ->
  `PDFTextStripperByArea`, `FilteredTextStripper`. No collapse
  even when the intermediate class is small.
- **Lazy loading and force-parsing.** Indirect objects resolve on
  read; force-parsing via the parser's `parse()` traversal honours
  the same lazy-vs-eager distinction; xref preservation across
  incremental updates is byte-identical to upstream.
- **Object streams.** Object-stream parsing, generation, and
  promotion follow upstream's policy. The trailer rebuild during
  `save_incremental` mirrors upstream's behaviour, including the
  trailing `/Prev` chain and the explicit `Startxref` placement.
- **Incremental append.** `save_incremental(out)` writes the
  appended xref + trailer at the end of the original byte stream
  with no compaction. The original bytes are preserved verbatim.

## Python idiom adjustments

A few cases where the Java pattern does not map directly to Python
have been re-expressed using the standard Python idiom. None of
these are observable in object state — they are language-surface
adjustments only.

| Java pattern | Python adjustment |
|---|---|
| `try (PDDocument doc = Loader.loadPDF(f)) {...}` | `with PDDocument.load("f.pdf") as doc: ...` |
| `Iterator<PDPage> it = pages.iterator(); while(it.hasNext()){...}` | `for page in pages: ...` |
| `List<PDPage> pages = doc.getPages();` | `pages = doc.get_pages()` returns `PDPageTree`, iterable as a `list[PDPage]` |
| `Map<COSName, COSBase> entries = dict.entrySet();` | `dict.entry_set()` returns an iterable of `(COSName, COSBase)` pairs |
| `Optional<PDOutlineItem> root = ...` | `root: PDOutlineItem | None = ...` |
| `boolean flag = ...` | `flag: bool = ...` |
| `throw new IOException("bad");` | `raise OSError("bad")` (Loader boundary); `raise PDFParseError("bad")` (parser layer) |
| `throw new IllegalArgumentException("...")` | `raise ValueError("...")` |
| `throw new IllegalStateException("...")` | `raise RuntimeError("...")` or `raise ValueError("...")` |
| `throw new UnsupportedOperationException("...")` | `raise NotImplementedError("...")` |
| `throw new NullPointerException(...)` | `raise TypeError("expected X; got None")` |
| `Calendar getCreationDate()` | `datetime.datetime get_creation_date()` (timezone-aware) |
| `byte[]` | `bytes` (immutable) or `bytearray` (mutable) |
| `String` | `str` |
| `int` (32-bit) | `int` (unbounded; behaviourally equivalent for PDF values) |
| `float` / `double` | `float` (Python is 64-bit by default; matches Java `double`) |
| `Color packed ARGB int` | `tuple[float, float, float]` from `PDColor.to_rgb()`; packed int via `to_rgb_int()` |

Exception types worth knowing by sight:

- `PDFParseError` — `pypdfbox.pdfparser.PDFParseError`, mirrors
  upstream's `IOException` raised from anywhere inside the parser
  family. The Loader boundary wraps this in `OSError` to match
  `Loader.loadPDF` semantics; if you parse directly via
  `PDFParser`, you will see `PDFParseError`.
- `MissingResourceException` — `pypdfbox.pdmodel.MissingResourceException`,
  raised when a resource lookup against `PDResources` cannot
  resolve. Mirrors upstream `org.apache.pdfbox.pdmodel.MissingResourceException`.
- `MissingImageReaderException` — raised by the rendering layer
  when an embedded image filter has no decoder available.

## Method signature notes (no Java overloads)

Python does not support method overloading by parameter type. Where
upstream PDFBox exposed multiple constructors or methods with the
same name and different signatures, pypdfbox folds them into a
single method that branches internally on argument type. The full
upstream call site list is preserved — only the dispatch is moved
from the call site to the receiver.

The pattern in practice:

```java
// Java (PDFBox 3.0.x)
new PDPage();
new PDPage(PDRectangle.A4);
new PDPage(existingDict);
```

```python
# Python (pypdfbox)
PDPage()                 # blank Letter-size page
PDPage(PDRectangle.A4)   # blank A4 page
PDPage(existing_dict)    # wrap an existing COSDictionary
```

`PDPage.__init__` accepts `COSDictionary | PDRectangle | None`
and dispatches internally on type. The "give me a typed COSDict"
overload, the "give me a blank page sized X" overload, and the
"give me a blank Letter page" overload all reach the same
constructor.

The same pattern applies for `PDColor`:

```python
# All upstream PDColor constructors map to one Python signature
# that branches on argument shape (see pypdfbox.pdmodel.graphics.color.PDColor)
PDColor((0.0, 0.0, 1.0), color_space=PDDeviceRGB.INSTANCE)
PDColor(COSName.getPDFName("MyPattern"), color_space=pattern_cs)
PDColor(cos_array, color_space=device_rgb)
```

`Loader` follows the same convention. Upstream's
`Loader.loadPDF(File)`, `Loader.loadPDF(InputStream)`,
`Loader.loadPDF(byte[])`, and `Loader.loadPDF(RandomAccessRead)`
all collapse into `Loader.load_pdf(source, password=None,
memory_usage_setting=None)`. The first positional argument accepts
`str | os.PathLike[str] | bytes | bytearray | memoryview |
BinaryIO | RandomAccessRead`. The Loader also exposes
`load_pdf_from_bytes` and `load_pdf_from_file` as eager
type-checking aliases when you want a clear error at the boundary.

`PDDocument.load` is the convenience top-level entry point. It
forwards to `Loader.load_pdf` and returns a `PDDocument`. Prefer
this for new code:

```python
from pypdfbox import PDDocument

with PDDocument.load("input.pdf") as doc:
    print(doc.get_number_of_pages())
```

## Naming-deviation gotchas

The snake_case translation is mechanical and, in a handful of
cases, this surfaces an upstream typo verbatim. The most visible
example lives at `pypdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment`:

```python
attachment.set_attachement_name("contract.pdf")  # sic, "Attachement"
```

The misspelling `Attachement` is on upstream's Java public API
(`PDAnnotationFileAttachment.setAttachementName`) and pypdfbox
preserves it under the strict-parity rule. Do not assume any
"obvious" rename has been silently fixed; if the upstream identifier
is wrong, the port preserves it.

A handful of acronym splits look unusual at first read but are
deliberate. `getCOSObject` becomes `get_cos_object`, not
`get_c_o_s_object`. `getURI` becomes `get_uri`. `getCMYK` would
become `get_cmyk` (acronym lowercased as a block, no underscores
inside). `setPDFA` -> `set_pdfa`. When in doubt, search the
identifier in source — pypdfbox uses one spelling per method and it
is the one returned by your IDE's autocomplete on the live class.

## Encoding and I/O

Python's split between `bytes` and `str` is sharper than Java's
between `byte[]` and `String`. pypdfbox honours the split:

- Anything labelled "raw PDF bytes" returns `bytes`. `COSString.get_bytes()`,
  `page.get_contents()`, `COSStream.create_input_stream().read()` all
  return `bytes`.
- Anything labelled "decoded text" returns `str`. `COSString.get_string()`
  decodes per the PDF 32000-1 rules (PDFDocEncoding for unmarked
  literal strings, UTF-16BE for BOM-marked strings) and returns
  `str`. `info.get_title()`, `info.get_author()`, and friends all
  return `str`.
- Passing `str` where `bytes` is expected raises `TypeError` at the
  boundary; `bytes`-vs-`str` confusion is one of the few translation
  bugs that surface immediately rather than corrupting your output.

File paths follow the standard `os.PathLike` convention. Anywhere a
PDFBox method took a `java.io.File`, the pypdfbox equivalent
accepts `str` or any `pathlib.Path` (or any other `PathLike`):

```python
from pathlib import Path
from pypdfbox import PDDocument

doc = PDDocument.load(Path.home() / "Documents" / "input.pdf")
```

Stream inputs follow Python's `BinaryIO` convention. Anywhere
upstream takes `InputStream`, pypdfbox accepts any object with a
`.read(n)` method that returns `bytes`. Stream contents are read
into memory at parse time (matching the upstream
`RandomAccessReadBuffer.create_buffer_from_stream` contract); the
caller's stream is closed immediately after buffering.

## Concurrency and threading

pypdfbox is not thread-safe. Mirror upstream's contract: one
`PDDocument` per thread. Sharing a `PDDocument`, a `COSDocument`,
or any of the parser's intermediate state across threads is not
supported. The same applies to derived objects (`PDPage`,
`PDDocumentCatalog`, etc.) — they hold references into the parent
document's lazy-load state and mutating them concurrently will
corrupt the object graph.

The GIL is not released in any of pypdfbox's pure-Python hot loops.
For embarrassingly-parallel page rendering, use `multiprocessing`
with each worker opening its own `PDDocument`. The skia-backed
rasteriser used by `PDFRenderer` releases the GIL inside skia
itself, so a single PDF being rendered page-by-page in a thread
pool may see modest speedup; CPU-bound parsing and content-stream
work will not.

## Resource lifecycle

`PDDocument` is closeable. Three ways to use it:

```python
# 1. Context-manager (preferred; matches Java try-with-resources)
with PDDocument.load("input.pdf") as doc:
    doc.get_document_catalog()
# doc is closed here

# 2. Explicit close
doc = PDDocument.load("input.pdf")
try:
    doc.get_document_catalog()
finally:
    doc.close()

# 3. Fire-and-forget (relies on garbage collection — discouraged for
#    documents backed by mmap or scratch files, since the underlying
#    file handle stays open until GC)
doc = PDDocument.load("input.pdf")
```

`close()` releases:

- The owned `RandomAccessRead` (file handle / mmap / buffer).
- The `ScratchFile` allocator if pypdfbox created one for the
  document (heap-only `MemoryUsageSetting` skips this).
- Any `TrueTypeFont` instances registered via
  `register_true_type_font_for_closing`.
- Pending in-memory caches.

Encrypted PDFs follow the upstream auto-decrypt-on-load pattern:
pass the password to `Loader.load_pdf` (or `PDDocument.load`) and
the security handler is wired in before the first content stream
is decoded. Passing `password=""` (empty string) is the canonical
"try blank user password" shape and works on PDFs that were
encrypted with a blank user password and a non-trivial owner
password.

## Common stumbling blocks

The five surprises most likely to bite a PDFBox developer on day
one with pypdfbox:

1. **Standard 14 fonts substitute via Liberation TTFs.** Apache
   PDFBox 3.0.x ships its own pre-built Standard 14 metrics + AFM
   files. pypdfbox cannot redistribute those (their license is
   incompatible with Apache 2.0). Instead, pypdfbox bundles
   Liberation Sans / Liberation Serif / Liberation Mono (SIL OFL)
   and DejaVu Sans (Bitstream Vera + public-domain changes) and
   uses them as drop-in metric-compatible substitutes for Helvetica,
   Times, Courier, Symbol, and ZapfDingbats. The substitute set
   covers Latin, Cyrillic, Greek, Hebrew, and Arabic glyphs.
   Glyphs outside the substitute set (CJK in particular) fall back
   to `.notdef`. The substitution is transparent — `PDType1Font.get_font_box_font()`
   returns the resolved fallback, so glyph metrics and outlines are
   consistent end-to-end.

2. **CJK content needs an opt-in install.** No CJK font ships with
   pypdfbox by default. To enable the Noto Sans CJK fallback:

   ```sh
   pip install pypdfbox[cjk]
   export PYPDFBOX_CJK_AUTODOWNLOAD=1
   ```

   Both gates must be set: the `[cjk]` extra is the licensing
   consent marker (the SIL OFL 1.1 Noto Sans CJK fonts are fetched
   from the internet at first use), and the environment variable
   is the per-run consent for the network fetch. Without both,
   unembedded CJK content renders as `.notdef`.

3. **Color is a tuple, not a packed int.** Upstream's
   `PDColor.toRGB()` returns a packed `int` containing R, G, B
   bytes. pypdfbox's `PDColor.to_rgb()` returns
   `tuple[float, float, float]` with each component in `[0.0, 1.0]`.
   If you need the packed-int form, call `to_rgb_int()` instead.
   For an alpha-aware variant, `to_rgba(opacity)` returns the
   ARGB-packed int upstream Java code expects.

4. **Dates are `datetime.datetime`, not `Calendar`.** Upstream
   PDFBox uses `java.util.Calendar` for PDF date values.
   pypdfbox uses Python's standard library `datetime.datetime`,
   timezone-aware where the source PDF carries a timezone offset.
   `info.set_creation_date(dt)` accepts any
   `datetime.datetime`; tz-naive datetimes are interpreted as
   local time, which matches upstream's `Calendar` behaviour.

5. **Bidi reordering is stdlib-based, not ICU.** Upstream PDFBox
   uses `com.ibm.icu.text.Bidi.reorderVisually` for RTL paragraph
   handling. pypdfbox uses Python's `unicodedata.bidirectional`
   stdlib — sufficient for pure-LTR and pure-RTL paragraphs, but
   not parity-equivalent for the full Unicode Bidi Algorithm on
   mixed-direction paragraphs. If you extract text from mixed
   Arabic/Latin or mixed Hebrew/English content, the visual order
   may differ from upstream. This is the single behavioural
   divergence documented in `CHANGES.md` "Active divergences".

## Behavioral divergences from upstream

The full list of documented divergences lives in `CHANGES.md` under
the "Active divergences vs upstream" header. As of the current
release the list contains five items:

- **ICU bidi reordering** — stdlib substitute, mixed-direction
  paragraph reordering not at parity.
- **`SimpleDateFormat` locale-sensitive parsing** —
  `pypdfbox.xmpbox.date_converter.parse_simple_date` is
  regex-driven; alpha-start patterns (`"Friday, January 11, 2115"`)
  fall through. Digit-start patterns are at parity.
- **`split_on_space` / `tokenize_on_space`** — Python `re.split`
  semantics differ from Java `String.split` on trailing-empty
  handling for all-whitespace inputs. Same tokens, different empty
  buckets.
- **`PDFRenderer` pixel-exact parity** — not portable. pypdfbox uses
  Pillow + skia-python rasterisation; byte-equivalent pixel output
  vs Java2D is not achievable. Structural parity is used for
  rendering tests (page count, MediaBox, Rotation, Contents shape,
  Resources keys, save-reload round-trip).
- **Skia anti-aliasing vs Java2D AA** — edge pixels may differ at
  low rasterisation resolutions.

Items deferred but not yet active divergences are tracked on the
[issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues),
each with a one-line summary and estimated effort.

## Performance characteristics

Pure-Python overhead dominates the inner-byte loops of the parser
and the content-stream engine. Indicative timings (your numbers
will differ — these are recent-development snapshots from the
benchmark module under `pypdfbox/benchmark/`):

- **Parse + render a 50-page text-heavy PDF at 150 DPI**: roughly
  5-10x slower than upstream Java PDFBox on the same hardware. Skia
  rasterisation is the dominant cost at high DPI and is GIL-free, so
  thread-pool parallelism over the page range scales close to linearly
  for the rendering step.
- **Parse-only (no render)**: roughly 2-5x slower than upstream. The
  cost is concentrated in `BaseParser.parse_token` and `COSParser`'s
  object-dispatch dictionary; both are pure-Python state machines.
- **Save + xref rebuild**: within 1.5x of upstream on most documents.
  The xref-rebuild path is dominated by sort + format, both stdlib
  hot paths.

Mitigations the port relies on, all permissively licensed:

- `skia-python` for rasterisation (BSD).
- `Pillow` for image decode and PIL compositing (HPND).
- `cryptography` for PDF security handlers (Apache 2.0 / BSD).
- `fontTools` for TrueType / OpenType / Type1 / Type1C glyph
  outlines (MIT).
- `imagecodecs` for CCITT Fax, LZW, JBIG2 fallback (BSD).
- `defusedxml` for XMP metadata + XFDF parsing (PSF).

No custom C extensions are shipped by pypdfbox itself.

## Mapping table: Java class to Python module

Append-only lookup. Pulled from `PROVENANCE.md`; consult that
file for the full per-file table including ported upstream test
files.

| upstream Java path | pypdfbox path |
|---|---|
| `org.apache.pdfbox.Loader` | `pypdfbox.Loader` (re-export of `pypdfbox.loader.Loader`) |
| `org.apache.pdfbox.io.RandomAccessRead` | `pypdfbox.io.random_access_read.RandomAccessRead` |
| `org.apache.pdfbox.io.RandomAccessWrite` | `pypdfbox.io.random_access_write.RandomAccessWrite` |
| `org.apache.pdfbox.io.MemoryUsageSetting` | `pypdfbox.io.memory_usage_setting.MemoryUsageSetting` |
| `org.apache.pdfbox.io.ScratchFile` | `pypdfbox.io.scratch_file.ScratchFile` |
| `org.apache.pdfbox.io.ScratchFileBuffer` | `pypdfbox.io.scratch_file_buffer.ScratchFileBuffer` |
| `org.apache.pdfbox.cos.COSBase` | `pypdfbox.cos.cos_base.COSBase` |
| `org.apache.pdfbox.cos.COSName` | `pypdfbox.cos.cos_name.COSName` |
| `org.apache.pdfbox.cos.COSString` | `pypdfbox.cos.cos_string.COSString` |
| `org.apache.pdfbox.cos.COSInteger` | `pypdfbox.cos.cos_integer.COSInteger` |
| `org.apache.pdfbox.cos.COSFloat` | `pypdfbox.cos.cos_float.COSFloat` |
| `org.apache.pdfbox.cos.COSBoolean` | `pypdfbox.cos.cos_boolean.COSBoolean` |
| `org.apache.pdfbox.cos.COSNull` | `pypdfbox.cos.cos_null.COSNull` |
| `org.apache.pdfbox.cos.COSNumber` | `pypdfbox.cos.cos_number.COSNumber` |
| `org.apache.pdfbox.cos.COSArray` | `pypdfbox.cos.cos_array.COSArray` |
| `org.apache.pdfbox.cos.COSDictionary` | `pypdfbox.cos.cos_dictionary.COSDictionary` |
| `org.apache.pdfbox.cos.COSStream` | `pypdfbox.cos.cos_stream.COSStream` |
| `org.apache.pdfbox.cos.COSObject` | `pypdfbox.cos.cos_object.COSObject` |
| `org.apache.pdfbox.cos.COSObjectKey` | `pypdfbox.cos.cos_object_key.COSObjectKey` |
| `org.apache.pdfbox.cos.COSDocument` | `pypdfbox.cos.cos_document.COSDocument` |
| `org.apache.pdfbox.cos.ICOSVisitor` | `pypdfbox.cos.i_cos_visitor.ICOSVisitor` |
| `org.apache.pdfbox.pdfparser.BaseParser` | `pypdfbox.pdfparser.base_parser.BaseParser` |
| `org.apache.pdfbox.pdfparser.COSParser` | `pypdfbox.pdfparser.cos_parser.COSParser` |
| `org.apache.pdfbox.pdfparser.PDFParser` | `pypdfbox.pdfparser.pdf_parser.PDFParser` |
| `org.apache.pdfbox.pdfparser.XrefTrailerResolver` | `pypdfbox.pdfparser.xref_trailer_resolver.XrefTrailerResolver` |
| `org.apache.pdfbox.pdfwriter.COSWriter` | `pypdfbox.pdfwriter.cos_writer.COSWriter` |
| `org.apache.pdfbox.pdfwriter.ContentStreamWriter` | `pypdfbox.pdfwriter.content_stream_writer.ContentStreamWriter` |
| `org.apache.pdfbox.pdfwriter.COSStandardOutputStream` | `pypdfbox.pdfwriter.cos_standard_output_stream.COSStandardOutputStream` |
| `org.apache.pdfbox.pdmodel.PDDocument` | `pypdfbox.pdmodel.pd_document.PDDocument` |
| `org.apache.pdfbox.pdmodel.PDDocumentCatalog` | `pypdfbox.pdmodel.pd_document_catalog.PDDocumentCatalog` |
| `org.apache.pdfbox.pdmodel.PDDocumentInformation` | `pypdfbox.pdmodel.pd_document_information.PDDocumentInformation` |
| `org.apache.pdfbox.pdmodel.PDPage` | `pypdfbox.pdmodel.pd_page.PDPage` |
| `org.apache.pdfbox.pdmodel.PDPageTree` | `pypdfbox.pdmodel.pd_page_tree.PDPageTree` |
| `org.apache.pdfbox.pdmodel.PDResources` | `pypdfbox.pdmodel.pd_resources.PDResources` |
| `org.apache.pdfbox.pdmodel.PDPageContentStream` | `pypdfbox.pdmodel.pd_page_content_stream.PDPageContentStream` |
| `org.apache.pdfbox.pdmodel.common.PDRectangle` | `pypdfbox.pdmodel.pd_rectangle.PDRectangle` |
| `org.apache.pdfbox.pdmodel.PageLayout` | `pypdfbox.pdmodel.page_layout.PageLayout` |
| `org.apache.pdfbox.pdmodel.PageMode` | `pypdfbox.pdmodel.page_mode.PageMode` |
| `org.apache.pdfbox.pdmodel.PDPageLabels` | `pypdfbox.pdmodel.pd_page_labels.PDPageLabels` |
| `org.apache.pdfbox.pdmodel.PDViewerPreferences` | `pypdfbox.pdmodel.pd_viewer_preferences.PDViewerPreferences` |
| `org.apache.pdfbox.pdmodel.font.PDFont` | `pypdfbox.pdmodel.font.pd_font.PDFont` |
| `org.apache.pdfbox.pdmodel.font.PDType1Font` | `pypdfbox.pdmodel.font.pd_type1_font.PDType1Font` |
| `org.apache.pdfbox.pdmodel.font.PDTrueTypeFont` | `pypdfbox.pdmodel.font.pd_true_type_font.PDTrueTypeFont` |
| `org.apache.pdfbox.pdmodel.font.PDType0Font` | `pypdfbox.pdmodel.font.pd_type0_font.PDType0Font` |
| `org.apache.pdfbox.pdmodel.font.Standard14Fonts` | `pypdfbox.pdmodel.font.standard14_fonts.Standard14Fonts` |
| `org.apache.pdfbox.pdmodel.graphics.color.PDColor` | `pypdfbox.pdmodel.graphics.color.pd_color.PDColor` |
| `org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace` | `pypdfbox.pdmodel.graphics.color.pd_color_space.PDColorSpace` |
| `org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB` | `pypdfbox.pdmodel.graphics.color.pd_device_rgb.PDDeviceRGB` |
| `org.apache.pdfbox.pdmodel.graphics.color.PDDeviceCMYK` | `pypdfbox.pdmodel.graphics.color.pd_device_cmyk.PDDeviceCMYK` |
| `org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray` | `pypdfbox.pdmodel.graphics.color.pd_device_gray.PDDeviceGray` |
| `org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation` | `pypdfbox.pdmodel.interactive.annotation.pd_annotation.PDAnnotation` |
| `org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment` | `pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment.PDAnnotationFileAttachment` |
| `org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm` | `pypdfbox.pdmodel.interactive.form.pd_acro_form.PDAcroForm` |
| `org.apache.pdfbox.pdmodel.interactive.form.PDField` | `pypdfbox.pdmodel.interactive.form.pd_field.PDField` |
| `org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem` | `pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item.PDOutlineItem` |
| `org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDStructureTreeRoot` | `pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_structure_tree_root.PDStructureTreeRoot` |
| `org.apache.pdfbox.pdmodel.encryption.StandardSecurityHandler` | `pypdfbox.pdmodel.encryption.standard_security_handler.StandardSecurityHandler` |
| `org.apache.pdfbox.pdmodel.fdf.FDFDocument` | `pypdfbox.pdmodel.fdf.fdf_document.FDFDocument` |
| `org.apache.pdfbox.contentstream.PDFStreamEngine` | `pypdfbox.contentstream.pdf_stream_engine.PDFStreamEngine` |
| `org.apache.pdfbox.contentstream.PDContentStream` | `pypdfbox.contentstream.pd_content_stream.PDContentStream` |
| `org.apache.pdfbox.text.PDFTextStripper` | `pypdfbox.text.pdf_text_stripper.PDFTextStripper` |
| `org.apache.pdfbox.text.PDFTextStripperByArea` | `pypdfbox.text.pdf_text_stripper_by_area.PDFTextStripperByArea` |
| `org.apache.pdfbox.text.TextPosition` | `pypdfbox.text.text_position.TextPosition` |
| `org.apache.pdfbox.text.LegacyPDFStreamEngine` | `pypdfbox.text.legacy_pdf_stream_engine.LegacyPDFStreamEngine` |
| `org.apache.pdfbox.rendering.PDFRenderer` | `pypdfbox.rendering.pdf_renderer.PDFRenderer` |
| `org.apache.pdfbox.rendering.PageDrawer` | `pypdfbox.rendering.page_drawer.PageDrawer` |
| `org.apache.pdfbox.rendering.PageDrawerParameters` | `pypdfbox.rendering.page_drawer_parameters.PageDrawerParameters` |
| `org.apache.pdfbox.rendering.ImageType` | `pypdfbox.rendering.image_type.ImageType` |
| `org.apache.pdfbox.rendering.RenderDestination` | `pypdfbox.rendering.render_destination.RenderDestination` |
| `org.apache.fontbox.ttf.TTFParser` | `pypdfbox.fontbox.ttf.ttf_parser.TTFParser` |
| `org.apache.fontbox.ttf.TrueTypeFont` | `pypdfbox.fontbox.ttf.true_type_font.TrueTypeFont` |
| `org.apache.fontbox.cff.CFFParser` | `pypdfbox.fontbox.cff.cff_parser.CFFParser` |
| `org.apache.fontbox.type1.Type1Font` | `pypdfbox.fontbox.type1.type1_font.Type1Font` |
| `org.apache.xmpbox.XMPMetadata` | `pypdfbox.xmpbox.xmp_metadata.XMPMetadata` |
| `org.apache.pdfbox.multipdf.PDFMergerUtility` | `pypdfbox.multipdf.pdf_merger_utility.PDFMergerUtility` |
| `org.apache.pdfbox.multipdf.Splitter` | `pypdfbox.multipdf.splitter.Splitter` |
| `org.apache.pdfbox.multipdf.Overlay` | `pypdfbox.multipdf.overlay.Overlay` |
| `org.apache.pdfbox.tools.PDFBox` | `pypdfbox.tools.pdfbox.PDFBox` (CLI entry point) |

For the complete table including every individual ported file plus
its derivation scope (interface-only vs full port vs adapter), see
`PROVENANCE.md` at the repository root. For per-file behavioral
divergences vs upstream, see `CHANGES.md` "Per-file deviations".

## Where to go next

- `README.md` — installation and the 30-second quick start.
- `docs/install.md` — extras matrix, platform-specific notes,
  troubleshooting native-build issues.
- `CHANGES.md` — full changelog and the canonical "Active
  divergences" list.
- The [issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues)
  — gaps vs upstream still on the work-queue.
- `PROVENANCE.md` — full per-file port-tracking table.
- `pypdfbox/examples/` — runnable scripts mirroring upstream's
  `org.apache.pdfbox.examples.*`.
