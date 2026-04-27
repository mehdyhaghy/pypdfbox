from __future__ import annotations

import io
from collections.abc import Iterable
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
        # Codepoints accumulated by :meth:`add_to_subset`; consumed by
        # :meth:`subset` on save. Type 0 fonts subset the descendant
        # CIDFontType2's embedded TrueType program.
        self._subset_codepoints: set[int] = set()

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

    # ---------- subsetting ----------

    def add_to_subset(self, code_point: int) -> None:
        """Register a Unicode codepoint to keep when :meth:`subset` runs.

        Mirrors upstream ``PDType0Font.addToSubset(int)``. The codepoint
        is the *Unicode* value (not the CID) — :meth:`subset` resolves
        Unicode → GID via the descendant's embedded cmap.
        """
        self._subset_codepoints.add(int(code_point))

    def add_text_to_subset(self, text: str) -> None:
        """Convenience: register every codepoint of ``text``."""
        for ch in text:
            self._subset_codepoints.add(ord(ch))

    def subset(
        self,
        text_or_codepoints: str | Iterable[int] | None = None,
        *,
        used_chars: Iterable[int] | None = None,
        prefix: str | None = None,
    ) -> bytes:
        """Build a TrueType subset for the descendant CIDFontType2 and
        embed it on save.

        Mirrors upstream ``PDType0Font.subset()``. The descendant's
        ``/FontFile2`` is replaced with the freshly-built subset, and a
        six-letter random tag is prepended to ``/BaseFont`` (on this
        Type 0 font *and* the descendant's font dictionary) and to
        ``/FontName`` on the descendant's descriptor — per
        PDF 32000-1 §9.6.4.

        Raises ``ValueError`` when no descendant CIDFont is present, the
        descendant lacks an embedded TrueType program, or the descendant
        is not a CIDFontType2 (CIDFontType0 wraps CFF, not TTF — those
        subset through a different code path that fontTools does not
        cover via :class:`TTFSubsetter`).
        """
        from pypdfbox.fontbox.ttf import TTFSubsetter

        from .pd_cid_font_type2 import PDCIDFontType2
        from .pd_true_type_font import (
            _embed_subset_bytes,
            _random_subset_tag,
        )

        descendant = self.get_descendant_font()
        if descendant is None:
            raise ValueError(
                "PDType0Font has no descendant CIDFont; cannot subset"
            )
        if not isinstance(descendant, PDCIDFontType2):
            raise ValueError(
                "subset() supports only TrueType-backed Type 0 fonts "
                "(/Subtype /CIDFontType2); got "
                f"{type(descendant).__name__}"
            )

        ttf = descendant.get_true_type_font()
        if ttf is None:
            raise ValueError(
                "descendant CIDFontType2 has no embedded /FontFile2; "
                "cannot subset"
            )

        codepoints = self._collect_subset_codepoints(text_or_codepoints, used_chars)
        tag = prefix if prefix is not None else _random_subset_tag()

        subsetter = TTFSubsetter(ttf)
        subsetter.add_all(codepoints)
        subsetter.set_prefix(tag)
        subset_bytes = subsetter.to_bytes()

        # Embed onto the descendant (where /FontFile2 lives).
        _embed_subset_bytes(descendant, subset_bytes, tag)
        # Mirror the tag onto our own /BaseFont — per PDF 32000-1 §9.7.6.2
        # the parent and descendant must share the tagged PostScript name.
        from .pd_true_type_font import _BASE_FONT  # noqa: PLC0415

        current_base = self.get_name()
        if current_base:
            if (
                len(current_base) >= 7
                and current_base[6] == "+"
                and current_base[:6].isalpha()
                and current_base[:6].isupper()
            ):
                new_base = current_base
            else:
                new_base = f"{tag}+{current_base}"
            self.get_cos_object().set_name(_BASE_FONT, new_base)

        # Drop the descendant's parsed-TTF cache so subsequent metric
        # lookups re-read the subset bytes.
        descendant._ttf = None  # noqa: SLF001
        self._subset_codepoints.clear()
        return subset_bytes

    def _collect_subset_codepoints(
        self,
        text_or_codepoints: str | Iterable[int] | None,
        used_chars: Iterable[int] | None,
    ) -> set[int]:
        codepoints: set[int] = set(self._subset_codepoints)
        if isinstance(text_or_codepoints, str):
            codepoints.update(ord(ch) for ch in text_or_codepoints)
        elif text_or_codepoints is not None:
            codepoints.update(int(cp) for cp in text_or_codepoints)
        if used_chars is not None:
            codepoints.update(int(cp) for cp in used_chars)
        return codepoints


__all__ = ["PDType0Font"]
