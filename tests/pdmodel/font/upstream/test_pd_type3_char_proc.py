"""Parity tests for ``PDType3CharProc``.

Upstream PDFBox ships no dedicated ``PDType3CharProcTest`` — the class is
exercised indirectly through Type-3 rendering corpora and the
``Type3FontValidator`` in preflight. The cases below mirror the documented
behaviours in
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType3CharProc.java``:

* constructor + ``getCOSObject`` / ``getFont`` (Java lines 53-66)
* ``getContentStream`` (line 69) — fresh ``PDStream`` wrapper each call
* ``getContents`` / ``getContentsForRandomAccess`` (lines 75-83)
* ``getResources`` (lines 86-95) — PDFBOX-5294 local-charproc dictionary
* ``getBBox`` (line 98) — delegates to font's ``/FontBBox``
* ``getGlyphBBox`` (lines 109-148) — d1 leading-operator path
* ``getMatrix`` (line 151) — delegates to font's ``/FontMatrix``
* ``getWidth`` / ``parseWidth`` (lines 158-194) — d0/d1 first-operand
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def _make_proc(body: bytes) -> tuple[PDType3Font, COSStream, PDType3CharProc]:
    font = PDType3Font()
    stream = COSStream()
    stream.set_raw_data(body)
    return font, stream, PDType3CharProc(font, stream)


# ---------- constructor + getCOSObject + getFont (lines 53-66) ----------


def test_constructor_stores_font_and_stream() -> None:
    """Upstream constructor (line 53):
        public PDType3CharProc(PDType3Font font, COSStream charStream)
    Both arguments are accessible via ``getFont()`` / ``getCOSObject()``."""
    font, stream, proc = _make_proc(b"500 0 d0\n")
    assert proc.get_font() is font
    assert proc.get_cos_object() is stream


def test_get_cos_object_returns_cos_stream_instance() -> None:
    """Upstream ``getCOSObject() : COSStream`` (line 60). Narrows the
    return type from ``COSObjectable``'s ``COSBase`` to ``COSStream``."""
    _, _, proc = _make_proc(b"500 0 d0\n")
    assert isinstance(proc.get_cos_object(), COSStream)


# ---------- getContentStream (line 69) ----------


def test_get_content_stream_returns_fresh_pd_stream_each_call() -> None:
    """Upstream ``getContentStream()`` (line 69):
        return new PDStream(charStream);
    A fresh wrapper on every call — the underlying ``COSStream`` is
    shared, but the ``PDStream`` instance is not cached."""
    _, _, proc = _make_proc(b"500 0 d0\n")
    a = proc.get_content_stream()
    b = proc.get_content_stream()
    assert isinstance(a, PDStream)
    assert isinstance(b, PDStream)
    assert a is not b
    assert a.get_cos_object() is b.get_cos_object()
    assert a.get_cos_object() is proc.get_cos_object()


# ---------- getContents / getContentsForRandomAccess (lines 75-83) ----------


def test_get_contents_returns_input_stream_over_decoded_bytes() -> None:
    """Upstream ``getContents() : InputStream`` (line 75):
        return new RandomAccessInputStream(getContentsForRandomAccess());
    """
    body = b"500 0 d0\nq Q\n"
    _, _, proc = _make_proc(body)
    with proc.get_contents() as stream:
        assert stream.read() == body


def test_get_contents_for_random_access_returns_random_access_view() -> None:
    """Upstream ``getContentsForRandomAccess()`` (line 81):
        return charStream.createView();
    Provides a random-access view over the decoded bytes."""
    body = b"500 0 d0\n"
    _, _, proc = _make_proc(body)
    rar = proc.get_contents_for_random_access()
    try:
        assert isinstance(rar, RandomAccessRead)
        # Drain it.
        out = bytearray()
        while True:
            b = rar.read()
            if b == RandomAccessRead.EOF:
                break
            out.append(b)
        assert bytes(out) == body
    finally:
        rar.close()


# ---------- getResources (lines 86-95, PDFBOX-5294) ----------


def test_get_resources_returns_font_resources_when_no_local_dict() -> None:
    """Upstream ``getResources()`` (line 86): when the char-proc stream
    has no ``/Resources`` entry, fall back to ``font.getResources()``."""
    font = PDType3Font()
    resources = PDResources()
    font.set_resources(resources)
    stream = COSStream()
    stream.set_raw_data(b"500 0 d0\n")
    proc = PDType3CharProc(font, stream)
    out = proc.get_resources()
    assert out is not None
    assert out.get_cos_object() is resources.get_cos_object()


def test_get_resources_prefers_local_charproc_dict_pdfbox_5294() -> None:
    """Upstream ``getResources()`` (lines 88-92):
        if (charStream.containsKey(COSName.RESOURCES)) {
            // PDFBOX-5294
            return new PDResources(charStream.getCOSDictionary(COSName.RESOURCES));
        }
    Tolerates the malformed-PDF case where /Resources lives on the
    char-proc stream itself instead of the parent font."""
    font = PDType3Font()
    font.set_resources(PDResources())
    stream = COSStream()
    stream.set_raw_data(b"500 0 d0\n")
    local = COSDictionary()
    stream.set_item(COSName.get_pdf_name("Resources"), local)
    proc = PDType3CharProc(font, stream)
    out = proc.get_resources()
    assert out is not None
    assert out.get_cos_object() is local


# ---------- getBBox (line 98) ----------


