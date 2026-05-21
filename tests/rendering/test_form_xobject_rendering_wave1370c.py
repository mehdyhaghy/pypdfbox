"""Form-XObject rendering parity tests for :class:`PDFRenderer`.

PDF 32000-1 §8.10: a Form XObject is rendered by saving the GS, applying
the form's ``/Matrix`` to the CTM, clipping to its ``/BBox``, switching
to its ``/Resources`` for the duration of its content stream, then
restoring. These tests pin the four interesting cases not already
covered by :mod:`tests.rendering.test_pdf_renderer_smask` or
:mod:`tests.rendering.test_pdf_renderer_knockout_isolation`:

* ``/BBox`` truly clips painting that runs outside it.
* ``/Matrix`` transforms drawn content (scale + translate).
* Nested ``/Resources`` resolves entries against the form's own dict, so
  a form referencing ``/F1`` finds it in *its* /Resources, not the
  page's.
* A form invocation must restore the parent CTM after ``Q`` — drawing
  outside the form after the ``Do`` op must not be transformed by the
  form's matrix.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer


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


def _build_form(
    content: bytes,
    bbox: PDRectangle | None = None,
    matrix: tuple[float, float, float, float, float, float] | None = None,
    resources: PDResources | None = None,
) -> PDFormXObject:
    stream = COSStream()
    stream.set_raw_data(content)
    form = PDFormXObject(stream)
    if bbox is None:
        bbox = PDRectangle(0.0, 0.0, 100.0, 100.0)
    form.set_b_box(bbox)
    if matrix is not None:
        m_arr = COSArray()
        for v in matrix:
            m_arr.add(COSFloat(float(v)))
        form.get_cos_object().set_item(COSName.get_pdf_name("Matrix"), m_arr)
    if resources is not None:
        form.set_resources(resources)
    return form


def _attach_form(
    page: PDPage,
    form: PDFormXObject,
    *,
    prefix: bytes = b"",
    suffix: bytes = b"",
) -> None:
    contents = COSStream()
    contents.set_raw_data(prefix + b"/F0 Do\n" + suffix)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )


def test_form_xobject_bbox_clips_painting_outside_box() -> None:
    """A form with /BBox = (10,10)-(30,30) painting a 100x100 page-fill
    should only mark pixels inside the bbox."""
    doc, page = _make_doc(60.0, 60.0)
    form = _build_form(
        # Try to fill the entire page with red.
        b"1 0 0 rg\n0 0 60 60 re\nf\n",
        bbox=PDRectangle(10.0, 10.0, 30.0, 30.0),
    )
    _attach_form(page, form)
    img = PDFRenderer(doc).render_image(0)
    # Inside the bbox PDF (10..30, 10..30) → PIL (10..30, 30..50). Sample
    # the centre.
    inside = img.getpixel((20, 40))
    assert _is_close(inside, (255, 0, 0), tol=20), inside
    # Outside the bbox — must be clipped, so page background visible.
    outside = img.getpixel((50, 10))
    assert _is_close(outside, (255, 255, 255), tol=8), outside
    # Just outside the bbox on the other edge.
    outside2 = img.getpixel((5, 5))
    assert _is_close(outside2, (255, 255, 255), tol=8), outside2


def test_form_xobject_matrix_scales_content() -> None:
    """A form with /Matrix [2 0 0 2 0 0] doubles every coordinate. A
    10x10 painted rect at the origin inside the form lands as a 20x20
    rect on the page."""
    doc, page = _make_doc(60.0, 60.0)
    form = _build_form(
        b"0 0 1 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 60.0, 60.0),
        matrix=(2.0, 0.0, 0.0, 2.0, 0.0, 0.0),
    )
    _attach_form(page, form)
    img = PDFRenderer(doc).render_image(0)
    # The form rect was (0..10, 0..10); scaled by 2 → PDF (0..20, 0..20)
    # → PIL (0..20, 40..60). Sample inside.
    inside = img.getpixel((10, 50))
    assert _is_close(inside, (0, 0, 255), tol=20), inside
    # Just past the painted area — should be background.
    past = img.getpixel((25, 55))
    assert _is_close(past, (255, 255, 255), tol=8), past


def test_form_xobject_matrix_translates_content() -> None:
    """/Matrix with translation [1 0 0 1 20 30] shifts content by (20, 30)."""
    doc, page = _make_doc(60.0, 60.0)
    form = _build_form(
        b"0 1 0 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 60.0, 60.0),
        matrix=(1.0, 0.0, 0.0, 1.0, 20.0, 30.0),
    )
    _attach_form(page, form)
    img = PDFRenderer(doc).render_image(0)
    # Translated to PDF (20..30, 30..40) → PIL (20..30, 20..30).
    inside = img.getpixel((25, 25))
    assert _is_close(inside, (0, 255, 0), tol=20), inside


def test_form_xobject_with_nested_resources_resolves_inner_xobject() -> None:
    """A form references ``/F1 Do`` against its own /Resources, not the
    page's. The renderer must switch to the form's resources during
    its content stream walk."""
    doc, page = _make_doc(80.0, 80.0)

    # Inner form: paints a magenta rectangle.
    inner = _build_form(
        b"1 0 1 rg\n5 5 15 15 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 80.0, 80.0),
    )
    # Outer form: invokes /F1 (the inner form), which is registered in
    # the *outer form's* /Resources — NOT in the page's.
    outer_resources = PDResources()
    outer_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F1"),
        inner.get_cos_object(),
    )
    outer = _build_form(
        b"q\n/F1 Do\nQ\n",
        bbox=PDRectangle(0.0, 0.0, 80.0, 80.0),
        resources=outer_resources,
    )
    _attach_form(page, outer)
    img = PDFRenderer(doc).render_image(0)
    # Magenta rect at PDF (5..20, 5..20) → PIL (5..20, 60..75).
    inside = img.getpixel((10, 70))
    assert _is_close(inside, (255, 0, 255), tol=30), inside


def test_form_xobject_matrix_restored_after_invocation() -> None:
    """After the form's ``Do`` returns and the wrapping ``Q`` restores
    GS, drawing on the page must use the *parent* CTM — the form's
    matrix must not leak. We invoke a form with a /Matrix that would
    shift content by (40, 40), then paint outside the form with a fresh
    rect — that rect must land at its literal coordinates, not shifted."""
    doc, page = _make_doc(80.0, 80.0)
    form = _build_form(
        b"1 0 0 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 80.0, 80.0),
        matrix=(1.0, 0.0, 0.0, 1.0, 40.0, 40.0),
    )
    contents = COSStream()
    contents.set_raw_data(
        b"q\n/F0 Do\nQ\n"
        # Now paint blue at (5, 5)-(15, 15). If the form's matrix
        # leaked, this would shift to (45, 45)-(55, 55).
        b"0 0 1 rg\n5 5 10 10 re\nf\n",
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    img = PDFRenderer(doc).render_image(0)
    # Blue rect at PDF (5..15, 5..15) → PIL (5..15, 65..75).
    blue_pixel = img.getpixel((10, 70))
    assert _is_close(blue_pixel, (0, 0, 255), tol=20), blue_pixel
    # And the form-painted red rect at PDF (40..50, 40..50) → PIL (40..50, 30..40).
    red_pixel = img.getpixel((45, 35))
    assert _is_close(red_pixel, (255, 0, 0), tol=20), red_pixel
    # Verify the position where blue *would* have leaked (PIL ~50, 30) is
    # not blue — i.e. the matrix didn't leak to the post-form fill.
    leaked = img.getpixel((50, 30))
    assert not _is_close(leaked, (0, 0, 255), tol=20), (
        f"matrix leaked — post-form blue at PIL (50, 30): {leaked}"
    )


def test_form_xobject_default_bbox_is_no_clip() -> None:
    """When /BBox spans the full page area the form's content must
    paint without being clipped."""
    doc, page = _make_doc(40.0, 40.0)
    form = _build_form(
        b"1 1 0 rg\n5 5 30 30 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 40.0, 40.0),
    )
    _attach_form(page, form)
    img = PDFRenderer(doc).render_image(0)
    # PIL (15, 25) — inside the 30x30 yellow rect.
    inside = img.getpixel((15, 25))
    assert _is_close(inside, (255, 255, 0), tol=20), inside


def test_form_xobject_zero_size_bbox_clips_everything() -> None:
    """A zero-area /BBox should clip everything inside the form."""
    doc, page = _make_doc(40.0, 40.0)
    form = _build_form(
        b"1 0 0 rg\n5 5 30 30 re\nf\n",
        bbox=PDRectangle(10.0, 10.0, 10.0, 10.0),
    )
    _attach_form(page, form)
    img = PDFRenderer(doc).render_image(0)
    # Nothing should be painted — page background everywhere.
    middle = img.getpixel((20, 20))
    assert _is_close(middle, (255, 255, 255), tol=8), middle


def test_form_xobject_with_matrix_and_bbox_composes_correctly() -> None:
    """Matrix should apply *before* bbox clipping (per spec): a form with
    /Matrix scaling 2× and /BBox (0, 0, 10, 10) should clip in the
    form's local space, then transform — leaving a 20x20 visible patch."""
    doc, page = _make_doc(60.0, 60.0)
    form = _build_form(
        b"1 0 0 rg\n0 0 30 30 re\nf\n",  # Try to fill 30x30 in form space.
        bbox=PDRectangle(0.0, 0.0, 10.0, 10.0),
        matrix=(2.0, 0.0, 0.0, 2.0, 0.0, 0.0),
    )
    _attach_form(page, form)
    img = PDFRenderer(doc).render_image(0)
    # /BBox local (0..10, 0..10) scaled to PDF (0..20, 0..20) → PIL (0..20, 40..60).
    inside = img.getpixel((10, 50))
    assert _is_close(inside, (255, 0, 0), tol=20), inside
    # Outside the clipped + scaled bbox.
    outside = img.getpixel((25, 50))
    assert _is_close(outside, (255, 255, 255), tol=8), outside


