from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ttf_parser import FontHeaders


class TrueTypeFontHeadersProcessor(ABC):
    """Callback for :meth:`TrueTypeCollection.process_all_font_headers`.

    Mirrors the upstream nested functional interface
    ``org.apache.fontbox.ttf.TrueTypeCollection.TrueTypeFontHeadersProcessor``
    (``TrueTypeCollection.java`` lines 204-211). Like the sibling
    :class:`TrueTypeFontProcessor`, this is upstream's Java
    ``@FunctionalInterface``; Python mirrors with a single-method ABC.

    The handler receives a populated :class:`FontHeaders` per font in
    the TTC — the same fast-path payload upstream's
    ``FileSystemFontProvider.scanFonts`` consumes to decide whether the
    font on disk is interesting before paying for a full table decode.
    Plain callables taking a single :class:`FontHeaders` are also
    accepted by :class:`TrueTypeCollection` for ergonomic parity with
    upstream's lambda form.
    """

    @abstractmethod
    def process(self, font_headers: FontHeaders) -> None:
        """Run logic over each :class:`FontHeaders` from a TTC.

        Mirrors ``void process(FontHeaders fontHeaders)``
        (``TrueTypeCollection.java`` line 210). Upstream's signature
        does *not* declare ``throws IOException`` — header parsing
        records failures on ``FontHeaders.get_error()`` rather than
        raising — so implementations should treat failures the same
        way for parity.
        """


__all__ = ["TrueTypeFontHeadersProcessor"]
