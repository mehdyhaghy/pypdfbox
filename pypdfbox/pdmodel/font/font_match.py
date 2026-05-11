"""Font match record — a scored candidate inside ``FontMapperImpl``.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontMapperImpl.FontMatch``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
FontMapperImpl.java`` lines 727-742).

Upstream Java declares ``FontMatch`` as a private nested class. We host
it as a top-level module so :class:`FontMapperImpl` can be split into a
matcher + scorer without re-introducing the nested-class boilerplate.

The class implements ``Comparable<FontMatch>`` so a ``PriorityQueue``
walks matches in *descending* score order — i.e. ``Double.compare(match.
score, this.score)``. Python's :mod:`heapq` is a min-heap; to match
upstream ordering we expose :meth:`__lt__` that flips the sign.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.fontbox.font_info import FontInfo


class FontMatch:
    """A scored font candidate.

    Mirrors upstream Java line 727-742. Two fields:

    * ``score`` (float, mutable — :class:`FontMapperImpl` adds and
      subtracts during scoring).
    * ``info`` (the :class:`FontInfo` of the candidate).

    ``__lt__`` returns the *opposite* of a naive comparison so a
    :mod:`heapq` (min-heap) pops the highest-scoring match first — the
    same behaviour as Java's ``PriorityQueue<FontMatch>`` driven by
    upstream's ``compareTo`` that flips the operands.
    """

    __slots__ = ("score", "info")

    def __init__(self, info: FontInfo) -> None:
        # Upstream constructor (Java line 732-735): no initial score, info
        # is final. We zero-init ``score`` because Python doesn't
        # default-zero double fields like Java does.
        self.score: float = 0.0
        self.info: FontInfo = info

    def __lt__(self, other: FontMatch) -> bool:
        # Mirror upstream ``compareTo`` (Java line 738-741):
        # ``Double.compare(match.score, this.score)`` orders descending.
        # ``heapq`` is min-heap, so we flip operands: ``self < other``
        # iff ``self.score > other.score``.
        if not isinstance(other, FontMatch):
            return NotImplemented
        return self.score > other.score

    def __repr__(self) -> str:
        return f"FontMatch(score={self.score!r}, info={self.info!r})"


__all__ = ["FontMatch"]
