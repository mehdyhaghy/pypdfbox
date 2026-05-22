# pypdfbox.benchmark

Port of `org.apache.pdfbox.benchmark` — micro-benchmarks for the
core pypdfbox surface. The upstream Java module is a JMH harness
(`@Benchmark` methods, `Blackhole` consume sinks); the Python port
preserves the same workload shapes but trades JMH for plain
`time.perf_counter` so the suite runs without a benchmarking
framework. Each upstream `Blackhole` is replaced with an
attribute-assignment "consume sink" that keeps the loaded /
rendered object reachable so the optimizer cannot dead-code-
eliminate the work.

## What's in here

Three benchmark suites — direct ports of the upstream Java
classes:

- **`load_and_save.py`** — `LoadAndSave`. Round-trips a medium PDF
  (`849-42-94772-1-10-20210818.pdf`) and a large PDF
  (`506-42-86246-2-10-20190822.pdf`) through `PDDocument.load()`
  and `PDDocument.save()`, with and without the object-stream
  compression path. Mirrors
  `benchmark/src/main/java/org/apache/pdfbox/benchmark/LoadAndSave.java`.
- **`rendering.py`** — `Rendering`. Rasterises three reference
  PDFs (the ECI Altona Technical 2 X4 test suite, the Ghent PDF
  Output Suite V50 CMYK X4 sample, and the ISO 32000-1 PDF spec)
  through `PDFRenderer.render_image_with_dpi`, with and without
  PNG output. Mirrors
  `benchmark/src/main/java/org/apache/pdfbox/benchmark/Rendering.java`.
- **`text_extraction.py`** — `TextExtraction`. Drives
  `PDFTextStripper.get_text` against the ISO 32000-1 spec PDF,
  once with position-based sorting on and once off. Mirrors
  `benchmark/src/main/java/org/apache/pdfbox/benchmark/TextExtraction.java`.

`null_output_stream.py` ports the upstream `NullOutputStream`
helper — a write-only sink used by the save benchmarks to avoid
measuring disk I/O.

## Running

Each benchmark class exposes one method per upstream
`@Benchmark`. Each method runs the workload once and returns the
elapsed time in milliseconds:

```python
from pypdfbox.benchmark import LoadAndSave, Rendering, TextExtraction

bench = LoadAndSave()
print(bench.load_medium_file(), "ms")
print(bench.save_medium_file(), "ms")
print(bench.save_medium_file_with_compression(), "ms")

print(Rendering().render_pdf_spec_no_output(), "ms")
print(TextExtraction().extract_pdf_spec_sorted(), "ms")
```

For statistically-meaningful numbers, drive the suite through
`pytest-benchmark` (development-time dep, not bundled at
runtime) or wrap each method in a `timeit.repeat` loop. The
single-shot methods are the lowest-friction shape — you can pipe
them into your own harness without taking on a benchmark
framework.

## Fixtures

The benchmark workloads expect the upstream PDFBox sample corpus
under `target/pdfs/` in the repository root:

- `target/pdfs/849-42-94772-1-10-20210818.pdf` — medium-size file
  for `LoadAndSave`.
- `target/pdfs/506-42-86246-2-10-20190822.pdf` — large file for
  `LoadAndSave`.
- `target/pdfs/eci_altona-test-suite-v2_technical2_x4.pdf` — ECI
  Altona Technical 2 X4 reference (rendering).
- `target/pdfs/Ghent_PDF_Output_Suite_V50_Full/Categories/1-CMYK/Test pages/Ghent_PDF-Output-Test-V50_CMYK_X4.pdf` —
  Ghent CMYK X4 (rendering).
- `target/pdfs/PDF32000_2008.pdf` — ISO 32000-1 specification PDF
  (rendering + text extraction).

These match the paths upstream's Java suite looks for, so a single
local copy of the PDFBox corpus serves both implementations.
Render output (PNG) goes to `target/renditions/`; `Rendering`
creates the directory on construction.

## Result format

Every benchmark method returns a single `float` (elapsed
milliseconds). There is no fixed report format — wrap the numbers
in whatever shape your tracking system needs (CSV row, JSON line,
`pytest-benchmark` fixture, etc.). For wave-to-wave regression
tracking we recommend logging method name + elapsed ms + git SHA
to a CSV under `.parity/`.

## Parity note

These are direct ports of the upstream benchmark workloads, not
new pypdfbox-specific suites. Per-method line references back to
the upstream Java source live in the module docstrings (e.g.
`# Mirror of loadMediumFile (line 40)` in `LoadAndSave`). The
intent is to be able to compare the same workload across the Java
and Python implementations on the same inputs.
