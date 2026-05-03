from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSFloat, COSNumber


class PDRange:
    """
    A numeric range ``a(min) <= a* <= a(max)``. Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDRange``.

    The wrapped ``COSArray`` may carry several ranges back-to-back, e.g. an
    ``[L_min L_max a_min a_max b_min b_max]`` list for a CIE Lab gamut. The
    ``starting_index`` argument selects which 2-element pair the wrapper
    addresses — a starting index of ``i`` reads positions ``2*i`` and
    ``2*i+1``.
    """

    __slots__ = ("_array", "_starting_index")

    def __init__(
        self,
        array: COSArray | None = None,
        index: int = 0,
    ) -> None:
        """Construct a PDRange.

        ``PDRange()`` allocates a fresh ``[0.0 1.0]`` array (matches the
        upstream no-arg constructor). ``PDRange(array)`` wraps an existing
        array with starting index ``0``. ``PDRange(array, index)`` selects
        the ``index``-th 2-element pair within ``array``.
        """
        if array is None:
            self._array = COSArray()
            self._array.add(COSFloat(0.0))
            self._array.add(COSFloat(1.0))
            self._starting_index = 0
        else:
            if not isinstance(array, COSArray):
                raise TypeError(
                    f"PDRange expected COSArray; got {type(array).__name__}"
                )
            self._array = array
            self._starting_index = int(index)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSArray:
        """Return the wrapped ``COSArray``. Mirrors upstream
        ``getCOSObject()``."""
        return self._array

    def get_cos_array(self) -> COSArray:
        """Alias of :meth:`get_cos_object` — mirrors upstream
        ``getCOSArray()``."""
        return self._array

    # ---------- starting index ----------

    def get_starting_index(self) -> int:
        """Return the 2-element pair offset this wrapper addresses.

        pypdfbox extension — upstream stores ``startingIndex`` privately and
        offers no accessor. Surfaced here so callers iterating multiple
        ranges over the same backing array can introspect / build new
        wrappers with offsets relative to a known reference.
        """
        return self._starting_index

    def set_starting_index(self, index: int) -> None:
        """Replace the 2-element pair offset.

        pypdfbox extension — upstream's ``startingIndex`` is final-after-
        construction (Java has no setter). Surfaced here as a mutator to
        let callers re-target a wrapper at a different pair within the
        same backing array, e.g. when sliding through a multi-range
        Lab/CalRGB/CalGray gamut without re-allocating the wrapper.
        """
        self._starting_index = int(index)

    # ---------- min ----------

    def get_min(self) -> float:
        """The lower bound (entry ``2 * starting_index``)."""
        entry = self._array.get_object(self._starting_index * 2)
        if not isinstance(entry, COSNumber):
            raise TypeError(
                f"PDRange.get_min: expected COSNumber at index "
                f"{self._starting_index * 2}, got "
                f"{type(entry).__name__}"
            )
        return entry.float_value()

    def set_min(self, minimum: float) -> None:
        """Replace the lower bound."""
        self._array.set(self._starting_index * 2, COSFloat(float(minimum)))

    # ---------- max ----------

    def get_max(self) -> float:
        """The upper bound (entry ``2 * starting_index + 1``)."""
        entry = self._array.get_object(self._starting_index * 2 + 1)
        if not isinstance(entry, COSNumber):
            raise TypeError(
                f"PDRange.get_max: expected COSNumber at index "
                f"{self._starting_index * 2 + 1}, got "
                f"{type(entry).__name__}"
            )
        return entry.float_value()

    def set_max(self, maximum: float) -> None:
        """Replace the upper bound."""
        self._array.set(self._starting_index * 2 + 1, COSFloat(float(maximum)))

    # ---------- predicates / convenience ----------

    def width(self) -> float:
        """Return ``max - min``.

        pypdfbox extension — upstream callers compute the gamut width by
        hand. Surfacing the helper avoids the recurring two-line idiom
        and reads naturally next to ``contains`` / ``clamp``.
        """
        return self.get_max() - self.get_min()

    def contains(self, value: float) -> bool:
        """Return ``True`` when ``value`` lies in ``[min, max]`` (inclusive
        on both ends).

        pypdfbox extension — the natural predicate complementing the raw
        accessors. Useful for callers validating tinting/lookup inputs
        before pushing them through a colour space evaluation.
        """
        v = float(value)
        return self.get_min() <= v <= self.get_max()

    def clamp(self, value: float) -> float:
        """Clamp ``value`` to the range.

        pypdfbox extension — values below :meth:`get_min` are pulled up to
        the minimum, values above :meth:`get_max` are pulled down to the
        maximum, and values in-range are returned unchanged. Mirrors
        upstream ``Math.max(min, Math.min(max, value))`` clamping idiom
        used in colour-space input normalisation.
        """
        v = float(value)
        lo = self.get_min()
        hi = self.get_max()
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    def is_normalized(self) -> bool:
        """Return ``True`` when the range is exactly ``[0.0, 1.0]``.

        pypdfbox extension — a frequent fast-path check (Function-typed
        colour spaces and many shading dictionaries default to a 0..1
        range, which can be omitted from serialisation when normalized).
        Compared exactly: a range stored as ``[0 1]`` (integers) equals
        ``[0.0 1.0]`` since ``COSNumber.float_value()`` widens both.
        """
        return self.get_min() == 0.0 and self.get_max() == 1.0

    def is_well_formed(self) -> bool:
        """Return ``True`` when ``min <= max``.

        pypdfbox extension — PDF 32000-1 doesn't formally require
        ``min <= max``, but reverse-ordered ranges are almost always a
        producer bug. Surfacing the check lets callers validate gamuts
        without re-typing the comparison.
        """
        return self.get_min() <= self.get_max()

    # ---------- equality / debug ----------

    def __eq__(self, other: object) -> bool:
        """Value equality — two ranges compare equal when their min and
        max bounds match.

        pypdfbox extension — upstream falls back to Java's identity
        ``equals``. Treating ranges as value-equal lets callers compare
        gamut entries cheaply (e.g. test assertions, deduplication of
        DecodeArrays). Note this compares numeric values: a range pair
        stored as integers compares equal to a float-typed pair with the
        same numeric content.
        """
        if not isinstance(other, PDRange):
            return NotImplemented
        return self.get_min() == other.get_min() and self.get_max() == other.get_max()

    def __hash__(self) -> int:
        """Hash matches :meth:`__eq__` — over (min, max).

        Note: the wrapped ``COSArray`` is mutable, so a range used as a
        dict key after subsequent ``set_min`` / ``set_max`` calls will
        not be locatable in the dict — same caveat as any mutable
        hashable object.
        """
        return hash((self.get_min(), self.get_max()))

    def __iter__(self) -> Any:
        """Yield ``(min, max)`` so callers can write ``min, max =
        pd_range``.

        pypdfbox extension — Pythonic unpacking sugar. The yield order
        matches the entry order in the wrapped array (min first, max
        second), so destructuring round-trips with the COS form.
        """
        yield self.get_min()
        yield self.get_max()

    def as_tuple(self) -> tuple[float, float]:
        """Return ``(min, max)`` as a plain tuple.

        pypdfbox extension — convenience for callers that hold a tuple
        shape (``PDLab.get_a_range`` / ``PDICCBased.get_range_for_component``
        return ``tuple[float, float]`` for backwards compatibility with
        the lite surface that pre-dated this wrapper).
        """
        return (self.get_min(), self.get_max())

    def __str__(self) -> str:
        """Match upstream ``toString()``: ``PDRange{min, max}``."""
        return "PDRange{" + str(self.get_min()) + ", " + str(self.get_max()) + "}"

    def __repr__(self) -> str:
        return (
            f"PDRange(min={self.get_min()!r}, max={self.get_max()!r}, "
            f"starting_index={self._starting_index!r})"
        )


__all__ = ["PDRange"]
