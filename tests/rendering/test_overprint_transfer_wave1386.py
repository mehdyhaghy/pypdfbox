"""Wave 1386 — ExtGState overprint (``/OP`` / ``/op`` / ``/OPM``) and
transfer functions (``/TR`` / ``/TR2``) honoured at paint time.

Before wave 1386 the renderer's ``gs`` operator carried the line-state /
alpha / soft-mask entries from PDExtendedGraphicsState onto the active
``_GState`` (wave 1385), but the overprint flags + mode and the
output-device transfer functions were silently discarded:

- ``/OP`` / ``/op`` / ``/OPM`` (PDF 32000-1 §11.7.4) — overprint controls
  whether a subsequent paint operation replaces or preserves the
  backdrop on a per-colorant basis.  On a CMYK separation device this is
  expressive; on an sRGB renderer like ours the spec doesn't fully
  apply.  The wave-1386 fix wires the three keys onto ``_GState``, then
  honours the OPM=1 ("nonzero overprint mode") rule on the narrow RGB
  path by suppressing paint when the source colour is pure ``(0, 0, 0)``
  (the only RGB colour with a zero on every channel).  OPM=0 is
  documented as a no-op on continuous-tone RGB output.

- ``/TR`` / ``/TR2`` (PDF 32000-1 §10.5) — output-device transfer
  functions remap a colour value through a per-channel function before
  it hits the device.  Wave 1386 applies the transfer to the resolved
  ``fill_rgb`` / ``stroke_rgb`` triples for solid paints and per-pixel
  to image XObjects in ``_paste_image``.  ``/TR2`` takes precedence
  over ``/TR`` when both are present (mirrors upstream's
  ``PDExtendedGraphicsState.copyIntoGraphicsState``).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.function.pd_function import (
    PDFunction,
    PDFunctionTypeIdentity,
)
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _attach_renderer(ext, ext_name="GS0"):
    """Construct a minimal renderer with a resources dict carrying
    ``ext`` under ``/Resources/ExtGState/<ext_name>``, then fire the
    ``gs`` operator so the full plumb-through runs."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
    doc.add_page(page)

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name(ext_name),
        ext.get_cos_object(),
    )

    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = res
    renderer._op_set_graphics_state_parameters(
        None, [COSName.get_pdf_name(ext_name)]
    )
    return renderer


def _build_type2_function(
    c0: list[float],
    c1: list[float],
    n: float = 1.0,
    domain: list[float] | None = None,
) -> PDFunction:
    """Build a PDF Type 2 (exponential interpolation) function.

    For ``C0 = [1]`` / ``C1 = [0]`` / ``N = 1`` this gives ``output =
    1 - input`` — the canonical "invert" transfer function used by the
    tests below.
    """
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(2))
    if domain is None:
        domain = [0.0, 1.0]
    d_arr = COSArray()
    for v in domain:
        d_arr.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("Domain"), d_arr)
    c0_arr = COSArray()
    for v in c0:
        c0_arr.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("C0"), c0_arr)
    c1_arr = COSArray()
    for v in c1:
        c1_arr.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("C1"), c1_arr)
    d.set_item(COSName.get_pdf_name("N"), COSFloat(n))
    return PDFunction.create(d)


# ---------------------------------------------------------------------------
# /OP /op /OPM plumb-through onto the active _GState
# ---------------------------------------------------------------------------


def test_op_flag_sets_overprint_stroking_on_gs() -> None:
    """``/OP true`` lands on ``gs.overprint_stroking`` (default False)."""
    ext = PDExtendedGraphicsState()
    ext.set_stroke_overprint(True)
    r = _attach_renderer(ext)
    assert r._gs.overprint_stroking is True


def test_op_lowercase_flag_sets_non_stroking_overprint() -> None:
    """``/op true`` lands on ``gs.overprint_non_stroking`` independently
    of the stroking flag (spec lets either be set on its own)."""
    ext = PDExtendedGraphicsState()
    ext.set_non_stroking_overprint(True)
    r = _attach_renderer(ext)
    assert r._gs.overprint_non_stroking is True


def test_op_only_set_falls_back_for_non_stroking() -> None:
    """Per upstream `getNonStrokingOverprint`, when only ``/OP`` is
    present (no ``/op``), the non-stroking flag falls back to the
    stroking value."""
    ext = PDExtendedGraphicsState()
    ext.set_stroke_overprint(True)  # /OP, no /op
    r = _attach_renderer(ext)
    assert r._gs.overprint_stroking is True
    assert r._gs.overprint_non_stroking is True