def test_form_xobject_nested_resources_extgstate_resolves_locally() -> None:
    """A form referencing /GS0 in its own /Resources must NOT pick up a
    page-level /GS0 with different settings — proper resource scoping
    requires the form's resources to mask the page's during the form
    content walk."""
    from pypdfbox.cos import COSDictionary

    doc, page = _make_doc(40.0, 40.0)

    # Form's local /GS0 sets ca = 1.0 (full opacity).
    form_egs = COSDictionary()
    form_egs.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState")
    )
    form_egs.set_item(COSName.get_pdf_name("ca"), COSFloat(1.0))

    form_resources = PDResources()
    form_resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        form_egs,
    )
    form = _build_form(
        b"/GS0 gs\n1 0 0 rg\n5 5 30 30 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 40.0, 40.0),
        resources=form_resources,
    )

    # Page's /GS0 sets ca = 0.0 (fully transparent) — but the form
    # should resolve /GS0 from its own /Resources, not the page's.
    page_egs = COSDictionary()
    page_egs.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState")
    )
    page_egs.set_item(COSName.get_pdf_name("ca"), COSFloat(0.0))
    page_resources = PDResources()
    page.set_resources(page_resources)
    page_resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        page_egs,
    )
    page_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # If form resolved /GS0 from its own /Resources (ca=1.0) → red painted.
    # If form leaked to page /GS0 (ca=0.0) → fully transparent → white.
    inside = img.getpixel((15, 25))
    assert _is_close(inside, (255, 0, 0), tol=30), (
        f"form's /Resources didn't scope correctly; got {inside}"
    )
