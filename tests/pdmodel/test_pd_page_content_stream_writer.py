"""Producer-side tests for the methods rounded out by Wave 35: the
polymorphic ``set_(non_)stroking_color`` overloads, the
``set_(non_)stroking_color_space`` operators, ``set_text_matrix`` (Tm),
``end_path`` (n), the ``clip()`` / ``clip_even_odd()`` aliases and the
upstream-spelled fill/stroke/leading aliases."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


def _stream_bytes(page: PDPage) -> bytes:
    return page.get_contents()


# ----------------------------------------------------------------------
# polymorphic set_stroking_color / set_non_stroking_color
# ----------------------------------------------------------------------


def test_set_stroking_color_with_gray_scalar() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(0.5)
    assert _stream_bytes(page) == b"0.5 G\n"


def test_set_non_stroking_color_with_gray_scalar() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.25)
    assert _stream_bytes(page) == b"0.25 g\n"


def test_set_stroking_color_with_rgb_triple() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(1, 0, 0)
    assert _stream_bytes(page) == b"1 0 0 RG\n"


def test_set_non_stroking_color_with_rgb_triple() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.1, 0.2, 0.3)
    assert _stream_bytes(page) == b"0.1 0.2 0.3 rg\n"


def test_set_stroking_color_with_cmyk_quadruple() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(0.1, 0.2, 0.3, 0.4)
    assert _stream_bytes(page) == b"0.1 0.2 0.3 0.4 K\n"


def test_set_non_stroking_color_with_cmyk_quadruple() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.5, 0.6, 0.7, 0.8)
    assert _stream_bytes(page) == b"0.5 0.6 0.7 0.8 k\n"


def test_set_stroking_color_with_pdcolor_devicergb() -> None:
    """A PDColor backed by DeviceRGB writes the colour-space name + ``CS``
    then the components + ``SC`` — mirroring upstream
    ``PDAbstractContentStream.setStrokingColor(PDColor)``, which never takes
    the ``RG`` device-shorthand path (that is only the ``float[]`` overload)."""
    doc = PDDocument()
    page = _make_page(doc)
    color = PDColor([1.0, 0.0, 0.5], PDDeviceRGB.INSTANCE)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(color)
    assert _stream_bytes(page) == b"/DeviceRGB CS\n1 0 0.5 SC\n"


def test_set_non_stroking_color_with_pdcolor_devicegray() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    color = PDColor([0.75], PDDeviceGray.INSTANCE)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(color)
    assert _stream_bytes(page) == b"/DeviceGray cs\n0.75 sc\n"


def test_set_stroking_color_with_pdcolor_devicecmyk() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    color = PDColor([0.1, 0.2, 0.3, 0.4], PDDeviceCMYK.INSTANCE)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(color)
    assert _stream_bytes(page) == b"/DeviceCMYK CS\n0.1 0.2 0.3 0.4 SC\n"


def test_set_stroking_color_rejects_two_args() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.set_stroking_color(0.5, 0.5)


def test_set_stroking_color_rejects_non_numeric_single_arg() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.set_stroking_color("nope")


# ----------------------------------------------------------------------
# set_(non_)stroking_color_space
# ----------------------------------------------------------------------


def test_set_stroking_color_space_devicergb_emits_well_known_name() -> None:
    """Device color spaces are emitted by their canonical name and do
    NOT register a /Resources/ColorSpace entry."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_space(PDDeviceRGB.INSTANCE)
    assert _stream_bytes(page) == b"/DeviceRGB CS\n"
    res = page.get_resources()
    assert res.get_color_space_names() == []


def test_set_non_stroking_color_space_devicegray() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_space(PDDeviceGray.INSTANCE)
    assert _stream_bytes(page) == b"/DeviceGray cs\n"


def test_set_non_stroking_color_space_devicecmyk() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_space(PDDeviceCMYK.INSTANCE)
    assert _stream_bytes(page) == b"/DeviceCMYK cs\n"


def test_set_stroking_color_space_named_registers_resource() -> None:
    """Non-device color spaces (e.g. ICCBased, Indexed) must be
    registered under /Resources/ColorSpace and referenced by their
    allocated key. PDResources allocates ``cs<n>`` (lowercase) keys —
    pypdfbox naming convention, see pd_resources._PREFIX_COLOR_SPACE."""
    from pypdfbox.cos import COSArray, COSStream
    from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased

    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSStream())
    icc = PDICCBased(arr)

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_space(icc)
    body = _stream_bytes(page)
    assert body == b"/cs1 CS\n"
    res = page.get_resources()
    keys = [n.get_name() for n in res.get_color_space_names()]
    assert keys == ["cs1"]