def test_opm_zero_is_carried_as_zero() -> None:
    """``/OPM 0`` (normal overprint mode) — the default, but a PDF may
    explicitly set it.  Confirm it round-trips cleanly."""
    ext = PDExtendedGraphicsState()
    ext.set_overprint_mode(0)
    r = _attach_renderer(ext)
    assert r._gs.overprint_mode == 0


def test_opm_one_is_carried_as_one() -> None:
    """``/OPM 1`` (nonzero overprint mode) lands on ``gs.overprint_mode``."""
    ext = PDExtendedGraphicsState()
    ext.set_overprint_mode(1)
    r = _attach_renderer(ext)
    assert r._gs.overprint_mode == 1


def test_opm_clamps_out_of_range_to_zero() -> None:
    """Per spec ``/OPM`` is 0 or 1; an out-of-range value must clamp
    (we clamp to 0 since OPM=1 is the explicit opt-in)."""
    ext = PDExtendedGraphicsState()
    ext.set_overprint_mode(99)
    r = _attach_renderer(ext)
    assert r._gs.overprint_mode == 0


def test_overprint_clone_preserves_fields() -> None:
    """``q`` / ``Q`` save/restore via ``_GState.clone()`` must carry
    every overprint field forward."""
    gs = _GState(
        overprint_stroking=True,
        overprint_non_stroking=True,
        overprint_mode=1,
    )
    clone = gs.clone()
    assert clone.overprint_stroking is True
    assert clone.overprint_non_stroking is True
    assert clone.overprint_mode == 1


# ---------------------------------------------------------------------------
# _overprint_suppresses_paint behavioural rules
# ---------------------------------------------------------------------------


def test_overprint_off_never_suppresses_paint() -> None:
    """Default GS — overprint flags off → paint always runs."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    assert r._overprint_suppresses_paint(stroke=True, fill=False) is False
    assert r._overprint_suppresses_paint(stroke=False, fill=True) is False
    assert r._overprint_suppresses_paint(stroke=True, fill=True) is False


def test_overprint_on_opm_zero_does_not_suppress_paint_on_rgb_device() -> None:
    """OPM=0 ("normal overprint mode") is a no-op on a continuous-tone
    RGB renderer — there are no separation channels to selectively
    preserve. The flag is carried for parity but the paint runs."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.overprint_stroking = True
    r._gs.overprint_non_stroking = True
    r._gs.overprint_mode = 0
    r._gs.fill_rgb = (0, 0, 0)
    r._gs.stroke_rgb = (0, 0, 0)
    assert r._overprint_suppresses_paint(stroke=False, fill=True) is False
    assert r._overprint_suppresses_paint(stroke=True, fill=False) is False


def test_overprint_on_opm_one_suppresses_pure_black_fill() -> None:
    """OPM=1 + pure-black ``fill_rgb`` + ``/op true`` → suppress the
    fill (every channel is zero — preserve backdrop on every channel)."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.overprint_non_stroking = True
    r._gs.overprint_mode = 1
    r._gs.fill_rgb = (0, 0, 0)
    assert r._overprint_suppresses_paint(stroke=False, fill=True) is True


def test_overprint_on_opm_one_does_not_suppress_non_black_fill() -> None:
    """OPM=1 only suppresses when every source channel is zero. A red
    fill ``(255, 0, 0)`` still paints (red component would replace the
    backdrop on the R separation)."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.overprint_non_stroking = True
    r._gs.overprint_mode = 1
    r._gs.fill_rgb = (255, 0, 0)
    assert r._overprint_suppresses_paint(stroke=False, fill=True) is False


