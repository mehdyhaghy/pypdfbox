"""Tests for PDF blend-mode compositing inside :class:`pypdfbox.rendering.PDFRenderer`.

The renderer reads ``/BM`` from an ExtGState dictionary (PDF 32000-1
§8.4.5 / §11.3.5) and applies the named separable blend mode when
pasting images and compositing transparency groups. These tests exercise
the per-channel blend formulas via the private :meth:`PDFRenderer._blend`
helper directly so we don't have to construct full content streams to
verify each of the twelve §11.3.5.1 modes.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering.pdf_renderer import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _solid(rgba: tuple[int, int, int, int], size: tuple[int, int] = (2, 1)) -> Image.Image:
    return Image.new("RGBA", size, rgba)


def _close(actual: tuple[int, ...], expected: tuple[int, int, int], tol: int = 1) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


# ---------------------------------------------------------------------------
# scalar formulas (PDF 32000-1 §11.3.5.1 Table 136)
# ---------------------------------------------------------------------------


def test_blend_scalar_multiply() -> None:
    assert PDFRenderer._blend_scalar(1.0, 0.0, "Multiply") == 0.0
    assert PDFRenderer._blend_scalar(0.5, 0.5, "Multiply") == 0.25


def test_blend_scalar_screen() -> None:
    assert PDFRenderer._blend_scalar(0.0, 1.0, "Screen") == 1.0
    assert PDFRenderer._blend_scalar(0.5, 0.5, "Screen") == 0.75


def test_blend_scalar_overlay_is_hardlight_swapped() -> None:
    # Overlay(b, s) = HardLight(s, b)
    for b in (0.0, 0.25, 0.5, 0.75, 1.0):
        for s in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert PDFRenderer._blend_scalar(b, s, "Overlay") == \
                PDFRenderer._blend_scalar(s, b, "HardLight")


def test_blend_scalar_darken_lighten() -> None:
    assert PDFRenderer._blend_scalar(0.3, 0.7, "Darken") == 0.3
    assert PDFRenderer._blend_scalar(0.3, 0.7, "Lighten") == 0.7


def test_blend_scalar_difference_exclusion() -> None:
    assert abs(PDFRenderer._blend_scalar(0.7, 0.3, "Difference") - 0.4) < 1e-9
    # Exclusion(b, s) = b + s - 2bs → 0.5 + 0.5 - 2*0.25 = 0.5
    assert abs(PDFRenderer._blend_scalar(0.5, 0.5, "Exclusion") - 0.5) < 1e-9


def test_blend_scalar_color_dodge_burn() -> None:
    # ColorDodge (PDF 2.0 §11.3.5.1, aligned with upstream PDFBox 3.0.x
    # ``BlendMode.java`` in wave 1363):
    #   b == 0 → 0; b >= 1 - s → 1; else b / (1 - s).
    assert PDFRenderer._blend_scalar(0.0, 1.0, "ColorDodge") == 0.0
    assert PDFRenderer._blend_scalar(0.5, 0.0, "ColorDodge") == 0.5  # b / (1-0) = b
    # ColorBurn:
    #   b == 1 → 1; 1 - b >= s → 0; else 1 - (1 - b) / s.
    assert PDFRenderer._blend_scalar(1.0, 0.0, "ColorBurn") == 1.0
    assert PDFRenderer._blend_scalar(0.5, 1.0, "ColorBurn") == 0.5  # 1 - 0.5/1 = 0.5


def test_blend_scalar_hardlight() -> None:
    # s<=0.5 → 2bs ; s>0.5 → 1 - 2(1-b)(1-s)
    assert PDFRenderer._blend_scalar(0.5, 0.25, "HardLight") == 0.25  # 2 * 0.5 * 0.25
    assert PDFRenderer._blend_scalar(0.5, 0.75, "HardLight") == 0.75  # 1 - 2 * 0.5 * 0.25


def test_blend_scalar_softlight_at_extremes() -> None:
    # s=0.5 is the inflection — leaves backdrop unchanged.
    for b in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = PDFRenderer._blend_scalar(b, 0.5, "SoftLight")
        assert abs(v - b) < 1e-9


# ---------------------------------------------------------------------------
# end-to-end PIL blend on a 2x1 canvas (red backdrop, blue source)
# ---------------------------------------------------------------------------


def test_blend_normal_overlap_shows_source() -> None:
    """Normal mode = plain Porter-Duff over."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.NORMAL)
    assert _close(out.getpixel((0, 0)), (0, 0, 255))


