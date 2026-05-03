from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.fontbox.encoding.win_ansi_encoding import _TABLE

from .encoding import Encoding


class WinAnsiEncoding(Encoding):
    """The Windows ANSI Encoding (CP1252 superset).

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.WinAnsiEncoding``. Per
    the PDF spec, all unused codes greater than 040 (octal) map to the
    ``bullet`` glyph — this fill-in is applied after the explicit table.
    """

    INSTANCE: "WinAnsiEncoding"

    #: First character code (inclusive) eligible for the ``bullet`` fall-back
    #: fill-in. Codes <= ``BULLET_FILL_START - 1`` (octal 040) remain
    #: ``.notdef`` and are not filled. Mirrors the upstream constructor's
    #: ``for (int i = 041; i < 256; i++)`` loop bound.
    BULLET_FILL_START: int = 0o41

    #: The canonical, explicit ``bullet`` glyph code from the WinAnsi table.
    #: Distinguishes the spec-mandated bullet position from the
    #: bullet-fill-in codes (every otherwise-unused code in
    #: ``BULLET_FILL_START..255``). Useful for writers that want to emit a
    #: real ``bullet`` glyph rather than a fall-back.
    EXPLICIT_BULLET_CODE: int = 0o225

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)
        # Track which codes were filled in (vs explicitly mapped) so writers
        # and round-trippers can distinguish a real ``bullet`` glyph from a
        # spec fall-back without re-deriving the set from the upstream table.
        bullet_fill_codes: set[int] = set()
        for i in range(self.BULLET_FILL_START, 256):
            if i not in self._code_to_name:
                self.add(i, "bullet")
                bullet_fill_codes.add(i)
        self._bullet_fill_codes: frozenset[int] = frozenset(bullet_fill_codes)

    def get_cos_object(self) -> COSBase:
        # Upstream returns COSName.WIN_ANSI_ENCODING directly. The base-class
        # implementation arrives at the same interned COSName via the encoding
        # name, but mirroring the override keeps the surface explicit.
        return COSName.get_pdf_name("WinAnsiEncoding")

    def get_encoding_name(self) -> str:
        return "WinAnsiEncoding"

    # -- bullet fill-in helpers -------------------------------------------

    def is_bullet_fill_code(self, code: int) -> bool:
        """``True`` when ``code`` was filled in with the ``bullet`` fall-back
        rather than mapped explicitly by the WinAnsi table.

        The PDF spec requires every otherwise-unused code in
        ``BULLET_FILL_START..255`` to map to ``bullet``. This predicate
        distinguishes those fall-back positions from the canonical
        :attr:`EXPLICIT_BULLET_CODE` (octal 0o225) which is a real glyph
        position from the WinAnsi table.

        Returns ``False`` for codes outside the fill-in range, for explicitly
        mapped codes, and for :attr:`EXPLICIT_BULLET_CODE` itself.
        """
        return code in self._bullet_fill_codes

    def get_bullet_fill_codes(self) -> frozenset[int]:
        """Return the immutable set of codes that resolve to ``bullet`` only
        because of the spec-mandated fall-back fill-in (excluding the
        canonical :attr:`EXPLICIT_BULLET_CODE`).

        The set is fixed at construction time and shared across all callers —
        :class:`frozenset` makes accidental mutation impossible.
        """
        return self._bullet_fill_codes

    def is_explicit_code(self, code: int) -> bool:
        """``True`` when ``code`` was mapped by the explicit WinAnsi table
        (i.e. *not* a ``bullet`` fall-back).

        Codes outside ``0..255`` and unmapped low codes (0..0o40) return
        ``False`` — the predicate strictly answers "is this an explicit table
        entry?", not "is this code mapped at all?". Use :meth:`contains_code`
        for the latter.
        """
        if code not in self._code_to_name:
            return False
        return code not in self._bullet_fill_codes


WinAnsiEncoding.INSTANCE = WinAnsiEncoding()


__all__ = ["WinAnsiEncoding"]
