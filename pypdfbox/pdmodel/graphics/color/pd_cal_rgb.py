from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_cal_gray import _xyz_to_srgb
from .pd_color import PDColor
from .pd_color_space import PDColorSpace

_WHITE_POINT: COSName = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT: COSName = COSName.get_pdf_name("BlackPoint")
_GAMMA: COSName = COSName.get_pdf_name("Gamma")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")


def _read_float_array(
    dictionary: COSDictionary,
    key: COSName,
    default: list[float],
) -> list[float]:
    entry = dictionary.get_dictionary_object(key)
    if isinstance(entry, COSArray):
        out = entry.to_float_array()
        if out:
            return out
    return list(default)


class PDCalRGB(PDColorSpace):
    """A CalRGB color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB``.

    Array form: ``[/CalRGB <dictionary>]`` with dictionary keys
    ``/WhitePoint`` (required), ``/BlackPoint`` (default ``[0 0 0]``),
    ``/Gamma`` (default ``[1 1 1]``) and ``/Matrix`` (default identity
    ``[1 0 0 0 1 0 0 0 1]``).
    """

    NAME: str = "CalRGB"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSDictionary())
        super().__init__(array)
        self._initial_color = PDColor([0.0, 0.0, 0.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 3

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- CIE dictionary access ----------

    def _dict(self) -> COSDictionary:
        assert self._array is not None
        entry = self._array.get_object(1)
        if not isinstance(entry, COSDictionary):
            raise TypeError(f"CalRGB array index 1 is not a dictionary: {entry!r}")
        return entry

    def get_white_point(self) -> list[float]:
        out = _read_float_array(self._dict(), _WHITE_POINT, [1.0, 1.0, 1.0])
        return out[:3] if len(out) >= 3 else out

    def set_white_point(self, white: list[float]) -> None:
        self._dict().set_item(_WHITE_POINT, COSArray.of_cos_floats(white))

    def has_white_point(self) -> bool:
        """Return ``True`` when ``/WhitePoint`` is present as an array."""
        return isinstance(self._dict().get_dictionary_object(_WHITE_POINT), COSArray)

    def get_black_point(self) -> list[float]:
        out = _read_float_array(self._dict(), _BLACK_POINT, [0.0, 0.0, 0.0])
        return out[:3] if len(out) >= 3 else out

    def set_black_point(self, black: list[float]) -> None:
        self._dict().set_item(_BLACK_POINT, COSArray.of_cos_floats(black))

    def has_black_point(self) -> bool:
        """Return ``True`` when ``/BlackPoint`` is present as an array."""
        return isinstance(self._dict().get_dictionary_object(_BLACK_POINT), COSArray)

    def clear_black_point(self) -> None:
        """Remove ``/BlackPoint`` so reads fall back to ``[0, 0, 0]``."""
        self._dict().remove_item(_BLACK_POINT)

    def get_gamma(self) -> list[float]:
        return _read_float_array(self._dict(), _GAMMA, [1.0, 1.0, 1.0])

    def set_gamma(self, gamma: list[float]) -> None:
        self._dict().set_item(_GAMMA, COSArray.of_cos_floats(gamma))

    def has_gamma(self) -> bool:
        """Return ``True`` when ``/Gamma`` is present as an array."""
        return isinstance(self._dict().get_dictionary_object(_GAMMA), COSArray)

    def clear_gamma(self) -> None:
        """Remove ``/Gamma`` so reads fall back to ``[1, 1, 1]``."""
        self._dict().remove_item(_GAMMA)

    def get_matrix(self) -> list[float] | None:
        entry = self._dict().get_dictionary_object(_MATRIX)
        if isinstance(entry, COSArray):
            return entry.to_float_array()
        return None

    def set_matrix(self, matrix: list[float] | None) -> None:
        d = self._dict()
        if matrix is None:
            d.remove_item(_MATRIX)
        else:
            d.set_item(_MATRIX, COSArray.of_cos_floats(matrix))

    def has_matrix(self) -> bool:
        """Return ``True`` when ``/Matrix`` is present as an array."""
        return isinstance(self._dict().get_dictionary_object(_MATRIX), COSArray)

    def clear_matrix(self) -> None:
        """Remove ``/Matrix`` so conversion uses the identity matrix."""
        self.set_matrix(None)

    # ---------- predicates ----------

    def is_white_point(self) -> bool:
        """Return ``True`` iff ``/WhitePoint`` is the unit tristimulus
        ``(1.0, 1.0, 1.0)``. Mirrors upstream
        ``PDCIEDictionaryBasedColorSpace.isWhitePoint()`` (``protected`` in
        Java; promoted to public here so callers can detect the
        no-calibration shortcut path used by upstream's ``toRGB``).
        """
        wp = self.get_white_point()
        if len(wp) < 3:
            return False
        return wp[0] == 1.0 and wp[1] == 1.0 and wp[2] == 1.0

    # ---------- conversion ----------

    def to_rgb(self, values: list[float]) -> tuple[float, float, float]:
        """Convert a 3-component CalRGB sample to clamped sRGB.

        Per PDF 32000-1 §8.6.5.3:

        ``A' = A ** GammaR``, ``B' = B ** GammaG``, ``C' = C ** GammaB``
        ``[X Y Z]^T = M * [A' B' C']^T`` where ``M`` is the column-major
        ``/Matrix`` (per spec: stored as 9 numbers ``[X_a Y_a Z_a X_b
        Y_b Z_b X_c Y_c Z_c]`` — three column vectors).

        Then XYZ → sRGB (IEC 61966-2-1).

        ``values`` must contain exactly three components in ``[0, 1]``.
        """
        if len(values) < 3:
            raise ValueError(
                f"CalRGB.to_rgb requires three components, got {len(values)}"
            )
        a = float(values[0])
        b = float(values[1])
        c = float(values[2])
        # Clamp
        a = 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)
        b = 0.0 if b < 0.0 else (1.0 if b > 1.0 else b)
        c = 0.0 if c < 0.0 else (1.0 if c > 1.0 else c)
        gammas = self.get_gamma()
        g_r = float(gammas[0]) if len(gammas) >= 1 else 1.0
        g_g = float(gammas[1]) if len(gammas) >= 2 else 1.0
        g_b = float(gammas[2]) if len(gammas) >= 3 else 1.0
        a_p = (a ** g_r) if a > 0.0 else 0.0
        b_p = (b ** g_g) if b > 0.0 else 0.0
        c_p = (c ** g_b) if c > 0.0 else 0.0

        m = self.get_matrix()
        if m is None or len(m) < 9:
            # Identity: X = A', Y = B', Z = C'
            x, y, z = a_p, b_p, c_p
        else:
            # Spec layout: [X_a Y_a Z_a  X_b Y_b Z_b  X_c Y_c Z_c]
            # X = X_a*A' + X_b*B' + X_c*C'  (etc)
            x_a, y_a, z_a = float(m[0]), float(m[1]), float(m[2])
            x_b, y_b, z_b = float(m[3]), float(m[4]), float(m[5])
            x_c, y_c, z_c = float(m[6]), float(m[7]), float(m[8])
            x = x_a * a_p + x_b * b_p + x_c * c_p
            y = y_a * a_p + y_b * b_p + y_c * c_p
            z = z_a * a_p + z_b * b_p + z_c * c_p
        return _xyz_to_srgb(x, y, z)


__all__ = ["PDCalRGB"]
