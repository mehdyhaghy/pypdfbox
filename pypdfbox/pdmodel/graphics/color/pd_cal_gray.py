from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_cie_dictionary_based_color_space import (
    PCS_WHITE_D65,
    xyz_to_srgb_adapted,
)
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
    return xyz_to_srgb_adapted(PCS_WHITE_D65, x, y, z)


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

        Deprecated upstream (PDFBOX-6260, "will be removed in 4.0"):
        :meth:`to_rgb` no longer special-cases this whitepoint.

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

        Mirrors upstream ``PDCalGray.toRGB`` on the 3.0 branch (PDFBOX-6260,
        unreleased 3.0.9): ``A' = A ** Gamma``, then
        ``X, Y, Z = WhitePoint * A'`` (the whitepoint scaled by the
        gamma-corrected value), then ``convXYZtoRGB``, which chromatically
        adapts the declared whitepoint (Bradford) before the conversion.
        A neutral gray therefore only depends on the gamma, not on the
        whitepoint. The former PDFBOX-2971 shortcut (calibrate only for
        whitepoint ``(1, 1, 1)``, return ``(A, A, A)`` otherwise, ignoring
        the gamma) is gone.

        ``values`` must contain exactly one component in ``[0, 1]``
        (out-of-range input is clamped so that a negative base can't reach
        ``pow``).
        """
        if not values:
            raise ValueError("CalGray.to_rgb requires one component, got 0")
        a = float(values[0])
        if a < 0.0:
            a = 0.0
        elif a > 1.0:
            a = 1.0
        gamma = float(self.get_gamma())
        # 0 ** non-positive blows up; guard.
        a_g = (a ** gamma) if a > 0.0 else 0.0
        wp = self.get_white_point()
        wp_x = float(wp[0]) if len(wp) >= 1 else 1.0
        wp_y = float(wp[1]) if len(wp) >= 2 else 1.0
        wp_z = float(wp[2]) if len(wp) >= 3 else 1.0
        return xyz_to_srgb_adapted(
            (wp_x, wp_y, wp_z), wp_x * a_g, wp_y * a_g, wp_z * a_g
        )


__all__ = ["PDCalGray"]
