from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSFloat, COSInteger


class PDRectangle:
    """
    PDF rectangle — four numbers ``[lower_left_x lower_left_y
    upper_right_x upper_right_y]``. Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDRectangle``.

    Cluster #1 ships a deliberately-thin port: just the four floats, the
    derived width / height accessors, and ``COSArray`` round-trip helpers.
    Subsequent waves backfilled ``contains``, ``createRetranslatedRectangle``,
    and ``to_general_path`` (corner sequence — see method docstring for
    why we don't return a Java ``GeneralPath``). The matrix-aware
    ``transform`` lands alongside the rendering cluster (PRD §6.12) where
    a Python ``Matrix`` port is actually consumed. See ``CHANGES.md``.
    """

    # ---------- common paper-size constants ----------
    # 1 PostScript point = 1/72 inch. Mirrors upstream constants.

    #: User-space units per inch (PostScript points).
    POINTS_PER_INCH: float = 72.0
    #: User-space units per millimetre (= ``POINTS_PER_INCH / 25.4``).
    POINTS_PER_MM: float = 72.0 / 25.4

    LETTER_WIDTH: float = 612.0
    LETTER_HEIGHT: float = 792.0
    A4_WIDTH: float = 595.0
    A4_HEIGHT: float = 842.0
    LEGAL_WIDTH: float = 612.0
    LEGAL_HEIGHT: float = 1008.0

    __slots__ = (
        "_lower_left_x",
        "_lower_left_y",
        "_upper_right_x",
        "_upper_right_y",
    )

    def __init__(
        self,
        lower_left_x: float = 0.0,
        lower_left_y: float = 0.0,
        upper_right_x: float = 0.0,
        upper_right_y: float = 0.0,
    ) -> None:
        self._lower_left_x = float(lower_left_x)
        self._lower_left_y = float(lower_left_y)
        self._upper_right_x = float(upper_right_x)
        self._upper_right_y = float(upper_right_y)

    # ---------- factory constructors ----------

    @classmethod
    def from_width_height(cls, width: float, height: float) -> PDRectangle:
        """Match upstream's ``PDRectangle(float width, float height)``."""
        return cls(0.0, 0.0, float(width), float(height))

    @classmethod
    def from_xywh(cls, x: float, y: float, width: float, height: float) -> PDRectangle:
        """Match upstream's ``PDRectangle(float x, float y, float w, float h)``."""
        return cls(float(x), float(y), float(x) + float(width), float(y) + float(height))

    #: Clamp threshold for malformed COS values — matches upstream's
    #: ``Integer.MAX_VALUE`` (Java ``int`` ceiling). Values whose absolute
    #: magnitude exceeds this are deemed malformed (PDFBOX-2818) and clipped
    #: in :meth:`from_cos_array`.
    _INT32_MAX: float = float(2**31 - 1)

    @classmethod
    def from_cos_array(cls, array: COSArray) -> PDRectangle:
        """Build from the 4-entry array form found in PDF dictionaries.

        Mirrors upstream's ``PDRectangle(COSArray)``: any combination of
        ``COSInteger`` / ``COSFloat`` is accepted, and lower-left/upper-right
        ordering is normalized so ``width`` / ``height`` are non-negative.

        Huge magnitudes (``abs(value) > 2**31 - 1``) are clamped to
        ``±(2**31 - 1)``, matching upstream's defensive guard against
        malformed PDFs whose rectangles overflow Java ``int`` range
        (PDFBOX-2818).
        """
        if array.size() < 4:
            raise ValueError(
                f"PDRectangle requires a 4-entry COSArray, got {array.size()}"
            )
        nums: list[float] = []
        for i in range(4):
            entry = array.get_object(i)
            if isinstance(entry, (COSInteger, COSFloat)):
                value = float(entry.value)
                # PDFBOX-2818: malformed PDFs sometimes encode rectangles
                # with absurdly large numbers; upstream clamps at the Java
                # ``Integer.MAX_VALUE`` boundary. Mirror that here.
                if abs(value) > cls._INT32_MAX:
                    value = cls._INT32_MAX if value > 0 else -cls._INT32_MAX
                nums.append(value)
            else:
                raise TypeError(
                    f"PDRectangle entry {i} is not numeric: {type(entry).__name__}"
                )
        x0, y0, x1, y1 = nums
        # Normalize so the "lower-left" pair really is the smaller corner —
        # PDF spec §7.9.5: "the order of these values is unimportant".
        return cls(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    # ---------- accessors ----------

    @property
    def lower_left_x(self) -> float:
        return self._lower_left_x

    @property
    def lower_left_y(self) -> float:
        return self._lower_left_y

    @property
    def upper_right_x(self) -> float:
        return self._upper_right_x

    @property
    def upper_right_y(self) -> float:
        return self._upper_right_y

    def get_lower_left_x(self) -> float:
        return self._lower_left_x

    def get_lower_left_y(self) -> float:
        return self._lower_left_y

    def get_upper_right_x(self) -> float:
        return self._upper_right_x

    def get_upper_right_y(self) -> float:
        return self._upper_right_y

    def set_lower_left_x(self, value: float) -> None:
        self._lower_left_x = float(value)

    def set_lower_left_y(self, value: float) -> None:
        self._lower_left_y = float(value)

    def set_upper_right_x(self, value: float) -> None:
        self._upper_right_x = float(value)

    def set_upper_right_y(self, value: float) -> None:
        self._upper_right_y = float(value)

    @property
    def width(self) -> float:
        return self._upper_right_x - self._lower_left_x

    @property
    def height(self) -> float:
        return self._upper_right_y - self._lower_left_y

    def get_width(self) -> float:
        return self.width

    def get_height(self) -> float:
        return self.height

    # ---------- geometry ----------

    def contains(self, x: float, y: float) -> bool:
        """Return ``True`` when the point ``(x, y)`` lies inside this rectangle
        (inclusive on all four edges). Mirrors upstream
        ``contains(float, float)``."""
        return (
            self._lower_left_x <= x <= self._upper_right_x
            and self._lower_left_y <= y <= self._upper_right_y
        )

    def create_retranslated_rectangle(self) -> PDRectangle:
        """Return a new rectangle with the same width/height but origin at
        ``(0, 0)``. Mirrors upstream ``createRetranslatedRectangle()``.

        Example: ``[100, 100, 400, 400]`` → ``[0, 0, 300, 300]``.
        """
        return PDRectangle(0.0, 0.0, self.width, self.height)

    def to_general_path(self) -> list[tuple[float, float]]:
        """Return the four corners of this rectangle as a counter-clockwise
        closed polygon. Mirrors upstream ``toGeneralPath()``.

        Returned in upstream order: ``(llx, lly) → (urx, lly) → (urx, ury)
        → (llx, ury)``. The polygon is implicitly closed; callers that
        need an explicit closing edge should treat the first point as the
        terminator. Java's ``GeneralPath`` doesn't have a direct Python
        equivalent in the standard library, so we expose the corners as a
        ``list[tuple[float, float]]`` rather than tying the API to a
        specific drawing toolkit.
        """
        x1 = self._lower_left_x
        y1 = self._lower_left_y
        x2 = self._upper_right_x
        y2 = self._upper_right_y
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    # ---------- COS round-trip ----------

    def to_cos_array(self) -> COSArray:
        """Emit a 4-entry direct ``COSArray`` of ``COSFloat`` values."""
        arr = COSArray(
            [
                COSFloat(self._lower_left_x),
                COSFloat(self._lower_left_y),
                COSFloat(self._upper_right_x),
                COSFloat(self._upper_right_y),
            ]
        )
        arr.set_direct(True)
        return arr

    def get_cos_array(self) -> COSArray:
        """Alias for ``to_cos_array`` — matches upstream method name."""
        return self.to_cos_array()

    def get_cos_object(self) -> COSArray:
        """``COSObjectable``-style accessor — returns the array form."""
        return self.to_cos_array()

    # ---------- equality / repr ----------

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PDRectangle):
            return NotImplemented
        return (
            self._lower_left_x == other._lower_left_x
            and self._lower_left_y == other._lower_left_y
            and self._upper_right_x == other._upper_right_x
            and self._upper_right_y == other._upper_right_y
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._lower_left_x,
                self._lower_left_y,
                self._upper_right_x,
                self._upper_right_y,
            )
        )

    def __repr__(self) -> str:
        return (
            f"PDRectangle("
            f"{self._lower_left_x}, {self._lower_left_y}, "
            f"{self._upper_right_x}, {self._upper_right_y})"
        )

    def __str__(self) -> str:
        return (
            f"[{self._lower_left_x}, {self._lower_left_y}, "
            f"{self._upper_right_x}, {self._upper_right_y}]"
        )


