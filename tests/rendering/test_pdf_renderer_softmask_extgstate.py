"""Rendering tests for ExtGState ``/SMask`` (soft-mask) compositing.

Mirrors PDF spec §11.6.5.2-3 plumbing through :class:`PDFRenderer`:

- ``/SMask`` is a soft-mask dictionary referenced from an ExtGState.
- ``/G`` is a transparency-group form XObject; its alpha or luminance
  (subtype ``/S = /Alpha`` or ``/Luminosity``) becomes the mask.
- ``/BC`` provides a backdrop colour for ``/Luminosity``.
- ``/TR`` (default ``/Identity``) is a transfer function applied to mask
  values before they become alpha.
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
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(
    width: float = 100.0, height: float = 100.0
) -> tuple[PDDocument, PDPage]:
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
    return all(
        abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True)
    )


def _build_mask_form(content: bytes, page_size: float = 100.0) -> PDFormXObject:
    """Build a transparency-group form XObject containing ``content``."""
    stream = COSStream()
    stream.set_raw_data(content)
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(0.0, 0.0, page_size, page_size))

    # Mark as a transparency group.
    group = COSDictionary()
    group.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
    )
    form.set_group(group)
    return form


# ---------------------------------------------------------------------------
# PDSoftMask wrapper
# ---------------------------------------------------------------------------


def test_pd_soft_mask_create_returns_none_for_none_name() -> None:
    """``PDSoftMask.create(/None)`` must return ``None`` so the renderer
    treats it as "no soft mask"."""
    assert PDSoftMask.create(COSName.get_pdf_name("None")) is None


def test_pd_soft_mask_create_wraps_dictionary() -> None:
    base = COSDictionary()
    base.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha"))
    sm = PDSoftMask.create(base)
    assert sm is not None
    assert sm.is_alpha()
    assert not sm.is_luminosity()


def test_pd_soft_mask_subtype_round_trip() -> None:
    sm = PDSoftMask()
    sm.set_subtype(COSName.get_pdf_name("Luminosity"))
    assert sm.is_luminosity()
    assert not sm.is_alpha()


def test_extgstate_get_soft_mask_typed_returns_pd_soft_mask() -> None:
    egs = PDExtendedGraphicsState()
    base = COSDictionary()
    base.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha"))
    egs.set_soft_mask(base)
    typed = egs.get_soft_mask_typed()
    assert isinstance(typed, PDSoftMask)
    assert typed.is_alpha()


def test_extgstate_get_soft_mask_typed_returns_none_for_none_name() -> None:
    egs = PDExtendedGraphicsState()
    egs.set_soft_mask(COSName.get_pdf_name("None"))
    assert egs.get_soft_mask_typed() is None


# ---------------------------------------------------------------------------
# rendering — renderer state
# ---------------------------------------------------------------------------


def test_renderer_resets_soft_mask_on_none_name() -> None:
    """A ``gs`` op pointing at an ExtGState with ``/SMask /None`` must
    clear any previously-active soft mask on the GS."""
    doc, page = _make_doc(50.0, 50.0)
    # Build an ExtGState with /SMask /None.
    egs_dict = COSDictionary()
    egs_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState")
    )
    egs_dict.set_item(
        COSName.get_pdf_name("SMask"), COSName.get_pdf_name("None")
    )

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs_dict,
    )

    contents = COSStream()
    contents.set_raw_data(
        b"/GS0 gs\n"
        b"1 0 0 rg\n"
        b"10 10 30 30 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Drawing should still happen — /SMask /None is a no-op mask.
    inside = img.getpixel((20, 30))  # PIL y flipped: PDF (20,20) → PIL (20,30)
    assert _is_close(inside, (255, 0, 0), tol=20), inside


# ---------------------------------------------------------------------------
# rendering — ExtGState SMask + transparency group
# ---------------------------------------------------------------------------


def test_extgstate_smask_alpha_masks_transparency_group() -> None:
    """A transparency group rendered with an active ExtGState
    ``/SMask`` whose subtype is ``/Alpha`` should be alpha-masked by the
    soft-mask group's accumulated alpha.

    The setup: the masked form fills a 30x30 red rectangle. The soft
    mask renders a 15x30 fully-opaque white block on the *left* half of
    that area (the right half stays transparent). The composited result
    should show red on the left and the page background (white) on the
    right.
    """
    doc, page = _make_doc(60.0, 60.0)

    # Soft-mask group: paint a 15x30 white block at (10, 10).
    mask_form = _build_mask_form(
        b"1 1 1 rg\n"
        b"10 10 15 30 re\n"
        b"f\n",
        page_size=60.0,
    )

    # Soft-mask dictionary.
    smask_dict = COSDictionary()
    smask_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Mask")
    )
    smask_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha")
    )
    smask_dict.set_item(
        COSName.get_pdf_name("G"), mask_form.get_cos_object()
    )

    # ExtGState carrying the SMask.
    egs_dict = COSDictionary()
    egs_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState")
    )
    egs_dict.set_item(COSName.get_pdf_name("SMask"), smask_dict)

    # Masked form: a transparency group that fills 30x30 red at (10, 10).
    masked_form = _build_mask_form(
        b"1 0 0 rg\n"
        b"10 10 30 30 re\n"
        b"f\n",
        page_size=60.0,
    )

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs_dict,
    )
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        masked_form.get_cos_object(),
    )

    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"/GS0 gs\n"
        b"/F0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # PIL y flipped — PDF y=10..40 → PIL y=20..50.
    # Mask covers PDF x=10..25 → PIL x=10..25.
    # Left side (PDF x≈18, y≈25 → PIL (18, 35)) — opaque mask + red form
    # → red.
    left = img.getpixel((18, 35))
    # Right side (PDF x≈35 → PIL (35, 35)) — transparent mask area →
    # page background (white).
    right = img.getpixel((35, 35))
    assert _is_close(left, (255, 0, 0), tol=40), f"left={left}"
    assert _is_close(right, (255, 255, 255), tol=8), f"right={right}"


def test_extgstate_smask_luminosity_empty_group_masks_to_zero() -> None:
    """A luminosity SMask whose mask group paints nothing yields mask
    alpha 0 everywhere — even with ``/BC`` set to white. Verified against
    the live PDFBox oracle (wave 1434): PDFBox derives the luminosity
    mask from the group result modulated by the group's *coverage*, so an
    uncovered region contributes alpha 0 regardless of the ``/BC``
    luminance. ``/BC`` only colours the backdrop the group composites
    *over* where it does paint (matters for partially-transparent mask
    content, §11.6.5.3). The masked content therefore does NOT show; the
    page background (white) is preserved.

    (This previously asserted the content was fully visible — a
    non-parity assumption the oracle disproved; see CHANGES.md wave
    1434.)"""
    doc, page = _make_doc(50.0, 50.0)

    # Empty mask group.
    mask_form = _build_mask_form(b"", page_size=50.0)

    smask_dict = COSDictionary()
    smask_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity")
    )
    smask_dict.set_item(
        COSName.get_pdf_name("G"), mask_form.get_cos_object()
    )
    # Backdrop colour: white in DeviceRGB.
    bc = COSArray()
    for v in (1.0, 1.0, 1.0):
        bc.add(COSFloat(v))
    smask_dict.set_item(COSName.get_pdf_name("BC"), bc)

    egs_dict = COSDictionary()
    egs_dict.set_item(COSName.get_pdf_name("SMask"), smask_dict)

    masked_form = _build_mask_form(
        b"0 0 1 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
        page_size=50.0,
    )

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs_dict,
    )
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        masked_form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"/GS0 gs\n"
        b"/F0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # The mask group paints nothing → coverage 0 → mask alpha 0 → the
    # blue content is fully masked out, leaving the white page background
    # (matches PDFBox: uncovered mask area is transparent regardless of
    # the white /BC).
    inside = img.getpixel((15, 25))
    assert _is_close(inside, (255, 255, 255), tol=20), inside


def test_extgstate_smask_luminosity_black_backdrop_masks_to_zero() -> None:
    """With ``/BC`` set to black for a luminosity mask, an empty mask
    group leaves zero luminance everywhere → alpha = 0 → nothing
    composites onto the parent.

    The page should remain at the page background colour (white)."""
    doc, page = _make_doc(50.0, 50.0)

    mask_form = _build_mask_form(b"", page_size=50.0)

    smask_dict = COSDictionary()
    smask_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity")
    )
    smask_dict.set_item(
        COSName.get_pdf_name("G"), mask_form.get_cos_object()
    )
    bc = COSArray()
    for v in (0.0, 0.0, 0.0):
        bc.add(COSFloat(v))
    smask_dict.set_item(COSName.get_pdf_name("BC"), bc)

    egs_dict = COSDictionary()
    egs_dict.set_item(COSName.get_pdf_name("SMask"), smask_dict)

    masked_form = _build_mask_form(
        b"0 1 0 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
        page_size=50.0,
    )

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs_dict,
    )
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        masked_form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"/GS0 gs\n"
        b"/F0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((15, 25))
    assert _is_close(inside, (255, 255, 255), tol=8), (
        f"expected page background, got {inside}"
    )


def test_pd_soft_mask_round_trip_with_form_group() -> None:
    """A soft-mask dict carrying a /G form XObject round-trips through
    :class:`PDSoftMask` — the typed wrapper exposes the form back."""
    mask_form = _build_mask_form(b"", page_size=20.0)
    smask_dict = COSDictionary()
    smask_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha")
    )
    smask_dict.set_item(
        COSName.get_pdf_name("G"), mask_form.get_cos_object()
    )
    sm = PDSoftMask(smask_dict)
    assert sm.get_group() is not None
    assert sm.is_alpha()


def test_extgstate_smask_with_transfer_function_remaps_alpha() -> None:
    """A ``/TR /Identity`` is a no-op; a constant transfer function
    (Type 2 N=1, C0=[1.0], C1=[1.0]) maps every mask value to 1.0 →
    fully visible regardless of the mask.

    Note: this is a parity-style test — even if the mask group paints
    nothing, the constant transfer function should still produce a
    fully-opaque alpha channel for any luminosity input."""
    doc, page = _make_doc(50.0, 50.0)

    # Empty mask group with /S=/Luminosity and BC=black (would normally
    # mask everything to zero alpha).
    mask_form = _build_mask_form(b"", page_size=50.0)
    smask_dict = COSDictionary()
    smask_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity")
    )
    smask_dict.set_item(
        COSName.get_pdf_name("G"), mask_form.get_cos_object()
    )
    bc = COSArray()
    for v in (0.0, 0.0, 0.0):
        bc.add(COSFloat(v))
    smask_dict.set_item(COSName.get_pdf_name("BC"), bc)

    # Transfer function = constant 1.0 — every input maps to 1.0
    # → alpha is fully opaque everywhere.
    tr_dict = COSDictionary()
    tr_dict.set_int(COSName.get_pdf_name("FunctionType"), 2)
    tr_domain = COSArray()
    tr_domain.add(COSFloat(0.0))
    tr_domain.add(COSFloat(1.0))
    tr_dict.set_item(COSName.get_pdf_name("Domain"), tr_domain)
    tr_c0 = COSArray()
    tr_c0.add(COSFloat(1.0))
    tr_dict.set_item(COSName.get_pdf_name("C0"), tr_c0)
    tr_c1 = COSArray()
    tr_c1.add(COSFloat(1.0))
    tr_dict.set_item(COSName.get_pdf_name("C1"), tr_c1)
    tr_dict.set_int(COSName.get_pdf_name("N"), 1)
    smask_dict.set_item(COSName.get_pdf_name("TR"), tr_dict)

    egs_dict = COSDictionary()
    egs_dict.set_item(COSName.get_pdf_name("SMask"), smask_dict)

    masked_form = _build_mask_form(
        b"0 1 0 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
        page_size=50.0,
    )

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs_dict,
    )
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        masked_form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"/GS0 gs\n"
        b"/F0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Transfer remapped black backdrop → 1.0 alpha → green visible.
    inside = img.getpixel((15, 25))
    assert _is_close(inside, (0, 255, 0), tol=20), inside


def test_transparency_group_with_cs_entry_renders_normally() -> None:
    """A transparency group with ``/CS /DeviceRGB`` should render
    identically to one without — the lite renderer logs and ignores the
    colour-space conversion (composes everything in sRGB)."""
    doc, page = _make_doc(50.0, 50.0)
    masked_form = _build_mask_form(
        b"0 0 1 rg\n"
        b"5 5 20 20 re\n"
        b"f\n",
        page_size=50.0,
    )
    # Inject /CS into the existing /Group dict.
    group = masked_form.get_group()
    if group is not None:
        group.set_item(
            COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB")
        )

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        masked_form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # PIL y flipped — PDF y=5..25 → PIL y=25..45.
    inside = img.getpixel((10, 35))
    assert _is_close(inside, (0, 0, 255), tol=20), inside
