from __future__ import annotations

from .composite_part import CompositePart


class Composite:
    """An AFM composite-glyph entry (``CC`` keyword).

    Mirrors ``org.apache.fontbox.afm.Composite``: a name plus an ordered
    list of :class:`CompositePart` entries giving the base glyphs and
    their relative displacements.
    """

    __slots__ = ("_name", "_parts")

    def __init__(self, name: str) -> None:
        self._name = name
        self._parts: list[CompositePart] = []

    def get_name(self) -> str:
        return self._name

    def add_part(self, part: CompositePart) -> None:
        self._parts.append(part)

    def get_parts(self) -> list[CompositePart]:
        """Return the parts list as an immutable copy."""
        return list(self._parts)

    def __repr__(self) -> str:
        return f"Composite({self._name!r}, parts={self._parts!r})"