def test_blend_multiply_red_blue_is_black() -> None:
    """Per-channel: r=255*0=0, g=0, b=0*255=0 → black."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.MULTIPLY)
    assert _close(out.getpixel((0, 0)), (0, 0, 0))


def test_blend_screen_red_blue_is_magenta() -> None:
    """Screen: r=255+0-0=255, g=0+0-0=0, b=0+255-0=255 → magenta."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.SCREEN)
    assert _close(out.getpixel((0, 0)), (255, 0, 255))


def test_blend_darken_red_blue() -> None:
    """Darken: per-channel min."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.DARKEN)
    assert _close(out.getpixel((0, 0)), (0, 0, 0))


def test_blend_lighten_red_blue_is_magenta() -> None:
    """Lighten: per-channel max → magenta."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.LIGHTEN)
    assert _close(out.getpixel((0, 0)), (255, 0, 255))


def test_blend_difference_red_blue_is_magenta() -> None:
    """Difference: |b-s| per channel → magenta."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.DIFFERENCE)
    assert _close(out.getpixel((0, 0)), (255, 0, 255))


def test_blend_exclusion_red_blue_is_magenta() -> None:
    """Exclusion at (1, 0) channels behaves like Difference."""
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.EXCLUSION)
    assert _close(out.getpixel((0, 0)), (255, 0, 255))


def test_blend_overlay_red_backdrop_preserves_red() -> None:
    """Overlay(b, s) = HardLight(s, b). For backdrop (1, 0, 0):
       r: backdrop=1>.5 → 1 - 2(1-1)(1-0) = 1
       g: backdrop=0<=.5 → 2*0*0 = 0
       b: backdrop=0<=.5 → 2*0*1 = 0
       → red preserved.
    """
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.OVERLAY)
    assert _close(out.getpixel((0, 0)), (255, 0, 0))


def test_blend_hardlight_blue_source_yields_blue() -> None:
    """HardLight per-channel:
       r: source=0<=.5 → 2*1*0=0
       g: source=0<=.5 → 0
       b: source=1>.5 → 1 - 2(1-0)(0) = 1
       → pure blue.
    """
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.HARD_LIGHT)
    assert _close(out.getpixel((0, 0)), (0, 0, 255))


def test_blend_color_dodge_red_blue() -> None:
    """ColorDodge (PDF 2.0 §11.3.5.1):
       r: b=1, s=0 → b != 0, b >= 1 - 0 → 1
       g: b=0, s=0 → 0 (dest == 0 short-circuit)
       b: b=0, s=1 → 0 (dest == 0 short-circuit)
       → red preserved.
    """
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.COLOR_DODGE)
    assert _close(out.getpixel((0, 0)), (255, 0, 0))


def test_blend_color_burn_red_blue_is_red() -> None:
    """ColorBurn (PDF 2.0 §11.3.5.1):
       r: b=1, s=0 → 1 (dest == 1 short-circuit)
       g: b=0, s=0 → 1 - 0 >= 0 → 0
       b: b=0, s=1 → 1 - 0 >= 1 → 0
       → red preserved (matches upstream PDFBox PDF 2.0 algorithm).
    """
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.COLOR_BURN)
    assert _close(out.getpixel((0, 0)), (255, 0, 0))


def test_blend_soft_light_red_backdrop_preserves_red() -> None:
    """SoftLight per-channel:
       r: source=0<=.5 → b - (1-0)*b*(1-b) = 1 - 0 = 1   (since b=1, (1-b)=0)
       g: source=0<=.5 → b - 1*0*1 = 0
       b: source=1>.5, b=0<=.25 → d = ((16*0-12)*0+4)*0 = 0; 0 + 1*(0-0) = 0
       → red preserved.
    """
    src = _solid((0, 0, 255, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.SOFT_LIGHT)
    assert _close(out.getpixel((0, 0)), (255, 0, 0))


# ---------------------------------------------------------------------------
# alpha + non-separable fallback
# ---------------------------------------------------------------------------


def test_blend_transparent_source_preserves_backdrop() -> None:
    """Per Porter-Duff: a transparent source pixel must leave the
    backdrop unchanged regardless of the chosen blend formula."""
    src = _solid((0, 0, 255, 0))  # fully transparent
    bg = _solid((255, 0, 0, 255))
    for mode in (
        BlendMode.MULTIPLY,
        BlendMode.SCREEN,
        BlendMode.OVERLAY,
        BlendMode.DARKEN,
        BlendMode.LIGHTEN,
        BlendMode.COLOR_DODGE,
        BlendMode.COLOR_BURN,
        BlendMode.HARD_LIGHT,
        BlendMode.SOFT_LIGHT,
        BlendMode.DIFFERENCE,
        BlendMode.EXCLUSION,
    ):
        out = PDFRenderer._blend(src, bg, mode)
        assert _close(out.getpixel((0, 0)), (255, 0, 0)), mode.name


def test_blend_hue_red_backdrop_green_source() -> None:
    """Hue: SetLum(SetSat(Cs, Sat(Cb)), Lum(Cb)).

    With Cb=red=(1,0,0) and Cs=green=(0,1,0):
       Sat(Cb)=1, Lum(Cb)=0.30, Lum(Cs)=0.59, Sat(Cs)=1.
       SetSat((0,1,0), 1) = (0,1,0)  (already saturated).
       SetLum((0,1,0), 0.30): d = 0.30 - 0.59 = -0.29 → (-0.29, 0.71, -0.29).
       ClipColor with lum=0.30 → (0, 0.5085, 0) ≈ (0, 130, 0).
    """
    src = _solid((0, 255, 0, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.HUE)
    assert _close(out.getpixel((0, 0)), (0, 130, 0), tol=2)


def test_blend_saturation_red_backdrop_green_source_preserves_red() -> None:
    """Saturation: SetLum(SetSat(Cb, Sat(Cs)), Lum(Cb)).

    With Cb=red and Cs=green: Sat(Cs)=1 leaves Cb's already-saturated
    profile intact, then SetLum to its own Lum(Cb)=0.30 is a no-op.
    Backdrop is preserved as pure red.
    """
    src = _solid((0, 255, 0, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.SATURATION)
    assert _close(out.getpixel((0, 0)), (255, 0, 0), tol=2)


def test_blend_color_red_backdrop_green_source() -> None:
    """Color: SetLum(Cs, Lum(Cb)).

    SetLum(green, 0.30) = (0, 0.5085, 0) after ClipColor — see Hue test.
    """
    src = _solid((0, 255, 0, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.COLOR)
    assert _close(out.getpixel((0, 0)), (0, 130, 0), tol=2)


def test_blend_luminosity_red_backdrop_green_source() -> None:
    """Luminosity: SetLum(Cb, Lum(Cs)).

    With Cb=red and Cs=green: SetLum(red, 0.59):
       d = 0.59 - 0.30 = 0.29 → (1.29, 0.29, 0.29).
       ClipColor with lum=0.59, cmax=1.29 > 1, denom=0.70:
         r = 0.59 + 0.70 * 0.41/0.70 = 1.0
         g = 0.59 - 0.30 * 0.41/0.70 ≈ 0.4143
         b = 0.4143
       → ≈ (255, 106, 106).
    """
    src = _solid((0, 255, 0, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.LUMINOSITY)
    assert _close(out.getpixel((0, 0)), (255, 106, 106), tol=2)


def test_blend_color_then_luminosity_round_trip_preserves_lum() -> None:
    """Color sets Lum to backdrop's; querying Lum on the result must
    equal Lum(Cb). Sanity check on the SetLum/ClipColor pair."""
    src = _solid((0, 255, 0, 255))
    bg = _solid((255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.COLOR)
    r, g, b = (c / 255.0 for c in out.getpixel((0, 0))[:3])
    backdrop_lum = PDFRenderer._hsl_lum(1.0, 0.0, 0.0)
    actual_lum = PDFRenderer._hsl_lum(r, g, b)
    assert abs(actual_lum - backdrop_lum) < 0.01


def _bm_int_blend(
    mode: str, cs: tuple[float, float, float], cb: tuple[float, float, float]
) -> tuple[int, int, int]:
    """Reference non-separable RGB result computed with upstream's integer
    8.16 fixed-point ``BlendMode`` helpers (``getSaturationRGB`` /
    ``getLuminosityRGB``), using the same source/dest argument order as
    ``BlendComposite.compose`` (src=top, dest=backdrop). Returns the
    0..255 rounded RGB triple."""
    result: list[float] = [0.0, 0.0, 0.0]
    if mode == "Hue":
        temp: list[float] = [0.0, 0.0, 0.0]
        BlendMode.get_saturation_rgb(list(cb), list(cs), temp)
        BlendMode.get_luminosity_rgb(list(cb), temp, result)
    elif mode == "Saturation":
        BlendMode.get_saturation_rgb(list(cs), list(cb), result)
    elif mode == "Color":
        BlendMode.get_luminosity_rgb(list(cb), list(cs), result)
    else:  # Luminosity
        BlendMode.get_luminosity_rgb(list(cs), list(cb), result)
    return tuple(int(round(c * 255.0)) for c in result)  # type: ignore[return-value]


def test_nonseparable_render_is_bit_identical_to_integer_blendmode() -> None:
    """The renderer's HSL blend path must produce the *same* bytes as
    upstream ``BlendMode.get_saturation_rgb`` / ``get_luminosity_rgb``
    (integer 8.16 fixed-point), not the older float ``SetLum`` / ``SetSat``
    form. Opaque source over opaque backdrop ⇒ the composite reduces to the
    raw blend result, so the rendered pixel must equal the integer-helper
    output exactly. Pins the wave-1507 fix that swapped the float HSL math
    for the integer form (the float Luminosity result was off by 1 on red).
    """
    cb = (0.9, 0.4, 0.1)  # backdrop
    cs = (0.2, 0.4, 0.8)  # source (top)
    # Quantise to the byte values the image pipeline actually carries.
    bg = _solid(tuple(round(c * 255) for c in cb) + (255,))  # type: ignore[arg-type]
    src = _solid(tuple(round(c * 255) for c in cs) + (255,))  # type: ignore[arg-type]
    bq = tuple(round(c * 255) / 255.0 for c in cb)
    sq = tuple(round(c * 255) / 255.0 for c in cs)
    modes = {
        "Hue": BlendMode.HUE,
        "Saturation": BlendMode.SATURATION,
        "Color": BlendMode.COLOR,
        "Luminosity": BlendMode.LUMINOSITY,
    }
    for name, mode in modes.items():
        out = PDFRenderer._blend(src, bg, mode)
        got = out.getpixel((0, 0))[:3]
        expected = _bm_int_blend(name, sq, bq)  # type: ignore[arg-type]
        assert got == expected, (
            f"{name}: renderer pixel {got} != integer BlendMode {expected}"
        )


def test_blend_resizes_mismatched_source() -> None:
    """``_blend`` resizes a smaller source up to the backdrop size before
    compositing so callers don't have to pre-align the buffers."""
    src = Image.new("RGBA", (1, 1), (0, 0, 255, 255))
    bg = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    out = PDFRenderer._blend(src, bg, BlendMode.MULTIPLY)
    # All four pixels become black (1*0, 0*0, 0*1) = (0, 0, 0).
    for x in range(4):
        for y in range(4):
            assert _close(out.getpixel((x, y)), (0, 0, 0))


def test_blend_accepts_rgb_inputs() -> None:
    """Inputs in modes other than RGBA are converted internally."""
    src = Image.new("RGB", (2, 1), (0, 0, 255))
    bg = Image.new("RGB", (2, 1), (255, 0, 0))
    out = PDFRenderer._blend(src, bg, BlendMode.MULTIPLY)
    assert _close(out.getpixel((0, 0)), (0, 0, 0))
    assert out.mode == "RGBA"
