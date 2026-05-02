from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


def _stream_bytes(page: PDPage) -> bytes:
    return page.get_contents()


# ------------------------------------------------------------------
# path / curve operators
# ------------------------------------------------------------------


def test_curve_to_1_emits_v() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.curve_to_1(1, 2, 3, 4)
    assert _stream_bytes(page) == b"1 2 3 4 v\n"


def test_curve_to_2_emits_y() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.curve_to_2(5, 6, 7, 8)
    assert _stream_bytes(page) == b"5 6 7 8 y\n"


def test_curve_to2_alias_emits_v() -> None:
    """``curve_to2`` mirrors upstream's ``curveTo2`` Java method (``v``)."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.curve_to2(1, 2, 3, 4)
    assert _stream_bytes(page) == b"1 2 3 4 v\n"


def test_curve_to1_alias_emits_y() -> None:
    """``curve_to1`` mirrors upstream's ``curveTo1`` Java method (``y``)."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.curve_to1(5, 6, 7, 8)
    assert _stream_bytes(page) == b"5 6 7 8 y\n"


# ------------------------------------------------------------------
# clipping
# ------------------------------------------------------------------


def test_clip_path_emits_W() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.clip_path()
    assert _stream_bytes(page) == b"W\n"


def test_clip_path_even_odd_emits_W_star() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.clip_path_even_odd()
    assert _stream_bytes(page) == b"W*\n"


def test_clip_non_zero_rule_alias_emits_W_n() -> None:
    """``clip_non_zero_rule`` mirrors PDFBox's ``clipPath(WIND_NON_ZERO)``
    legacy spelling — same byte output as :meth:`clip`."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.clip_non_zero_rule()
    assert _stream_bytes(page) == b"W\nn\n"


def test_clip_even_odd_rule_alias_emits_W_star_n() -> None:
    """``clip_even_odd_rule`` mirrors PDFBox's ``clipPath(WIND_EVEN_ODD)``
    legacy spelling — same byte output as :meth:`clip_even_odd`."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.clip_even_odd_rule()
    assert _stream_bytes(page) == b"W*\nn\n"


# ------------------------------------------------------------------
# fill / stroke variants
# ------------------------------------------------------------------


def test_fill_even_odd_emits_f_star() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.fill_even_odd()
    assert _stream_bytes(page) == b"f*\n"


def test_fill_and_stroke_even_odd_emits_B_star() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.fill_and_stroke_even_odd()
    assert _stream_bytes(page) == b"B*\n"


def test_close_fill_and_stroke_emits_b() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.close_fill_and_stroke()
    assert _stream_bytes(page) == b"b\n"


def test_close_fill_and_stroke_even_odd_emits_b_star() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.close_fill_and_stroke_even_odd()
    assert _stream_bytes(page) == b"b*\n"


# ------------------------------------------------------------------
# dash / rendering intent / flatness
# ------------------------------------------------------------------


def test_set_dash_pattern_emits_d_with_array() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_dash_pattern([5.0, 3.0], 0.0)
    assert _stream_bytes(page) == b"[5 3] 0 d\n"


def test_set_dash_pattern_with_floats() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_dash_pattern([2.5, 1.25], 0.5)
    assert _stream_bytes(page) == b"[2.5 1.25] 0.5 d\n"


def test_set_dash_pattern_solid_line() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_dash_pattern([], 0.0)
    assert _stream_bytes(page) == b"[] 0 d\n"


def test_set_rendering_intent_emits_ri() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_rendering_intent("RelativeColorimetric")
    assert _stream_bytes(page) == b"/RelativeColorimetric ri\n"


def test_set_flatness_emits_i() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_flatness(1.5)
    assert _stream_bytes(page) == b"1.5 i\n"


# ------------------------------------------------------------------
# matrix / text
# ------------------------------------------------------------------


def test_concatenate_matrix_alias_for_transform() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.concatenate_matrix(1, 0, 0, 1, 10, 20)
    assert _stream_bytes(page) == b"1 0 0 1 10 20 cm\n"


def test_set_text_rendering_mode_emits_Tr() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_text_rendering_mode(2)
    assert _stream_bytes(page) == b"2 Tr\n"


def test_set_text_rendering_mode_accepts_0_through_7() -> None:
    for mode in range(8):
        doc = PDDocument()
        page = _make_page(doc)
        with PDPageContentStream(doc, page) as cs:
            cs.set_text_rendering_mode(mode)
        assert _stream_bytes(page) == f"{mode} Tr\n".encode("ascii")


def test_set_text_rendering_mode_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(ValueError):
            cs.set_text_rendering_mode(8)
        with pytest.raises(ValueError):
            cs.set_text_rendering_mode(-1)
