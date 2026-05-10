from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont


class TrueTypeFontProcessor(ABC):
    """Callback for :meth:`TrueTypeCollection.process_all_fonts`.

    Mirrors the upstream nested functional interface
    ``org.apache.fontbox.ttf.TrueTypeCollection.TrueTypeFontProcessor``
    (``TrueTypeCollection.java`` lines 198-202). Upstream uses Java's
    ``@FunctionalInterface``; Python doesn't need a sugar form so the
    interface is exposed as an ABC with a single :meth:`process`
    method. Plain callables that accept a :class:`TrueTypeFont` are also
    accepted by :class:`TrueTypeCollection` for ergonomic parity with
    upstream's lambda form (``ttc.process_all_fonts(lambda f: ...)``).
    """

    @abstractmethod
    def process(self, ttf: TrueTypeFont) -> None:
        """Run logic over each :class:`TrueTypeFont` from a collection.

        Mirrors ``void process(TrueTypeFont ttf) throws IOException``
        (``TrueTypeCollection.java`` line 201). Raise ``OSError`` /
        ``PDFParseError`` from inside to abort iteration; the collection
        propagates the exception without swallowing.
        """


__all__ = ["TrueTypeFontProcessor"]
