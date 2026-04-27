from __future__ import annotations


class KernPair:
    """An AFM kerning-pair entry.

    Mirrors ``org.apache.fontbox.afm.KernPair``. AFM ``KPX`` lines yield
    ``y == 0``; ``KPY`` lines yield ``x == 0``; ``KP`` lines carry both.
    Hex-pair (``KPH``) entries decode to the same fields after the angle
    brackets are stripped and the hex pair is mapped to ISO-8859-1.
    """

    __slots__ = ("_first", "_second", "_x", "_y")

    def __init__(
        self,
        first_kern_character: str,
        second_kern_character: str,
        x: float,
        y: float,
    ) -> None:
        self._first = first_kern_character
        self._second = second_kern_character
        self._x = float(x)
        self._y = float(y)

    def get_first_kern_character(self) -> str:
        """First glyph name in the pair."""
        return self._first

    def get_second_kern_character(self) -> str:
        """Second glyph name in the pair."""
        return self._second

    def get_x(self) -> float:
        """Kerning displacement along the x-axis (1/1000 em)."""
        return self._x

    def get_y(self) -> float:
        """Kerning displacement along the y-axis (1/1000 em)."""
        return self._y

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KernPair):
            return NotImplemented
        return (
            self._first == other._first
            and self._second == other._second
            and self._x == other._x
            and self._y == other._y
        )

    def __hash__(self) -> int:
        return hash((self._first, self._second, self._x, self._y))

    def __repr__(self) -> str:
        return (
            f"KernPair({self._first!r}, {self._second!r}, "
            f"{self._x}, {self._y})"
        )
