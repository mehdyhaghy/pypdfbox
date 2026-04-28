"""Rendering tests for function-based (Type 1) shading.

PDF 32000-1 §8.7.4.5.2 — the function evaluates over the shading's
``/Domain`` rectangle and returns the colour at each ``(x, y)`` point
inside that rectangle. The optional ``/Matrix`` transforms the domain
into pattern user space.
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
from pypdfbox.pdmodel.graphics.shading import PDShadingType1
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer


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
        abs(a - e) <= tol for a, e in zip(actual, expected, strict=True)
    )


def _type4_postscript_function(domain: list[float], range_: list[float], code: bytes) -> COSStream:
    """Build a Type 4 PostScript-calculator function stream."""
    fn_stream = COSStream()
    fn_stream.set_int(COSName.get_pdf_name("FunctionType"), 4)
    domain_arr = COSArray()
    for v in domain:
        domain_arr.add(COSFloat(v))
    fn_stream.set_item(COSName.get_pdf_name("Domain"), domain_arr)
    range_arr = COSArray()
    for v in range_:
        range_arr.add(COSFloat(v))
    fn_stream.set_item(COSName.get_pdf_name("Range"), range_arr)
    fn_stream.set_raw_data(code)
    return fn_stream


def _exp_function(
    c0: list[float],
    c1: list[float],
    domain: tuple[float, float] = (0.0, 1.0),
) -> COSDictionary:
    """Build a Type 2 (exponential) function dict — single-input only."""
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


def test_function_shading_array_of_per_channel_functions() -> None:
    """When ``/Function`` is a 3-element array of single-output Type 2
    functions (one per RGB channel), the renderer should pick up each
    channel from the corresponding sub-function.

    We don't depend on Type 4 PostScript functions for this test
    (FunctionType 4 may not be implemented in the lite parser); instead
    we use three Type 2 (exponential) functions that interpolate between
    constants. The "x-direction" gradient inherent in a 1-input function
    won't materialise here (each function ignores the y input — Type 2
    functions take one input and broadcast), but the picked colour at
    the domain centre should reflect a midpoint blend.
    """
    doc, page = _make_doc(60.0, 60.0)

    shading = PDShadingType1()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    # Domain spans [0,1]x[0,1] (PDF-domain space).
    domain = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0):
        domain.add(COSFloat(v))
    shading.set_domain(domain)
    # Matrix maps domain to a 60x60 pattern-space rectangle (renderer's
    # device CTM then handles px-pt scaling via the page CTM).
    matrix = COSArray()
    for v in (60.0, 0.0, 0.0, 60.0, 0.0, 0.0):
        matrix.add(COSFloat(v))
    shading.set_matrix(matrix)
    # Three single-output exponential functions: R goes 0→1, G stays 0, B stays 0.
    fn_array = COSArray()
    fn_array.add(_exp_function([0.0], [1.0]))  # R
    fn_array.add(_exp_function([0.0], [0.0]))  # G
    fn_array.add(_exp_function([0.0], [0.0]))  # B
    shading.set_function(fn_array)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh1"),
        shading.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh1 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # The exponential function takes its first input (x) so the pixel at
    # x=10 should be darker red than at x=50.
    near_left = img.getpixel((5, 30))
    near_right = img.getpixel((55, 30))
    # Red channel grows left→right.
    assert near_right[0] >= near_left[0], (
        f"expected red to increase rightward, got {near_left} vs {near_right}"
    )
    # Pure red at x=60 → near (255, 0, 0). Allow generous tol since
    # exponential interpolates with N=1 (linear in x).
    assert near_right[0] > 200, near_right


def test_function_shading_outside_domain_keeps_canvas_white() -> None:
    """A function shading whose ``/Matrix`` maps the domain to a small
    region should not paint outside that region — pixels far away should
    remain at the page background colour."""
    doc, page = _make_doc(60.0, 60.0)
    shading = PDShadingType1()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    domain = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0):
        domain.add(COSFloat(v))
    shading.set_domain(domain)
    # Map domain to a 10x10 region at (20, 20).
    matrix = COSArray()
    for v in (10.0, 0.0, 0.0, 10.0, 20.0, 20.0):
        matrix.add(COSFloat(v))
    shading.set_matrix(matrix)
    fn_array = COSArray()
    fn_array.add(_exp_function([1.0], [1.0]))
    fn_array.add(_exp_function([0.0], [0.0]))
    fn_array.add(_exp_function([0.0], [0.0]))
    shading.set_function(fn_array)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh1"),
        shading.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh1 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Inside the patched region — should be red.
    inside = img.getpixel((25, 25))  # PIL y is flipped; PDF (25,25) → PIL (25, 35)
    # The PIL coords inside the patch region (PDF 20..30 mapped to PIL
    # 30..40). Sample at PIL y=35 to be safely inside.
    inside = img.getpixel((25, 35))
    assert inside[0] > 200, f"expected red inside, got {inside}"
    # Outside the patched region — should be page background (white).
    outside = img.getpixel((5, 5))
    assert _is_close(outside, (255, 255, 255), tol=4), outside
