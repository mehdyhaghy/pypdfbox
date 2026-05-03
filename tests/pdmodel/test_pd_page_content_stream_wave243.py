"""Wave 243 — PDPageContentStream small gaps.

Covers:

- ``begin_text`` rejects nested calls (mirrors upstream's
  ``IllegalStateException`` "Error: Nested beginText() calls are not
  allowed.").
- ``end_text`` rejects unmatched calls (mirrors upstream's
  ``IllegalStateException`` "Error: You must call beginText() before
  calling endText.").
- ``is_in_text_mode`` predicate accessor — exposes the upstream
  protected ``inTextMode`` field.
- ``set_stroking_color_rgb_int`` / ``set_non_stroking_color_rgb_int``
  convenience setters that take 8-bit integer 0..255 RGB components and
  forward to the float-form RGB setters (mirrors upstream's
  ``setStrokingColor(java.awt.Color)`` /
  ``setNonStrokingColor(java.awt.Color)``).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


# ------------------------------------------------------------------
# is_in_text_mode predicate + begin_text/end_text guards
# ------------------------------------------------------------------


def test_is_in_text_mode_starts_false_and_toggles_with_bt_et() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        assert cs.is_in_text_mode() is False
        cs.begin_text()
        assert cs.is_in_text_mode() is True
        cs.end_text()
        assert cs.is_in_text_mode() is False


def test_begin_text_rejects_nested_calls() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError, match="Nested begin_text"):
            cs.begin_text()
        # Recover so the stream closes cleanly.
        cs.end_text()


def test_end_text_without_begin_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(RuntimeError, match="begin_text"):
            cs.end_text()
        # State stays consistent — predicate still False.
        assert cs.is_in_text_mode() is False


def test_end_text_after_failed_begin_text_still_works() -> None:
    """Failed nested begin_text shouldn't corrupt the state machine."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.begin_text()
        # We are still in text mode after a rejected nested begin_text.
        assert cs.is_in_text_mode() is True
        cs.end_text()
        assert cs.is_in_text_mode() is False


# ------------------------------------------------------------------
# 8-bit-int RGB color setters (AWT Color parity)
# ------------------------------------------------------------------


def test_set_stroking_color_rgb_int_emits_normalized_floats() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_rgb_int(255, 0, 128)
    body = page.get_contents()
    # 255/255 = 1, 0/255 = 0, 128/255 ≈ 0.502 (rounded to 4 digits and
    # trailing-zero-stripped by _format_number).
    assert b" RG\n" in body
    assert b"1 0 " in body  # leading r=1 g=0
    # Any 4-digit-rounded representation of 128/255 is acceptable; just
    # confirm the operator structure plus the operand triple.
    line = body.split(b"\n")[0]
    parts = line.split(b" ")
    # parts == [r, g, b, "RG"]
    assert parts[0] == b"1"
    assert parts[1] == b"0"
    assert parts[3] == b"RG"
    b_value = float(parts[2].decode())
    assert abs(b_value - 128 / 255.0) < 1e-3


def test_set_non_stroking_color_rgb_int_emits_lowercase_op() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb_int(0, 255, 0)
    body = page.get_contents()
    # 0/255 = 0, 255/255 = 1, 0/255 = 0  →  0 1 0 rg
    assert body == b"0 1 0 rg\n"


def test_set_stroking_color_rgb_int_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(ValueError, match="0..255"):
            cs.set_stroking_color_rgb_int(256, 0, 0)
        with pytest.raises(ValueError, match="0..255"):
            cs.set_stroking_color_rgb_int(0, -1, 0)
        with pytest.raises(ValueError, match="0..255"):
            cs.set_stroking_color_rgb_int(0, 0, 999)


def test_set_non_stroking_color_rgb_int_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(ValueError, match="0..255"):
            cs.set_non_stroking_color_rgb_int(-5, 0, 0)
        with pytest.raises(ValueError, match="0..255"):
            cs.set_non_stroking_color_rgb_int(255, 256, 255)


def test_rgb_int_setters_accept_zero_and_max_endpoints() -> None:
    """0..255 endpoints are inclusive (mirrors upstream's
    ``isOutside255Interval`` boundary)."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_rgb_int(0, 0, 0)
        cs.set_stroking_color_rgb_int(255, 255, 255)
        cs.set_non_stroking_color_rgb_int(0, 0, 0)
        cs.set_non_stroking_color_rgb_int(255, 255, 255)
    body = page.get_contents()
    assert body == (
        b"0 0 0 RG\n"
        b"1 1 1 RG\n"
        b"0 0 0 rg\n"
        b"1 1 1 rg\n"
    )
