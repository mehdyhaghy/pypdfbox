# pypdfbox.text — text extraction

`PDFTextStripper` is the canonical text-extraction entry point: feed it a
`PDDocument` and it produces line-broken, paragraph-aware Unicode output.
The implementation is a `PDFStreamEngine` subclass (via
`LegacyPDFStreamEngine`); subclass it to capture positioned text instead of
discarding it. Bidi reordering is implemented against the stdlib
`unicodedata` module — pypdfbox does not depend on ICU.

## Public surface

| Class / function | Purpose |
| --- | --- |
| `PDFTextStripper` | Full-document text extraction. `get_text(doc) -> str`, `write_text(doc, writer)`, `set_start_page(n)`, `set_end_page(n)`, `set_paragraph_start(str)`, `set_paragraph_end(str)`, `set_page_start(str)`, `set_page_end(str)`, `set_word_separator(str)`, `set_line_separator(str)`, `set_sort_by_position(bool)`. |
| `PDFTextStripperByArea` | Extract text from one or more rectangular regions. `add_region(name, rect)`, `extract_regions(page)`, `get_text_for_region(name)`. |
| `LegacyPDFStreamEngine` | Upstream-compatible base class that captures glyph positions into `TextPosition` instances. Subclass when `PDFTextStripper` is too high-level. |
| `TextPosition` | One painted glyph. Carries the page-space rotation, x/y, width, height (font-relative + text-state-adjusted), font, font size, unicode string, and individual character codes. Mirrors upstream `TextPosition` field-for-field. |
| `TextMetrics` | Aggregate metrics for a sequence of glyphs (ascent, descent, height). |
| `TextPositionComparator` | Ordering for `TextPosition` instances when reconstructing lines. |
| `PositionWrapper` | Adapter that bridges between `TextPosition` and the line-merge logic. |
| `WordWithTextPositions` | A reconstructed word + its underlying `TextPosition` list. |
| `LineItem` | One line during paragraph construction. |
| `FilteredTextStripper` | `PDFTextStripper` that filters glyphs by callback (e.g. by rotation). Used internally by the region extractor. |
| `AngleCollector` | Helper that tallies text-rotation angles on a page (used by the rotated-text detector). |
| `PDFMarkedContentExtractor` | Captures `BMC`/`BDC`/`EMC` marked-content sequences alongside their text — used by the tagged-PDF accessibility path. |
| `get_angle(text_position) -> float` | Convenience: page-space rotation angle (degrees) of a `TextPosition`. |

## Typical usage

```python
from pypdfbox import Loader
from pypdfbox.text import PDFTextStripper, PDFTextStripperByArea, PDRectangle

with Loader.load_pdf("doc.pdf") as doc:
    stripper = PDFTextStripper()
    stripper.set_sort_by_position(True)
    text = stripper.get_text(doc)
    print(text[:500])

    by_area = PDFTextStripperByArea()
    by_area.add_region("header", PDRectangle(0, 720, 612, 792))
    by_area.extract_regions(doc.get_page(0))
    print(by_area.get_text_for_region("header"))
```

## Subclassing for positions

```python
from pypdfbox.text import LegacyPDFStreamEngine, TextPosition

class CapturePositions(LegacyPDFStreamEngine):
    def __init__(self):
        super().__init__()
        self.positions: list[TextPosition] = []

    def write_string(self, string, positions):
        self.positions.extend(positions)
```

`write_string(self, string, positions)` is the per-`Tj` hook that
`PDFTextStripper` overrides. `string` is the merged Unicode for the
`Tj`/`TJ` operator; `positions` is the corresponding `list[TextPosition]`
with the per-glyph metadata.

## Bidi note

Upstream PDFBox uses ICU's bidirectional algorithm. pypdfbox uses
`unicodedata.bidirectional` and a small in-house resolver to apply the same
five-step process from UAX #9. The output matches upstream for all
Right-to-Left scripts shipped in the corpus (Arabic, Hebrew, N'Ko); if you
need ICU-grade conformance for novel scripts, override
`PDFTextStripper.normalize_word(...)`.

## PDFBox divergence

- `setSortByPosition(boolean)` → `set_sort_by_position(bool)`.
- `setStartPage(int)` and `setEndPage(int)` are 1-indexed (same as Java).
- `getText(doc)` returns a `str`; the Java `writeText(doc, Writer)` →
  `write_text(doc, file_like)` accepts any object with `.write(str)`.
- `TextPosition.getX()` / `.getY()` are kept as method-style accessors
  (not properties) for source-parity with subclasses that override them
  in the upstream code.
- The `PDFTextStripper.suppressDuplicateOverlappingText` flag is
  `suppress_duplicate_overlapping_text`.

## See also

- [contentstream.md](contentstream.md) — `PDFTextStripper`'s parent class.
- [pdmodel-font.md](pdmodel-font.md) — fonts contribute the
  glyph-name-to-Unicode mapping.
- [guides/text-extraction.md](../guides/text-extraction.md) — recipes for
  table-aware extraction.