def test_get_b_box_delegates_to_font_font_bbox() -> None:
    """Upstream ``getBBox()`` (line 98):
        return font.getFontBBox();
    Always the parent font's bbox — the d1 per-glyph bbox is exposed
    separately via ``getGlyphBBox()``."""
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 1000.0, 1000.0))
    stream = COSStream()
    stream.set_raw_data(b"500 0 50 -10 450 700 d1\n")
    proc = PDType3CharProc(font, stream)
    bbox = proc.get_b_box()
    # Reflects /FontBBox, NOT the d1 operands.
    assert bbox.get_lower_left_x() == pytest.approx(0.0)
    assert bbox.get_upper_right_x() == pytest.approx(1000.0)


# ---------- getGlyphBBox (lines 109-148) ----------


def test_get_glyph_b_box_returns_bbox_when_first_operator_is_d1() -> None:
    """Upstream ``getGlyphBBox()`` (lines 109-148): walks tokens until the
    first operator. If it is ``d1`` and there are 6 numeric operands,
    constructs ``new PDRectangle(x, y, urx-x, ury-y)``."""
    body = b"600 0 50 -10 550 700 d1\nq Q\n"
    _, _, proc = _make_proc(body)
    bbox = proc.get_glyph_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(50.0)
    assert bbox.get_lower_left_y() == pytest.approx(-10.0)
    assert bbox.get_upper_right_x() == pytest.approx(550.0)
    assert bbox.get_upper_right_y() == pytest.approx(700.0)


def test_get_glyph_b_box_returns_none_when_first_operator_is_d0() -> None:
    """Upstream ``getGlyphBBox()`` (line 138): non-d1 first operator →
    return null."""
    _, _, proc = _make_proc(b"600 0 d0\n")
    assert proc.get_glyph_b_box() is None


def test_get_glyph_b_box_returns_none_for_short_d1_argument_list() -> None:
    """Upstream ``getGlyphBBox()`` (line 117):
        if (((Operator) token).getName().equals("d1") && arguments.size() == 6)
    Fewer than 6 operands → return null path (exercised at line 138)."""
    _, _, proc = _make_proc(b"600 0 50 -10 d1\n")
    assert proc.get_glyph_b_box() is None


def test_get_glyph_b_box_returns_none_when_token_stream_empty() -> None:
    """Upstream ``getGlyphBBox()`` (line 147): no tokens at all → ``return
    null`` after the while loop."""
    _, _, proc = _make_proc(b"")
    assert proc.get_glyph_b_box() is None


# ---------- getMatrix (line 151) ----------


def test_get_matrix_delegates_to_font_font_matrix() -> None:
    """Upstream ``getMatrix()`` (line 151):
        return font.getFontMatrix();
    """
    font = PDType3Font()
    font.set_font_matrix([0.002, 0.0, 0.0, 0.002, 0.0, 0.0])
    stream = COSStream()
    stream.set_raw_data(b"500 0 d0\n")
    proc = PDType3CharProc(font, stream)
    matrix = proc.get_matrix()
    assert matrix == pytest.approx([0.002, 0.0, 0.0, 0.002, 0.0, 0.0], rel=1e-6)


# ---------- getWidth / parseWidth (lines 158-194) ----------


def test_get_width_returns_first_operand_for_d0() -> None:
    """Upstream ``getWidth()`` (lines 158-176) → ``parseWidth`` (line 178)
    → ``arguments.get(0).floatValue()``."""
    _, _, proc = _make_proc(b"600 0 d0\n")
    assert proc.get_width() == pytest.approx(600.0)


def test_get_width_returns_first_operand_for_d1() -> None:
    """Upstream ``parseWidth`` (line 178): both ``d0`` and ``d1`` resolve
    via the same operand-zero path; the trailing 4 operands of d1 do not
    affect the returned width."""
    _, _, proc = _make_proc(b"720 0 50 -10 550 700 d1\n")
    assert proc.get_width() == pytest.approx(720.0)


def test_parse_width_d0_returns_first_operand() -> None:
    """Upstream private ``parseWidth(Operator, List<COSBase>)`` (line 178):
    when operator is ``d0``, return ``arguments.get(0).floatValue()``."""
    _, _, proc = _make_proc(b"")
    assert proc.parse_width(b"d0", [b"600", b"0"]) == pytest.approx(600.0)


def test_parse_width_d1_returns_first_operand() -> None:
    """Upstream private ``parseWidth`` (line 178): same path for ``d1``."""
    _, _, proc = _make_proc(b"")
    assert proc.parse_width(
        b"d1", [b"720", b"0", b"50", b"-10", b"550", b"700"]
    ) == pytest.approx(720.0)


def test_parse_width_returns_zero_for_non_d0_d1_operator() -> None:
    """Upstream ``parseWidth`` (line 192): non-``d0``/``d1`` operator
    raises ``IOException("First operator must be d0 or d1")``. We diverge
    by returning 0.0 (documented in CHANGES.md / source docstring)."""
    _, _, proc = _make_proc(b"")
    assert proc.parse_width(b"cm", [b"1", b"0", b"0", b"1", b"0", b"0"]) == 0.0


def test_get_width_returns_zero_for_empty_stream() -> None:
    """Upstream ``getWidth()`` (line 175):
        throw new IOException("Unexpected end of stream");
    We diverge by returning 0.0 so a single broken glyph doesn't abort
    text-extraction over the rest of the font's char-procs."""
    _, _, proc = _make_proc(b"")
    assert proc.get_width() == 0.0
