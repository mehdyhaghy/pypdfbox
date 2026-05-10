from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_cal_gray import _xyz_to_srgb
from .pd_color import PDColor
from .pd_color_space import PDColorSpace

_WHITE_POINT: COSName = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT: COSName = COSName.get_pdf_name("BlackPoint")
_RANGE: COSName = COSName.get_pdf_name("Range")


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


class PDLab(PDColorSpace):
    """A Lab color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDLab``.

    Array form: ``[/Lab <dictionary>]`` with dictionary keys
    ``/WhitePoint`` (required), ``/BlackPoint`` (default ``[0 0 0]``),
    and ``/Range`` (default ``[-100 100 -100 100]``) holding the a*/b*
    component bounds.
    """

    NAME: str = "Lab"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSDictionary())
        super().__init__(array)
        # Initial color per upstream: L=0, a=max(0, aMin), b=max(0, bMin)
        rng = self.get_range()
        a_min = rng[0] if len(rng) >= 1 else -100.0
        b_min = rng[2] if len(rng) >= 3 else -100.0
        self._initial_color = PDColor(
            [0.0, max(0.0, a_min), max(0.0, b_min)],
            self,
        )

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
            raise TypeError(f"Lab array index 1 is not a dictionary: {entry!r}")
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

    def get_range(self) -> list[float]:
        out = _read_float_array(
            self._dict(), _RANGE, [-100.0, 100.0, -100.0, 100.0]
        )
        return out[:4] if len(out) >= 4 else out

    def set_range(self, rng: list[float]) -> None:
        self._dict().set_item(_RANGE, COSArray.of_cos_floats(rng))

    def has_range(self) -> bool:
        """Return ``True`` when ``/Range`` is present as an array."""
        return isinstance(self._dict().get_dictionary_object(_RANGE), COSArray)

    def clear_range(self) -> None:
        """Remove ``/Range`` and restore default a*/b* bounds."""
        self._dict().remove_item(_RANGE)
        self._initial_color = PDColor([0.0, 0.0, 0.0], self)

    # Component-level range accessors mirror upstream
    # ``PDLab.getARange()`` / ``getBRange()`` / ``setARange(PDRange)`` /
    # ``setBRange(PDRange)``. Pypdfbox returns ``(min, max)`` tuples
    # directly because there is no ``PDRange`` class in the lite surface
    # — same shape as :meth:`PDICCBased.get_range_for_component`.

    def get_a_range(self) -> tuple[float, float]:
        """Return the ``a*`` component range as ``(min, max)``. Defaults
        to ``(-100, 100)`` when ``/Range`` is absent."""
        rng = self.get_range()
        a_min = float(rng[0]) if len(rng) >= 1 else -100.0
        a_max = float(rng[1]) if len(rng) >= 2 else 100.0
        return a_min, a_max

    def get_b_range(self) -> tuple[float, float]:
        """Return the ``b*`` component range as ``(min, max)``. Defaults
        to ``(-100, 100)`` when ``/Range`` is absent."""
        rng = self.get_range()
        b_min = float(rng[2]) if len(rng) >= 3 else -100.0
        b_max = float(rng[3]) if len(rng) >= 4 else 100.0
        return b_min, b_max

    def set_a_range(self, low_high: tuple[float, float] | None) -> None:
        """Set the ``a*`` component range. ``None`` resets to the
        ``(-100, 100)`` default. Mirrors upstream
        ``PDLab.setARange(PDRange)`` (null resets to defaults).
        """
        self._set_component_range(low_high, 0)

    def set_b_range(self, low_high: tuple[float, float] | None) -> None:
        """Set the ``b*`` component range. ``None`` resets to the
        ``(-100, 100)`` default. Mirrors upstream
        ``PDLab.setBRange(PDRange)`` (null resets to defaults).
        """
        self._set_component_range(low_high, 2)

    def _set_component_range(
        self,
        low_high: tuple[float, float] | None,
        index: int,
    ) -> None:
        d = self._dict()
        existing = d.get_dictionary_object(_RANGE)
        range_array = existing if isinstance(existing, COSArray) else COSArray()
        defaults = (-100.0, 100.0, -100.0, 100.0)
        while range_array.size() < len(defaults):
            range_array.add(COSFloat(defaults[range_array.size()]))
        if low_high is None:
            range_array.set(index, COSFloat(-100.0))
            range_array.set(index + 1, COSFloat(100.0))
        else:
            lo, hi = low_high
            range_array.set(index, COSFloat(float(lo)))
            range_array.set(index + 1, COSFloat(float(hi)))
        d.set_item(_RANGE, range_array)
        # Upstream invalidates the cached initial color when the range
        # changes; keep parity by recomputing on next access.
        rng = self.get_range()
        a_min = rng[0] if len(rng) >= 1 else -100.0
        b_min = rng[2] if len(rng) >= 3 else -100.0
        self._initial_color = PDColor(
            [0.0, max(0.0, a_min), max(0.0, b_min)],
            self,
        )

    # ---------- predicates ----------

    def is_white_point(self) -> bool:
        """Return ``True`` iff ``/WhitePoint`` is the unit tristimulus
        ``(1.0, 1.0, 1.0)``. Mirrors upstream
        ``PDCIEDictionaryBasedColorSpace.isWhitePoint()`` (``protected`` in
        Java; promoted to public here so callers can probe the
        no-calibration shortcut without poking at internal state).
        """
        wp = self.get_white_point()
        if len(wp) < 3:
            return False
        return wp[0] == 1.0 and wp[1] == 1.0 and wp[2] == 1.0

    # ---------- decode ----------

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Default Lab decode per PDF 32000-1 §8.9.5.1 Table 90:
        ``[0, 100, a_min, a_max, b_min, b_max]``. ``L*`` always spans
        ``[0, 100]``; the ``a*``/``b*`` bounds come from ``/Range``
        (default ``[-100, 100, -100, 100]``).
        """
        rng = self.get_range()
        if len(rng) >= 4:
            return [0.0, 100.0, float(rng[0]), float(rng[1]), float(rng[2]), float(rng[3])]
        return [0.0, 100.0, -100.0, 100.0, -100.0, 100.0]

    # ---------- private upstream parity helpers ----------

    @staticmethod
    def get_default_range_array() -> COSArray:
        """Return a fresh ``/Range`` array filled with the default
        ``[-100, 100, -100, 100]``. Mirrors the private upstream
        ``PDLab.getDefaultRangeArray()`` (PDLab.java line 184); kept
        package-private in Java but exposed as a static helper here so
        callers that want the raw COS array (e.g. when initialising
        sparse Lab dictionaries) don't have to re-create the literals.
        """
        minus100 = COSFloat(-100.0)
        plus100 = COSFloat(100.0)
        out = COSArray()
        out.add(minus100)
        out.add(plus100)
        out.add(minus100)
        out.add(plus100)
        return out

    @staticmethod
    def inverse(x: float) -> float:
        """Inverse of the CIE ``f`` companding function used by Lab to
        XYZ. Mirrors private upstream ``PDLab.inverse(float)`` (PDLab.java
        line 140). Outside the test surface this is only used by
        :meth:`to_rgb`; exposed here so direct upstream-style callers can
        replicate the per-channel transform if they want to.

        Threshold and constants come straight from upstream: ``x > 6/29``
        cubes; otherwise affine ``(108/841) * (x - 4/29)``.
        """
        if x > 6.0 / 29.0:
            return x * x * x
        return (108.0 / 841.0) * (x - (4.0 / 29.0))

    def set_component_range_array(
        self, low_high: tuple[float, float] | None, index: int
    ) -> None:
        """Underlying setter for ``setARange`` / ``setBRange``. Mirrors
        the private upstream ``PDLab.setComponentRangeArray(PDRange, int)``
        (PDLab.java line 246). ``index`` is 0 for the ``a*`` slot and
        2 for the ``b*`` slot — same convention upstream uses.

        Public here for parity-tracking parity; production callers
        should still prefer :meth:`set_a_range` / :meth:`set_b_range`.
        """
        self._set_component_range(low_high, index)

    # ---------- conversion ----------

    def to_rgb(self, value: list[float]) -> tuple[float, float, float]:
        """Convert a single Lab triple ``[L*, a*, b*]`` to clamped sRGB.

        Mirrors upstream ``PDLab.toRGB(float[])`` (PDLab.java line 122).
        Uses the dictionary's ``/WhitePoint`` (defaulting to ``[1, 1, 1]``)
        as the XYZ reference instead of the hardcoded D65 used by
        :meth:`PDColor._lab_to_rgb`, matching upstream's
        ``wpX / wpY / wpZ`` cache exactly. Black-point compensation is
        skipped — upstream notes the same TODO at line 129.
        """
        if len(value) < 3:
            raise ValueError(
                f"Lab.to_rgb requires three components, got {len(value)}"
            )
        l_star = float(value[0])
        a_star = float(value[1])
        b_star = float(value[2])

        # L*
        lstar = (l_star + 16.0) * (1.0 / 116.0)

        wp = self.get_white_point()
        wp_x = float(wp[0]) if len(wp) >= 1 else 1.0
        wp_y = float(wp[1]) if len(wp) >= 2 else 1.0
        wp_z = float(wp[2]) if len(wp) >= 3 else 1.0

        x = wp_x * self.inverse(lstar + a_star * (1.0 / 500.0))
        y = wp_y * self.inverse(lstar)
        z = wp_z * self.inverse(lstar - b_star * (1.0 / 200.0))

        # Upstream's convXYZtoRGB clamps negatives to 0.
        if x < 0.0:
            x = 0.0
        if y < 0.0:
            y = 0.0
        if z < 0.0:
            z = 0.0

        return _xyz_to_srgb(x, y, z)

    # ---------- rendering ----------

    def to_rgb_image(self, raster: bytes, width: int, height: int) -> Any:
        """Convert a Lab-encoded raster of 8-bit samples to a Pillow sRGB
        image. Mirrors upstream ``PDLab.toRGBImage(WritableRaster)``
        (PDLab.java line 65); the per-pixel scaling matches the upstream
        loop:

        - ``abc[0]``: 0..255 → 0..1 → 0..100 (L*)
        - ``abc[1]``: 0..255 → 0..1 → ``minA + t*deltaA`` (a*)
        - ``abc[2]``: 0..255 → 0..1 → ``minB + t*deltaB`` (b*)

        Each transformed triple is forwarded to :meth:`to_rgb` and
        encoded as 8-bit sRGB. ``raster`` is interpreted as a tightly
        packed ``width * height * 3`` byte buffer.
        """
        from PIL import Image

        a_min, a_max = self.get_a_range()
        b_min, b_max = self.get_b_range()
        delta_a = a_max - a_min
        delta_b = b_max - b_min

        n = 3
        expected = int(width) * int(height) * n
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))

        out = bytearray(int(width) * int(height) * 3)
        for pixel_index in range(int(width) * int(height)):
            offset = pixel_index * n
            l_byte = data[offset]
            a_byte = data[offset + 1]
            b_byte = data[offset + 2]

            l_star = (l_byte / 255.0) * 100.0
            a_star = a_min + (a_byte / 255.0) * delta_a
            b_star = b_min + (b_byte / 255.0) * delta_b

            r, g, b = self.to_rgb([l_star, a_star, b_star])
            base = pixel_index * 3
            out[base] = max(0, min(255, int(round(r * 255.0))))
            out[base + 1] = max(0, min(255, int(round(g * 255.0))))
            out[base + 2] = max(0, min(255, int(round(b * 255.0))))
        return Image.frombytes(
            "RGB", (int(width), int(height)), bytes(out)
        )

    def to_raw_image(self, raster: bytes, width: int, height: int) -> Any:
        """Return ``None`` to mirror upstream ``PDLab.toRawImage`` —
        Lab has no native Pillow analogue (Pillow's ``LAB`` mode uses a
        different range convention, and upstream notes "Not handled at
        the moment" at PDLab.java line 116).
        """
        return None


__all__ = ["PDLab"]
