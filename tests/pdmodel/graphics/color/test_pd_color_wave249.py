"""Wave 249 — :class:`PDColor` round-out: hand-written coverage for surface
gaps not yet exercised by the existing parity / round-out tests.

Targets:

* :meth:`PDColor.__init__` colored-pattern variant — upstream's
  ``PDColor(COSName patternName, PDColorSpace colorSpace)`` form (empty
  components, only the pattern name).
* :meth:`PDColor.to_rgb_int` — packed sRGB int (``0xRRGGBB``) mirroring
  upstream ``PDColor.toRGB() -> int`` (Java's
  ``Math.round(float * 255)`` semantics).
* :meth:`PDColor.__str__` — upstream-shaped
  ``PDColor{components=[...], patternName=..., colorSpace=...}``
  mirroring upstream ``toString()``. Java's ``Float.toString`` always
  emits a trailing ``.0`` for integral floats.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

# ---------- colored-pattern constructor (PDColor(COSName, PDColorSpace)) ----------


def test_constructor_colored_pattern_pattern_name_only() -> None:
    """Upstream: ``PDColor(COSName patternName, PDColorSpace colorSpace)``
    — empty components, pattern name set, color space stored verbatim.
    """
    name = COSName.get_pdf_name("P1")
    cs = PDPattern()
    color = PDColor(name, cs)
    assert color.get_components() == []
    assert color.get_pattern_name() is name
    assert color.get_color_space() is cs
    assert color.is_pattern() is True


def test_constructor_colored_pattern_disallows_third_positional() -> None:
    name = COSName.get_pdf_name("P1")
    with pytest.raises(TypeError, match="no third"):
        PDColor(name, PDPattern(), COSName.get_pdf_name("Other"))


def test_constructor_colored_pattern_disallows_pattern_keyword() -> None:
    name = COSName.get_pdf_name("P1")
    with pytest.raises(TypeError, match="no third"):
        PDColor(name, PDPattern(), pattern=COSName.get_pdf_name("Other"))


def test_constructor_colored_pattern_rejects_cosname_color_space() -> None:
    """``PDColor(COSName, COSName)`` is malformed — the second argument
    must be a color space, not another name.
    """
    name = COSName.get_pdf_name("P1")
    with pytest.raises(TypeError, match="must be a PDColorSpace"):
        PDColor(name, COSName.get_pdf_name("Other"))  # type: ignore[arg-type]


def test_constructor_colored_pattern_round_trip_through_cos_array() -> None:
    name = COSName.get_pdf_name("P1")
    cs = PDPattern()
    color = PDColor(name, cs)
    array = color.to_cos_array()
    # Empty-components + trailing pattern name → a 1-entry COSArray.
    assert array.size() == 1
    rebuilt = PDColor(array, cs)
    assert rebuilt.get_components() == []
    assert rebuilt.get_pattern_name() == name


# ---------- to_rgb_int (packed sRGB) ----------


def test_to_rgb_int_pure_red() -> None:
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.to_rgb_int() == 0xFF0000


def test_to_rgb_int_pure_green() -> None:
    color = PDColor([0.0, 1.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.to_rgb_int() == 0x00FF00


def test_to_rgb_int_pure_blue() -> None:
    color = PDColor([0.0, 0.0, 1.0], PDDeviceRGB.INSTANCE)
    assert color.to_rgb_int() == 0x0000FF


def test_to_rgb_int_black() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.to_rgb_int() == 0x000000


def test_to_rgb_int_white() -> None:
    color = PDColor([1.0, 1.0, 1.0], PDDeviceRGB.INSTANCE)
    assert color.to_rgb_int() == 0xFFFFFF


def test_to_rgb_int_mid_gray_uses_round_half_up() -> None:
    """Java ``Math.round(0.5f * 255)`` == ``Math.round(127.5)`` == 128
    (round half away from zero); Python's banker's ``round`` gives 128
    too, but the explicit ``+ 0.5`` floor reproduces Java exactly. The
    test pins the boundary case.
    """
    color = PDColor([0.5], PDDeviceGray.INSTANCE)
    rgb = color.to_rgb_int()
    # 0.5 → 128 across all three channels: 0x808080.
    assert rgb == 0x808080


def test_to_rgb_int_clamps_negative_components() -> None:
    """Components below 0.0 clamp to 0; matches upstream's
    pre-clamp via ``to_rgb``.
    """
    color = PDColor([-0.1, 0.5, 1.5], PDDeviceRGB.INSTANCE)
    rgb = color.to_rgb_int()
    # red == 0, green == 128, blue == 255
    assert (rgb >> 16) & 0xFF == 0
    assert (rgb >> 8) & 0xFF == 128
    assert rgb & 0xFF == 255


def test_to_rgb_int_cmyk_round_trip() -> None:
    """CMYK (0, 1, 1, 0) is pure red: ``(1-0)*(1-0) = 1`` for R, 0 for
    G/B → 0xFF0000.
    """
    color = PDColor([0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE)
    assert color.to_rgb_int() == 0xFF0000


def test_to_rgb_int_fits_in_24_bits() -> None:
    """The packed result must always be in [0, 0xFFFFFF]."""
    color = PDColor([0.7, 0.3, 0.9], PDDeviceRGB.INSTANCE)
    rgb = color.to_rgb_int()
    assert 0 <= rgb <= 0xFFFFFF


def test_to_rgb_int_low_byte_is_blue() -> None:
    """Bit-packing convention: ``r << 16 | g << 8 | b`` — low byte is
    blue. Pin a non-symmetric color so all three channels differ.
    """
    color = PDColor([0.0, 0.5, 1.0], PDDeviceRGB.INSTANCE)
    rgb = color.to_rgb_int()
    assert (rgb >> 16) & 0xFF == 0  # red
    assert (rgb >> 8) & 0xFF == 128  # green
    assert rgb & 0xFF == 255  # blue


# ---------- __str__ (upstream toString shape) ----------


def test_str_upstream_shape_components_only() -> None:
    color = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    text = str(color)
    assert text.startswith("PDColor{components=[0.5, 0.25, 0.75]")
    assert "patternName=None" in text
    assert "colorSpace=" in text


def test_str_includes_pattern_name() -> None:
    name = COSName.get_pdf_name("P1")
    color = PDColor([0.5], PDDeviceGray.INSTANCE, name)
    text = str(color)
    # Java's COSName.toString() renders "/P1"; pypdfbox COSName.__str__
    # returns just the name. Either is acceptable — what we pin is that
    # the pattern name's identity is reflected in the string.
    assert "patternName=" in text
    assert "P1" in text


def test_str_integral_components_render_with_trailing_zero() -> None:
    """Java ``Float.toString(1.0f) == "1.0"`` — never bare ``1``. Pin
    the .0 suffix on integral inputs so ``str(PDColor)`` diffs cleanly
    against Java logs.
    """
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    text = str(color)
    assert "components=[1.0, 0.0, 0.0]" in text


def test_str_empty_components() -> None:
    name = COSName.get_pdf_name("P1")
    cs = PDPattern()
    color = PDColor(name, cs)
    text = str(color)
    assert text.startswith("PDColor{components=[]")
    assert text.endswith("}")
    assert "patternName=" in text
    assert "P1" in text
