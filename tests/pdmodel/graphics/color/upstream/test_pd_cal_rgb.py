"""Upstream-derived tests for ``PDCalRGB``.

There is no dedicated ``PDCalRGBTest.java`` in upstream PDFBox; these
tests assert the public behavior expressed directly by
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDCalRGB.java``.

Each test ties to a specific Java method or constructor.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB

# ---------- constructors ----------


def test_default_constructor_produces_calrgb_array() -> None:
    """``new PDCalRGB()`` (Java line 41-44) wraps a fresh array headed by
    ``/CalRGB`` plus an empty dictionary."""
    cs = PDCalRGB()
    array = cs._array
    assert array is not None
    assert array.size() == 2
    assert array.get_object(0) == COSName.get_pdf_name("CalRGB")
    assert isinstance(array.get_object(1), COSDictionary)


def test_array_constructor_wraps_provided_array() -> None:
    """``new PDCalRGB(COSArray rgb)`` (Java line 49-52) reuses the
    caller's array verbatim."""
    inner = COSDictionary()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    arr.add(inner)
    cs = PDCalRGB(arr)
    assert cs._array is arr
    assert cs._dict() is inner


# ---------- abstract surface ----------


def test_get_name_returns_calrgb() -> None:
    """``getName()`` (Java line 55-58) returns the literal string
    ``"CalRGB"``."""
    assert PDCalRGB().get_name() == "CalRGB"


def test_get_number_of_components_is_three() -> None:
    """``getNumberOfComponents()`` (Java line 61-64) is always 3."""
    assert PDCalRGB().get_number_of_components() == 3


def test_get_default_decode_ignores_bpc() -> None:
    """``getDefaultDecode(int)`` (Java line 67-70) returns
    ``[0, 1, 0, 1, 0, 1]`` regardless of ``bitsPerComponent``."""
    cs = PDCalRGB()
    for bpc in (1, 8, 16):
        assert cs.get_default_decode(bpc) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_get_initial_color_is_zero_triple() -> None:
    """``getInitialColor()`` (Java line 73-76) yields the cached
    ``PDColor`` whose components are ``[0, 0, 0]``."""
    cs = PDCalRGB()
    init = cs.get_initial_color()
    assert init.get_components() == [0.0, 0.0, 0.0]
    # Cached: same instance on repeated calls (Java holds it as a final
    # field).
    assert cs.get_initial_color() is init


# ---------- gamma ----------


def test_get_gamma_default_is_unit_triple() -> None:
    """``getGamma()`` (Java line 119-131) returns ``[1, 1, 1]`` when
    ``/Gamma`` is absent, and writes that default back into the
    dictionary (Java sets it eagerly)."""
    cs = PDCalRGB()
    assert cs.get_gamma() == [1.0, 1.0, 1.0]


def test_set_gamma_round_trip() -> None:
    """``setGamma(PDGamma)`` (Java line 154-162) replaces the
    ``/Gamma`` entry."""
    cs = PDCalRGB()
    cs.set_gamma([2.2, 2.2, 2.2])
    assert cs.get_gamma() == pytest.approx([2.2, 2.2, 2.2])


# ---------- matrix ----------


def test_get_matrix_default_is_identity() -> None:
    """``getMatrix()`` (Java line 138-148) returns the 3x3 identity
    when ``/Matrix`` is absent."""
    cs = PDCalRGB()
    assert cs.get_matrix() == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


def test_set_matrix_round_trip() -> None:
    """``setMatrix(Matrix)`` (Java line 168-187) writes nine floats.
    Passing ``None`` clears the entry."""
    cs = PDCalRGB()
    m = [
        0.4124564,
        0.2126729,
        0.0193339,
        0.3575761,
        0.7151522,
        0.1191920,
        0.1804375,
        0.0721750,
        0.9503041,
    ]
    cs.set_matrix(m)
    assert cs.get_matrix() == pytest.approx(m)
    cs.set_matrix(None)
    # After clearing, default identity is reported again.
    assert cs.get_matrix() == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


# ---------- toRGB ----------


def test_to_rgb_with_unit_white_point_unit_gamma_identity_matrix_is_identity() -> None:
    """``toRGB(float[])`` (Java line 79-110): with ``/WhitePoint
    [1 1 1]``, ``/Gamma [1 1 1]``, ``/Matrix`` identity, the X/Y/Z
    intermediate equals the input — meaning conversion to sRGB is the
    standard XYZ→sRGB transform of those components."""
    cs = PDCalRGB()
    cs.set_white_point([1.0, 1.0, 1.0])
    out = cs.to_rgb([0.0, 0.0, 0.0])
    assert out == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_to_rgb_skips_calibration_when_white_point_not_unit() -> None:
    """Java fallback branch (line 105-108): when ``isWhitePoint()`` is
    false the calibration is skipped and the input components are
    returned directly as RGB."""
    cs = PDCalRGB()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.to_rgb([0.25, 0.5, 0.75]) == pytest.approx((0.25, 0.5, 0.75))


def test_to_rgb_rejects_short_input() -> None:
    """Java ``toRGB`` indexes ``value[0..2]``; we surface a
    ``ValueError`` for fewer than three components."""
    with pytest.raises(ValueError):
        PDCalRGB().to_rgb([0.5, 0.5])
