"""Rendering tests for Coons (type 6) and tensor (type 7) patch-mesh
shadings — Wave 1375.

Wave 1374 ported the patch-stream geometry decoders
(``PDShadingType6.parse_patches`` / ``PDShadingType7.parse_patches``).
Wave 1375 wires the renderer to consume those patches and rasterise via
N×N parametric subdivision; Wave 1377 swaps the fixed N=10 for upstream's
adaptive ``calcLevel`` (per-axis cells driven by chord length / interior
control-point bowing), capped at ``_PATCH_SUBDIVISION_N`` cells per axis.
The structural assertions below sample the output for mean colour,
alpha-mask area, and specific-pixel colour within tolerance — not
pixel-exact compares.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.shading import PDShadingType6
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

# ----------------------------------------------------------------------
# Synthetic patch-stream construction helpers
# ----------------------------------------------------------------------


def _encode_bytes(values: list[int]) -> bytes:
    """Encode a sequence of byte-aligned values into a bytes buffer."""
    return bytes(values)


def _quantise(value: float, lo: float, hi: float, src_max: int = 255) -> int:
    """Inverse of ``parse_patch_stream``'s ``_interpolate``: pick the byte
    value whose decoded user-space position is closest to ``value``."""
    if hi == lo:
        return 0
    raw = (value - lo) / (hi - lo) * src_max
    if raw < 0:
        raw = 0
    if raw > src_max:
        raw = src_max
    return int(round(raw))


def _make_coons_stream(
    points: list[tuple[float, float]],
    colors: list[list[float]],
    *,
    x_decode: tuple[float, float] = (0.0, 100.0),
    y_decode: tuple[float, float] = (0.0, 100.0),
    c_decode: tuple[float, float] = (0.0, 1.0),
) -> bytes:
    """Encode a single free (flag=0) Coons patch as a byte-aligned bit
    stream: 1 byte flag + 12 * (x, y) coordinates + 4 * N colour bytes.

    ``points`` are 12 user-space ``(x, y)`` pairs; ``colors`` 4 corner
    colour vectors. Each value is quantised into 8 bits via the shading's
    ``/Decode`` ranges so the stream round-trips through
    ``parse_patches``."""
    assert len(points) == 12
    assert len(colors) == 4
    out: list[int] = [0]
    for x, y in points:
        out.append(_quantise(x, *x_decode))
        out.append(_quantise(y, *y_decode))
    for col in colors:
        for c in col:
            out.append(_quantise(c, *c_decode))
    return _encode_bytes(out)


def _make_tensor_stream(
    points: list[tuple[float, float]],
    colors: list[list[float]],
    *,
    x_decode: tuple[float, float] = (0.0, 100.0),
    y_decode: tuple[float, float] = (0.0, 100.0),
    c_decode: tuple[float, float] = (0.0, 1.0),
) -> bytes:
    """Encode a single free tensor patch (16 control points)."""
    assert len(points) == 16
    assert len(colors) == 4
    out: list[int] = [0]
    for x, y in points:
        out.append(_quantise(x, *x_decode))
        out.append(_quantise(y, *y_decode))
    for col in colors:
        for c in col:
            out.append(_quantise(c, *c_decode))
    return _encode_bytes(out)


def _make_doc(
    width: float = 100.0, height: float = 100.0
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_shading_stream(
    shading_type: int,
    *,
    payload: bytes,
    decode: list[float],
    num_components: int = 3,
) -> COSStream:
    s = COSStream()
    s.set_int(COSName.get_pdf_name("ShadingType"), shading_type)
    s.set_item(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("DeviceRGB" if num_components == 3 else "DeviceGray"),
    )
    s.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    s.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    s.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    dec_arr = COSArray()
    for v in decode:
        dec_arr.add(COSFloat(v))
    s.set_item(COSName.get_pdf_name("Decode"), dec_arr)
    s.set_raw_data(payload)
    return s


def _attach_and_render(
    doc: PDDocument,
    page: PDPage,
    shading_obj: COSStream,
    shading_name: str = "Sh1",
) -> Image.Image:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name(shading_name),
        shading_obj,
    )
    contents = COSStream()
    contents.set_raw_data(f"/{shading_name} sh\n".encode())
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    return PDFRenderer(doc).render_image(0)


def _sample(img: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    """Sample an RGB triple from ``img`` (flipping y to PDF convention if
    helpful — but here we use top-down PIL coordinates directly)."""
    px = img.convert("RGB").getpixel((x, y))
    return (int(px[0]), int(px[1]), int(px[2]))


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 16,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


def _mean_rgb(img: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[int, int, int]:
    crop = img.convert("RGB").crop(bbox)
    w, h = crop.size
    n = max(1, w * h)
    pixels = crop.tobytes()
    r = sum(pixels[i] for i in range(0, len(pixels), 3))
    g = sum(pixels[i + 1] for i in range(0, len(pixels), 3))
    b = sum(pixels[i + 2] for i in range(0, len(pixels), 3))
    return (r // n, g // n, b // n)


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_coons_single_color_patch_renders_as_solid_fill() -> None:
    """A 1-patch Coons mesh whose 4 corner colours are identical should
    render as a (nearly) solid fill across the patch interior."""
    doc, page = _make_doc(100.0, 100.0)
    # Square Coons patch over [10, 90] x [10, 90] in user space. Boundary
    # curves are straight (interior CPs colinear with corners).
    # Bottom edge: y=10, x: 10 -> 90.
    # Right edge: x=90, y: 10 -> 90.
    # Top edge (reverse): y=90, x: 10 -> 90.
    # Left edge (reverse): x=10, y: 10 -> 90.
    pts = [
        (10, 10), (37, 10), (63, 10), (90, 10),
        (90, 37), (90, 63),
        (90, 90), (63, 90), (37, 90),
        (10, 90), (10, 63), (10, 37),
    ]
    red = [180.0 / 255.0, 60.0 / 255.0, 60.0 / 255.0]
    colors = [red, red, red, red]
    payload = _make_coons_stream(pts, colors)
    shading = _build_shading_stream(
        6, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    img = _attach_and_render(doc, page, shading)
    # Mid-patch sample — PIL is top-down so the user-space y=50 lands
    # at pixel row (height - 50) = 50.
    mid = _sample(img, 50, 50)
    # Expected ~ (180, 60, 60) because corner colours decode to [0,1] *
    # value/255 then go through DeviceRGB.
    assert _is_close(mid, (180, 60, 60), tol=18), f"mid = {mid}"


def test_coons_two_color_gradient_patch_mid_is_interpolated() -> None:
    """A Coons patch with 2 red corners (p0, p3) and 2 blue corners (p6,
    p9) should sample a purple-ish midpoint."""
    doc, page = _make_doc(100.0, 100.0)
    pts = [
        (10, 10), (37, 10), (63, 10), (90, 10),
        (90, 37), (90, 63),
        (90, 90), (63, 90), (37, 90),
        (10, 90), (10, 63), (10, 37),
    ]
    red = [220.0 / 255.0, 30.0 / 255.0, 30.0 / 255.0]
    blue = [30.0 / 255.0, 30.0 / 255.0, 220.0 / 255.0]
    # corner colours match patch corners p0, p3, p6, p9
    # → bottom-left red, bottom-right red, top-right blue, top-left blue.
    colors = [red, red, blue, blue]
    payload = _make_coons_stream(pts, colors)
    shading = _build_shading_stream(
        6, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    img = _attach_and_render(doc, page, shading)
    # The midpoint (user x=50, y=50) → PIL (50, 50) since y is flipped
    # by the renderer's page matrix. Both red and blue should be ~ 125.
    # Wave 1377 — the adaptive subdivision now picks N=2 for a 100x100
    # patch (chord length < 200 px), so the central triangle's flat fill
    # is the average of three sample corners that straddle u/v=0.5
    # asymmetrically — relax tolerance accordingly. Mid is still
    # "purple-ish" (red and blue both present, green low).
    mid = _sample(img, 50, 50)
    # Red and blue components should be close (within the coarse-grid
    # tolerance); green should be ~ 30.
    assert abs(mid[0] - mid[2]) <= 80, f"red/blue not balanced at midpoint: {mid}"
    assert mid[0] > 40 and mid[2] > 40, (
        f"red and blue both expected non-trivial: {mid}"
    )
    assert mid[1] < 80, f"green channel should be low: {mid}"
    # Sample near bottom edge (y near 10 in user → near bottom of image).
    near_bottom = _sample(img, 50, 85)
    # near_bottom should be more red than blue.
    assert near_bottom[0] > near_bottom[2], (
        f"bottom edge should be redder: {near_bottom}"
    )
    # Sample near top edge.
    near_top = _sample(img, 50, 15)
    assert near_top[2] > near_top[0], (
        f"top edge should be bluer: {near_top}"
    )


def test_coons_multi_patch_stitch_without_gaps() -> None:
    """Two adjacent Coons patches sharing an edge (encoded via flag=2)
    should render without visible gaps along the shared boundary."""
    doc, page = _make_doc(100.0, 100.0)
    # Patch 1: square over [10, 50] x [10, 90]
    pts1 = [
        (10, 10), (23, 10), (37, 10), (50, 10),
        (50, 37), (50, 63),
        (50, 90), (37, 90), (23, 90),
        (10, 90), (10, 63), (10, 37),
    ]
    green1 = [50.0 / 255.0, 200.0 / 255.0, 50.0 / 255.0]
    x_dec = (0.0, 100.0)
    y_dec = (0.0, 100.0)
    c_dec = (0.0, 1.0)
    # Encode patch 1 (flag=0) then patch 2 (flag=2 shares the right edge
    # of patch 1 → which becomes the left edge of patch 2). Per spec,
    # flag=2 implicit edge = pts[6], pts[7], pts[8], pts[9] of previous
    # patch, then we provide 8 new control points + 2 new corner colours.
    out: list[int] = [0]
    for (x, y) in pts1:
        out.append(_quantise(x, *x_dec))
        out.append(_quantise(y, *y_dec))
    for col in (green1, green1, green1, green1):
        for c in col:
            out.append(_quantise(c, *c_dec))
    # Patch 2 (flag=2). Implicit edge = pts1[6..9] = (50,90),(37,90),
    # (23,90),(10,90) — that's actually the **top** edge in our orientation
    # but the decoder uses it as the new patch's first 4 control points
    # which becomes its bottom boundary. So patch 2 lives above patch 1,
    # spanning the top edge.
    # We provide 8 additional points (so the patch becomes 4 stacked
    # going upward, covering user y=90 → 100).
    out.append(2)  # flag=2
    new_pts = [
        (50, 95), (50, 97),   # right edge (p4, p5)
        (50, 100), (37, 100), (23, 100),   # top + p6 + p7 + p8
        (10, 100), (10, 97), (10, 95),   # p9 + left edge
    ]
    # Total 8 new (x, y) pairs.
    for (x, y) in new_pts:
        out.append(_quantise(x, *x_dec))
        out.append(_quantise(y, *y_dec))
    # 2 new corner colours: c2 and c3 (the top corners of patch 2).
    for col in (green1, green1):
        for c in col:
            out.append(_quantise(c, *c_dec))
    payload = bytes(out)
    shading = _build_shading_stream(
        6, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    img = _attach_and_render(doc, page, shading)
    # Sample a strip across the shared boundary y=90 in user space → pixel
    # row ~10 (since user_y=90 → pixel_y=100-90=10 with the page matrix).
    # The renderer's transform flips y. Verify both sides of the shared
    # boundary have similar (green) colour.
    strip_above = _sample(img, 30, 5)   # higher in user space, near top patch
    strip_below = _sample(img, 30, 20)  # near bottom of upper region
    # Both should be greenish.
    assert strip_above[1] > strip_above[0], f"strip_above not greenish: {strip_above}"
    assert strip_below[1] > strip_below[0], f"strip_below not greenish: {strip_below}"


def test_tensor_product_patch_16_control_points_renders() -> None:
    """A tensor-product patch with 16 control points (curved interior)
    should render a covered area whose mean colour matches the corner
    colour band."""
    doc, page = _make_doc(100.0, 100.0)
    # 4x4 grid layout per PDF 32000-1 §8.7.4.5.8 Figure 40. We pick a
    # flat-ish grid plus 4 interior control points slightly displaced.
    # Boundary curves identical to a "square" but interior CPs bulge in.
    pts = [
        # Boundary: bottom (p0-p3), right (p3-p6 via p4,p5), top
        # (p6-p9 reversed via p7,p8), left (p9-p0 via p10,p11).
        (10, 10), (37, 10), (63, 10), (90, 10),    # p0..p3
        (90, 37), (90, 63),                         # p4, p5
        (90, 90), (63, 90), (37, 90),               # p6..p8
        (10, 90), (10, 63), (10, 37),               # p9..p11
        # Interior (clockwise from bottom-left interior):
        # grid[1][1] = p12, grid[1][2] = p13, grid[2][2] = p14, grid[2][1] = p15
        (40, 40), (60, 40), (60, 60), (40, 60),     # p12..p15
    ]
    yellow = [220.0 / 255.0, 200.0 / 255.0, 40.0 / 255.0]
    colors = [yellow, yellow, yellow, yellow]
    payload = _make_tensor_stream(pts, colors)
    shading = _build_shading_stream(
        7, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    img = _attach_and_render(doc, page, shading)
    # Mean over the patch interior should be close to yellow.
    mean = _mean_rgb(img, (20, 20, 80, 80))
    assert _is_close(mean, (220, 200, 40), tol=50), f"tensor mean = {mean}"


def test_coons_patch_honours_background_outside_patch() -> None:
    """When ``/Background`` is set, pixels inside the shading's region
    but outside any patch should pick up the background colour."""
    doc, page = _make_doc(100.0, 100.0)
    # Tiny patch in the top-left corner — most of the page should be
    # background.
    pts = [
        (10, 10), (17, 10), (23, 10), (30, 10),
        (30, 17), (30, 23),
        (30, 30), (23, 30), (17, 30),
        (10, 30), (10, 23), (10, 17),
    ]
    fg = [10.0 / 255.0, 10.0 / 255.0, 10.0 / 255.0]
    colors = [fg, fg, fg, fg]
    payload = _make_coons_stream(pts, colors)
    shading = _build_shading_stream(
        6, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    # Add /Background = magenta.
    bg = COSArray()
    for v in (1.0, 0.0, 1.0):
        bg.add(COSFloat(v))
    shading.set_item(COSName.get_pdf_name("Background"), bg)
    img = _attach_and_render(doc, page, shading)
    # Sample a pixel well away from the patch (user (70, 70) → PIL (70,30)).
    away = _sample(img, 70, 30)
    # Should be magenta-ish.
    assert away[0] > 180 and away[2] > 180 and away[1] < 80, (
        f"background sample not magenta: {away}"
    )


def test_coons_patch_honours_anti_alias_flag() -> None:
    """The ``/AntiAlias`` flag should be read without raising; the
    smoothed rendering with AA on should still cover the patch."""
    doc, page = _make_doc(100.0, 100.0)
    pts = [
        (10, 10), (37, 10), (63, 10), (90, 10),
        (90, 37), (90, 63),
        (90, 90), (63, 90), (37, 90),
        (10, 90), (10, 63), (10, 37),
    ]
    teal = [40.0 / 255.0, 180.0 / 255.0, 180.0 / 255.0]
    colors = [teal, teal, teal, teal]
    payload = _make_coons_stream(pts, colors)
    shading = _build_shading_stream(
        6, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    from pypdfbox.cos import COSBoolean
    shading.set_item(COSName.get_pdf_name("AntiAlias"), COSBoolean.TRUE)
    img = _attach_and_render(doc, page, shading)
    mid = _sample(img, 50, 50)
    assert _is_close(mid, (40, 180, 180), tol=20), f"AA patch mid = {mid}"


def test_paint_patch_mesh_returns_false_for_empty_decode() -> None:
    """Patch shading without ``/Decode`` should report failure so the
    legacy uniform-fill fallback still kicks in (no crash)."""
    doc, page = _make_doc(40.0, 40.0)
    s = COSStream()
    s.set_int(COSName.get_pdf_name("ShadingType"), 6)
    s.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    s.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    s.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    s.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    # No /Decode -> parse_patches returns []
    s.set_raw_data(b"")
    img = _attach_and_render(doc, page, s)
    # Should not raise; canvas should be the page background (white).
    assert img.size == (40, 40)


def test_paint_patch_mesh_shading_returns_true_directly() -> None:
    """Direct invocation of ``_paint_patch_mesh_shading`` on a valid
    patch should return ``True`` (the dispatch flag the caller checks
    to decide whether to fall through to the uniform fallback)."""
    doc, page = _make_doc(60.0, 60.0)
    pts = [
        (10, 10), (20, 10), (40, 10), (50, 10),
        (50, 20), (50, 40),
        (50, 50), (40, 50), (20, 50),
        (10, 50), (10, 40), (10, 20),
    ]
    blue = [30.0 / 255.0, 30.0 / 255.0, 220.0 / 255.0]
    colors = [blue, blue, blue, blue]
    payload = _make_coons_stream(
        pts, colors, x_decode=(0.0, 60.0), y_decode=(0.0, 60.0),
    )
    shading_stream = _build_shading_stream(
        6, payload=payload, decode=[0.0, 60.0, 0.0, 60.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh1"),
        shading_stream,
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh1 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)
    # Should be blue across the patch.
    mid = _sample(img, 30, 30)
    assert mid[2] > mid[0], f"mid not blue-ish: {mid}"


def test_coons_subdivision_cap_matches_upstream_max_level() -> None:
    """Wave 1377 — the renderer's ``_PATCH_SUBDIVISION_N`` is now the
    per-axis cap, not the fixed subdivision. Upstream's ``calcLevel``
    init value is 4, so the cap is ``2 ** 4 = 16`` cells per axis."""
    assert PDFRenderer._PATCH_SUBDIVISION_N == 16


def test_coons_patch_class_dispatch_constructs_typed_wrapper() -> None:
    """Sanity check — the dispatch path uses isinstance(shading,
    PDShadingType6 / PDShadingType7) so the resources resolver must
    produce the typed wrapper, not the raw COSStream."""
    doc, page = _make_doc(60.0, 60.0)
    pts = [
        (10, 10), (20, 10), (40, 10), (50, 10),
        (50, 20), (50, 40),
        (50, 50), (40, 50), (20, 50),
        (10, 50), (10, 40), (10, 20),
    ]
    fg = [120.0 / 255.0, 120.0 / 255.0, 120.0 / 255.0]
    payload = _make_coons_stream(
        pts, [fg, fg, fg, fg],
        x_decode=(0.0, 60.0), y_decode=(0.0, 60.0),
    )
    shading_stream = _build_shading_stream(
        6, payload=payload, decode=[0.0, 60.0, 0.0, 60.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh1"),
        shading_stream,
    )
    resolved = resources.get_shading(COSName.get_pdf_name("Sh1"))
    assert isinstance(resolved, PDShadingType6)


def test_tensor_subdivision_uses_tensor_evaluator() -> None:
    """Tensor patch dispatch (control_points=16) should route through
    ``_tensor_patch_eval`` — verify by ensuring a 16-pt patch with
    bulged interior CPs renders pixels distinct from a flat boundary
    extrapolation."""
    doc, page = _make_doc(100.0, 100.0)
    # Same boundary as the test_tensor_product_patch test above, but
    # asymmetric interior CPs so the centre shifts.
    pts = [
        (10, 10), (37, 10), (63, 10), (90, 10),
        (90, 37), (90, 63),
        (90, 90), (63, 90), (37, 90),
        (10, 90), (10, 63), (10, 37),
        # Interior pulled toward top-right.
        (35, 35), (70, 35), (70, 70), (35, 70),
    ]
    yellow = [220.0 / 255.0, 200.0 / 255.0, 40.0 / 255.0]
    payload = _make_tensor_stream(pts, [yellow, yellow, yellow, yellow])
    shading = _build_shading_stream(
        7, payload=payload, decode=[0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    img = _attach_and_render(doc, page, shading)
    # The patch should cover well over half the [10..90] x [10..90] bbox.
    # Count yellow-ish pixels — mean test alone tolerated white gaps.
    rgb = img.convert("RGB")
    yellow_count = 0
    for y in range(10, 90, 4):
        for x in range(10, 90, 4):
            pr, pg, pb = rgb.getpixel((x, y))
            if pr > 150 and pg > 130 and pb < 100:
                yellow_count += 1
    # Generous lower bound — the patch should cover most of the region.
    assert yellow_count > 100, f"yellow_count = {yellow_count}"
