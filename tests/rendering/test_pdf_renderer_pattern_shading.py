"""Rendering coverage for tiling-pattern fill and axial/radial shading fill.

These tests synthesise tiny PDFs with raw content streams (the public
`PDPageContentStream` API doesn't yet expose ``cs``/``scn``/``sh``) and
verify pixel colours after :class:`PDFRenderer` paints them.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType2,
    PDShadingType3,
)
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
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


def _exp_function(
    c0: list[float], c1: list[float], domain: tuple[float, float] = (0.0, 1.0)
) -> COSDictionary:
    """Build a minimal Type 2 (exponential) function dictionary."""
    fn_dict = COSDictionary()
    fn_dict.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain_arr = COSArray()
    domain_arr.add(COSFloat(domain[0]))
    domain_arr.add(COSFloat(domain[1]))
    fn_dict.set_item(COSName.get_pdf_name("Domain"), domain_arr)
    c0_arr = COSArray()
    for v in c0:
        c0_arr.add(COSFloat(v))
    fn_dict.set_item(COSName.get_pdf_name("C0"), c0_arr)
    c1_arr = COSArray()
    for v in c1:
        c1_arr.add(COSFloat(v))
    fn_dict.set_item(COSName.get_pdf_name("C1"), c1_arr)
    fn_dict.set_int(COSName.get_pdf_name("N"), 1)
    return fn_dict


# ---------------------------------------------------------------------------
# tiling pattern
# ---------------------------------------------------------------------------


def test_tiling_pattern_fill_paints_tile_pixels_inside_path() -> None:
    """A coloured tiling pattern that paints a solid red 10x10 cell should
    fill the path's interior with red pixels."""
    doc, page = _make_doc(60.0, 60.0)

    # Build a tiling pattern: 10x10 pt cell, fully red.
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 10.0, 10.0))
    pattern.set_x_step(10.0)
    pattern.set_y_step(10.0)
    # Fill the cell with red.
    cell_stream = pattern.get_cos_object()
    cell_stream.set_raw_data(
        b"1 0 0 rg\n"
        b"0 0 10 10 re\n"
        b"f\n"
    )

    # Page resources: register the pattern as /P0.
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )

    # Page contents: select /Pattern colour space, then scn /P0, then
    # fill a 40x40 box at (10,10).
    contents = COSStream()
    contents.set_raw_data(
        b"/Pattern cs\n"
        b"/P0 scn\n"
        b"10 10 40 40 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Inside the rect (PDF (10..50, 10..50) → PIL (10..50, 10..50)).
    assert _is_close(img.getpixel((20, 20)), (255, 0, 0)), img.getpixel((20, 20))
    assert _is_close(img.getpixel((40, 40)), (255, 0, 0)), img.getpixel((40, 40))
    # Outside — should remain white.
    assert _is_close(img.getpixel((5, 5)), (255, 255, 255)), img.getpixel((5, 5))
    assert _is_close(img.getpixel((55, 55)), (255, 255, 255)), img.getpixel((55, 55))


def test_tiling_pattern_fill_outside_path_is_unchanged() -> None:
    """The fill must be clipped to the path; pattern pixels must not leak
    outside the painted rect."""
    doc, page = _make_doc(50.0, 50.0)
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 5.0, 5.0))
    pattern.set_x_step(5.0)
    pattern.set_y_step(5.0)
    pattern.get_cos_object().set_raw_data(
        b"0 1 0 rg\n"
        b"0 0 5 5 re\n"
        b"f\n"
    )
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        b"/Pattern cs\n"
        b"/P0 scn\n"
        b"15 15 20 20 re\n"  # 20x20 patch at (15,15)
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Inside patch → green.
    assert _is_close(img.getpixel((20, 20)), (0, 255, 0)), img.getpixel((20, 20))
    # Outside patch → white.
    assert _is_close(img.getpixel((5, 5)), (255, 255, 255)), img.getpixel((5, 5))
    assert _is_close(img.getpixel((40, 40)), (255, 255, 255)), img.getpixel((40, 40))


# ---------------------------------------------------------------------------
# axial shading (Type 2)
# ---------------------------------------------------------------------------


