"""Abstract built-in CFF encoding plus its nested ``Supplement`` data class.

Mirrors the inner class
``org.apache.fontbox.cff.CFFParser.CFFBuiltInEncoding`` (and its inner
``Supplement``) from upstream PDFBox 3.0. Extracted into its own module
in pypdfbox for cleaner test isolation; semantics are unchanged.

A built-in encoding is one that ships embedded in a CFF font (Format 0
or Format 1), as opposed to the predefined Standard / Expert encodings.
It carries a list of post-table "supplement" entries that map extra
character codes to SIDs after the main table is parsed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cff_encoding import CFFEncoding


@dataclass(frozen=True)
class Supplement:
    """A single (code, sid, name) supplement entry.

    Mirrors upstream nested class
    ``CFFParser.CFFBuiltInEncoding.Supplement``. The Java original is a
    ``private static class`` with a 3-arg constructor and ``toString()``
    that prints ``code`` and ``sid``; we expose the same attributes and
    a parity-formatted ``__repr__``.
    """

    code: int
    sid: int
    name: str

    def to_string(self) -> str:
        """Mirror upstream ``CFFBuiltInEncoding.Supplement.toString``."""
        return f"{type(self).__name__}[code={self.code}, sid={self.sid}]"

    def __repr__(self) -> str:
        # Match Java toString format: ClassName[code=N, sid=M]
        return self.to_string()


class CFFBuiltInEncoding(CFFEncoding):
    """Abstract base for embedded (Format0 / Format1) CFF encodings.

    Holds a tuple of :class:`Supplement` entries that the parser appends
    after the main encoding table; :meth:`add_supplement` applies one
    such entry to the encoding map.
    """

    def __init__(self) -> None:
        super().__init__()
        self._supplement: tuple[Supplement, ...] = ()

    # -- supplement handling ---------------------------------------------

    @property
    def supplement(self) -> tuple[Supplement, ...]:
        """Return the supplement list (immutable snapshot)."""
        return self._supplement

    @supplement.setter
    def supplement(self, value: tuple[Supplement, ...] | list[Supplement]) -> None:
        self._supplement = tuple(value)

    def add_supplement(self, sup: Supplement) -> None:
        """Apply a single supplement to the encoding.

        Mirrors upstream ``add(Supplement supplement)`` which delegates
        to the 3-arg ``add(code, sid, name)``.
        """
        self.add(sup.code, sup.sid, sup.name)


__all__ = ["CFFBuiltInEncoding", "Supplement"]
