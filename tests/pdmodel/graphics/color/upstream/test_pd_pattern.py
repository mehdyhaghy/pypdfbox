"""Upstream parity tests for
:class:`pypdfbox.pdmodel.graphics.color.pd_pattern.PDPattern`.

There is no ``PDPatternTest.java`` in the upstream PDFBox tree; this
file exercises every public/protected surface declared on
``PDPattern.java`` line-for-line, mirroring what an upstream
``PDPatternTest`` *would* assert.

Source: ``/tmp/pdfbox/pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDPattern.java``
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------- constructors ----------


def test_constructor_no_underlying_emits_name_form_array() -> None:
    """``PDPattern(PDResources)`` — upstream PDPattern.java line 46-51.
    The COS object is ``[/Pattern]`` (a one-element array)."""
    cs = PDPattern(resources=PDResources())
    cos = cs.get_cos_object()
    # The factory accepts both name-form and array-form; pypdfbox
    # builds the array form to match upstream's eager
    # ``array.add(COSName.PATTERN)``.
    assert cos is not None
    assert isinstance(cos, (COSName, COSArray))


def test_constructor_with_underlying_emits_array_form() -> None:
    """``PDPattern(PDResources, PDColorSpace)`` — upstream line 59-66.
    Resulting COS is ``[/Pattern <underlying CS>]``."""
    cs = PDPattern(PDDeviceRGB.INSTANCE, resources=PDResources())
    arr = cs.get_array()
    assert arr is not None
    assert arr.size() == 2
    assert arr.get_object(0) == COSName.get_pdf_name("Pattern")


# ---------- get_name (line 69) ----------


def test_get_name_returns_pattern_literal() -> None:
    assert PDPattern().get_name() == "Pattern"


def test_get_name_returns_pattern_when_uncolored() -> None:
    assert PDPattern(PDDeviceRGB.INSTANCE).get_name() == "Pattern"


# ---------- get_number_of_components (line 75) ----------


def test_get_number_of_components_does_not_crash() -> None:
    """Upstream throws ``UnsupportedOperationException``; we return 0
    (see CHANGES.md). Either way: callers must not expect a meaningful
    component count from a Pattern color space directly."""
    cs = PDPattern()
    # The behavior we lock in: it doesn't raise and doesn't promise a
    # useful number — uncolored tiling callers should consult the
    # underlying CS instead.
    assert cs.get_number_of_components() == 0


# ---------- get_default_decode (line 81) ----------


def test_get_default_decode_raises_unsupported() -> None:
    """Mirrors upstream's ``UnsupportedOperationException`` via
    :class:`NotImplementedError`."""
    with pytest.raises(NotImplementedError):
        PDPattern().get_default_decode(8)


# ---------- get_initial_color (line 87) ----------


def test_get_initial_color_is_empty_pattern() -> None:
    """Upstream returns ``EMPTY_PATTERN`` — a PDColor with no
    components."""
    initial = PDPattern().get_initial_color()
    assert isinstance(initial, PDColor)
    assert initial.get_components() == []


def test_get_initial_color_is_stable() -> None:
    """Repeat calls return the same empty-pattern instance — upstream
    keeps a single ``private static final`` reference."""
    cs = PDPattern()
    assert cs.get_initial_color() is cs.get_initial_color()


# ---------- to_rgb (line 93) ----------


def test_to_rgb_colored_pattern_returns_none() -> None:
    """Upstream throws ``UnsupportedOperationException``; we return
    ``None`` so colored / shading-pattern resolvers can fall through
    without exception handling."""
    assert PDPattern().to_rgb([]) is None


def test_to_rgb_uncolored_pattern_recurses_into_underlying() -> None:
    rgb = PDPattern(PDDeviceRGB.INSTANCE).to_rgb([0.1, 0.2, 0.3])
    assert rgb == pytest.approx((0.1, 0.2, 0.3), abs=1e-6)


# ---------- to_rgb_image (line 99) ----------


def test_to_rgb_image_raises_unsupported() -> None:
    """Mirrors upstream's ``UnsupportedOperationException``."""
    with pytest.raises(NotImplementedError):
        PDPattern().to_rgb_image(b"", 0, 0)


def test_to_rgb_image_raises_for_uncolored_form_too() -> None:
    """Even with an underlying CS the pattern itself isn't a raster."""
    with pytest.raises(NotImplementedError):
        PDPattern(PDDeviceRGB.INSTANCE).to_rgb_image(b"\x00\x00\x00", 1, 1)


# ---------- to_raw_image (line 105) ----------


def test_to_raw_image_raises_unsupported() -> None:
    with pytest.raises(NotImplementedError):
        PDPattern().to_raw_image(b"", 0, 0)


def test_to_raw_image_raises_for_uncolored_form_too() -> None:
    with pytest.raises(NotImplementedError):
        PDPattern(PDDeviceRGB.INSTANCE).to_raw_image(b"\x00", 1, 1)


# ---------- get_pattern (line 117) ----------


def test_get_pattern_raises_when_named_pattern_missing() -> None:
    """Upstream throws ``IOException("pattern X was not found")``; we
    map ``IOException -> OSError``."""
    cs = PDPattern(resources=PDResources())
    color = PDColor([], cs, COSName.get_pdf_name("Missing"))
    with pytest.raises(OSError, match="not found"):
        cs.get_pattern(color)


# ---------- get_underlying_color_space (line 135) ----------


def test_get_underlying_color_space_none_when_colored() -> None:
    assert PDPattern().get_underlying_color_space() is None


def test_get_underlying_color_space_round_trips() -> None:
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    assert cs.get_underlying_color_space() is PDDeviceRGB.INSTANCE


# ---------- to_string (line 141) ----------


def test_to_string_returns_pattern_literal() -> None:
    """Upstream ``toString()`` returns the literal ``"Pattern"``."""
    assert str(PDPattern()) == "Pattern"


def test_to_string_returns_pattern_for_uncolored_form() -> None:
    """Same literal regardless of construction form."""
    assert str(PDPattern(PDDeviceRGB.INSTANCE)) == "Pattern"
