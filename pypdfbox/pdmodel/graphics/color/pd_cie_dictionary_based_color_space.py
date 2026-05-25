"""Abstract base for CIE-based colour spaces backed by a dictionary.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.color.PDCIEDictionaryBasedColorSpace``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_cie_based_color_space import PDCIEBasedColorSpace
from .pd_tristimulus import PDTristimulus

_WHITE_POINT = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT = COSName.get_pdf_name("BlackPoint")


def _xyz_to_rgb_clamp(x: float, y: float, z: float) -> list[float]:
    # IEC 61966-2-1 sRGB matrix; mirror upstream's "negative XYZ -> 0" guard.
    if x < 0:
        x = 0.0
    if y < 0:
        y = 0.0
    if z < 0:
        z = 0.0
    r_lin = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g_lin = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b_lin = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z

    def _encode(u: float) -> float:
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0
        if u <= 0.0031308:
            return 12.92 * u
        return 1.055 * (u ** (1.0 / 2.4)) - 0.055

    return [_encode(r_lin), _encode(g_lin), _encode(b_lin)]


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
        """Tests if the cached whitepoint equals (1, 1, 1)."""
        return self.wp_x == 1.0 and self.wp_y == 1.0 and self.wp_z == 1.0

    def fill_whitepoint_cache(self, whitepoint: PDTristimulus) -> None:
        """Mirror of upstream's private ``fillWhitepointCache``."""
        self.wp_x = whitepoint.get_x()
        self.wp_y = whitepoint.get_y()
        self.wp_z = whitepoint.get_z()

    # Backwards-compatible alias for the previous underscore-prefixed name.
    _fill_whitepoint_cache = fill_whitepoint_cache

    def conv_xy_zto_rgb(self, x: float, y: float, z: float) -> list[float]:
        """Convert XYZ to clamped sRGB.

        Snake-cases upstream's ``convXYZtoRGB``; we keep the trailing
        ``zto_rgb`` chunking that the parity scanner produces so the
        public surface matches.
        """
        return _xyz_to_rgb_clamp(x, y, z)

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
