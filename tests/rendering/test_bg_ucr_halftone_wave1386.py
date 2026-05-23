"""Wave 1386 — Black Generation (/BG, /BG2), Undercolour Removal
(/UCR, /UCR2), and Halftone (/HT).

Before wave 1386 the renderer's ``_op_set_graphics_state_parameters``
listed ``/BG``, ``/BG2``, ``/UCR``, ``/UCR2``, ``/HT`` under "deferred":
the GS fields were never stored, and there was no path to apply BG /
UCR during a CMYK conversion (the lite renderer's screen path never
goes through CMYK, but ``PDFRenderer.convert_rgb_to_cmyk`` /
``convert_rgb_image_to_cmyk`` are now public hooks for downstream
print-prep tooling).

This wave wires:

- ``_GState.black_generation`` / ``black_generation2``,
- ``_GState.undercolor_removal`` / ``undercolor_removal2``,
- ``_GState.halftone``,
- The accessors ``get_active_black_generation`` /
  ``get_active_undercolor_removal`` / ``get_active_halftone`` on
  ``PDFRenderer``,
- The conversion helpers ``convert_rgb_to_cmyk`` /
  ``convert_rgb_image_to_cmyk``.

Upstream reference:
``org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState``
(getBlackGeneration / getBlackGeneration2 / getUndercolorRemoval /
getUndercolorRemoval2 / getHalftone).
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _attach_renderer(ext: PDExtendedGraphicsState, ext_name: str = "GS1") -> Any:
    """Spin up a minimal renderer with a resources dict carrying the
    given ExtGState, then invoke ``_op_set_graphics_state_parameters``
    so the ``gs`` operator fires its full plumb-through. Mirrors the
    helper in ``test_pdf_renderer_extgstate_wave1385.py``.
    """
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


def _identity_function_type2() -> COSDictionary:
    """Build a Type 2 (exponential) function with N=1 (linear,
    identity over [0, 1] -> [0, 1])."""
    dict_ = COSDictionary()
    dict_.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    dict_.set_item(COSName.get_pdf_name("Domain"), domain)
    range_ = COSArray()
    range_.add(COSFloat(0.0))
    range_.add(COSFloat(1.0))
    dict_.set_item(COSName.get_pdf_name("Range"), range_)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    dict_.set_item(COSName.get_pdf_name("C0"), c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    dict_.set_item(COSName.get_pdf_name("C1"), c1)
    dict_.set_item(COSName.get_pdf_name("N"), COSInteger.get(1))
    return dict_


def _constant_function_type2(value: float) -> COSDictionary:
    """Build a Type 2 (exponential) function with N=1 and
    C0 == C1 == ``value`` — produces ``value`` for every input."""
    dict_ = COSDictionary()
    dict_.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    dict_.set_item(COSName.get_pdf_name("Domain"), domain)
    range_ = COSArray()
    range_.add(COSFloat(0.0))
    range_.add(COSFloat(1.0))
    dict_.set_item(COSName.get_pdf_name("Range"), range_)
    c0 = COSArray()
    c0.add(COSFloat(value))
    dict_.set_item(COSName.get_pdf_name("C0"), c0)
    c1 = COSArray()
    c1.add(COSFloat(value))
    dict_.set_item(COSName.get_pdf_name("C1"), c1)
    dict_.set_item(COSName.get_pdf_name("N"), COSInteger.get(1))
    return dict_


def _halftone_dict() -> COSDictionary:
    """Build a minimal Type 1 halftone dictionary per PDF 32000-1
    §10.6.5. Type 1 = spot-function-based, requires Frequency / Angle
    / SpotFunction (we use the literal name ``/Round``)."""
    ht = COSDictionary()
    ht.set_name(COSName.get_pdf_name("Type"), "Halftone")
    ht.set_int(COSName.get_pdf_name("HalftoneType"), 1)
    ht.set_item(
        COSName.get_pdf_name("Frequency"), COSFloat(60.0)
    )
    ht.set_item(COSName.get_pdf_name("Angle"), COSFloat(45.0))
    ht.set_item(
        COSName.get_pdf_name("SpotFunction"),
        COSName.get_pdf_name("Round"),
    )
    return ht


# ---------------------------------------------------------------------------
# /BG / /BG2 — black-generation storage
# ---------------------------------------------------------------------------


def test_bg_stored_on_gs() -> None:
    """``/BG`` (a function) should land on ``gs.black_generation``."""
    ext = PDExtendedGraphicsState()
    bg_fn = _identity_function_type2()
    ext.set_black_generation(bg_fn)
    r = _attach_renderer(ext)
    assert r._gs.black_generation is bg_fn


def test_bg2_stored_on_gs() -> None:
    """``/BG2`` (a function or /Default) should land on
    ``gs.black_generation2``."""
    ext = PDExtendedGraphicsState()
    bg2_fn = _identity_function_type2()
    ext.set_black_generation2(bg2_fn)
    r = _attach_renderer(ext)
    assert r._gs.black_generation2 is bg2_fn


def test_bg2_default_name_stored_as_cosname() -> None:
    """``/BG2 /Default`` — the spec sentinel that resets the per-page
    override — should land verbatim on ``gs.black_generation2``."""
    ext = PDExtendedGraphicsState()
    ext.set_black_generation2(COSName.get_pdf_name("Default"))
    r = _attach_renderer(ext)
    assert isinstance(r._gs.black_generation2, COSName)
    assert r._gs.black_generation2.get_name() == "Default"


def test_get_active_black_generation_prefers_bg2() -> None:
    """``/BG2`` should take precedence over ``/BG`` per spec."""
    ext = PDExtendedGraphicsState()
    bg_fn = _constant_function_type2(0.25)
    bg2_fn = _constant_function_type2(0.75)
    ext.set_black_generation(bg_fn)
    ext.set_black_generation2(bg2_fn)
    r = _attach_renderer(ext)
    active = r.get_active_black_generation()
    assert active is bg2_fn


def test_get_active_black_generation_falls_back_to_bg() -> None:
    """When ``/BG2`` is absent, ``/BG`` should be the active function."""
    ext = PDExtendedGraphicsState()
    bg_fn = _identity_function_type2()
    ext.set_black_generation(bg_fn)
    r = _attach_renderer(ext)
    assert r.get_active_black_generation() is bg_fn


# ---------------------------------------------------------------------------
# /UCR / /UCR2 — undercolour-removal storage
# ---------------------------------------------------------------------------


def test_ucr_stored_on_gs() -> None:
    ext = PDExtendedGraphicsState()
    ucr_fn = _identity_function_type2()
    ext.set_undercolor_removal(ucr_fn)
    r = _attach_renderer(ext)
    assert r._gs.undercolor_removal is ucr_fn


def test_ucr2_stored_on_gs() -> None:
    ext = PDExtendedGraphicsState()
    ucr2_fn = _identity_function_type2()
    ext.set_undercolor_removal2(ucr2_fn)
    r = _attach_renderer(ext)
    assert r._gs.undercolor_removal2 is ucr2_fn


def test_get_active_undercolor_removal_prefers_ucr2() -> None:
    ext = PDExtendedGraphicsState()
    ucr_fn = _constant_function_type2(0.0)
    ucr2_fn = _constant_function_type2(0.5)
    ext.set_undercolor_removal(ucr_fn)
    ext.set_undercolor_removal2(ucr2_fn)
    r = _attach_renderer(ext)
    assert r.get_active_undercolor_removal() is ucr2_fn


# ---------------------------------------------------------------------------
# /HT — halftone storage + accessor
# ---------------------------------------------------------------------------


def test_ht_dict_stored_on_gs() -> None:
    """A halftone dictionary should round-trip through the ``gs`` op."""
    ext = PDExtendedGraphicsState()
    ht = _halftone_dict()
    ext.set_halftone(ht)
    r = _attach_renderer(ext)
    assert r._gs.halftone is ht


def test_ht_default_name_stored_as_cosname() -> None:
    """The spec sentinel ``/HT /Default`` should land verbatim."""
    ext = PDExtendedGraphicsState()
    ext.set_halftone(COSName.get_pdf_name("Default"))
    r = _attach_renderer(ext)
    assert isinstance(r._gs.halftone, COSName)
    assert r._gs.halftone.get_name() == "Default"


def test_get_active_halftone_returns_active_value() -> None:
    ext = PDExtendedGraphicsState()
    ht = _halftone_dict()
    ext.set_halftone(ht)
    r = _attach_renderer(ext)
    assert r.get_active_halftone() is ht


def test_get_active_halftone_defaults_to_none() -> None:
    """With no ``/HT`` set, the active halftone is ``None`` (device
    default)."""
    ext = PDExtendedGraphicsState()
    r = _attach_renderer(ext)
    assert r.get_active_halftone() is None


# ---------------------------------------------------------------------------
# RGB → CMYK conversion (scalar + raster), applying BG / UCR
# ---------------------------------------------------------------------------


def test_convert_rgb_to_cmyk_identity_no_overrides() -> None:
    """With no ExtGState BG / UCR overrides, the conversion collapses
    to the textbook pure-CMYK derivation::

        K = min(1-R, 1-G, 1-B)
        C = 1 - R - K, etc.

    Pure red ``(1, 0, 0)`` therefore gives K = 0, C = 0, M = 1, Y = 1.
    """
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    c, m, y, k = renderer.convert_rgb_to_cmyk(1.0, 0.0, 0.0)
    assert k == 0.0
    assert c == 0.0
    assert m == 1.0
    assert y == 1.0


def test_convert_rgb_to_cmyk_pure_black() -> None:
    """``(0, 0, 0)`` should map to K=1, C=M=Y=0."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    c, m, y, k = renderer.convert_rgb_to_cmyk(0.0, 0.0, 0.0)
    assert k == 1.0
    assert c == 0.0
    assert m == 0.0
    assert y == 0.0