def test_overprint_only_for_relevant_paint_kind() -> None:
    """Stroke-only overprint (``/OP true /op false``) must not suppress
    fills, and vice-versa."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    # /OP only, /op false (default before we set non-stroking back to False).
    r._gs.overprint_stroking = True
    r._gs.overprint_non_stroking = False
    r._gs.overprint_mode = 1
    r._gs.fill_rgb = (0, 0, 0)
    r._gs.stroke_rgb = (0, 0, 0)
    assert r._overprint_suppresses_paint(stroke=False, fill=True) is False
    assert r._overprint_suppresses_paint(stroke=True, fill=False) is True


# ---------------------------------------------------------------------------
# /TR /TR2 plumb-through onto the active _GState
# ---------------------------------------------------------------------------


def test_tr_identity_function_resolves_to_none() -> None:
    """``/TR /Identity`` is the spec sentinel meaning "no remap" — the
    renderer stores it as ``None`` so the hot-path no-op check fires."""
    ext = PDExtendedGraphicsState()
    ext.set_transfer(COSName.get_pdf_name("Identity"))
    r = _attach_renderer(ext)
    assert r._gs.transfer_function is None


def test_tr_function_stored_on_gs() -> None:
    """A single-function ``/TR`` (uniform per-channel transfer) lands on
    ``gs.transfer_function`` as the typed PDFunction wrapper."""
    invert = _build_type2_function([1.0], [0.0])
    ext = PDExtendedGraphicsState()
    ext.set_transfer(invert.get_cos_object())
    r = _attach_renderer(ext)
    assert r._gs.transfer_function is not None
    # eval(0.0) → 1.0, eval(1.0) → 0.0 (inverse).
    assert r._gs.transfer_function.eval([0.0])[0] == 1.0
    assert r._gs.transfer_function.eval([1.0])[0] == 0.0


def test_tr2_takes_precedence_over_tr() -> None:
    """When both ``/TR`` and ``/TR2`` are present, the spec says ``/TR2``
    wins (PDF 32000-1 §11.7.5.3) — upstream's
    ``copyIntoGraphicsState`` enforces this by skipping ``/TR`` when
    ``/TR2`` is set."""
    invert = _build_type2_function([1.0], [0.0])
    half = _build_type2_function([0.0], [0.5])  # output = 0.5 * x
    ext = PDExtendedGraphicsState()
    ext.set_transfer(invert.get_cos_object())
    ext.set_transfer2(half.get_cos_object())
    r = _attach_renderer(ext)
    # If /TR2 won we'll see y = 0.5 * x semantics (eval(1.0) → 0.5);
    # if /TR had won, we'd see eval(1.0) → 0.0.
    assert r._gs.transfer_function is not None
    assert r._gs.transfer_function.eval([1.0])[0] == 0.5


def test_tr2_default_name_resolves_to_none() -> None:
    """``/TR2 /Default`` resets the per-page TR — store as None so the
    no-op hot path fires."""
    ext = PDExtendedGraphicsState()
    ext.set_transfer2(COSName.get_pdf_name("Default"))
    r = _attach_renderer(ext)
    assert r._gs.transfer_function is None


def test_tr_clone_preserves_transfer_function() -> None:
    """``q`` / ``Q`` carries the transfer function across save/restore."""
    invert = _build_type2_function([1.0], [0.0])
    gs = _GState(transfer_function=invert)
    clone = gs.clone()
    assert clone.transfer_function is invert


# ---------------------------------------------------------------------------
# Transfer function applied to resolved RGB bytes
# ---------------------------------------------------------------------------


def test_apply_transfer_to_rgb_bytes_noop_when_no_transfer() -> None:
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    assert r._apply_transfer_to_rgb_bytes((128, 64, 200)) == (128, 64, 200)


def test_apply_transfer_to_rgb_bytes_inverts_each_channel() -> None:
    """The ``1 - x`` Type 2 function should invert every byte channel."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.transfer_function = _build_type2_function([1.0], [0.0])
    assert r._apply_transfer_to_rgb_bytes((0, 0, 0)) == (255, 255, 255)
    assert r._apply_transfer_to_rgb_bytes((255, 255, 255)) == (0, 0, 0)
    out = r._apply_transfer_to_rgb_bytes((128, 64, 200))
    # 1 - 128/255 = ~0.498, *255 = ~127; tolerance for the rounding.
    assert abs(out[0] - 127) <= 1
    assert abs(out[1] - 191) <= 1
    assert abs(out[2] - 55) <= 1


def test_apply_transfer_per_channel_with_four_function_form() -> None:
    """The four-function CMYK form maps R/G/B through functions 0..2;
    function 3 (K) is unused on the RGB device."""
    invert = _build_type2_function([1.0], [0.0])
    half = _build_type2_function([0.0], [0.5])  # y = 0.5 * x
    keep = _build_type2_function([0.0], [1.0])  # identity (y = x)
    # K function — unused; build a "would set to 0" function as proof.
    zero = _build_type2_function([0.0], [0.0])
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.transfer_function = [invert, half, keep, zero]
    # R inverted, G halved, B unchanged.
    out = r._apply_transfer_to_rgb_bytes((128, 200, 100))
    assert abs(out[0] - 127) <= 1   # 1 - 128/255 ≈ 0.498
    assert abs(out[1] - 100) <= 1   # 0.5 * 200
    assert out[2] == 100            # identity


