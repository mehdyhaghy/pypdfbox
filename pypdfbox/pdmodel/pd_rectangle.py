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
    The upstream class additionally exposes ``contains``, ``transform``,
    ``toGeneralPath``, ``createRetranslatedRectangle`` — those land
    alongside the rendering cluster (PRD §6.12) where they are actually
    consumed. See ``CHANGES.md``.
    """

    # ---------- common paper-size constants ----------
    # 1 PostScript point = 1/72 inch. Mirrors upstream constants.

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

    @classmethod
    def from_cos_array(cls, array: COSArray) -> PDRectangle:
        """Build from the 4-entry array form found in PDF dictionaries.

        Mirrors upstream's ``PDRectangle(COSArray)``: any combination of
        ``COSInteger`` / ``COSFloat`` is accepted, and lower-left/upper-right
        ordering is normalized so ``width`` / ``height`` are non-negative.
        """
        if array.size() < 4:
            raise ValueError(
                f"PDRectangle requires a 4-entry COSArray, got {array.size()}"
            )
        nums: list[float] = []
        for i in range(4):
            entry = array.get_object(i)
            if isinstance(entry, (COSInteger, COSFloat)):
                nums.append(float(entry.value))
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
