from __future__ import annotations

import math
from typing import Union

from pypdfbox.cos import COSArray, COSFloat, COSInteger

_Number = Union[int, float]


class PDLineDashPattern:
    """
    Line dash pattern for stroking paths (PDF 32000-1:2008 §8.4.3.6).
    Mirrors ``org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern``.

    Instances are conceptually immutable.

    Two ``__init__`` shapes match upstream:

    * ``PDLineDashPattern()`` — empty dash array, phase 0.
    * ``PDLineDashPattern(array, phase)`` — ``array`` is a ``COSArray`` of
      dash/gap lengths, ``phase`` is a number.

    A third pythonic shape covers the PDF on-disk form:

    * ``PDLineDashPattern.from_cos_array(cos)`` — ``cos`` is a 2-entry
      ``COSArray`` ``[dash_array_inner, phase]`` as serialised in a PDF.
    """

    def __init__(
        self,
        array: COSArray | None = None,
        phase: _Number = 0,
    ) -> None:
        if array is None:
            self._array: list[float] = []
            self._phase: _Number = 0
            return

        if not isinstance(array, COSArray):
            raise TypeError(
                f"PDLineDashPattern array must be COSArray, got {type(array).__name__}"
            )

        self._array = list(array.to_float_array())

        # PDF 2.0 §8.4.3.6: "If the dash phase is negative, it shall be
        # incremented by twice the sum of all lengths in the dash array
        # until it is positive."
        if phase < 0:
            sum2 = sum(self._array) * 2
            if sum2 > 0:
                if -phase < sum2:
                    phase += sum2
                else:
                    phase += (math.floor(-phase / sum2) + 1) * sum2
            else:
                phase = 0
        self._phase = phase

    @classmethod
    def from_cos_array(cls, cos: COSArray) -> PDLineDashPattern:
        """Construct from the PDF on-disk form ``[dash_array, phase]``."""
        if not isinstance(cos, COSArray):
            raise TypeError(
                f"from_cos_array expects COSArray, got {type(cos).__name__}"
            )
        if cos.size() != 2:
            raise ValueError(
                f"PDLineDashPattern COSArray form must have 2 entries, got {cos.size()}"
            )
        inner = cos.get_object(0)
        if not isinstance(inner, COSArray):
            raise TypeError(
                "PDLineDashPattern COSArray form: first entry must be COSArray"
            )
        phase_obj = cos.get_object(1)
        if isinstance(phase_obj, (COSInteger, COSFloat)):
            phase: _Number = phase_obj.value
        else:
            phase = 0
        return cls(inner, phase)

    # ---------- COSObjectable surface ----------

    def get_cos_object(self) -> COSArray:
        """Return the canonical PDF form ``[dash_array_inner, phase]``."""
        return self.get_cos_array()

    def get_cos_array(self) -> COSArray:
        """Return the canonical PDF form ``[dash_array_inner, phase]``."""
        out = COSArray()
        inner = COSArray()
        inner.set_float_array(self._array)
        out.add(inner)
        if isinstance(self._phase, int) and not isinstance(self._phase, bool):
            out.add(COSInteger.get(self._phase))
        else:
            out.add(COSFloat(float(self._phase)))
        return out

    def to_cos_array(self) -> COSArray:
        """Alias for :meth:`get_cos_array`."""
        return self.get_cos_array()

    # ---------- accessors ----------

    def get_dash_array(self) -> list[float]:
        """Defensive copy of the dash/gap lengths."""
        return list(self._array)

    def set_dash_array(self, values: list[float]) -> None:
        """Replace the dash/gap lengths with ``values`` (defensive copy)."""
        if values is None:
            self._array = []
            return
        self._array = [float(v) for v in values]

    def get_phase(self) -> _Number:
        return self._phase

    def set_phase(self, value: _Number) -> None:
        """Replace the dash phase with ``value``."""
        self._phase = value

    def is_solid(self) -> bool:
        """True when the dash array is empty (solid line)."""
        return len(self._array) == 0

    def is_zero_pattern(self) -> bool:
        """True when every entry in the dash array is zero (treat as solid)."""
        if len(self._array) == 0:
            return False
        return all(v == 0 for v in self._array)

    # ---------- python protocols ----------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PDLineDashPattern):
            return NotImplemented
        return self._array == other._array and self._phase == other._phase

    def __hash__(self) -> int:
        return hash((tuple(self._array), self._phase))

    def __repr__(self) -> str:
        return f"PDLineDashPattern(array={self._array!r}, phase={self._phase!r})"


__all__ = ["PDLineDashPattern"]
