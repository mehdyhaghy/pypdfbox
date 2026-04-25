# CHANGES

Substantive behavioral deviations of pypdfbox vs upstream Apache PDFBox.
Per-release notes go here; trivial naming changes (camelCase → snake_case) are not listed.

## Format

```
- pypdfbox/<path>: <one-line description of deviation>
  upstream: PDFBox <version> <java path>
  reason: <why we deviate>
```

## Project-wide deviations vs upstream

- **No `preflight` module.** Apache PDFBox 4.0 removes Preflight; we follow that decision. PDF/A and PDF/UA validation is performed via external veraPDF / PAC.
- **No commons-logging / log4j.** Python `logging` (stdlib) is used throughout.
- **Method naming.** Java camelCase → Python snake_case across the entire API surface. Semantics unchanged.

## Per-file deviations

- `pypdfbox/io/random_access_read_buffer.py`: wraps `io.BytesIO` instead of reimplementing PDFBox's chunked-list storage. Observable behavior is identical; implementation is C-backed and ~25 lines instead of ~120. Justification: PRD §3.7 (stdlib-first for generic infrastructure).
- `pypdfbox/io/random_access_read_buffered_file.py`: wraps `io.BufferedReader` over a raw file fd. Stdlib provides the read-ahead buffering that upstream's `RandomAccessReadBufferedFile` implements manually. Justification: PRD §3.7.
- `pypdfbox/io/random_access_read_memory_mapped.py`: net-new optional implementation backed by `mmap.mmap`. No upstream counterpart; offered as opt-in for very large files where kernel paging beats userspace buffering. Justification: PRD §3.7 — use stdlib affordances when they fit.
- `pypdfbox/io/random_access_read_view.py`: original slice-view implementation. Mirrors the upstream `RandomAccessReadView` API; storage strategy is direct seek-on-parent rather than upstream's bounded-stream wrapper.
- `pypdfbox/io/scratch_file.py`: backed by `tempfile.SpooledTemporaryFile` (mixed mode), `tempfile.TemporaryFile` (temp-file-only), or `io.BytesIO` (memory-only). Upstream uses page-based scratch storage; we delegate spill-to-disk policy to stdlib. Behavior visible to callers (read/write/seek/clear) is identical. Justification: PRD §3.7. Default spill threshold in MIXED mode without an explicit cap is 16 MiB.

## Backfill — aligned with upstream test expectations

Driven by porting upstream JUnit tests (PRD §12.1):

- `pypdfbox/io/random_access_read.py`: added `read_fully(buf, offset, length)` (raises `EOFError` on premature EOF) and `skip(n)` (clamps to length). Mirrors upstream `RandomAccessRead.readFully` / `skip`.
- `pypdfbox/io/random_access_read_buffer.py`, `_buffered_file.py`, `_memory_mapped.py`, `_view.py`: `seek(negative)` now raises `OSError` (was `ValueError`), `seek(past_end)` clamps to length and leaves the stream at EOF (was: raised `ValueError`). Matches upstream PDFBox semantics; required by ported `seek*` tests.
- `pypdfbox/io/random_access_read_view.py`: removed `start_position + length > parent_length` validation (upstream allows logical views past parent end; reads simply stop at parent EOF). `create_view()` on a view raises `OSError` (upstream forbids).
- `pypdfbox/io/scratch_file.py::ScratchFileBuffer.create_view()` raises `NotImplementedError` (upstream's `UnsupportedOperationException`).
- `pypdfbox/cos/cos_number.py`: new abstract base `COSNumber` (parses string → `COSInteger`/`COSFloat`, handling exponential notation and Java-Long-out-of-range markers). `COSInteger`/`COSFloat` now extend `COSNumber`.
- `pypdfbox/cos/cos_float.py`: values are now clamped to **IEEE-754 single precision** (`float32`) on both `__init__` paths to match Java `float` semantics — required for upstream parity tests on `equals()`/`hashCode()`. `_normalize_negatives` recovers from PDFBOX-2990 / -3369 / -3500 / -4289 misplaced-`-` cases (`--16.33` → `-16.33`, `0.-262` → `-0.262`, `0.00000-33917698` → `-0.0000033917698`); raises `OSError` on unrecoverable double-`-`.
- `pypdfbox/cos/cos_integer.py`: added `is_valid()` / `set_valid()` for PDFBOX-5176 large-integer-out-of-Long-range marking.
- `pypdfbox/cos/cos_string.py`: `parse_hex` raises `OSError` (was `ValueError`) to mirror upstream `IOException`. Added `to_hex_string()`.
- `pypdfbox/cos/cos_stream.py`: `create_raw_input_stream()` raises `OSError` when no body. Added `create_input_stream()` and `create_output_stream(filters=None)` stubs that raise `NotImplementedError` when filters are requested (filter encoding lives in `filter` module).
- `pypdfbox/cos/cos_array.py`: added `remove_object`, `remove_all`, `retain_all`, `grow_to_size`, typed `set_name`/`get_name`/`set_int`/`get_int`/`set_string`/`get_string`, `set_float_array`/`to_float_array`, `to_cos_*_list` converters, factory classmethods `of_cos_names`/`of_cos_strings`/`of_cos_integers`/`of_cos_floats`. All match upstream signatures.
- `pypdfbox/cos/cos_document.py`: added `add_xref_table`, `get_objects_by_type`, `get_linearized_dictionary` (placeholder returning `None` until linearization-hint parsing lands).
- `pypdfbox/cos/cos_name.py`: added single-letter and short-name constants (`A`, `B`, `C`, `D`, `T`, `BE`, `PARAMS`, `FLATE_DECODE`, `ASCII85_DECODE`, `STANDARD_ENCODING`) referenced by ported tests.
- `pypdfbox/pdfparser/base_parser.py::read_name`: a `#` not followed by two hex digits is now kept literally rather than raising `PDFParseError`. Matches upstream `TestBaseParser.testInvalidHexSequence`.