def test_apply_transfer_to_byte_returns_input_on_function_failure() -> None:
    """If the function raises on eval, we degrade gracefully (return
    the input unchanged) — protects against malformed PDFs."""

    class _Bomb:
        @staticmethod
        def eval(_input):
            raise RuntimeError("boom")

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.transfer_function = _Bomb()
    # Whole tuple unchanged.
    assert r._apply_transfer_to_rgb_bytes((1, 2, 3)) == (1, 2, 3)


# ---------------------------------------------------------------------------
# Transfer function applied to image pixels (_apply_transfer_to_pil_image)
# ---------------------------------------------------------------------------


def test_apply_transfer_to_pil_image_inverts_rgb_pixels() -> None:
    from PIL import Image

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.transfer_function = _build_type2_function([1.0], [0.0])
    src = Image.new("RGB", (4, 4), (10, 200, 100))
    out = r._apply_transfer_to_pil_image(src)
    pix = out.getpixel((0, 0))
    # Each channel: 1 - x/255, *255.
    assert abs(pix[0] - 245) <= 1
    assert abs(pix[1] - 55) <= 1
    assert abs(pix[2] - 155) <= 1


def test_apply_transfer_to_pil_image_preserves_alpha() -> None:
    """Transfer applies only to colour channels per §10.5; the alpha
    channel must come through unchanged."""
    from PIL import Image

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.transfer_function = _build_type2_function([1.0], [0.0])
    src = Image.new("RGBA", (2, 2), (50, 100, 150, 200))
    out = r._apply_transfer_to_pil_image(src)
    pix = out.getpixel((0, 0))
    assert pix[3] == 200, f"alpha preserved; got {pix}"
    # Colour channels still inverted.
    assert abs(pix[0] - 205) <= 1


def test_apply_transfer_to_pil_image_noop_without_transfer() -> None:
    from PIL import Image

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    src = Image.new("RGB", (2, 2), (50, 100, 150))
    out = r._apply_transfer_to_pil_image(src)
    # Same image (no copy) when no transfer.
    assert out is src


def test_apply_transfer_to_pil_image_handles_grayscale_mode() -> None:
    from PIL import Image

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._gs.transfer_function = _build_type2_function([1.0], [0.0])
    src = Image.new("L", (4, 4), 100)
    out = r._apply_transfer_to_pil_image(src)
    assert abs(out.getpixel((0, 0)) - 155) <= 1


# ---------------------------------------------------------------------------
# End-to-end: render a synthetic PDF and confirm pixels reflect overprint
# / transfer behaviour.
# ---------------------------------------------------------------------------


def _make_doc(width=60.0, height=60.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def test_overprint_opm_one_suppresses_pure_black_fill_in_full_render() -> None:
    """Render a page that paints first a red rectangle, then sets
    ``/OP true /op true /OPM 1`` and tries to paint a pure-black
    rectangle over the same region.  The black paint must be suppressed
    — the red survives."""
    from pypdfbox.cos import COSStream

    doc, page = _make_doc(60.0, 60.0)

    egs = COSDictionary()
    egs.set_boolean(COSName.get_pdf_name("OP"), True)
    egs.set_boolean(COSName.get_pdf_name("op"), True)
    egs.set_item(COSName.get_pdf_name("OPM"), COSInteger.get(1))

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )

    # Paint red first, then activate overprint (OPM=1) and try to paint
    # pure black on top.  With suppression, the black paint is dropped
    # and the red rectangle survives.
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"1 0 0 rg\n"
        b"10 10 40 40 re\n"
        b"f\n"
        b"/GS0 gs\n"
        b"0 0 0 rg\n"
        b"10 10 40 40 re\n"
        b"f\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # PIL flipped Y: PDF (30, 30) → PIL (30, 30) on a 60×60 canvas.
    px = img.getpixel((30, 30))
    # Pure red would be (255, 0, 0); the black-paint suppression must
    # leave most of the red intact.  Tolerance ample for anti-aliasing.
    assert px[0] > 200, f"red preserved (overprint suppressed black); got {px}"
    assert px[1] < 80, f"red preserved; got {px}"
    assert px[2] < 80, f"red preserved; got {px}"


def test_overprint_opm_zero_does_not_suppress_paint_in_full_render() -> None:
    """OPM=0 must NOT suppress paint on the RGB renderer (documented
    divergence vs spec; see ``_overprint_suppresses_paint`` docstring).
    Same setup as the previous test but with OPM=0 — the black paint
    should land and replace the red."""
    from pypdfbox.cos import COSStream

    doc, page = _make_doc(60.0, 60.0)

    egs = COSDictionary()
    egs.set_boolean(COSName.get_pdf_name("OP"), True)
    egs.set_boolean(COSName.get_pdf_name("op"), True)
    egs.set_item(COSName.get_pdf_name("OPM"), COSInteger.get(0))

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"1 0 0 rg\n"
        b"10 10 40 40 re\n"
        b"f\n"
        b"/GS0 gs\n"
        b"0 0 0 rg\n"
        b"10 10 40 40 re\n"
        b"f\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((30, 30))
    # Black replaced red (no suppression on OPM=0 / RGB renderer).
    assert px[0] < 30 and px[1] < 30 and px[2] < 30, f"black landed; got {px}"