def test_convert_rgb_to_cmyk_pure_white() -> None:
    """``(1, 1, 1)`` should map to K=0, C=M=Y=0."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    c, m, y, k = renderer.convert_rgb_to_cmyk(1.0, 1.0, 1.0)
    assert k == 0.0
    assert c == 0.0
    assert m == 0.0
    assert y == 0.0


def test_convert_rgb_to_cmyk_applies_bg() -> None:
    """A constant-0.5 BG should force K=0.5 regardless of input
    (overriding the candidate K' = min(1-R, 1-G, 1-B))."""
    ext = PDExtendedGraphicsState()
    ext.set_black_generation(_constant_function_type2(0.5))
    r = _attach_renderer(ext)
    # Mid-gray RGB: K' = min(.5, .5, .5) = 0.5, BG(0.5) = 0.5 — but
    # try a non-gray input to prove the BG override is what counts.
    c, m, y, k = r.convert_rgb_to_cmyk(0.8, 0.2, 0.2)
    # K should come from BG(min(.2, .8, .8)) = BG(.2) = 0.5 (constant).
    assert k == 0.5


def test_convert_rgb_to_cmyk_applies_ucr() -> None:
    """A constant-0.5 UCR should subtract 0.5 from each CMY component
    (the candidate K' stays unchanged since BG is identity).

    Pure red (1, 0, 0): K' = 0 → K = 0 → UCR(0) = 0.5 →
    C = clamp01(1 - 1 - 0.5) = 0, M = clamp01(1 - 0 - 0.5) = 0.5,
    Y = clamp01(1 - 0 - 0.5) = 0.5.
    """
    ext = PDExtendedGraphicsState()
    ext.set_undercolor_removal(_constant_function_type2(0.5))
    r = _attach_renderer(ext)
    c, m, y, k = r.convert_rgb_to_cmyk(1.0, 0.0, 0.0)
    assert k == 0.0
    assert c == 0.0
    assert m == 0.5
    assert y == 0.5


def test_convert_rgb_image_to_cmyk_no_overrides_pure_red() -> None:
    """A solid red Pillow image should convert to a CMYK image with
    C=0, M=255, Y=255, K=0 per pixel under the default identity BG /
    UCR."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    src = Image.new("RGB", (4, 4), color=(255, 0, 0))
    cmyk = renderer.convert_rgb_image_to_cmyk(src)
    assert cmyk.mode == "CMYK"
    px = cmyk.getpixel((0, 0))
    assert px == (0, 255, 255, 0)


def test_convert_rgb_image_to_cmyk_with_bg_constant() -> None:
    """A constant-0.25 BG → every pixel's K should be 64 (≈0.25*255)."""
    ext = PDExtendedGraphicsState()
    ext.set_black_generation(_constant_function_type2(0.25))
    r = _attach_renderer(ext)
    src = Image.new("RGB", (2, 2), color=(255, 0, 0))
    cmyk = r.convert_rgb_image_to_cmyk(src)
    px = cmyk.getpixel((0, 0))
    # K = round(0.25 * 255) = 64. C/M/Y depend on UCR(K) which is
    # identity-clamped here: UCR(K) = K/255 = 0.25 → 64.
    assert px[3] == 64
    # Identity UCR: ucr_k = bg(k') = 64; C = clamp(255-255-64,0,255)=0
    # M = clamp(255-0-64,0,255) = 191, Y = same as M = 191.
    assert px[0] == 0
    assert px[1] == 191
    assert px[2] == 191


def test_convert_rgb_image_to_cmyk_accepts_non_rgb_mode() -> None:
    """A Pillow image in mode 'L' (grayscale) should be promoted to
    RGB before conversion — no AttributeError."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    src = Image.new("L", (2, 2), color=128)
    cmyk = renderer.convert_rgb_image_to_cmyk(src)
    assert cmyk.mode == "CMYK"
    # Mid-gray (128, 128, 128) → K' = 127, K = 127, C=M=Y = 0.
    px = cmyk.getpixel((0, 0))
    assert px == (0, 0, 0, 127)


# ---------------------------------------------------------------------------
# halftone — non-applying parity (must not crash the screen render)
# ---------------------------------------------------------------------------


def test_halftone_does_not_affect_active_gs_other_fields() -> None:
    """Setting /HT on an otherwise-empty ExtGState should not perturb
    any other GS field (line width, stroke alpha, blend mode, etc.)."""
    ext = PDExtendedGraphicsState()
    ext.set_halftone(_halftone_dict())
    r = _attach_renderer(ext)
    # Halftone is stored …
    assert r._gs.halftone is not None
    # … and nothing else has shifted from its spec default.
    assert r._gs.line_width == 1.0
    assert r._gs.stroke_alpha == 1.0
    assert r._gs.fill_alpha == 1.0
    assert r._gs.blend_mode is None
    assert r._gs.soft_mask is None


def test_halftone_does_not_crash_screen_render_helpers() -> None:
    """The screen-render helpers should never touch the halftone
    field. Building + cloning a ``_GState`` with halftone set should
    round-trip the value."""
    gs = _GState()
    ht = _halftone_dict()
    gs.halftone = ht
    clone = gs.clone()
    assert clone.halftone is ht


# ---------------------------------------------------------------------------
# misuse / robustness
# ---------------------------------------------------------------------------


def test_bg_with_unparseable_function_falls_through_to_identity() -> None:
    """If BG is set to something the PDFunction factory can't parse,
    ``_apply_function`` should silently fall back to the identity
    transform (clamped to [0, 1])."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    # Stuff a junk COSDictionary (no /FunctionType) into the GS slot.
    junk = COSDictionary()
    renderer._gs.black_generation = junk
    # Identity fall-through means apply(0.4) == 0.4.
    result = renderer._apply_black_generation(0.4)
    assert result == 0.4


def test_apply_function_clamps_out_of_range_to_unit() -> None:
    """A function that returns 1.5 should be clamped to 1.0; a
    function that returns -0.5 should be clamped to 0.0."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    # Constant 1.5 (out of [0, 1]) — our static helper clamps.
    above = _constant_function_type2(1.5)
    assert renderer._apply_function(above, 0.0) == 1.0
    below = _constant_function_type2(-0.5)
    assert renderer._apply_function(below, 0.0) == 0.0


def test_apply_function_handles_default_cosname() -> None:
    """``/Default`` (the BG2 / UCR2 sentinel) should produce the
    identity transform when passed to ``_apply_function``."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    assert (
        renderer._apply_function(COSName.get_pdf_name("Default"), 0.42)
        == 0.42
    )


def test_apply_function_handles_none() -> None:
    """``None`` (absent function) should produce the identity
    transform."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = None
    assert renderer._apply_function(None, 0.42) == 0.42
