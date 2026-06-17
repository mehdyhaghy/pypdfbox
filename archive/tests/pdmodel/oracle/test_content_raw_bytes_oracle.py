"""Live PDFBox differential parity for the RAW bytes
:class:`PDPageContentStream` emits.

The sibling :mod:`test_content_gen_oracle` saves a PDF and re-tokenizes the
page, which canonicalises the operator stream and therefore *cannot* catch
format-only divergences: ``2.5`` vs ``2.50000``, a missing trailing space
inside a dash array, hex vs literal ``showText`` strings, or a wrong
fraction-digit count all round-trip to the same token list. This test pins
the **literal bytes** the writer produces before any save round-trip.

The Java side (``oracle/probes/ContentRawBytesProbe.java``) builds a page
with a fixed operator sequence using ``compress=false``, reads the
freshly-written content-stream body straight out of the page's COSStream
(``createRawInputStream``), and emits it as lower-hex. We reproduce the
identical sequence with pypdfbox's :class:`PDPageContentStream`, read
``page.get_contents()``, and assert the byte streams are equal.

The only legitimate (non-bug) difference is the auto-allocated font
resource-slot name in ``Tf`` (PDFBox ``/F1`` vs pypdfbox ``/F0``); the
``text`` case normalises that one name token before comparing.

Surfaces pinned (one selector each):

- ``numbers`` — ``formatDecimal``: 5 max fraction digits, HALF_EVEN
  rounding, integral floats as bare integers, sub-threshold values, and
  negatives. (Pins the wave-1458 fix from 4 → 5 fraction digits.)
- ``colors`` — ``RG``/``rg``/``G``/``g``/``K``/``k`` operand + operator
  bytes for every device colour space, stroking + non-stroking.
- ``path`` — ``m``/``l``/``c``/``re``/``h``/``B``/``S``/``f`` framing.
- ``dash`` — ``[a b ] phase d`` (trailing space inside the bracket, empty
  pattern ``[]``). (Pins the wave-1458 dash trailing-space fix.)
- ``transform`` — ``q``/``cm``/``Q`` from a translate matrix and a full
  six-component matrix.
- ``text`` — ``BT``/``Tf``/``TL``/``Td``/``Tj``/``T*``/``ET`` plus literal
  ``( )`` string serialisation with ``( ) \\`` backslash-escaping.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _build(selector: str) -> bytes:
    """Reproduce ``ContentRawBytesProbe.draw`` for ``selector`` and return
    the raw content-stream bytes pypdfbox wrote (uncompressed)."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
        doc.add_page(page)
        font = PDType1Font()
        font.get_cos_object().set_name(
            COSName.get_pdf_name("BaseFont"), "Helvetica"
        )
        with PDPageContentStream(doc, page) as cs:
            _DRAW[selector](cs, font)
        return bytes(page.get_contents())
    finally:
        doc.close()


def _draw_numbers(cs: PDPageContentStream, _font: PDType1Font) -> None:
    cs.set_line_width(2.5)
    cs.set_line_width(1.0)        # integral float -> "1"
    cs.set_line_width(0.123456)   # -> "0.12346" (5 digits, HALF_EVEN)
    cs.set_line_width(0.00001)    # -> "0.00001" (5th digit retained)
    cs.set_line_width(100.0)      # -> "100"
    cs.set_line_width(0.5)
    cs.move_to(-1.25, 12.75)      # negatives
    cs.line_to(0.0, 3.14159)      # -> "3.14159"


def _draw_colors(cs: PDPageContentStream, _font: PDType1Font) -> None:
    cs.set_stroking_color(1.0, 0.0, 0.0)          # RG
    cs.set_non_stroking_color(0.0, 1.0, 0.0)      # rg
    cs.set_stroking_color(0.25)                   # G
    cs.set_non_stroking_color(0.75)               # g
    cs.set_stroking_color(0.1, 0.2, 0.3, 0.4)     # K
    cs.set_non_stroking_color(0.5, 0.6, 0.7, 0.8)  # k


def _draw_path(cs: PDPageContentStream, _font: PDType1Font) -> None:
    cs.move_to(0, 0)
    cs.line_to(50, 0)
    cs.curve_to(60, 10, 70, 20, 80, 30)
    cs.add_rect(5, 5, 20, 20)
    cs.close_path()
    cs.fill_and_stroke()
    cs.move_to(100, 100)
    cs.line_to(150, 150)
    cs.stroke()
    cs.add_rect(200, 200, 30, 40)
    cs.fill()


def _draw_dash(cs: PDPageContentStream, _font: PDType1Font) -> None:
    cs.set_line_dash_pattern([3, 2], 1)
    cs.set_line_dash_pattern([], 0)
    cs.set_line_dash_pattern([1.5], 0.5)
    cs.set_line_cap_style(1)
    cs.set_line_join_style(2)
    cs.set_miter_limit(4.0)


def _draw_transform(cs: PDPageContentStream, _font: PDType1Font) -> None:
    cs.save_graphics_state()
    # Matrix.getTranslateInstance(10, 20) == (1 0 0 1 10 20).
    cs.transform(1, 0, 0, 1, 10, 20)
    cs.transform(2, 0, 0, 2, 5.5, 7.25)
    cs.restore_graphics_state()


def _draw_text(cs: PDPageContentStream, font: PDType1Font) -> None:
    cs.begin_text()
    cs.set_font(font, 12)
    cs.set_leading(14)
    cs.new_line_at_offset(15, 200)
    cs.show_text("Hello")
    cs.new_line()
    cs.show_text("World")
    cs.new_line()
    # Balanced parens + backslash — escaped in the literal ( ) form.
    cs.show_text("paren (a) and \\backslash")
    cs.end_text()


_DRAW = {
    "numbers": _draw_numbers,
    "colors": _draw_colors,
    "path": _draw_path,
    "dash": _draw_dash,
    "transform": _draw_transform,
    "text": _draw_text,
}


def _normalize_font_key(data: bytes) -> bytes:
    """Replace the auto-allocated font resource-slot name (``/F<n>``)
    immediately preceding a ``Tf`` operator with a stable placeholder, so
    PDFBox's ``/F1`` and pypdfbox's ``/F0`` compare equal. Only the slot
    number is implementation-defined; everything else is load-bearing."""
    import re

    return re.sub(rb"/F\d+ (\d[^\n]*Tf)", rb"/F\1", data)


@requires_oracle
@pytest.mark.parametrize(
    "selector",
    ["numbers", "colors", "path", "dash", "transform", "text"],
)
def test_raw_content_bytes_match_pdfbox(selector: str) -> None:
    java_hex = run_probe_text("ContentRawBytesProbe", selector).strip()
    java_bytes = bytes.fromhex(java_hex)
    py_bytes = _build(selector)

    if selector == "text":
        java_bytes = _normalize_font_key(java_bytes)
        py_bytes = _normalize_font_key(py_bytes)

    assert py_bytes == java_bytes, (
        f"raw content-stream bytes diverge from PDFBox for '{selector}'.\n"
        f"--- pypdfbox ---\n{py_bytes!r}\n"
        f"--- java ---\n{java_bytes!r}"
    )
