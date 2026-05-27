from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace

_WHITE_POINT: COSName = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT: COSName = COSName.get_pdf_name("BlackPoint")
_GAMMA: COSName = COSName.get_pdf_name("Gamma")


def _read_tristimulus(
    dictionary: COSDictionary,
    key: COSName,
    default: list[float],
) -> list[float]:
    entry = dictionary.get_dictionary_object(key)
    if isinstance(entry, COSArray):
        out = entry.to_float_array()
        if len(out) >= 3:
            return out[:3]
    return list(default)


def _xyz_to_srgb(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert CIE XYZ (D65) tristimulus values to clamped sRGB ``[0, 1]``.

    Uses the IEC 61966-2-1 sRGB matrix and gamma encoding. No chromatic
    adaptation; assumes the source XYZ is already on a D65 white point.
    """
    r_lin = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g_lin = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b_lin = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z

    def _srgb_encode(u: float) -> float:
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0
        if u <= 0.0031308:
            return 12.92 * u
        return float(1.055 * (u ** (1.0 / 2.4)) - 0.055)

    return (_srgb_encode(r_lin), _srgb_encode(g_lin), _srgb_encode(b_lin))


class PDCalGray(PDColorSpace):
    """A CalGray color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDCalGray``.

    Array form: ``[/CalGray <dictionary>]`` with dictionary keys
    ``/WhitePoint`` (required), ``/BlackPoint`` (default ``[0 0 0]``)
    and ``/Gamma`` (default ``1``).
    """

    NAME: str = "CalGray"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSDictionary())
        super().__init__(array)
        self._initial_color = PDColor([0.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- CIE dictionary access ----------

    def _dict(self) -> COSDictionary:
        assert self._array is not None
        entry = self._array.get_object(1)
        if not isinstance(entry, COSDictionary):
            raise TypeError(f"CalGray array index 1 is not a dictionary: {entry!r}")
        return entry

    def get_white_point(self) -> list[float]:
        return _read_tristimulus(self._dict(), _WHITE_POINT, [1.0, 1.0, 1.0])

    def set_white_point(self, white: list[float]) -> None:
        self._dict().set_item(_WHITE_POINT, COSArray.of_cos_floats(white))

    def has_white_point(self) -> bool:
        """Return ``True`` when ``/WhitePoint`` is present as a valid tristimulus."""
        return isinstance(self._dict().get_dictionary_object(_WHITE_POINT), COSArray)

    def get_black_point(self) -> list[float]:
        return _read_tristimulus(self._dict(), _BLACK_POINT, [0.0, 0.0, 0.0])

    def set_black_point(self, black: list[float]) -> None:
        self._dict().set_item(_BLACK_POINT, COSArray.of_cos_floats(black))

    def has_black_point(self) -> bool:
        """Return ``True`` when ``/BlackPoint`` is present as a valid tristimulus."""
        return isinstance(self._dict().get_dictionary_object(_BLACK_POINT), COSArray)

    def clear_black_point(self) -> None:
        """Remove ``/BlackPoint`` so reads fall back to ``[0, 0, 0]``."""
        self._dict().remove_item(_BLACK_POINT)

    def get_gamma(self) -> float:
        return float(self._dict().get_float(_GAMMA, 1.0))

    def set_gamma(self, gamma: float) -> None:
        self._dict().set_item(_GAMMA, COSFloat(gamma))

    def has_gamma(self) -> bool:
        """Return ``True`` when ``/Gamma`` is explicitly present."""
        return self._dict().contains_key(_GAMMA)

    def clear_gamma(self) -> None:
        """Remove ``/Gamma`` so reads fall back to ``1.0``."""
        self._dict().remove_item(_GAMMA)

    # ---------- predicates ----------

    def is_white_point(self) -> bool:
        """Return ``True`` iff ``/WhitePoint`` is the unit tristimulus
        ``(1.0, 1.0, 1.0)``. Mirrors upstream
        ``PDCIEDictionaryBasedColorSpace.isWhitePoint()`` (``protected`` in
        Java; promoted to public here so callers can detect the
        no-calibration shortcut path used by upstream's ``toRGB``).

        Float comparison uses exact equality on the three components —
        upstream uses ``Float.compare(...) == 0`` which is the same
        semantics for non-NaN values; pypdfbox stores Python ``float``
        (double precision) so an embedded literal ``1.0`` round-trips
        exactly.
        """
        wp = self.get_white_point()
        if len(wp) < 3:
            return False
        return wp[0] == 1.0 and wp[1] == 1.0 and wp[2] == 1.0

    # ---------- conversion ----------

    def to_rgb(self, values: list[float]) -> tuple[float, float, float]:
        """Convert a single-component CalGray sample to clamped sRGB.

        Mirrors upstream ``PDCalGray.toRGB`` (PDFBox 3.0.x): when
        ``isWhitePoint()`` is ``True`` (the ``/WhitePoint`` is the unit
        tristimulus ``(1, 1, 1)``) the calibrated CIE pipeline runs:

        ``A' = A ** Gamma``; then ``convXYZtoRGB(A', A', A')`` — the
        gamma-decoded value is fed to the CMM as all three of X, Y and Z
        (upstream does NOT multiply by the white point; with the unit
        white point that multiply would be a no-op anyway).

        For any other white point upstream skips CIE calibration and
        returns ``(A, A, A)`` verbatim — a documented PDFBOX-2553 hack
        that only behaves correctly for whitepoint D65; we follow it so
        CalGray ``toRGB`` is byte-parity with PDFBox.

        ``values`` must contain exactly one component in ``[0, 1]``.
        """
        if not values:
            raise ValueError("CalGray.to_rgb requires one component, got 0")
        a = float(values[0])
        if not self.is_white_point():
            # Upstream PDFBox shortcut (PDFBOX-2553): skip CIE
            # calibration, return the component verbatim as grey.
            return (a, a, a)
        if a < 0.0:
            a = 0.0
        elif a > 1.0:
            a = 1.0
        gamma = float(self.get_gamma())
        # 0 ** non-positive blows up; guard.
        a_g = (a ** gamma) if a > 0.0 else 0.0
        # Upstream feeds the gamma-decoded value to the CMM as X = Y = Z;
        # the white point is NOT applied (it is the unit tristimulus here).
        return _xyz_to_srgb(a_g, a_g, a_g)


__all__ = ["PDCalGray"]