def test_set_color_space_reuses_existing_key() -> None:
    """Two calls with the same color space must reuse the same key."""
    from pypdfbox.cos import COSArray, COSStream
    from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased

    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSStream())
    icc = PDICCBased(arr)

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_space(icc)
        cs.set_non_stroking_color_space(icc)
    body = _stream_bytes(page)
    assert body == b"/cs1 CS\n/cs1 cs\n"
    res = page.get_resources()
    assert [n.get_name() for n in res.get_color_space_names()] == ["cs1"]


# ----------------------------------------------------------------------
# end_path / clip aliases
# ----------------------------------------------------------------------


def test_end_path_emits_n() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(0, 0, 10, 10)
        cs.end_path()
    assert _stream_bytes(page) == b"0 0 10 10 re\nn\n"


def test_clip_emits_w_then_n() -> None:
    """``clip()`` matches upstream's clip-and-end-path emission."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(0, 0, 50, 50)
        cs.clip()
    assert _stream_bytes(page) == b"0 0 50 50 re\nW\nn\n"


def test_clip_even_odd_emits_w_star_then_n() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(0, 0, 50, 50)
        cs.clip_even_odd()
    assert _stream_bytes(page) == b"0 0 50 50 re\nW*\nn\n"


def test_fill_even_odd_and_stroke_alias_matches_existing() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.fill_even_odd_and_stroke()
    assert _stream_bytes(page) == b"B*\n"


def test_close_fill_even_odd_and_stroke_alias() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.close_fill_even_odd_and_stroke()
    assert _stream_bytes(page) == b"b*\n"


# ----------------------------------------------------------------------
# text-matrix / leading alias
# ----------------------------------------------------------------------


def test_set_text_matrix_six_components() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix(1, 0, 0, 1, 100, 200)
        cs.end_text()
    body = _stream_bytes(page)
    assert b"1 0 0 1 100 200 Tm\n" in body


def test_set_text_matrix_with_iterable() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix([0.5, 0, 0, 0.5, 50, 60])
        cs.end_text()
    assert b"0.5 0 0 0.5 50 60 Tm\n" in _stream_bytes(page)


def test_set_text_matrix_with_tuple() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix((1, 0, 0, 1, 0, 0))
        cs.end_text()
    assert b"1 0 0 1 0 0 Tm\n" in _stream_bytes(page)


def test_set_text_matrix_iterable_wrong_arity_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(ValueError):
            cs.set_text_matrix([1, 0, 0, 1])
        cs.end_text()


def test_set_text_matrix_with_get_value_matrix_like() -> None:
    """An object exposing ``get_value(row, col)`` (the upstream Matrix
    shape) decomposes into the 2D affine."""

    class _FakeMatrix:
        def get_value(self, row: int, col: int) -> float:
            grid = [
                [2.0, 0.0, 0.0],
                [0.0, 3.0, 0.0],
                [10.0, 20.0, 1.0],
            ]
            return grid[row][col]

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix(_FakeMatrix())
        cs.end_text()
    assert b"2 0 0 3 10 20 Tm\n" in _stream_bytes(page)


def test_set_text_matrix_with_get_a_to_get_f_accessors() -> None:
    """An object exposing get_a..get_f also works."""

    class _FakeMatrix2:
        def get_a(self) -> float: return 1.0  # noqa: E704
        def get_b(self) -> float: return 0.0  # noqa: E704
        def get_c(self) -> float: return 0.0  # noqa: E704
        def get_d(self) -> float: return 1.0  # noqa: E704
        def get_e(self) -> float: return 7.0  # noqa: E704
        def get_f(self) -> float: return 8.0  # noqa: E704

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix(_FakeMatrix2())
        cs.end_text()
    assert b"1 0 0 1 7 8 Tm\n" in _stream_bytes(page)


def test_set_text_matrix_rejects_unknown_shape() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(TypeError):
            cs.set_text_matrix(object())
        cs.end_text()


def test_set_leading_alias_emits_tl() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_leading(14.5)
    assert _stream_bytes(page) == b"14.5 TL\n"
