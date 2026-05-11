"""Gamma array (R, G, B floats).

Mirrors ``org.apache.pdfbox.pdmodel.graphics.color.PDGamma``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSFloat, COSNumber


class PDGamma:
    """Gamma values used for CalRGB color spaces."""

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            self._values = COSArray()
            self._values.add(COSFloat.ZERO)
            self._values.add(COSFloat.ZERO)
            self._values.add(COSFloat.ZERO)
        else:
            self._values = array

    def get_cos_object(self) -> COSBase:
        """Return the COS object (the underlying array)."""
        return self._values

    def get_cos_array(self) -> COSArray:
        """Return the underlying ``COSArray``."""
        return self._values

    def _read(self, idx: int) -> float:
        entry = self._values.get(idx)
        if isinstance(entry, COSNumber):
            return entry.float_value()
        return 0.0

    def _write(self, idx: int, value: float) -> None:
        self._values.set(idx, COSFloat(float(value)))

    def get_r(self) -> float:
        """Return the R value."""
        return self._read(0)

    def set_r(self, r: float) -> None:
        """Set the R value."""
        self._write(0, r)

    def get_g(self) -> float:
        """Return the G value."""
        return self._read(1)

    def set_g(self, g: float) -> None:
        """Set the G value."""
        self._write(1, g)

    def get_b(self) -> float:
        """Return the B value."""
        return self._read(2)

    def set_b(self, b: float) -> None:
        """Set the B value."""
        self._write(2, b)


__all__ = ["PDGamma"]
