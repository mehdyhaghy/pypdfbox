from __future__ import annotations

import io
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

from .pd_font import PDFont

if TYPE_CHECKING:
    from pypdfbox.fontbox.cmap import CMap

    from .pd_cid_font import PDCIDFont

_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")


class PDType0Font(PDFont):
    """PDF Type 0 (composite) font. Mirrors PDFBox ``PDType0Font``.

    A composite font references exactly one descendant CIDFont via the
    ``/DescendantFonts`` array and uses a CMap (named in ``/Encoding``)
    to map input character codes to CIDs. The descendant font then maps
    CIDs to glyph metrics and (for Type2/TrueType) glyph indices via
    ``/CIDToGIDMap``.
    """

    SUB_TYPE = "Type0"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazy caches — populated on first lookup, dropped only by
        # constructing a fresh wrapper. Mutating ``/Encoding`` /
        # ``/ToUnicode`` after parsing requires a new instance.
        self._cmap: CMap | None = None
        self._cmap_loaded: bool = False
        self._to_unicode_cmap: CMap | None = None
        self._to_unicode_cmap_loaded: bool = False

    # ---------- /DescendantFonts ----------

    def get_descendant_font(self) -> PDCIDFont | None:
        """Return the typed ``PDCIDFont`` wrapper for the first
        ``/DescendantFonts`` entry, or ``None`` when absent / malformed.
        """
        arr = self._dict.get_dictionary_object(_DESCENDANT_FONTS)
        if not isinstance(arr, COSArray) or arr.size() == 0:
            return None
        first = arr.get_object(0)
        if isinstance(first, COSDictionary):
            return PDType0Font._wrap_descendant(first, self)
        return None

    @staticmethod
    def _wrap_descendant(
        font_dict: COSDictionary, parent: PDType0Font
    ) -> PDCIDFont | None:
        from .pd_cid_font_type0 import PDCIDFontType0
        from .pd_cid_font_type2 import PDCIDFontType2

        sub_type = font_dict.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        if sub_type == PDCIDFontType0.SUB_TYPE:
            return PDCIDFontType0(font_dict, parent)
        if sub_type == PDCIDFontType2.SUB_TYPE:
            return PDCIDFontType2(font_dict, parent)
        return None

    # ---------- /Encoding (CMap) ----------

    def get_cmap(self) -> CMap | None:
        """Return the encoding CMap parsed from ``/Encoding``.

        Per PDF 32000-1 §9.7.5.2 the entry is either a predefined CMap
        name (e.g. ``/Identity-H``) or a CMap stream. Cached on first
        successful resolution.
        """
        if self._cmap_loaded:
            return self._cmap
        self._cmap_loaded = True
        from pypdfbox.fontbox.cmap import CMapParser

        raw = self._dict.get_dictionary_object(_ENCODING)
        if isinstance(raw, COSName):
            try:
                self._cmap = CMapParser.parse_predefined(raw.name)
            except OSError:
                self._cmap = None
        elif isinstance(raw, COSStream):
            try:
                self._cmap = CMapParser().parse(raw.to_byte_array())
            except (OSError, ValueError):
                self._cmap = None
        else:
            self._cmap = None
        return self._cmap

    # ---------- /ToUnicode (CMap) ----------

    def get_to_unicode_cmap(self) -> CMap | None:
        """Parsed ``/ToUnicode`` CMap, or ``None`` when absent / malformed.
        """
        if self._to_unicode_cmap_loaded:
            return self._to_unicode_cmap
        self._to_unicode_cmap_loaded = True
        from pypdfbox.fontbox.cmap import CMapParser

        raw = self._dict.get_dictionary_object(_TO_UNICODE)
        if isinstance(raw, COSStream):
            try:
                self._to_unicode_cmap = CMapParser().parse(raw.to_byte_array())
            except (OSError, ValueError):
                self._to_unicode_cmap = None
        elif isinstance(raw, COSName):
            # PDF 32000-1 §9.10.3 allows a predefined name (e.g.
            # ``/Identity-H``) as a ``/ToUnicode`` shortcut.
            try:
                self._to_unicode_cmap = CMapParser.parse_predefined(raw.name)
            except OSError:
                self._to_unicode_cmap = None
        else:
            self._to_unicode_cmap = None
        return self._to_unicode_cmap

    # ---------- code -> CID / GID ----------

    def code_to_cid(self, code: int) -> int:
        """Map an input character code to a CID through the encoding CMap.

        For Identity / missing CMaps the code passes through unchanged
        — matches upstream ``PDType0Font.codeToCID``.
        """
        cmap = self.get_cmap()
        if cmap is not None and cmap.has_cid_mappings():
            cid = cmap.to_cid(code)
            if cid != 0 or code == 0:
                return cid
            # Fall through to descendant for codes the active CMap
            # doesn't explicitly map (e.g. Identity-H).
        descendant = self.get_descendant_font()
        if descendant is not None:
            return descendant.code_to_cid(code)
        return int(code)

    def code_to_gid(self, code: int) -> int:
        """Map an input character code to a glyph index.

        Resolves code → CID via the encoding CMap, then CID → GID via
        the descendant font's ``/CIDToGIDMap`` (Type2). For Type0/CFF
        descendants the GID equals the CID, mirroring upstream behavior.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return self.code_to_cid(code)
        # Prefer the descendant's own ``code_to_gid`` when available
        # (PDCIDFontType2). Otherwise fall back to CID == GID.
        cid = self.code_to_cid(code)
        cid_to_gid = getattr(descendant, "cid_to_gid", None)
        if callable(cid_to_gid):
            return cid_to_gid(cid)
        return cid

    # ---------- read_code (PDF 32000-1 §9.7.6.2) ----------

    def read_code(self, input_bytes: bytes, offset: int = 0) -> tuple[int, int]:
        """Read one character code from ``input_bytes`` starting at
        ``offset``. Returns ``(code, bytes_consumed)``.

        Delegates to the active CMap's ``read_code`` when one is parsed;
        otherwise falls back to a single-byte read (Adobe Reader's
        behavior when no CMap is available).
        """
        if offset < 0 or offset >= len(input_bytes):
            return (0, 0)
        cmap = self.get_cmap()
        if cmap is None:
            return (input_bytes[offset] & 0xFF, 1)
        stream = io.BytesIO(bytes(input_bytes[offset:]))
        before = stream.tell()
        code = cmap.read_code(stream)
        consumed = stream.tell() - before
        if consumed <= 0:
            consumed = 1
        return (code, consumed)

    # ---------- glyph metrics ----------

    def get_glyph_width(self, code: int) -> float:
        """Width of the glyph for ``code`` in 1/1000 em.

        Resolves code → CID, then defers to the descendant CIDFont's
        ``get_glyph_width(cid)``. Returns ``0.0`` when no descendant
        font is present.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return 0.0
        return descendant.get_glyph_width(self.code_to_cid(code))

    # ---------- writing direction ----------

    def is_vertical(self) -> bool:
        """``True`` when the active CMap declares ``/WMode 1`` (vertical
        writing). Defaults to ``False`` for missing CMaps.
        """
        cmap = self.get_cmap()
        if cmap is None:
            return False
        return cmap.get_wmode() == 1

    # ---------- to_unicode ----------

    def to_unicode(self, code: int) -> str | None:
        """Return the Unicode string for ``code``.

        Tries the ``/ToUnicode`` CMap first, then falls back to the
        encoding CMap's own bf-mappings. Mirrors upstream
        ``PDType0Font.toUnicode``.
        """
        to_unicode_cmap = self.get_to_unicode_cmap()
        if to_unicode_cmap is not None and to_unicode_cmap.has_unicode_mappings():
            mapped = to_unicode_cmap.to_unicode(code)
            if mapped is not None:
                return mapped
        cmap = self.get_cmap()
        if cmap is not None and cmap.has_unicode_mappings():
            return cmap.to_unicode(code)
        return None

    # ---------- embedding ----------

    def is_embedded(self) -> bool:
        """``True`` when the descendant CIDFont's font program is
        embedded in the file.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return False
        return descendant.is_embedded()


__all__ = ["PDType0Font"]
