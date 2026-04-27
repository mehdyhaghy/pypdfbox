"""Tests for transparency-group ``/K`` (knockout) and ``/I`` (isolation)
flag handling in :class:`pypdfbox.rendering.PDFRenderer`. Implements
PDF 32000-1 §11.4.7.

A knockout group has each top-level painted child fully replace the
prior contents at the group level — so two overlapping shapes inside a
``/K true`` group leave only the *second* visible, with the first
"knocked out" (reverted to the group-entry snapshot).

A non-isolated group's backdrop is the parent canvas's contents at
group entry; an isolated group's backdrop is fully transparent. With
opaque paints the two are visually equivalent at the painted region but
the structural code paths still differ.
"""

from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _build_two_square_form(
    *,
    isolated: bool | None,
    knockout: bool | None,
) -> PDFormXObject:
    """Form XObject containing two overlapping painted squares:

    - red square at PDF coords (20, 20)..(60, 60)
    - green square at PDF coords (40, 40)..(80, 80)

    ``/Group/S /Transparency`` is always set; ``/I`` and ``/K`` are
    populated only when explicitly requested (``None`` leaves them out
    so the spec defaults of false apply).
    """
    stream = COSStream()
    stream.set_raw_data(
        b"1 0 0 rg\n"        # red fill
        b"20 20 40 40 re\n"  # 40x40 rect
        b"f\n"
        b"0 1 0 rg\n"        # green fill
        b"40 40 40 40 re\n"  # 40x40 rect, overlapping
        b"f\n"
    )
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))

    group_dict = COSDictionary()
    group_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    if isolated is not None:
        group_dict.set_item(COSName.get_pdf_name("I"), COSBoolean.get(isolated))
    if knockout is not None:
        group_dict.set_item(COSName.get_pdf_name("K"), COSBoolean.get(knockout))
    form.set_group(group_dict)
    return form


def _attach_form_to_page(
    page: PDPage,
    form: PDFormXObject,
    *,
    page_prefix: bytes = b"",
) -> None:
    """Wire up a single-form page: optional ``page_prefix`` paints the
    backdrop, then ``/Form0 Do`` invokes the transparency group."""
    page_dict = page.get_cos_object()
    contents = COSStream()
    contents.set_raw_data(
        page_prefix
        + b"q\n"
        b"/Form0 Do\n"
        b"Q\n"
    )
    page_dict.set_item(COSName.CONTENTS, contents)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Form0"),
        form.get_cos_object(),
    )


# Sample points (PIL coords; PIL y is flipped from PDF y).
# Page is 100x100. PDF (x, y) → PIL (x, 100 - y).
# Red-only PDF region: (20..40, 20..40) → PIL (20..40, 60..80). Sample (30, 70).
# Green-only PDF region: (60..80, 60..80) → PIL (60..80, 20..40). Sample (70, 30).
# Outside both squares: PDF (90, 90) → PIL (90, 10).
_RED_ONLY_PIL = (30, 70)
_GREEN_ONLY_PIL = (70, 30)
_OUTSIDE_PIL = (90, 10)


# ---------------------------------------------------------------------------
# K=false I=true  →  isolated, non-knockout (the Wave 31 baseline)
# ---------------------------------------------------------------------------


def test_isolated_non_knockout_shows_both_squares() -> None:
    """``/I true /K false``: the group composites onto a transparent
    backdrop; both red and green squares should be visible in their
    respective regions."""
    doc, page = _make_doc()
    form = _build_two_square_form(isolated=True, knockout=False)
    _attach_form_to_page(page, form)

    img = PDFRenderer(doc).render_image(0)
    red = img.getpixel(_RED_ONLY_PIL)
    green = img.getpixel(_GREEN_ONLY_PIL)
    outside = img.getpixel(_OUTSIDE_PIL)
    assert _is_close(red, (255, 0, 0)), red
    assert _is_close(green, (0, 255, 0)), green
    assert _is_close(outside, (255, 255, 255), tol=4), outside


