"""Wave 1384 — direct fill/stroke with an active ExtGState ``/SMask``.

Before wave 1384, the renderer only applied the active soft mask at
transparency-group composite time. Fills and strokes that lived *outside*
a transparency group silently dropped the mask, so any real-world PDF
that activates an SMask on a plain page-level path (without wrapping the
geometry inside a Form XObject) rendered as if the SMask were absent.

Upstream PDFBox invokes ``applySoftMaskToPaint`` from
``getNonStrokingPaint`` / ``getStrokingPaint`` / ``drawBufferedImage`` —
i.e. every paint that consults the current GS picks up the mask. The
wave-1384 fix routes direct fills/strokes through ``_paint_through_clip``
with the active soft mask plumbed in, so the rendered alpha plane is
multiplied into the layer's alpha before compositing.

Also verifies the inverse: when the same SMask is active *inside* a
transparency group's recursive render, the mask is **not** applied per
paint (the group composite step applies it once) — no double-masking.

Includes a real-world smoke test against the three bundled PDFs whose
content carries ``/SMask`` references.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer


def _is_close(actual, expected, tol=12):
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _build_mask_form(content, page_size=60.0):
    s = COSStream()
    s.set_raw_data(content)
    f = PDFormXObject(s)
    f.set_b_box(PDRectangle(0.0, 0.0, page_size, page_size))
    g = COSDictionary()
    g.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
    )
    f.set_group(g)
    return f


def _make_doc(width=60.0, height=60.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def test_smask_modulates_direct_fill_outside_transparency_group() -> None:
    """A path filled at page top level with an active ExtGState
    ``/SMask`` must be masked by the soft mask's alpha plane. Before
    wave 1384 the mask was silently dropped because direct fills never
    consulted ``self._gs.soft_mask``.

    Setup: a Luminosity soft mask whose group paints a 15x30 white block
    on the **left half** of a 60x60 page (with black backdrop). The page
    then fills a 40x40 red rectangle directly (no enclosing form). The
    left half should remain red; the right half should drop to the page
    background (white).
    """
    doc, page = _make_doc(60.0, 60.0)

    mask_form = _build_mask_form(
        b"1 1 1 rg\n10 10 15 30 re\nf\n", page_size=60.0
    )

    smask = COSDictionary()
    smask.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity")
    )
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
    bc = COSArray()
    for v in (0.0, 0.0, 0.0):
        bc.add(COSFloat(v))
    smask.set_item(COSName.get_pdf_name("BC"), bc)

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("SMask"), smask)

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )

    contents = COSStream()
    contents.set_raw_data(
        b"q\n/GS0 gs\n1 0 0 rg\n10 10 40 40 re\nf\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # PIL y-flip — PDF y=10..50 → PIL y=10..50.
    left = img.getpixel((18, 35))   # mask opaque → red survives
    right = img.getpixel((40, 35))  # mask zero → background visible
    assert _is_close(left, (255, 0, 0), tol=40), f"left={left}"
    assert _is_close(right, (255, 255, 255), tol=8), f"right={right}"


def test_smask_does_not_double_apply_inside_transparency_group() -> None:
    """When the same SMask is active during a transparency-group render,
    the per-paint application path must be **suppressed** — the mask is
    applied exactly once at the group's composite step. Without this
    guard the alpha would be multiplied twice (once per fill inside the
    group, once at composite), producing an obviously darker / more
    transparent result than upstream."""
    doc, page = _make_doc(60.0, 60.0)

    mask_form = _build_mask_form(
        b"1 1 1 rg\n10 10 15 30 re\nf\n", page_size=60.0
    )

    smask = COSDictionary()
    smask.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity")
    )
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
    bc = COSArray()
    for v in (0.0, 0.0, 0.0):
        bc.add(COSFloat(v))
    smask.set_item(COSName.get_pdf_name("BC"), bc)

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("SMask"), smask)

    masked_form = _build_mask_form(
        b"1 0 0 rg\n10 10 40 40 re\nf\n", page_size=60.0
    )

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )
    res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        masked_form.get_cos_object(),
    )

    contents = COSStream()
    contents.set_raw_data(b"q\n/GS0 gs\n/F0 Do\nQ\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    left = img.getpixel((18, 35))
    right = img.getpixel((40, 35))
    # The masked-in side stays at near-pure red (single mask application).
    # Double-masking would have driven alpha to near-zero on the page
    # white backdrop → a pinker / washed-out colour.
    assert _is_close(left, (255, 0, 0), tol=40), f"left={left}"
    assert _is_close(right, (255, 255, 255), tol=8), f"right={right}"


def test_smask_modulates_direct_stroke_outside_transparency_group() -> None:
    """Same as the direct-fill case but for stroke ops — the mask must
    gate the stroked pixels too. Mirrors upstream's
    ``getStrokingPaint`` → ``applySoftMaskToPaint`` chain."""
    doc, page = _make_doc(60.0, 60.0)

    # Mask: opaque on left half only.
    mask_form = _build_mask_form(
        b"1 1 1 rg\n10 10 15 30 re\nf\n", page_size=60.0
    )

    smask = COSDictionary()
    smask.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity")
    )
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
    bc = COSArray()
    for v in (0.0, 0.0, 0.0):
        bc.add(COSFloat(v))
    smask.set_item(COSName.get_pdf_name("BC"), bc)

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("SMask"), smask)

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )

    # Wide horizontal red stroke across the page through the mask area.
    contents = COSStream()
    contents.set_raw_data(
        b"q\n/GS0 gs\n1 0 0 RG\n6 w\n0 25 m\n60 25 l\nS\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Y centre of stroke is at PDF y=25 → PIL y=35.
    left = img.getpixel((18, 35))
    right = img.getpixel((40, 35))
    # Left should carry the red stroke; right should be background.
    assert _is_close(left, (255, 0, 0), tol=80), f"left={left}"
    assert _is_close(right, (255, 255, 255), tol=8), f"right={right}"


def test_real_world_pdfs_with_smask_render_without_error() -> None:
    """Smoke test: the three bundled PDFs that carry ``/SMask`` in their
    content streams render to a non-empty image with no exception. Wave
    1384 added a new code path through ``_paint_through_clip`` whenever
    an SMask is active; a regression would either crash here or produce
    a fully-white image."""
    paths = [
        "tests/fixtures/pdfwriter/unencrypted.pdf",
        "tests/fixtures/multipdf/PDFBOX-5811-362972.pdf",
    ]
    for path in paths:
        doc = PDDocument.load(path)
        try:
            renderer = PDFRenderer(doc)
            img = renderer.render_image(0)
            assert img.size[0] > 0 and img.size[1] > 0
            gray = img.convert("L")
            hist = gray.histogram()
            non_white = sum(hist[:240])
            assert non_white > 0, (
                f"{path}: rendered image is fully white — likely renderer "
                "regressed and silently dropped all paint operators"
            )
        finally:
            doc.close()


def test_nested_transparency_groups_no_crash_two_levels() -> None:
    """Wave 1384 introduced a transparency-group depth counter. Verify
    nesting two groups deep (outer wraps a Do that draws inner) renders
    without crashing and the inner geometry is visible."""
    doc, page = _make_doc(60.0, 60.0)

    inner = _build_mask_form(b"1 0 0 rg\n10 10 30 30 re\nf\n", 60.0)
    outer_res = PDResources()
    outer_res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Inner"),
        inner.get_cos_object(),
    )
    outer = _build_mask_form(b"/Inner Do\n", 60.0)
    outer.set_resources(outer_res)

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Outer"),
        outer.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/Outer Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # PDF y=10..40 → PIL y=20..50.
    inside = img.getpixel((20, 35))
    assert _is_close(inside, (255, 0, 0), tol=20), inside
