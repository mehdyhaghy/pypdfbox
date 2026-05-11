"""Vertical displacement range — a CID range with its W2/DW2 vector.

Mirrors ``org.apache.pdfbox.pdmodel.font.PDCIDFont.VerticalDisplacementRange``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
PDCIDFont.java`` lines 443-472).

Upstream Java declares ``VerticalDisplacementRange`` as a private nested
class on :class:`PDCIDFont`. pypdfbox lifts it to a top-level module so
the same record can be reused by :class:`PDCIDFontType2Embedder` when
synthesizing W2 / DW2 arrays.

The record carries:

* ``range_start`` / ``range_end`` — inclusive CID range.
* ``position_vector`` — the (vx, vy) vertical-origin offset
  (a :class:`Vector` in PDFBox; pypdfbox accepts any 2-tuple-like value
  with ``__getitem__`` 0/1).
* ``vertical_displacement`` — the W2 advance height (signed float).
"""

from __future__ import annotations

from typing import Any


class VerticalDisplacementRange:
    """Immutable record describing the W2 entry for a CID range.

    Mirrors upstream Java (line 443-472).
    """

    __slots__ = (
        "_range_start",
        "_range_end",
        "_position_vector",
        "_vertical_displacement",
    )

    def __init__(
        self,
        start: int,
        end: int,
        vector: Any,
        displacement: float,
    ) -> None:
        # Upstream constructor (Java line 450-456): four fields assigned
        # directly. Misspelling ``verticalDisplacment`` (sic) is in the
        # upstream source; we use the corrected snake_case spelling.
        self._range_start: int = start
        self._range_end: int = end
        self._position_vector: Any = vector
        self._vertical_displacement: float = displacement

    def range_matches(self, value: int) -> bool:
        """Return ``True`` if *value* falls inside ``[start, end]``.

        Mirrors upstream ``rangeMatches`` (Java line 458-461).
        """
        return self._range_start <= value <= self._range_end

    def get_position_vector(self) -> Any:
        """Return the (vx, vy) position vector.

        Mirrors upstream ``getPositionVector`` (Java line 463-466).
        """
        return self._position_vector

    def get_vertical_displacement(self) -> float:
        """Return the W2 advance height.

        Mirrors upstream ``getVerticalDisplacement`` (Java line 468-471).
        Note the upstream getter spells the field correctly even though
        the underlying field name has a typo (``verticalDisplacment``).
        """
        return self._vertical_displacement

    @property
    def range_start(self) -> int:
        """Inclusive start of the CID range."""
        return self._range_start

    @property
    def range_end(self) -> int:
        """Inclusive end of the CID range."""
        return self._range_end

    def __repr__(self) -> str:
        return (
            f"VerticalDisplacementRange(range_start={self._range_start}, "
            f"range_end={self._range_end}, vector={self._position_vector!r}, "
            f"displacement={self._vertical_displacement!r})"
        )


__all__ = ["VerticalDisplacementRange"]
