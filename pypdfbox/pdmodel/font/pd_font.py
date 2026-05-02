from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream

from .standard14_fonts import Standard14Fonts

if TYPE_CHECKING:
    from pypdfbox.fontbox.cmap.cmap import CMap

    from .pd_font_descriptor import PDFontDescriptor

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_FONT_FILE: COSName = COSName.get_pdf_name("FontFile")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")

# PDF subset marker: six uppercase letters + '+' prefix on /BaseFont
# (PDF 32000-1 §9.6.4 — "tagged" subset font names).
_SUBSET_RE = re.compile(r"^[A-Z]{6}\+")

# Default space width when the font dictionary cannot supply one. Matches
# upstream PDFBox ``PDFont.getSpaceWidth`` which falls back to 250 (1/4 em
# in 1000-unit coordinates).
_DEFAULT_SPACE_WIDTH: float = 250.0

# Default font matrix per PDF 32000-1 §9.2.4 — maps glyph space (1/1000 em
# units) to text space. Mirrors upstream ``PDFont.DEFAULT_FONT_MATRIX``.
_DEFAULT_FONT_MATRIX: tuple[float, ...] = (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)


class PDFont:
    """Abstract base font wrapper. Mirrors PDFBox ``PDFont``.

    A ``PDFont`` wraps a ``COSDictionary`` whose ``/Type`` is ``/Font``.
    Concrete subclasses set the appropriate ``/Subtype``.
    """

    SUB_TYPE: str | None = None

    # Default 6-element font matrix shared by simple-font subtypes (Type 1,
    # TrueType, etc.). Type 3 fonts override via the ``/FontMatrix`` entry
    # on the dictionary; CIDFonts inherit through their parent Type 0 font.
    DEFAULT_FONT_MATRIX: tuple[float, ...] = _DEFAULT_FONT_MATRIX

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        self._dict = font_dict if font_dict is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _FONT)
        if font_dict is None and self.SUB_TYPE is not None:
            self._dict.set_name(_SUBTYPE, self.SUB_TYPE)
        # Lazy ``/ToUnicode`` CMap parse cache — populated on first call to
        # :meth:`get_to_unicode_cmap`.
        self._to_unicode_cmap: CMap | None = None
        self._to_unicode_cmap_loaded: bool = False

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- font identity ----------

    def get_name(self) -> str | None:
        """``/BaseFont`` — the PostScript / lookup name of the font."""
        return self._dict.get_name(_BASE_FONT)

    def get_subtype(self) -> str | None:
        """``/Subtype`` — e.g. ``Type1``, ``TrueType``, ``Type0``."""
        return self._dict.get_name(_SUBTYPE)

    def get_type(self) -> str | None:
        """``/Type`` — always ``"Font"`` for a well-formed font dictionary.

        Mirrors PDFBox ``PDFont.getType``. Returns whatever name is present
        on the underlying dictionary (``None`` if the entry is missing or
        not a name); the constructor writes ``"Font"`` on a fresh dict.
        """
        return self._dict.get_name(_TYPE)

    # ---------- font descriptor ----------

    def get_font_descriptor(self) -> PDFontDescriptor | None:
        from .pd_font_descriptor import PDFontDescriptor

        fd = self._dict.get_dictionary_object(_FONT_DESCRIPTOR)
        if isinstance(fd, COSDictionary):
            return PDFontDescriptor(fd)
        return None

    def set_font_descriptor(self, font_descriptor: PDFontDescriptor | None) -> None:
        if font_descriptor is None:
            self._dict.remove_item(_FONT_DESCRIPTOR)
            return
        self._dict.set_item(_FONT_DESCRIPTOR, font_descriptor.get_cos_object())

    # ---------- embedding / damage state ----------

    def is_embedded(self) -> bool:
        """``True`` when the font program is embedded in the PDF.

        Mirrors PDFBox ``PDFont.isEmbedded``: a font is embedded when its
        ``/FontDescriptor`` carries any of ``/FontFile`` (Type 1),
        ``/FontFile2`` (TrueType), or ``/FontFile3`` (CFF / OpenType).
        """
        fd = self._dict.get_dictionary_object(_FONT_DESCRIPTOR)
        if not isinstance(fd, COSDictionary):
            return False
        return (
            fd.get_dictionary_object(_FONT_FILE) is not None
            or fd.get_dictionary_object(_FONT_FILE2) is not None
            or fd.get_dictionary_object(_FONT_FILE3) is not None
        )

    def is_damaged(self) -> bool:
        """``True`` when the embedded font program failed to parse.

        Mirrors PDFBox ``PDFont.isDamaged``. The base implementation returns
        ``False``; concrete subclasses override after their parse step has
        had a chance to fail.
        """
        return False

    # ---------- char-range / widths ----------

    def get_widths(self) -> list[float]:
        """Return the contents of ``/Widths`` as a list of floats.

        Mirrors PDFBox ``PDFont.getWidths``. Non-numeric entries are
        skipped. Returns an empty list when ``/Widths`` is absent.
        """
        arr = self._dict.get_dictionary_object(_WIDTHS)
        if not isinstance(arr, COSArray):
            return []
        widths: list[float] = []
        for item in arr:
            if isinstance(item, (COSInteger, COSFloat)):
                widths.append(float(item.value))
        return widths

    def get_first_char(self) -> int:
        """``/FirstChar`` — first character code in ``/Widths``. Default ``-1``."""
        return self._dict.get_int(_FIRST_CHAR, -1)

    def get_last_char(self) -> int:
        """``/LastChar`` — last character code in ``/Widths``. Default ``-1``."""
        return self._dict.get_int(_LAST_CHAR, -1)

    def get_average_font_width(self) -> float:
        """Return the average glyph advance for this font in thousandths of an em.

        Computed as the arithmetic mean of the positive entries in
        ``/Widths``; zero-width entries (typically ``.notdef`` slots) are
        skipped to avoid dragging the mean toward zero. Returns ``0.0``
        when the font has no usable width entries.
        """
        widths = self.get_widths()
        non_zero = [w for w in widths if w > 0.0]
        if not non_zero:
            return 0.0
        return sum(non_zero) / len(non_zero)

    def get_space_width(self) -> float:
        """Return the advance width of the space glyph (character code 32).

        Looks up code 32 in ``/Widths`` (offset by ``/FirstChar``). When
        unavailable, falls back to 250 (the upstream PDFBox default).
        """
        widths = self.get_widths()
        if widths:
            first = self.get_first_char()
            if first < 0:
                first = 0
            index = 32 - first
            if 0 <= index < len(widths):
                width = widths[index]
                if width > 0.0:
                    return width
        return _DEFAULT_SPACE_WIDTH

    # ---------- font matrix ----------

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element font matrix that maps glyph space to text
        space. Mirrors PDFBox ``PDFont.getFontMatrix``.

        Defaults to ``[0.001, 0, 0, 0.001, 0, 0]`` per PDF 32000-1 §9.2.4 —
        the simple-font (Type 1 / TrueType) standard. ``PDType3Font``
        overrides to read the dictionary's ``/FontMatrix`` entry which
        carries the per-font glyph-procedure transform.
        """
        return list(self.DEFAULT_FONT_MATRIX)

    # ---------- /ToUnicode (CMap) ----------

    def has_to_unicode(self) -> bool:
        """``True`` iff the font dictionary carries a ``/ToUnicode`` entry.

        Mirrors PDFBox's ``dict.containsKey(COSName.TO_UNICODE)`` predicate
        used internally before reaching for :meth:`get_to_unicode_cmap`.
        Cheap probe that does not parse the CMap.
        """
        return self._dict.get_dictionary_object(_TO_UNICODE) is not None

    def get_to_unicode_cmap(self) -> CMap | None:
        """Return the parsed ``/ToUnicode`` CMap, or ``None`` when absent
        or malformed.

        Mirrors PDFBox ``PDFont.getToUnicodeCMap``. Per PDF 32000-1 §9.10.3
        the entry is either an embedded CMap stream or a predefined CMap
        name (e.g. ``/Identity-H``). Cached on first successful parse so
        repeat calls are O(1).
        """
        if self._to_unicode_cmap_loaded:
            return self._to_unicode_cmap
        self._to_unicode_cmap_loaded = True

        raw = self._dict.get_dictionary_object(_TO_UNICODE)
        if raw is None:
            self._to_unicode_cmap = None
            return None

        # Defer the CMap import — keeps the font module's import graph
        # light for callers that never reach for /ToUnicode.
        from pypdfbox.fontbox.cmap import CMapParser

        if isinstance(raw, COSStream):
            try:
                self._to_unicode_cmap = CMapParser().parse(raw.to_byte_array())
            except (OSError, ValueError):
                self._to_unicode_cmap = None
        elif isinstance(raw, COSName):
            try:
                self._to_unicode_cmap = CMapParser.parse_predefined(raw.name)
            except OSError:
                self._to_unicode_cmap = None
        else:
            self._to_unicode_cmap = None
        return self._to_unicode_cmap

    # ---------- Standard 14 ----------

    def is_standard14(self) -> bool:
        """``True`` iff this font is one of the 14 PDF Standard fonts.

        Mirrors PDFBox ``PDFont.isStandard14``: an embedded font is *never*
        treated as Standard 14 (the embedded program wins regardless of
        the name), otherwise the ``/BaseFont`` name (or a known alias) is
        looked up via :meth:`Standard14Fonts.contains_name`. Acrobat
        applies this rule per PDFBOX-2372.

        Concrete subclasses (``PDType0Font``, ``PDType3Font``) that can
        never be Standard 14 override this to return ``False`` directly.
        ``PDSimpleFont`` overrides to additionally exclude fonts whose
        ``/Encoding`` carries a non-trivial ``/Differences`` overlay.
        """
        if self.is_embedded():
            return False
        return Standard14Fonts.contains_name(self.get_name())

    # ---------- subset detection ----------

    def is_subset(self) -> bool:
        """``True`` when ``/BaseFont`` carries the six-letter subset prefix.

        PDF 32000-1 §9.6.4 specifies that a subsetted font's ``/BaseFont``
        is prefixed with six uppercase letters followed by ``+`` (e.g.
        ``ABCDEF+Helvetica``). Mirrors PDFBox ``PDFont.isSubset``.
        """
        name = self.get_name()
        if not name:
            return False
        return _SUBSET_RE.match(name) is not None

    # ---------- identity / repr ----------

    def __eq__(self, other: object) -> bool:
        """Two ``PDFont`` wrappers compare equal iff they wrap the *same*
        underlying ``COSDictionary`` instance.

        Mirrors PDFBox ``PDFont.equals`` which uses ``getCOSObject() ==``
        (Java reference identity). This is intentionally narrower than a
        deep-equality check — two distinct dicts with identical contents
        are *not* equal because they may diverge under later mutation.
        """
        return isinstance(other, PDFont) and other.get_cos_object() is self._dict

    def __hash__(self) -> int:
        """Hash by the underlying ``COSDictionary``'s identity. Matches
        the equality rule above so ``PDFont`` is usable as a dict key."""
        return id(self._dict)

    def __repr__(self) -> str:
        """``<ClassName> <BaseFont>`` — mirrors PDFBox ``PDFont.toString``.

        Falls back to the bare class name when ``/BaseFont`` is absent.
        """
        name = self.get_name()
        if name is None:
            return type(self).__name__
        return f"{type(self).__name__} {name}"

    __str__ = __repr__


__all__ = ["PDFont"]
