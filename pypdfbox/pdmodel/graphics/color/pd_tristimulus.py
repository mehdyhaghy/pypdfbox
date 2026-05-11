"""A 3-float tristimulus (XYZ) value.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.color.PDTristimulus``.
"""

from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.cos import COSArray, COSBase, COSFloat, COSNumber


class PDTristimulus:
    """A tristimulus, or collection of three floating point parameters used
    for color operations.
    """

    def __init__(self, source: COSArray | Sequence[float] | None = None) -> None:
        if source is None:
            self._values = COSArray()
            self._values.add(COSFloat.ZERO)
            self._values.add(COSFloat.ZERO)
            self._values.add(COSFloat.ZERO)
        elif isinstance(source, COSArray):
            self._values = source
        else:
            self._values = COSArray()
            for i, v in enumerate(source):
                if i >= 3:
                    break
                self._values.add(COSFloat(float(v)))

    def get_cos_object(self) -> COSBase:
        """Return the underlying ``COSArray``."""
        return self._values

    def _read(self, idx: int) -> float:
        entry = self._values.get(idx)
        if isinstance(entry, COSNumber):
            return entry.float_value()
        return 0.0

    def _write(self, idx: int, value: float) -> None:
        self._values.set(idx, COSFloat(float(value)))

    def get_x(self) -> float:
        """Return the X value."""
        return self._read(0)

    def set_x(self, x: float) -> None:
        """Set the X value."""
        self._write(0, x)

    def get_y(self) -> float:
        """Return the Y value."""
        return self._read(1)

    def set_y(self, y: float) -> None:
        """Set the Y value."""
        self._write(1, y)

    def get_z(self) -> float:
        """Return the Z value."""
        return self._read(2)

    def set_z(self, z: float) -> None:
        """Set the Z value."""
        self._write(2, z)


__all__ = ["PDTristimulus"]