def test_transfer_function_inverts_solid_fill_color_in_full_render() -> None:
    """An invert (``1 - x``) ``/TR`` applied to a solid red fill must
    yield cyan in the rendered pixels (inverse of red on every
    channel)."""
    from pypdfbox.cos import COSStream

    doc, page = _make_doc(60.0, 60.0)

    # Build the invert function for /TR.
    invert = _build_type2_function([1.0], [0.0])
    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("TR"), invert.get_cos_object())

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )

    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"/GS0 gs\n"
        b"1 0 0 rg\n"
        b"10 10 40 40 re\n"
        b"f\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((30, 30))
    # Invert(255, 0, 0) → (0, 255, 255) — cyan.
    assert px[0] < 30, f"red inverted to 0; got {px}"
    assert px[1] > 200, f"green inverted from 0 to 255; got {px}"
    assert px[2] > 200, f"blue inverted from 0 to 255; got {px}"


def test_transfer_function_applied_per_pixel_to_image_xobject() -> None:
    """A bitmap image XObject pasted while ``/TR`` is active should be
    transformed per-pixel — the rendered pixels reflect the inverse of
    the source pixels."""

    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    doc, page = _make_doc(60.0, 60.0)

    # Build a 4x4 solid-red image XObject (raw 8-bit RGB).
    width = height = 4
    img_dict = COSStream()
    raw = b"\xff\x00\x00" * (width * height)
    img_dict.set_raw_data(raw)
    img_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    img_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image")
    )
    img_dict.set_item(COSName.get_pdf_name("Width"), COSInteger.get(width))
    img_dict.set_item(COSName.get_pdf_name("Height"), COSInteger.get(height))
    img_dict.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    img_dict.set_item(
        COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8)
    )
    image = PDImageXObject(img_dict)

    # ExtGState: identity transfer would be a no-op; use the invert.
    invert = _build_type2_function([1.0], [0.0])
    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("TR"), invert.get_cos_object())

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        egs,
    )
    res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("IM0"),
        image.get_cos_object(),
    )

    contents = COSStream()
    # cm scales the unit square up to a 40×40 box at (10, 10); Do paints.
    contents.set_raw_data(
        b"q\n"
        b"/GS0 gs\n"
        b"40 0 0 40 10 10 cm\n"
        b"/IM0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((30, 30))
    # The source image was (255, 0, 0); after invert it should be cyan.
    assert px[0] < 30, f"red channel inverted; got {px}"
    assert px[1] > 200, f"green channel inverted; got {px}"
    assert px[2] > 200, f"blue channel inverted; got {px}"


# ---------------------------------------------------------------------------
# Regression: pre-1386 ExtGState behaviour still applies alongside new wiring
# ---------------------------------------------------------------------------


def test_pre_1386_extgstate_entries_still_apply() -> None:
    """Sanity guard — the new overprint / transfer wiring sits beside
    existing /CA /ca handlers; make sure they still apply."""
    ext = PDExtendedGraphicsState()
    ext.set_stroking_alpha_constant(0.5)
    ext.set_non_stroking_alpha_constant(0.25)
    ext.set_stroke_overprint(True)
    ext.set_overprint_mode(1)
    r = _attach_renderer(ext)
    assert r._gs.stroke_alpha == 0.5
    assert r._gs.fill_alpha == 0.25
    assert r._gs.overprint_stroking is True
    assert r._gs.overprint_mode == 1


def test_transfer_typed_identity_stored_as_none() -> None:
    """``PDFunctionTypeIdentity`` instances are normalised to ``None``
    on the GS so the hot-path no-op check fires."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    # Sanity — directly stash a PDFunctionTypeIdentity and confirm the
    # apply path treats it just like None.  (The plumb-through path
    # normalises before storing, but downstream callers may set it
    # post-hoc for ad-hoc tests.)
    r._gs.transfer_function = PDFunctionTypeIdentity()
    # Apply path should swallow the identity (its eval is just x → x).
    # Round-trips cleanly without raising even when not pre-normalised.
    assert r._apply_transfer_to_rgb_bytes((50, 100, 150)) == (50, 100, 150)
