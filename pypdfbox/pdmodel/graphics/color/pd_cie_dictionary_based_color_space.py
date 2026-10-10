"""Abstract base for CIE-based colour spaces backed by a dictionary.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.color.PDCIEDictionaryBasedColorSpace``.
"""

import functools

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_cie_based_color_space import PDCIEBasedColorSpace
from .pd_tristimulus import PDTristimulus

_WHITE_POINT = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT = COSName.get_pdf_name("BlackPoint")


# IEC 61966-2-1 sRGB matrix (linear sRGB from D65-relative XYZ).
_XYZ_TO_LINEAR_SRGB: tuple[tuple[float, float, float], ...] = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)

# PDFBOX-6260: Bradford cone-response matrix used for the chromatic
# adaptation of the declared whitepoint (same constants as upstream).
_BRADFORD: tuple[tuple[float, float, float], ...] = (
    (0.8951000, 0.2664000, -0.1614000),
    (-0.7502000, 1.7135000, 0.0367000),
    (0.0389000, -0.0685000, 1.0296000),
)

# Upstream's profile connection space white (java.awt CS_CIEXYZ is D50).
PCS_WHITE_D50: tuple[float, float, float] = (0.9642, 1.0, 0.8249)


def _multiply_mv(
    m: tuple[tuple[float, float, float], ...] | list[list[float]],
    v: tuple[float, float, float] | list[float],
) -> list[float]:
    return [
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ]


def _multiply_mm(
    a: tuple[tuple[float, float, float], ...] | list[list[float]],
    b: tuple[tuple[float, float, float], ...] | list[list[float]],
) -> list[list[float]]:
    return [
        [
            a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]
            for j in range(3)
        ]
        for i in range(3)
    ]


