"""Font-subsetter interface — common shape across TTF / CFF embedders.

Mirrors ``org.apache.pdfbox.pdmodel.font.Subsetter`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/Subsetter.java``
lines 25-40).

Upstream Java is a package-private interface with two methods:
``addToSubset(int)`` and ``subset()``. pypdfbox surfaces it as an
:class:`~abc.ABC` so :class:`TrueTypeEmbedder` and any future Type 1 /
CFF subsetters share the same opt-in contract.

Library-first note: actual subsetting is delegated to ``fontTools``
(``fontTools.subset.Subsetter``) inside the concrete embedder. This
interface stays small — it's a *protocol*, not an implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Subsetter(ABC):
    """Abstract base for font subsetters.

    Mirrors upstream Java interface (line 25-40). Two abstract methods,
    no concrete state. Sub-classes that wrap ``fontTools`` shell out the
    real glyph filtering at :meth:`subset` time.
    """

    @abstractmethod
    def add_to_subset(self, code_point: int) -> None:
        """Register a Unicode code point for inclusion in the subset.

        Mirrors upstream ``addToSubset(int)`` (Java line 32). Repeated
        calls with the same code point are idempotent; upstream uses a
        ``HashSet<Integer>`` internally.
        """

    @abstractmethod
    def subset(self) -> None:
        """Compute the subset *now*.

        Mirrors upstream ``subset()`` (Java line 39). Raises an
        ``OSError`` (Java's ``IOException``) if the font program cannot
        be read or the subset cannot be written.
        """


__all__ = ["Subsetter"]
