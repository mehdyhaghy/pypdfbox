"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``pdfbox/src/test/java/org/apache/pdfbox/rendering/HintingPpemTest.java``.

Tests :meth:`PageDrawer.hinting_ppem`, the derivation of the
grid-fitting ppem from the glyph-space-to-device transform. The input
transform maps 1000-units-per-em glyph coordinates to device pixels.

Java's ``AffineTransform`` is replaced by a small double-precision
helper below; transforms are passed to ``hinting_ppem`` as PDF-style
``(a, b, c, d, e, f)`` tuples, i.e. AffineTransform's
``(m00, m10, m01, m11, m02, m12)``.
"""

import math

from pypdfbox.rendering.page_drawer import PageDrawer


class _AffineTransform:
    """Minimal ``java.awt.geom.AffineTransform`` (double precision)."""

    def __init__(
        self,
        m00: float = 1.0,
        m10: float = 0.0,
        m01: float = 0.0,
        m11: float = 1.0,
        m02: float = 0.0,
        m12: float = 0.0,
    ) -> None:
        self.m = [m00, m10, m01, m11, m02, m12]

    @classmethod
    def get_scale_instance(cls, sx: float, sy: float) -> _AffineTransform:
        return cls(sx, 0.0, 0.0, sy, 0.0, 0.0)

    @classmethod
    def get_translate_instance(cls, tx: float, ty: float) -> _AffineTransform:
        return cls(1.0, 0.0, 0.0, 1.0, tx, ty)

    def copy(self) -> _AffineTransform:
        return _AffineTransform(*self.m)

    def concatenate(self, other: _AffineTransform) -> None:
        a00, a10, a01, a11, a02, a12 = self.m
        b00, b10, b01, b11, b02, b12 = other.m
        self.m = [
            a00 * b00 + a01 * b10,
            a10 * b00 + a11 * b10,
            a00 * b01 + a01 * b11,
            a10 * b01 + a11 * b11,
            a00 * b02 + a01 * b12 + a02,
            a10 * b02 + a11 * b12 + a12,
        ]

    def scale(self, sx: float, sy: float) -> None:
        self.concatenate(_AffineTransform.get_scale_instance(sx, sy))

    def translate(self, tx: float, ty: float) -> None:
        self.concatenate(_AffineTransform.get_translate_instance(tx, ty))

    def rotate(self, theta: float) -> None:
        c, s = math.cos(theta), math.sin(theta)
        self.concatenate(_AffineTransform(c, s, -s, c, 0.0, 0.0))

    def as_tuple(self) -> tuple[float, float, float, float, float, float]:
        return tuple(self.m)  # type: ignore[return-value]


def _ppem(at: _AffineTransform) -> int:
    return PageDrawer.hinting_ppem(at.as_tuple())


def _scale(s: float) -> _AffineTransform:
    return _AffineTransform.get_scale_instance(s, s)


def test_upright_scale_gives_ppem() -> None:
    # 16px em: one normalized unit is 16/1000 device pixels
    assert _ppem(_scale(0.016)) == 16
    assert _ppem(_scale(0.011)) == 11


def test_y_flip_is_still_hinted() -> None:
    # typical PDF-to-device flip has a negative y scale but is still axis-aligned
    at = _AffineTransform(0.024, 0, 0, -0.024, 100, 200)
    assert _ppem(at) == 24


def test_anisotropic_uses_vertical_ppem() -> None:
    # ppem is taken from the vertical scale
    at = _AffineTransform(0.020, 0, 0, -0.016, 0, 0)
    assert _ppem(at) == 16


def test_rotation_is_still_hinted() -> None:
    # rotated text is grid-fit in upright glyph space at the transform's scale;
    # the rotation is applied afterwards. ppem is the rotation-invariant scale.
    at = _scale(0.016)
    at.rotate(math.radians(30))
    assert _ppem(at) == 16

    vertical = _AffineTransform(0, 0.016, -0.016, 0, 0, 0)  # 90-degree rotation
    assert _ppem(vertical) == 16


def test_shear_takes_vertical_scale() -> None:
    # a sheared (fake-italic) transform is hinted at its vertical-basis magnitude
    at = _AffineTransform(0.016, 0, 0.006, 0.016, 0, 0)
    assert _ppem(at) == math.floor(1000 * math.hypot(0.006, 0.016) + 0.5)


def test_fractional_scale_rounds_to_nearest_ppem() -> None:
    """Fractional device sizes round half up, never truncate."""
    assert _ppem(_scale(0.01864)) == 19  # 18.64
    assert _ppem(_scale(0.01408)) == 14  # 14.08
    assert _ppem(_scale(0.0125)) == 13  # 12.5 -> 13
    assert _ppem(_scale(0.01249)) == 12  # 12.49 -> 12
    assert _ppem(_scale(0.0005)) == 1  # 0.5 -> 1
    assert _ppem(_scale(0.00049)) == 0  # 0.49 -> 0


def _device_glyph_transform(dpi: float, size_pt: float, degrees: float) -> _AffineTransform:
    """Device xform (dpi scale and y flip) composed with a text rendering
    matrix at ``size_pt`` rotated by ``degrees``, composed with the 1/1000
    font matrix."""
    xform = _AffineTransform()
    xform.scale(dpi / 72, dpi / 72)
    xform.translate(0, 842)
    xform.scale(1, -1)
    trm = _AffineTransform.get_translate_instance(72, 700)
    trm.rotate(math.radians(degrees))
    trm.scale(size_pt, size_pt)
    at = xform.copy()
    at.concatenate(trm)
    at.scale(0.001, 0.001)
    return at


def test_composed_device_transform_gives_device_ppem() -> None:
    """7pt at 300dpi is 29.17px -> 29; 10.5pt at 96dpi is exactly 14."""
    assert _ppem(_device_glyph_transform(300, 7, 0)) == 29
    assert _ppem(_device_glyph_transform(96, 10.5, 0)) == 14
    assert _ppem(_device_glyph_transform(72, 7, 0)) == 7
    assert _ppem(_device_glyph_transform(96, 9, 0)) == 12


def test_rotation_under_device_transform() -> None:
    for degrees in (0, 30, 45, 90, 180, 270, -90):
        assert _ppem(_device_glyph_transform(300, 7, degrees)) == 29, f"rotation {degrees}"
        assert _ppem(_device_glyph_transform(96, 10.5, degrees)) == 14, f"rotation {degrees}"


def test_anisotropic_under_device_transform() -> None:
    """Horizontal text scaling (Tz) changes only x: the ppem is unaffected."""
    narrow = _device_glyph_transform(96, 12, 0)
    narrow.scale(0.5, 1)  # Tz 50
    assert _ppem(narrow) == 16
    wide = _device_glyph_transform(96, 12, 0)
    wide.scale(2, 1)
    assert _ppem(wide) == 16
    tall = _device_glyph_transform(96, 12, 0)
    tall.scale(1, 1.5)
    assert _ppem(tall) == 24


def test_degenerate_transform_is_not_hinted() -> None:
    assert _ppem(_scale(0)) == 0
    # sub-half-pixel em rounds to 0 ppem -> no hinting
    assert _ppem(_scale(0.0004)) == 0
