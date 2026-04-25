# PROVENANCE

This file tracks every source file in `pypdfbox/` that is **ported from Apache PDFBox**, satisfying Apache 2.0 §4(b) ("notices stating that You changed the files") in one centralized place.

## Conventions

- Entries are grouped by `pypdfbox/` module.
- Each row records the **pypdfbox path**, the **upstream PDFBox version** the port was derived from, and the **upstream Java path**.
- Files that have **no** PDFBox counterpart (Python-only utilities, glue, net-new code) are **not** listed here. Their absence here means: original work.
- For per-port behavioral changes vs upstream, see `CHANGES.md`.

## Upstream baseline

- Apache PDFBox **3.0.x latest stable** at time of port. Designed to align with PDFBox 4.0 changes (Preflight removed; see `CLAUDE.md` § PDFBox 4.0 Alignment Notes).
- Upstream repository: https://github.com/apache/pdfbox

## Ported files

### `pypdfbox/io/`

Per PRD §3.7 (stdlib-first), the io module is adapter code over Python stdlib (`io.BytesIO`, `io.BufferedReader`, etc.). Only the **interface contracts** below derive from PDFBox; concrete implementations are original work wrapping stdlib.

| pypdfbox path | upstream PDFBox version | upstream Java path | derivation scope |
|---|---|---|---|
| `pypdfbox/io/random_access_read.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/RandomAccessRead.java` | interface contract only (method signatures + semantics) |
| `pypdfbox/io/random_access_write.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/RandomAccessWrite.java` | interface contract only |
| `pypdfbox/io/memory_usage_setting.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/MemoryUsageSetting.java` | API surface (modes, factories, predicates) |
| `pypdfbox/io/scratch_file.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/ScratchFile.java` | API surface (`create_buffer()`, lifecycle); storage is `tempfile.SpooledTemporaryFile`, not page-based |

Original work (no PROVENANCE entry needed; listed here for clarity):
- `pypdfbox/io/random_access_read_buffer.py` — adapter over `io.BytesIO`
- `pypdfbox/io/random_access_read_buffered_file.py` — adapter over `io.BufferedReader`
- `pypdfbox/io/random_access_read_memory_mapped.py` — adapter over `mmap.mmap`
- `pypdfbox/io/random_access_read_view.py` — slice view, original
- `pypdfbox/io/random_access_write_buffer.py` — adapter over `io.BytesIO`
- `pypdfbox/io/io_utils.py` — small convenience helpers (most usage delegates to stdlib)

### `pypdfbox/cos/`

PDF-specific code, not stdlib-adapter territory. Ports the PDFBox COS object model.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/cos/cos_base.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSBase.java` |
| `pypdfbox/cos/i_cos_visitor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/ICOSVisitor.java` (with `visit_from_object` per 4.0) |
| `pypdfbox/cos/cos_name.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSName.java` |
| `pypdfbox/cos/cos_string.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSString.java` |
| `pypdfbox/cos/cos_integer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSInteger.java` |
| `pypdfbox/cos/cos_float.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSFloat.java` |
| `pypdfbox/cos/cos_boolean.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSBoolean.java` |
| `pypdfbox/cos/cos_null.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSNull.java` |
| `pypdfbox/cos/cos_array.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSArray.java` |
| `pypdfbox/cos/cos_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSDictionary.java` |
| `pypdfbox/cos/cos_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSObject.java` |
| `pypdfbox/cos/cos_object_key.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSObjectKey.java` |
| `pypdfbox/cos/cos_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSStream.java` |
| `pypdfbox/cos/cos_document.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSDocument.java` |

### `pypdfbox/pdfparser/`
_(not started)_

### `pypdfbox/pdfwriter/`
_(not started)_

### `pypdfbox/filter/`
_(not started)_

### `pypdfbox/contentstream/`
_(not started)_

### `pypdfbox/text/`
_(not started)_

### `pypdfbox/rendering/`
_(not started)_

### `pypdfbox/pdmodel/`
_(not started)_

### `pypdfbox/fontbox/`
_(not started)_

### `pypdfbox/xmpbox/`
_(not started)_

### `pypdfbox/tools/`
_(not started)_