def _invert(
    m: tuple[tuple[float, float, float], ...] | list[list[float]],
) -> list[list[float]]:
    det = (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
    return [
        [
            (m[1][1] * m[2][2] - m[1][2] * m[2][1]) / det,
            -(m[0][1] * m[2][2] - m[0][2] * m[2][1]) / det,
            (m[0][1] * m[1][2] - m[0][2] * m[1][1]) / det,
        ],
        [
            -(m[1][0] * m[2][2] - m[1][2] * m[2][0]) / det,
            (m[0][0] * m[2][2] - m[0][2] * m[2][0]) / det,
            -(m[0][0] * m[1][2] - m[0][2] * m[1][0]) / det,
        ],
        [
            (m[1][0] * m[2][1] - m[1][1] * m[2][0]) / det,
            -(m[0][0] * m[2][1] - m[0][1] * m[2][0]) / det,
            (m[0][0] * m[1][1] - m[0][1] * m[1][0]) / det,
        ],
    ]


_BRADFORD_INV: list[list[float]] = _invert(_BRADFORD)

# The whitepoint that the sRGB matrix above maps to RGB (1, 1, 1), i.e. D65
# as encoded by that matrix (about 0.95047 1.0 1.08883). Upstream adapts to
# the D50 PCS because java.awt's CS_CIEXYZ expects D50-relative input and
# the JDK sRGB profile then adapts D50 to D65 internally. pypdfbox converts
# with a D65-relative matrix, so it adapts straight to this D65 white: both
# are Bradford adaptations, and a Bradford adaptation wp -> D50 -> D65 is
# the same as wp -> D65.
PCS_WHITE_D65: tuple[float, float, float] = tuple(  # type: ignore[assignment]
    _multiply_mv(_invert(_XYZ_TO_LINEAR_SRGB), (1.0, 1.0, 1.0))
)


@functools.lru_cache(maxsize=128)
def adaptation_matrix(
    src_x: float,
    src_y: float,
    src_z: float,
    dst_white: tuple[float, float, float] = PCS_WHITE_D65,
) -> tuple[tuple[float, float, float], ...]:
    """Bradford chromatic adaptation matrix from the source whitepoint to
    ``dst_white``. Mirrors upstream private
    ``PDCIEDictionaryBasedColorSpace.adaptationMatrix(double[], double[])``
    (PDFBOX-6260). Cached per whitepoint, as upstream caches it per color
    space instance.

    A degenerate source whitepoint (a zero cone response, which a valid
    whitepoint never has) yields the identity matrix instead of a division
    by zero.
    """
    src_cone = _multiply_mv(_BRADFORD, (src_x, src_y, src_z))
    dst_cone = _multiply_mv(_BRADFORD, dst_white)
    if src_cone[0] == 0.0 or src_cone[1] == 0.0 or src_cone[2] == 0.0:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    scale = [
        [dst_cone[0] / src_cone[0], 0.0, 0.0],
        [0.0, dst_cone[1] / src_cone[1], 0.0],
        [0.0, 0.0, dst_cone[2] / src_cone[2]],
    ]
    m = _multiply_mm(_multiply_mm(_BRADFORD_INV, scale), _BRADFORD)
    return tuple(tuple(row) for row in m)  # type: ignore[return-value]


def _srgb_encode(u: float) -> float:
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    if u <= 0.0031308:
        return 12.92 * u
    return float(1.055 * (u ** (1.0 / 2.4)) - 0.055)


def xyz_to_srgb_adapted(
    whitepoint: tuple[float, float, float] | list[float],
    x: float,
    y: float,
    z: float,
) -> tuple[float, float, float]:
    """Convert XYZ relative to ``whitepoint`` to clamped sRGB ``[0, 1]``.

    Mirrors upstream ``PDCIEDictionaryBasedColorSpace.convXYZtoRGB`` after
    PDFBOX-6260: the XYZ is first chromatically adapted (Bradford) from the
    declared whitepoint to the white of the conversion, then negative values
    are clamped to 0 ("XYZ must be non-negative anyway"), then converted.
    """
    m = adaptation_matrix(
        float(whitepoint[0]), float(whitepoint[1]), float(whitepoint[2])
    )
    ax = m[0][0] * x + m[0][1] * y + m[0][2] * z
    ay = m[1][0] * x + m[1][1] * y + m[1][2] * z
    az = m[2][0] * x + m[2][1] * y + m[2][2] * z
    ax = max(ax, 0.0)
    ay = max(ay, 0.0)
    az = max(az, 0.0)
    r_lin, g_lin, b_lin = _multiply_mv(_XYZ_TO_LINEAR_SRGB, (ax, ay, az))
    return (_srgb_encode(r_lin), _srgb_encode(g_lin), _srgb_encode(b_lin))


def _xyz_to_rgb_clamp(x: float, y: float, z: float) -> list[float]:
    # Unadapted conversion (whitepoint already D65): kept for callers that
    # feed D65-relative XYZ directly.
    return list(xyz_to_srgb_adapted(PCS_WHITE_D65, x, y, z))


class PDCIEDictionaryBasedColorSpace(PDCIEBasedColorSpace):
    """CIE-based color space whose parameters live in a dictionary."""

    def __init__(self, source: COSArray | COSName | None = None) -> None:
        super().__init__()
        if source is None or isinstance(source, COSName):
            self._array = COSArray()
            self.dictionary = COSDictionary()
            if isinstance(source, COSName):
                self._array.add(source)
            self._array.add(self.dictionary)
        else:
            self._array = source
            obj = source.get_object(1)
            self.dictionary = obj if isinstance(obj, COSDictionary) else COSDictionary()
        # cached whitepoint
        wp = self.get_whitepoint()
        self.wp_x = wp.get_x()
        self.wp_y = wp.get_y()
        self.wp_z = wp.get_z()

    def is_white_point(self) -> bool:
        """Tests if the cached whitepoint equals (1, 1, 1).

        Deprecated upstream (PDFBOX-6260, "will be removed in 4.0"): the
        conversion no longer special-cases this whitepoint.
        """
        return self.wp_x == 1.0 and self.wp_y == 1.0 and self.wp_z == 1.0

    def fill_whitepoint_cache(self, whitepoint: PDTristimulus) -> None:
        """Mirror of upstream's private ``fillWhitepointCache``."""
        self.wp_x = whitepoint.get_x()
        self.wp_y = whitepoint.get_y()
        self.wp_z = whitepoint.get_z()

    # Backwards-compatible alias for the previous underscore-prefixed name.
    _fill_whitepoint_cache = fill_whitepoint_cache

    def conv_xy_zto_rgb(self, x: float, y: float, z: float) -> list[float]:
        """Convert XYZ relative to this space's whitepoint to clamped sRGB.

        Snake-cases upstream's ``convXYZtoRGB``; we keep the trailing
        ``zto_rgb`` chunking that the parity scanner produces so the
        public surface matches. Since PDFBOX-6260 the XYZ is chromatically
        adapted (Bradford) from the cached whitepoint first.
        """
        return list(
            xyz_to_srgb_adapted((self.wp_x, self.wp_y, self.wp_z), x, y, z)
        )

    # Friendlier alias retained for existing callers.
    conv_xyz_to_rgb = conv_xy_zto_rgb

    def get_whitepoint(self) -> PDTristimulus:
        """Return the WhitePoint tristimulus, defaulting to (1, 1, 1)."""
        wp: COSArray | None = None
        if hasattr(self.dictionary, "get_cos_array"):  # pragma: no branch
            # Defensive: self.dictionary is a COSDictionary which always
            # carries get_cos_array; the False arm has no live caller.
            wp = self.dictionary.get_cos_array(_WHITE_POINT)
        if wp is None:
            entry = self.dictionary.get_dictionary_object(_WHITE_POINT)
            wp = entry if isinstance(entry, COSArray) else None
        if wp is None:
            wp = COSArray()
            wp.add(COSFloat.ONE)
            wp.add(COSFloat.ONE)
            wp.add(COSFloat.ONE)
        return PDTristimulus(wp)

    def get_black_point(self) -> PDTristimulus:
        """Return the BlackPoint tristimulus, defaulting to (0, 0, 0)."""
        bp = None
        entry = self.dictionary.get_dictionary_object(_BLACK_POINT)
        if isinstance(entry, COSArray):
            bp = entry
        if bp is None:
            bp = COSArray()
            bp.add(COSFloat.ZERO)
            bp.add(COSFloat.ZERO)
            bp.add(COSFloat.ZERO)
        return PDTristimulus(bp)

    def set_white_point(self, whitepoint: PDTristimulus) -> None:
        """Set the WhitePoint. Raises ``ValueError`` if ``None``."""
        if whitepoint is None:
            raise ValueError("Whitepoint may not be null")
        self.dictionary.set_item(_WHITE_POINT, whitepoint.get_cos_object())
        self._fill_whitepoint_cache(whitepoint)

    def set_black_point(self, blackpoint: PDTristimulus) -> None:
        """Set the BlackPoint."""
        if blackpoint is None:
            return
        self.dictionary.set_item(_BLACK_POINT, blackpoint.get_cos_object())


__all__ = ["PDCIEDictionaryBasedColorSpace"]
