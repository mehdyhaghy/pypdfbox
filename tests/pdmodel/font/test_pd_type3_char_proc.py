"""Hand-written tests for :class:`PDType3CharProc`."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def _glyph_with_body(body: bytes) -> COSStream:
    s = COSStream()
    s.set_raw_data(body)
    return s


def _font_and_proc(body: bytes) -> tuple[PDType3Font, PDType3CharProc]:
    font = PDType3Font()
    glyph = _glyph_with_body(body)
    proc = PDType3CharProc(font, glyph)
    return font, proc


# ---------- back-pointer / COS surface ----------


def test_get_font_returns_parent_font() -> None:
    font, proc = _font_and_proc(b"500 0 d0\n")
    assert proc.get_font() is font


def test_get_cos_object_returns_underlying_stream() -> None:
    font, proc = _font_and_proc(b"500 0 d0\n")
    # Same object identity as the wrapped COSStream.
    assert isinstance(proc.get_cos_object(), COSStream)


def test_get_content_stream_alias_matches() -> None:
    font, proc = _font_and_proc(b"500 0 d0\n")
    assert proc.get_content_stream() is proc.get_cos_object()


# ---------- PDContentStream surface ----------


def test_get_contents_yields_decoded_bytes() -> None:
    body = b"500 0 d0\n"
    _, proc = _font_and_proc(body)
    with proc.get_contents() as stream:
        assert stream.read() == body


def test_get_contents_for_random_access_returns_random_access() -> None:
    body = b"500 0 d0\n"
    _, proc = _font_and_proc(body)
    rar = proc.get_contents_for_random_access()
    assert isinstance(rar, RandomAccessRead)
    # And it can stream the same bytes.
    out = bytearray()
    while True:
        b = rar.read()
        if b == RandomAccessRead.EOF:
            break
        out.append(b)
    assert bytes(out) == body
    rar.close()


def test_get_resources_falls_back_to_font_resources() -> None:
    font = PDType3Font()
    resources = PDResources()
    font.set_resources(resources)
    glyph = _glyph_with_body(b"")
    proc = PDType3CharProc(font, glyph)
    out = proc.get_resources()
    assert isinstance(out, PDResources)
    # Same underlying COSDictionary.
    assert out.get_cos_object() is resources.get_cos_object()


def test_get_resources_returns_none_when_font_has_none() -> None:
    font, proc = _font_and_proc(b"")
    assert proc.get_resources() is None


def test_get_matrix_delegates_to_font_font_matrix() -> None:
    font = PDType3Font()
    font.set_font_matrix([0.002, 0.0, 0.0, 0.002, 0.0, 0.0])
    glyph = _glyph_with_body(b"")
    proc = PDType3CharProc(font, glyph)
    matrix = proc.get_matrix()
    assert matrix == pytest.approx([0.002, 0.0, 0.0, 0.002, 0.0, 0.0], rel=1e-6)


def test_get_matrix_default_when_font_has_no_matrix() -> None:
    font, proc = _font_and_proc(b"")
    # Inherits PDType3Font's default identity-/1000.
    assert proc.get_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------- d1 / d0 leading-operator parsing ----------


def test_get_glyph_bbox_from_leading_d1() -> None:
    # PDF 32000-1 §9.6.5: "wx wy llx lly urx ury d1"
    body = b"600 0 50 -10 550 700 d1\nq Q\n"
    _, proc = _font_and_proc(body)
    bbox = proc.get_glyph_bbox()
    assert isinstance(bbox, PDRectangle)
    assert bbox.get_lower_left_x() == pytest.approx(50.0)
    assert bbox.get_lower_left_y() == pytest.approx(-10.0)
    assert bbox.get_upper_right_x() == pytest.approx(550.0)
    assert bbox.get_upper_right_y() == pytest.approx(700.0)


def test_get_glyph_bbox_returns_none_for_d0() -> None:
    # d0 declares width but no bbox.
    body = b"600 0 d0\nq Q\n"
    _, proc = _font_and_proc(body)
    assert proc.get_glyph_bbox() is None


def test_get_glyph_bbox_returns_none_when_stream_empty() -> None:
    _, proc = _font_and_proc(b"")
    assert proc.get_glyph_bbox() is None


def test_get_glyph_bbox_returns_none_when_no_metric_op() -> None:
    body = b"q 1 0 0 1 0 0 cm Q\n"
    _, proc = _font_and_proc(body)
    assert proc.get_glyph_bbox() is None


def test_get_glyph_bbox_handles_signed_and_real_operands() -> None:
    body = b"600.5 0 -50.25 -10.0 550.5 700.75 d1\n"
    _, proc = _font_and_proc(body)
    bbox = proc.get_glyph_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(-50.25, rel=1e-5)
    assert bbox.get_lower_left_y() == pytest.approx(-10.0, rel=1e-5)
    assert bbox.get_upper_right_x() == pytest.approx(550.5, rel=1e-5)
    assert bbox.get_upper_right_y() == pytest.approx(700.75, rel=1e-5)


def test_get_glyph_bbox_skips_leading_whitespace_and_comments() -> None:
    body = b"  \n%comment line\n  600 0 50 -10 550 700 d1\n"
    _, proc = _font_and_proc(body)
    bbox = proc.get_glyph_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(50.0)


# ---------- get_width ----------


def test_get_width_from_d0() -> None:
    body = b"600 0 d0\n"
    _, proc = _font_and_proc(body)
    assert proc.get_width() == pytest.approx(600.0)


def test_get_width_from_d1() -> None:
    body = b"720 0 50 -10 550 700 d1\n"
    _, proc = _font_and_proc(body)
    assert proc.get_width() == pytest.approx(720.0)


def test_get_width_zero_for_empty_stream() -> None:
    _, proc = _font_and_proc(b"")
    assert proc.get_width() == 0.0


def test_get_width_zero_when_no_metric_op() -> None:
    body = b"q Q\n"  # only painting ops, no d0/d1
    _, proc = _font_and_proc(body)
    assert proc.get_width() == 0.0


# ---------- get_bbox (PDContentStream contract) ----------


def test_get_bbox_returns_font_font_bbox_when_present() -> None:
    # Upstream contract: getBBox() returns font.getFontBBox() unconditionally.
    # The d1 leading-operator bbox is exposed via get_glyph_bbox(), not get_bbox().
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 1000.0, 1000.0))
    glyph = _glyph_with_body(b"600 0 50 -10 550 700 d1\n")
    proc = PDType3CharProc(font, glyph)
    bbox = proc.get_bbox()
    # Reflects /FontBBox, NOT the d1 operands.
    assert bbox.get_upper_right_x() == pytest.approx(1000.0)
    assert bbox.get_upper_right_y() == pytest.approx(1000.0)


def test_get_bbox_falls_back_to_font_font_bbox() -> None:
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 1000.0, 1000.0))
    glyph = _glyph_with_body(b"600 0 d0\n")
    proc = PDType3CharProc(font, glyph)
    bbox = proc.get_bbox()
    assert bbox.get_upper_right_x() == pytest.approx(1000.0)
    assert bbox.get_upper_right_y() == pytest.approx(1000.0)


def test_get_bbox_returns_origin_rect_when_no_font_bbox() -> None:
    _, proc = _font_and_proc(b"600 0 d0\n")
    bbox = proc.get_bbox()
    # PDRectangle's default-constructed shape.
    assert bbox.get_lower_left_x() == pytest.approx(0.0)
    assert bbox.get_lower_left_y() == pytest.approx(0.0)
    assert bbox.get_upper_right_x() == pytest.approx(0.0)
    assert bbox.get_upper_right_y() == pytest.approx(0.0)


# ---------- has_d0 / has_d1 predicates ----------


def test_has_d1_true_when_leading_d1() -> None:
    _, proc = _font_and_proc(b"600 0 50 -10 550 700 d1\n")
    assert proc.has_d1() is True
    assert proc.has_d0() is False


def test_has_d0_true_when_leading_d0() -> None:
    _, proc = _font_and_proc(b"600 0 d0\nq Q\n")
    assert proc.has_d0() is True
    assert proc.has_d1() is False


def test_has_d0_and_has_d1_both_false_for_empty_stream() -> None:
    _, proc = _font_and_proc(b"")
    assert proc.has_d0() is False
    assert proc.has_d1() is False


def test_has_d0_and_has_d1_both_false_when_no_metric_op() -> None:
    _, proc = _font_and_proc(b"q 1 0 0 1 0 0 cm Q\n")
    assert proc.has_d0() is False
    assert proc.has_d1() is False


# ---------- charproc-local /Resources (PDFBOX-5294) ----------


def test_get_resources_prefers_charproc_local_resources_dict() -> None:
    # PDFBOX-5294: malformed PDFs sometimes stash /Resources on the
    # char-proc itself instead of the parent font. Upstream tolerates
    # this and prefers the local entry; mirror that.
    font = PDType3Font()
    font_resources = PDResources()
    font.set_resources(font_resources)

    glyph = _glyph_with_body(b"600 0 d0\n")
    local_res_dict = COSDictionary()
    glyph.set_item(COSName.get_pdf_name("Resources"), local_res_dict)

    proc = PDType3CharProc(font, glyph)
    out = proc.get_resources()
    assert isinstance(out, PDResources)
    # Preferred: local /Resources, NOT the font's.
    assert out.get_cos_object() is local_res_dict
    assert out.get_cos_object() is not font_resources.get_cos_object()


def test_has_resources_false_for_well_formed_charproc() -> None:
    font = PDType3Font()
    glyph = _glyph_with_body(b"600 0 d0\n")
    proc = PDType3CharProc(font, glyph)
    assert proc.has_resources() is False


def test_has_resources_true_when_local_resources_dict_present() -> None:
    font = PDType3Font()
    glyph = _glyph_with_body(b"600 0 d0\n")
    glyph.set_item(COSName.get_pdf_name("Resources"), COSDictionary())
    proc = PDType3CharProc(font, glyph)
    assert proc.has_resources() is True


# ---------- integration with PDType3Font.get_char_proc(int) ----------


# ---------- _first_metric_operator / _is_numeric_token edges ----------


def test_get_glyph_bbox_returns_none_when_stream_begins_with_delimiter() -> None:
    """A char-proc whose decoded body starts with a PDF delimiter (e.g. a
    string literal ``(`` or an array ``[``) before any numeric tokens or
    operator names cannot have a valid leading ``d0`` / ``d1`` and must
    parse as "no metric operator". The tokenizer bails out on the first
    delimiter and the bbox accessor returns ``None``."""
    for body in (b"(string literal)\n", b"[1 2 3]\n", b"<aabbcc>\n", b"/Name d1\n"):
        _, proc = _font_and_proc(body)
        assert proc.get_glyph_bbox() is None
        assert proc.has_d0() is False
        assert proc.has_d1() is False


def test_get_width_zero_when_multi_dot_number_breaks_token_classification() -> None:
    """A malformed numeric token with two dots (e.g. ``600.5.5``) is NOT
    a valid PDF number literal — :func:`_is_numeric_token` must reject
    it. The tokenizer then treats it as an operator name, which makes
    the stream look like an operator with no operands; :meth:`get_width`
    must surface ``0.0`` rather than crash on the bad token."""
    # 600.5.5 -> classified as operator, not a number. No d0/d1 prefix
    # was seen, so width defaults to 0 and bbox is None.
    _, proc = _font_and_proc(b"600.5.5 d1\n")
    assert proc.get_width() == 0.0
    assert proc.get_glyph_bbox() is None
    # has_d1 is False because the operator we see is "600.5.5", not "d1".
    assert proc.has_d1() is False


def test_get_width_zero_for_sign_only_token() -> None:
    """A bare ``+`` or ``-`` (no digits) is not a number — must be
    classified as an operator. Width defaults to 0 because the leading
    operator isn't ``d0`` / ``d1``."""
    _, proc = _font_and_proc(b"- d1\n")
    assert proc.get_width() == 0.0
    assert proc.has_d0() is False
    assert proc.has_d1() is False


def test_get_glyph_bbox_returns_none_for_d1_with_too_few_operands() -> None:
    """``d1`` declares ``wx wy llx lly urx ury`` — six operands. When the
    stream has fewer than six numeric operands ahead of the ``d1``
    operator, the bbox accessor must surface ``None`` (and not raise)."""
    # 4 operands, then d1 — short of the 6 d1 needs.
    _, proc = _font_and_proc(b"600 0 50 -10 d1\n")
    assert proc.get_glyph_bbox() is None
    # has_d1 is still True (the operator is d1 even if its operands are short).
    assert proc.has_d1() is True
    # And get_width still picks up the wx from operands[0].
    assert proc.get_width() == pytest.approx(600.0)


def test_get_glyph_bbox_handles_signed_real_with_leading_plus() -> None:
    """``+50.0`` is a valid PDF real literal — the numeric-token check
    must accept the optional leading ``+`` sign on the first byte."""
    body = b"600 0 +50.0 -10 +550 +700 d1\n"
    _, proc = _font_and_proc(body)
    bbox = proc.get_glyph_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(50.0)
    assert bbox.get_upper_right_x() == pytest.approx(550.0)
    assert bbox.get_upper_right_y() == pytest.approx(700.0)


def test_first_metric_operator_skips_carriage_return_and_tab_whitespace() -> None:
    """PDF whitespace includes \\x00, \\t, \\n, \\f, \\r, and space —
    all five must be skipped by the tokenizer when scanning for the
    leading metric operator. Cover the less-common members (CR + TAB +
    NUL + FF) explicitly."""
    body = b"\x00\t\r\f600 0 d0\n"
    _, proc = _font_and_proc(body)
    assert proc.has_d0() is True
    assert proc.get_width() == pytest.approx(600.0)


def test_first_metric_operator_inline_comment_to_eol_skipped() -> None:
    """A ``%`` comment runs to end-of-line. A comment between the
    operands and the operator must be skipped without breaking the
    metric-operator parse."""
    body = b"600 0 %inline comment\nd0\n"
    _, proc = _font_and_proc(body)
    assert proc.has_d0() is True
    assert proc.get_width() == pytest.approx(600.0)


def test_round_trip_via_pd_type3_font_get_char_proc() -> None:
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 1000.0, 1000.0))
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    char_procs = COSDictionary()
    glyph = _glyph_with_body(b"500 0 50 -10 450 700 d1\n")
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    font.set_char_procs(char_procs)

    proc = font.get_char_proc(0x41)
    assert isinstance(proc, PDType3CharProc)
    assert proc.get_width() == pytest.approx(500.0)
    # get_bbox() returns /FontBBox per upstream contract.
    bbox = proc.get_bbox()
    assert bbox.get_upper_right_x() == pytest.approx(1000.0)
    # The per-glyph bbox is exposed via get_glyph_bbox().
    glyph_bbox = proc.get_glyph_bbox()
    assert glyph_bbox is not None
    assert glyph_bbox.get_lower_left_x() == pytest.approx(50.0)
    assert glyph_bbox.get_upper_right_x() == pytest.approx(450.0)
