"""External font service provider — enumerates system fonts.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontProvider`` from PDFBox 3.0.

A :class:`FontProvider` is the *back-end* for a :class:`FontMapper`:
the mapper decides which font to substitute for an unembedded request,
the provider supplies the catalogue of candidate fonts on the system.
Upstream ships :class:`FileSystemFontProvider` as the default — pypdfbox
hasn't ported that yet (it would pull in a full TTF scanner / system
font directory walker) so the default :class:`DefaultFontMapper` works
without a provider at all and resolves only the bundled Standard 14
metrics. Apps that need full system-font enumeration provide their own
:class:`FontProvider` and wire it into a custom :class:`FontMapper`.

Java is an abstract class with two abstract methods. Python uses an
:class:`~abc.ABC` for the same shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .font_info import FontInfo


class FontProvider(ABC):
    """External font service provider — produces :class:`FontInfo` records.

    Subclasses scan some external source (filesystem, font cache,
    fontconfig, matplotlib's font_manager, etc.) and return a list of
    :class:`FontInfo` records describing what was found. The mapper
    walks that list when a non-embedded request comes in.
    """

    @abstractmethod
    def to_debug_string(self) -> str | None:
        """Return free-form diagnostic text, or ``None``.

        Mirrors upstream ``String toDebugString()``. Logged by the
        mapper when no candidate font can be resolved and no fallback
        is configured. ``None`` is allowed (upstream contract).
        """

    @abstractmethod
    def get_font_info(self) -> Sequence[FontInfo]:
        """Return a sequence of :class:`FontInfo` records on the system.

        Mirrors upstream ``List<? extends FontInfo> getFontInfo()``.
        Implementors are free to return any sequence type — list, tuple,
        a lazy view — provided iteration is stable across calls (the
        mapper may walk the list multiple times).
        """


__all__ = ["FontProvider"]