# ---------------------------------------------------------------------------
# K=false I=false  →  non-isolated, non-knockout
# ---------------------------------------------------------------------------


def test_non_isolated_non_knockout_shows_both_squares_over_backdrop() -> None:
    """``/I false /K false``: the group's backdrop is the parent canvas's
    contents at group entry. Painting opaque squares on top should still
    show both squares; outside the squares the parent backdrop wins."""
    doc, page = _make_doc()
    form = _build_two_square_form(isolated=False, knockout=False)
    # Yellow rectangle covers the whole page; sample points outside the
    # squares should pick up that yellow rather than the page's white.
    backdrop = b"1 1 0 rg\n0 0 100 100 re\nf\n"
    _attach_form_to_page(page, form, page_prefix=backdrop)

    img = PDFRenderer(doc).render_image(0)
    red = img.getpixel(_RED_ONLY_PIL)
    green = img.getpixel(_GREEN_ONLY_PIL)
    outside = img.getpixel(_OUTSIDE_PIL)
    assert _is_close(red, (255, 0, 0)), red
    assert _is_close(green, (0, 255, 0)), green
    # Yellow backdrop visible at (90, 10) — outside both squares.
    assert _is_close(outside, (255, 255, 0)), outside


# ---------------------------------------------------------------------------
# K=true I=true  →  isolated knockout — red erased before green paints
# ---------------------------------------------------------------------------


def test_isolated_knockout_erases_first_square() -> None:
    """``/I true /K true``: knockout resets the group canvas to the
    (transparent) entry snapshot before each top-level paint. The red
    square is painted, then knocked out, then the green square is
    painted. After composite onto the white parent the red region
    should reveal the parent's white, while green remains visible."""
    doc, page = _make_doc()
    form = _build_two_square_form(isolated=True, knockout=True)
    _attach_form_to_page(page, form)

    img = PDFRenderer(doc).render_image(0)
    red_region = img.getpixel(_RED_ONLY_PIL)
    green = img.getpixel(_GREEN_ONLY_PIL)
    # Red is fully knocked out — parent (white page) shows through.
    assert _is_close(red_region, (255, 255, 255), tol=4), red_region
    assert _is_close(green, (0, 255, 0)), green


# ---------------------------------------------------------------------------
# K=true I=false  →  non-isolated knockout — red erased, parent shows through
# ---------------------------------------------------------------------------


def test_non_isolated_knockout_erases_first_and_shows_parent_backdrop() -> None:
    """``/I false /K true``: knockout snapshot is a copy of the parent
    canvas at group entry. After the red square is knocked out and only
    the green remains, the red region should reveal the *parent's*
    contents (yellow backdrop, not the page's default white)."""
    doc, page = _make_doc()
    form = _build_two_square_form(isolated=False, knockout=True)
    backdrop = b"1 1 0 rg\n0 0 100 100 re\nf\n"
    _attach_form_to_page(page, form, page_prefix=backdrop)

    img = PDFRenderer(doc).render_image(0)
    red_region = img.getpixel(_RED_ONLY_PIL)
    green = img.getpixel(_GREEN_ONLY_PIL)
    outside = img.getpixel(_OUTSIDE_PIL)
    # The red region was knocked out and the snapshot (yellow backdrop)
    # reappeared; non-isolated means the snapshot is the parent canvas.
    assert _is_close(red_region, (255, 255, 0)), red_region
    assert _is_close(green, (0, 255, 0)), green
    # Outside the squares: yellow backdrop unchanged.
    assert _is_close(outside, (255, 255, 0)), outside


# ---------------------------------------------------------------------------
# Code-path sanity: the four combinations must all complete without raising.
# ---------------------------------------------------------------------------


def test_all_four_combinations_render_without_error() -> None:
    for isolated, knockout in [
        (True, False),
        (False, False),
        (True, True),
        (False, True),
    ]:
        doc, page = _make_doc()
        form = _build_two_square_form(isolated=isolated, knockout=knockout)
        _attach_form_to_page(page, form)
        img = PDFRenderer(doc).render_image(0)
        assert img.size == (100, 100)
