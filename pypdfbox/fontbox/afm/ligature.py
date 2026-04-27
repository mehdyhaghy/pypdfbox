from __future__ import annotations


class Ligature:
    """A single ligature entry on a CharMetric.

    Mirrors ``org.apache.fontbox.afm.Ligature``. AFM ``L successor ligature``
    declares that the current glyph followed by ``successor`` may be
    rendered as the single glyph ``ligature`` (e.g. ``f`` + ``i`` -> ``fi``).
    """

    __slots__ = ("_successor", "_ligature")

    def __init__(self, successor: str, ligature: str) -> None:
        self._successor = successor
        self._ligature = ligature

    def get_successor(self) -> str:
        """The follow-on glyph name (e.g. ``"i"``)."""
        return self._successor

    def get_ligature(self) -> str:
        """The replacement (ligature) glyph name (e.g. ``"fi"``)."""
        return self._ligature

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ligature):
            return NotImplemented
        return (
            self._successor == other._successor
            and self._ligature == other._ligature
        )

    def __hash__(self) -> int:
        return hash((self._successor, self._ligature))

    def __repr__(self) -> str:
        return f"Ligature({self._successor!r} -> {self._ligature!r})"