# Module-level paper-size constants. Match upstream PDFBox naming.
PDRectangle.LETTER = PDRectangle(0.0, 0.0, 612.0, 792.0)  # type: ignore[attr-defined]
PDRectangle.A4 = PDRectangle(0.0, 0.0, 595.0, 842.0)  # type: ignore[attr-defined]
PDRectangle.LEGAL = PDRectangle(0.0, 0.0, 612.0, 1008.0)  # type: ignore[attr-defined]

# Additional paper-size constants. Mirrors upstream constants computed as
# ``mm * POINTS_PER_MM`` (= ``mm * 72 / 25.4``). Tabloid is 11" x 17".
_PPI: float = PDRectangle.POINTS_PER_INCH
_PPMM: float = PDRectangle.POINTS_PER_MM
PDRectangle.TABLOID = PDRectangle(0.0, 0.0, 11.0 * _PPI, 17.0 * _PPI)  # type: ignore[attr-defined]
PDRectangle.A0 = PDRectangle(0.0, 0.0, 841.0 * _PPMM, 1189.0 * _PPMM)  # type: ignore[attr-defined]
PDRectangle.A1 = PDRectangle(0.0, 0.0, 594.0 * _PPMM, 841.0 * _PPMM)  # type: ignore[attr-defined]
PDRectangle.A2 = PDRectangle(0.0, 0.0, 420.0 * _PPMM, 594.0 * _PPMM)  # type: ignore[attr-defined]
PDRectangle.A3 = PDRectangle(0.0, 0.0, 297.0 * _PPMM, 420.0 * _PPMM)  # type: ignore[attr-defined]
PDRectangle.A5 = PDRectangle(0.0, 0.0, 148.0 * _PPMM, 210.0 * _PPMM)  # type: ignore[attr-defined]
PDRectangle.A6 = PDRectangle(0.0, 0.0, 105.0 * _PPMM, 148.0 * _PPMM)  # type: ignore[attr-defined]
del _PPI, _PPMM
