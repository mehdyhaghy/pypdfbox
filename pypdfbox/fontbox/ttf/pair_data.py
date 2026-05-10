"""Kerning pair-data interface.

Mirrors the private ``PairData`` interface declared inside
``org.apache.fontbox.ttf.KerningSubtable`` (upstream
``KerningSubtable.java`` L248-253). Promoted to a top-level module so
that concrete subclasses (currently :class:`PairData0Format0`) can be
plugged in without the consumer reaching into a nested private type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ttf_data_stream import TTFDataStream


class PairData(ABC):
    """Abstract kerning pair-data backend.

    Mirrors ``KerningSubtable$PairData`` (KerningSubtable.java L248-253).
    Two operations: read the binary body from a :class:`TTFDataStream`,
    and look up the kerning adjustment for an ordered (left, right) GID
    pair.
    """

    @abstractmethod
    def read(self, data: TTFDataStream) -> None:
        """Decode this pair-data block from ``data`` at the current cursor.

        Mirrors ``PairData#read(TTFDataStream)`` (upstream L250).
        Implementations may consume a variable number of bytes — see the
        concrete subclass for the exact layout.
        """

    @abstractmethod
    def get_kerning(self, left: int, right: int) -> int:
        """Return the kerning adjustment for the ordered (left, right)
        GID pair, or ``0`` if absent.

        Mirrors ``PairData#getKerning(int, int)`` (upstream L252).
        """


__all__ = ["PairData"]
