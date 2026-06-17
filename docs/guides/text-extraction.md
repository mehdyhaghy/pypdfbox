# Text extraction

Pypdfbox ports the upstream `PDFTextStripper` and `PDFTextStripperByArea`
class pair under [`pypdfbox.text`](../api/text.md). The lite stripper
covers single-column reading order; the by-area subclass restricts
extraction to one or more clipping rectangles.

## Strip text from a PDF

```python
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text import PDFTextStripper

with PDDocument.load("input.pdf") as doc:
    stripper = PDFTextStripper()
    text = stripper.get_text(doc)
    print(text)
```

`get_text` returns the full document text as a `str`. A `write_text`
overload is also available for callers that already hold a
file-like sink and want to skip the intermediate string allocation:

```python
from pathlib import Path

with PDDocument.load("input.pdf") as doc, Path("out.txt").open("w", encoding="utf-8") as fh:
    PDFTextStripper().write_text(doc, fh)
```

## Extract a page range

Page numbers are 1-based and inclusive, matching upstream PDFBox.

```python
with PDDocument.load("input.pdf") as doc:
    stripper = PDFTextStripper()
    stripper.set_start_page(2)
    stripper.set_end_page(4)
    print(stripper.get_text(doc))
```

When `end_page` exceeds the page count it is clamped to the last
page; the same default sentinel (`sys.maxsize`) means "to end of
document".

## Extract from a clipping region

`PDFTextStripperByArea` works one page at a time. You define named
rectangles (in PDF user-space coordinates — points, origin at the
bottom-left corner of the page) and then ask the stripper for the
text inside each one.

```python
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text import PDFTextStripperByArea

with PDDocument.load("invoice.pdf") as doc:
    page = doc.get_page(0)
    stripper = PDFTextStripperByArea()
    stripper.set_sort_by_position(True)

    header = PDRectangle(0, 720, 612, 792)   # top inch on US Letter
    body = PDRectangle(0, 72, 612, 720)
    stripper.add_region("header", header)
    stripper.add_region("body", body)

    stripper.extract_regions(page)

    print("HEADER:", stripper.get_text_for_region("header"))
    print("BODY:", stripper.get_text_for_region("body"))
```

`add_region` also accepts a 4-tuple `(llx, lly, urx, ury)` in case you
prefer not to import `PDRectangle`.

## Sort by position vs original order

By default the stripper emits text in the order operators appear in
the content stream. For PDFs whose producers write columns out of
visual order, enable position sorting:

```python
stripper.set_sort_by_position(True)
```

This is the equivalent of upstream's `setSortByPosition(true)` and
sorts text positions by their y-coordinate (line) and then by
x-coordinate (within a line).

## Custom line and page separators

```python
stripper = PDFTextStripper()
stripper.set_line_separator("\r\n")
stripper.set_word_separator(" | ")
stripper.set_page_start("--- PAGE BEGIN ---\n")
stripper.set_page_end("\n--- PAGE END ---\n")
stripper.set_paragraph_start(">>> ")
stripper.set_paragraph_end(" <<<\n")
```

Every separator is a plain string and is written verbatim around the
matching boundary. The paragraph separators feed off the same line
break heuristic that drives `set_line_separator`.

## Word-level position via TextPosition

To get pixel-level coordinates per glyph run, subclass the stripper
and override `write_string_with_positions`:

```python
from pypdfbox.text import PDFTextStripper, TextPosition


class PositionLogger(PDFTextStripper):
    def write_string_with_positions(self, text, text_positions):
        for pos in text_positions:
            print(
                f"{pos.get_character()!r} @ "
                f"({pos.get_x_dir_adj():.1f}, {pos.get_y_dir_adj():.1f}) "
                f"font={pos.get_font_name()} size={pos.get_font_size_in_pt():.1f}"
            )
        super().write_string_with_positions(text, text_positions)
```

Useful `TextPosition` accessors:

- `get_unicode()` / `get_character()` — the decoded text
- `get_x()` / `get_y()` — origin in user space
- `get_end_x()` / `get_end_y()` — end of the run
- `get_x_dir_adj()` / `get_y_dir_adj()` — rotation-aware coordinates
- `get_font_name()` / `get_font_size_in_pt()` — font metadata
- `get_width_of_space()` — the font's advance for `U+0020`

## Tuning the line-break heuristic

Upstream's full setter surface for the formatting layer is
ported. Defaults match upstream PDFBox 3.0; tune them when your
document has tight leading, deep indentation, or unusual spacing.

| Setter | Purpose | Upstream default |
|---|---|---|
| `set_drop_threshold(float)` | minimum y-gap (in multiples of font size) that triggers a paragraph break | 2.5 |
| `set_indent_threshold(float)` | minimum x-offset (in spaces) that registers as an indent | 2.0 |
| `set_spacing_tolerance(float)` | extra whitespace allowed before splitting a word | 0.5 |
| `set_average_char_tolerance(float)` | sensitivity of duplicate-glyph suppression | 0.3 |
| `set_should_separate_by_beads(bool)` | honour `/Beads` (article threads) when sorting | True |

```python
stripper = PDFTextStripper()
stripper.set_drop_threshold(3.0)
stripper.set_indent_threshold(1.5)
stripper.set_should_separate_by_beads(False)
```

## Built-in CLIs

For one-off conversion the `pypdfbox` package ships two ready-made
tools that wrap the stripper:

- `python -m pypdfbox.tools.pdf_text2_html input.pdf out.html`
- `python -m pypdfbox.tools.pdf_text2_markdown input.pdf out.md`

The umbrella CLI also exposes `pypdfbox extracttext` with `--html`,
`--md`, and `--sort` flags — see [the CLI guide](cli.md).

## See also

- [API reference: `pypdfbox.text`](../api/text.md)
- [Documentation index](../index.md)