def test_axial_shading_via_sh_paints_gradient_endpoints() -> None:
    """An axial shading from black to white along x ∈ [10, 50] should
    produce dark pixels near x=10 and bright pixels near x=50."""
    doc, page = _make_doc(60.0, 30.0)

    shading = PDShadingType2()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    coords = COSArray()
    for v in (10.0, 0.0, 50.0, 0.0):
        coords.add(COSFloat(v))
    shading.set_coords(coords)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    shading.set_domain(domain)
    shading.set_function(_exp_function([0.0, 0.0, 0.0], [1.0, 1.0, 1.0]))
    # Extend on both sides to fill the page entirely.
    extend = COSArray()
    from pypdfbox.cos import COSBoolean

    extend.add(COSBoolean.get(True))
    extend.add(COSBoolean.get(True))
    shading.set_extend(extend)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh0"),
        shading.get_cos_object(),
    )

    contents = COSStream()
    contents.set_raw_data(b"/Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Near the start of the axis (x≈10) — should be dark.
    near_start = img.getpixel((10, 15))
    assert near_start[0] < 60, f"expected dark near start, got {near_start}"
    # Near the end (x≈50) — should be bright.
    near_end = img.getpixel((50, 15))
    assert near_end[0] > 200, f"expected bright near end, got {near_end}"
    # Roughly midway should land near grey.
    mid = img.getpixel((30, 15))
    assert 80 < mid[0] < 200, f"expected mid grey, got {mid}"


def test_axial_shading_fill_via_pattern_inside_rect() -> None:
    """A shading-pattern wrapping a Type 2 axial shading, used as the
    non-stroking colour, should fill the path with the gradient (and not
    bleed outside the path)."""
    from pypdfbox.pdmodel.graphics.pattern import PDShadingPattern

    doc, page = _make_doc(60.0, 60.0)

    shading = PDShadingType2()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    coords = COSArray()
    for v in (10.0, 0.0, 50.0, 0.0):
        coords.add(COSFloat(v))
    shading.set_coords(coords)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    shading.set_domain(domain)
    # Black -> red gradient.
    shading.set_function(_exp_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    from pypdfbox.cos import COSBoolean

    extend = COSArray()
    extend.add(COSBoolean.get(True))
    extend.add(COSBoolean.get(True))
    shading.set_extend(extend)

    sp = PDShadingPattern()
    sp.set_shading(shading)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        sp.get_cos_object(),
    )

    contents = COSStream()
    contents.set_raw_data(
        b"/Pattern cs\n"
        b"/P0 scn\n"
        b"10 10 40 40 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Outside path stays white.
    assert _is_close(img.getpixel((5, 5)), (255, 255, 255)), img.getpixel((5, 5))
    assert _is_close(img.getpixel((55, 55)), (255, 255, 255)), img.getpixel((55, 55))
    # Inside path: near x=10 should be dark; near x=50 should be red.
    near_start = img.getpixel((12, 30))
    near_end = img.getpixel((48, 30))
    assert near_start[0] < 80, f"expected dark near start, got {near_start}"
    assert near_end[0] > 200 and near_end[1] < 60, (
        f"expected near red, got {near_end}"
    )


# ---------------------------------------------------------------------------
# radial shading (Type 3)
# ---------------------------------------------------------------------------


def test_radial_shading_via_sh_is_brighter_at_centre() -> None:
    """A radial shading from white at (30,30) r=0 to black at (30,30) r=20
    should be bright in the centre and dark near the outer circle."""
    doc, page = _make_doc(60.0, 60.0)

    shading = PDShadingType3()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    coords = COSArray()
    for v in (30.0, 30.0, 0.0, 30.0, 30.0, 20.0):
        coords.add(COSFloat(v))
    shading.set_coords(coords)
    shading.set_domain([0.0, 1.0])
    # White at centre (s=0), black at outer (s=1).
    shading.set_function(_exp_function([1.0, 1.0, 1.0], [0.0, 0.0, 0.0]))
    shading.set_extend(False, False)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh0"),
        shading.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # The centre should be near-white.
    centre = img.getpixel((30, 30))
    assert centre[0] > 200, f"expected near-white centre, got {centre}"
    # The outer edge should be near-black.
    edge = img.getpixel((30, 11))  # 19 px from centre vertically
    assert edge[0] < 80, f"expected dark near outer circle, got {edge}"
