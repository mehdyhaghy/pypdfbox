from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger


class PDLineInfo:
    """Typed wrapper around a 4-element ``[x1, y1, x2, y2]`` line array —
    the ``/L`` entry of a ``/Subtype /Line`` annotation
    (PDF 32000-1:2008 §12.5.6.7).
    """

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray(
                [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(0.0)]
            )
        # Pad short arrays defensively so accessors do not raise.
        while array.size() < 4:
            array.add(COSFloat(0.0))
        self._array: COSArray = array

    def get_cos_array(self) -> COSArray:
        return self._array

    @staticmethod
    def _to_float(item: object) -> float:
        if isinstance(item, (COSFloat, COSInteger)):
            return float(item.value)
        return 0.0

    def get_start(self) -> tuple[float, float]:
        return self._to_float(self._array.get(0)), self._to_float(self._array.get(1))

    def get_end(self) -> tuple[float, float]:
        return self._to_float(self._array.get(2)), self._to_float(self._array.get(3))

    def set_start(self, x: float, y: float) -> None:
        self._array.set(0, COSFloat(float(x)))
        self._array.set(1, COSFloat(float(y)))

    def set_end(self, x: float, y: float) -> None:
        self._array.set(2, COSFloat(float(x)))
        self._array.set(3, COSFloat(float(y)))


__all__ = ["PDLineInfo"]
