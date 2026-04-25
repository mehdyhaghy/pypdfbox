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
