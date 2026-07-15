from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream

from .standard14_fonts import Standard14Fonts

if TYPE_CHECKING:
    from pypdfbox.fontbox.cmap.cmap import CMap
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    from .afm_loader import AfmMetrics
    from .pd_font_descriptor import PDFontDescriptor

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_MISSING_WIDTH: COSName = COSName.get_pdf_name("MissingWidth")
_FONT_FILE: COSName = COSName.get_pdf_name("FontFile")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_IDENTITY_H: COSName = COSName.get_pdf_name("Identity-H")
_IDENTITY_V: COSName = COSName.get_pdf_name("Identity-V")

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
        # Per-code width cache — mirrors upstream's ``codeToWidthMap``.
        # Populated on first call to :meth:`get_width` per code.
        self._code_to_width: dict[int, float] = {}
        # Per-code ``to_unicode`` cache — same shape as ``_code_to_width``
        # but keyed only for the default (``custom_glyph_list is None``)
        # call so the common per-glyph text-extraction path does not
        # re-walk the /ToUnicode CMap + encoding + glyph list on every
        # occurrence of a code. ``None`` is a legitimate result (no
        # mapping), so membership (``code in ...``) — not a ``None``
        # sentinel — distinguishes "cached miss" from "not yet computed".
        self._code_to_unicode: dict[int, str | None] = {}
        # Memoised average font width (mirrors upstream ``avgFontWidth``).
        self._avg_font_width_cached: float | None = None
        # Memoised space width (mirrors upstream ``fontWidthOfSpace``).
        # Sentinel ``None`` means "not yet computed".
        self._font_width_of_space: float | None = None
        # Memoised AFM lookup for Standard 14 fonts. Lazily populated by
        # :meth:`get_standard14_afm` so unused fonts do not pay for the
        # AFM parse.
        self._standard14_afm_loaded: bool = False
        self._standard14_afm: AfmMetrics | None = None

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- font identity ----------

    def get_name(self) -> str | None:
        """``/BaseFont`` — the PostScript / lookup name of the font."""
        return self._dict.get_name_as_string(_BASE_FONT)

    def get_sub_type(self) -> str | None:
        """``/Subtype`` — e.g. ``Type1``, ``TrueType``, ``Type0``.

        Mirrors PDFBox ``PDFont.getSubType`` (note the capital ``T`` in the
        upstream Java spelling, which snake-cases to ``get_sub_type``).
        :meth:`get_subtype` is the older codebase-internal name and now
        delegates here.
        """
        return self._dict.get_name_as_string(_SUBTYPE)

    def get_subtype(self) -> str | None:
        """Codebase-internal alias for :meth:`get_sub_type`. Kept for
        backward compatibility with existing call sites that adopted the
        single-token snake-case form before the upstream-faithful
        ``get_sub_type`` was available."""
        return self.get_sub_type()

    def get_type(self) -> str | None:
        """``/Type`` — always ``"Font"`` for a well-formed font dictionary.

        Mirrors PDFBox ``PDFont.getType``. Returns whatever name is present
        on the underlying dictionary (``None`` if the entry is missing or
        not a name); the constructor writes ``"Font"`` on a fresh dict.
        """
        return self._dict.get_name_as_string(_TYPE)

    # ---------- font descriptor ----------

    def get_font_descriptor(self) -> PDFontDescriptor | None:
        return self.load_font_descriptor()

    def load_font_descriptor(self) -> PDFontDescriptor | None:
        """Read ``/FontDescriptor`` and wrap it as a :class:`PDFontDescriptor`.

        Mirrors upstream ``PDFont.loadFontDescriptor`` (private in Java).
        Returns ``None`` when the entry is absent and the font is not a
        Standard 14 font. For Standard 14 fonts without an explicit
        ``/FontDescriptor`` (the common case — they are unembedded and
        live entirely in the AFM), upstream synthesises a descriptor
        from the AFM via ``PDType1FontEmbedder.buildFontDescriptor``;
        we mirror that path so callers like :class:`PDFText2HTML`'s
        ``FontState`` can introspect bold/italic flags on Standard 14
        fonts.

        Unlike upstream, the wrapper is constructed on each call rather
        than eagerly cached at construction time — pypdfbox's font
        descriptor objects are stateless wrappers, so a fresh instance is
        cheap and avoids stale caching when callers mutate the underlying
        ``COSDictionary``.
        """
        from .pd_font_descriptor import PDFontDescriptor

        fd = self._dict.get_dictionary_object(_FONT_DESCRIPTOR)
        if isinstance(fd, COSDictionary):
            return PDFontDescriptor(fd)
        # Standard 14 fallback — synthesize from the AFM. Matches
        # upstream PDFont.loadFontDescriptor's ``else if (afmStandard14
        # != null)`` branch (PDFont.java:140-144).
        try:
            afm = self.get_standard14_afm()
        except (AttributeError, NotImplementedError, ValueError, OSError):
            afm = None
        if afm is not None:
            from .pd_type1_font_embedder import PDType1FontEmbedder

            try:
                return PDType1FontEmbedder.build_font_descriptor_from_metrics(afm)
            except (AttributeError, TypeError, ValueError):
                return None
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

    def get_widths(self) -> list[float | None]:
        """Return the contents of ``/Widths`` as a list of floats.

        Mirrors PDFBox ``PDFont.getWidths`` which delegates to
        ``COSArray.toCOSNumberFloatList``: every entry maps to its float
        value, and a non-``COSNumber`` entry (a ``null`` or a stray name)
        maps to ``None`` **in place** so the list keeps its length and the
        index of every later entry stays aligned with ``/FirstChar``.
        Returns an empty list when ``/Widths`` is absent.
        """
        arr = self._dict.get_dictionary_object(_WIDTHS)
        if not isinstance(arr, COSArray):
            return []
        widths: list[float | None] = []
        for item in arr:
            if isinstance(item, (COSInteger, COSFloat)):
                widths.append(float(item.value))
            else:
                widths.append(None)
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
        when the font has no usable width entries. Memoised after first
        call, mirroring upstream ``PDFont.getAverageFontWidth``.
        """
        if self._avg_font_width_cached is not None:
            return self._avg_font_width_cached
        widths = self.get_widths()
        non_zero = [w for w in widths if w is not None and w > 0.0]
        if not non_zero:
            self._avg_font_width_cached = 0.0
        else:
            self._avg_font_width_cached = sum(non_zero) / len(non_zero)
        return self._avg_font_width_cached

    def get_space_width(self) -> float:
        """Return the advance width of the space glyph (character code 32).

        Mirrors upstream ``PDFont.getSpaceWidth``: tries the ``/ToUnicode``
        CMap's recorded space mapping first, then ``getStringWidth(" ")``
        (so encoded fonts get the right code), then a direct ``/Widths``
        lookup at offset ``32 - /FirstChar``, then ``getWidthFromFont(32)``,
        finally falling back to ``getAverageFontWidth`` and 250 as the
        ultimate default. Cached on first call.
        """
        if self._font_width_of_space is not None:
            return self._font_width_of_space
        # 1) Use /ToUnicode CMap space mapping when present.
        try:
            if self.has_to_unicode():
                cmap = self.get_to_unicode_cmap()
                if cmap is not None:
                    space_mapping = cmap.get_space_mapping()
                    if space_mapping > -1:
                        try:
                            width = self.get_width(space_mapping)
                            if width > 0:
                                self._font_width_of_space = width
                                return width
                        except (NotImplementedError, OSError, ValueError):
                            pass
            # 2) Try get_string_width(" ") so encoded fonts hit the right code.
            try:
                width = self.get_string_width(" ")
                if width > 0:
                    self._font_width_of_space = width
                    return width
            except (NotImplementedError, OSError, ValueError):
                pass
            # 3) Direct /Widths lookup at code 32.
            widths = self.get_widths()
            if widths:
                first = self.get_first_char()
                if first < 0:
                    first = 0
                index = 32 - first
                if 0 <= index < len(widths):
                    width = widths[index]
                    if width is not None and width > 0.0:
                        self._font_width_of_space = width
                        return width
            # 4) Ask the embedded font program directly.
            try:
                width = self.get_width_from_font(32)
                if width > 0:
                    self._font_width_of_space = width
                    return width
            except (NotImplementedError, OSError, ValueError):
                pass
            # 5) Average font width fallback.
            avg = self.get_average_font_width()
            if avg > 0:
                self._font_width_of_space = avg
                return avg
        except Exception:
            # Mirrors upstream's broad catch — never let space-width
            # calculation propagate; fall through to the 250 default.
            pass
        self._font_width_of_space = _DEFAULT_SPACE_WIDTH
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
        return self._dict.contains_key(_TO_UNICODE)

    def get_to_unicode_cmap(self) -> CMap | None:
        """Return the parsed ``/ToUnicode`` CMap, or ``None`` when absent
        or malformed.

        Mirrors PDFBox ``PDFont.getToUnicodeCMap``. Per PDF 32000-1 §9.10.3
        the entry is either an embedded CMap stream or a predefined CMap
        name (e.g. ``/Identity-H``). Cached on first successful parse so
        repeat calls are O(1). The actual parse is delegated to
        :meth:`load_unicode_cmap` so the cached path stays trivial.
        """
        if self._to_unicode_cmap_loaded:
            return self._to_unicode_cmap
        self._to_unicode_cmap_loaded = True
        self._to_unicode_cmap = self.load_unicode_cmap()
        return self._to_unicode_cmap

    def get_to_unicode_c_map(self) -> CMap | None:
        """Upstream-faithful spelling of :meth:`get_to_unicode_cmap`.

        Mirrors PDFBox ``PDFont.getToUnicodeCMap`` (snake-cased per the
        parity script's run-of-uppercase rule, ``CMap`` → ``c_map``).
        Delegates to :meth:`get_to_unicode_cmap`; both return the same
        cached instance.
        """
        return self.get_to_unicode_cmap()

    def load_unicode_cmap(self) -> CMap | None:
        """Parse the ``/ToUnicode`` entry and return the resulting CMap.

        Mirrors upstream ``PDFont.loadUnicodeCmap`` (private in Java) but
        without the verbose Identity-H/V fixup logging — pypdfbox surfaces
        broken ``/ToUnicode`` CMaps as ``None`` and lets :meth:`to_unicode`
        fall back to the encoding-driven resolver. Returns ``None`` when
        ``/ToUnicode`` is absent, unparseable, or of an unsupported COS
        type.
        """
        raw = self._dict.get_dictionary_object(_TO_UNICODE)
        if raw is None:
            return None
        if isinstance(raw, (COSStream, COSName)):
            try:
                return self.read_c_map(raw)
            except (OSError, ValueError):
                return None
        return None

    def read_c_map(self, base: object) -> CMap | None:
        """Parse a ``/ToUnicode`` source — either a ``COSStream`` carrying
        the CMap text or a ``COSName`` naming a predefined CMap.

        Mirrors upstream ``protected final CMap readCMap(COSBase)``. Raises
        :class:`OSError` when ``base`` is neither a stream nor a name (the
        upstream ``IOException("Expected Name or Stream")`` analogue) so
        callers can distinguish "no CMap" from "wrong COS type". Snake
        case follows the parity script's run-of-uppercase rule:
        ``readCMap`` → ``read_c_map``.
        """
        # Defer the CMap import — keeps the font module's import graph
        # light for callers that never reach for /ToUnicode.
        from pypdfbox.fontbox.cmap import CMapParser

        if isinstance(base, COSStream):
            return CMapParser().parse(base.to_byte_array())
        if isinstance(base, COSName):
            return CMapParser.parse_predefined(base.name)
        raise OSError("Expected Name or Stream")

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

    # ---------- Standard 14 AFM ----------

    def get_standard14_afm(self) -> AfmMetrics | None:
        """Return the AFM for this font when it is one of the Standard 14.

        Mirrors upstream ``PDFont.getStandard14AFM`` (``protected final``):
        a non-``None`` return guarantees AFM-driven width / metrics
        lookups are usable. Result is cached on first call.
        """
        if self._standard14_afm_loaded:
            return self._standard14_afm
        self._standard14_afm_loaded = True
        name = self.get_name()
        if name is None:
            self._standard14_afm = None
            return None
        # Be permissive — only load when the name resolves to a Standard 14
        # canonical name. ``Standard14Fonts.contains_name`` accepts aliases.
        if not Standard14Fonts.contains_name(name):
            self._standard14_afm = None
            return None
        try:
            self._standard14_afm = Standard14Fonts.get_afm(name)
        except (KeyError, OSError, ValueError):
            self._standard14_afm = None
        return self._standard14_afm

    def get_standard14_width(self, code: int) -> float:
        """Glyph advance for ``code`` taken from the Standard 14 AFM.

        Mirrors upstream ``protected abstract float getStandard14Width(int)``.
        The base implementation raises :class:`NotImplementedError`;
        concrete subclasses (``PDType1Font``, ``PDTrueTypeFont``) override
        with subtype-specific glyph-name resolution.
        """
        raise NotImplementedError(
            "get_standard14_width must be implemented by a concrete subclass"
        )

    # ---------- bounding box / position / displacement ----------

    def get_bounding_box(self) -> PDRectangle | None:
        """Return the font's bounding box.

        Mirrors upstream ``PDFontLike.getBoundingBox``. The base
        implementation pulls ``/FontBBox`` from the font descriptor when
        present; subclasses override to read the embedded font program
        directly when more accurate bounds are available.
        """
        fd = self.get_font_descriptor()
        if fd is None:
            return None
        return fd.get_font_bounding_box()

    def get_position_vector(self, code: int) -> tuple[float, float]:
        """Return the position vector ``(x, y)`` for ``code``.

        Mirrors upstream ``PDFont.getPositionVector`` which raises
        ``UnsupportedOperationException`` — horizontal-only fonts have no
        position vector. Vertical-writing subclasses (``PDType0Font`` /
        ``PDCIDFont``) override.
        """
        raise NotImplementedError(
            "Horizontal fonts have no position vector"
        )

    def get_displacement(self, code: int) -> tuple[float, float]:
        """Return the displacement vector ``(w0, w1)`` for ``code`` in
        text space.

        Mirrors upstream ``PDFont.getDisplacement``: horizontal text uses
        only the x component, vertical only the y. The base implementation
        returns ``(get_width(code) / 1000, 0)``; vertical fonts override.
        """
        return (self.get_width(code) / 1000.0, 0.0)

    # ---------- writing-mode / damage / subset ----------

    def is_vertical(self) -> bool:
        """``True`` when the font uses vertical writing mode.

        Mirrors upstream ``abstract boolean isVertical()``. Default
        ``False``; ``PDType0Font`` overrides based on the CMap's writing
        mode entry.
        """
        return False

    def will_be_subset(self) -> bool:
        """``True`` iff this font will be subset when embedded.

        Mirrors upstream ``abstract boolean willBeSubset()``. Base default
        ``False``; ``PDTrueTypeFont`` / ``PDType0Font`` override when
        subsetting is enabled.
        """
        return False

    def add_to_subset(self, code_point: int) -> None:
        """Register ``code_point`` for inclusion in the subsetted font.

        Mirrors upstream ``abstract void addToSubset(int)``. The base
        implementation raises :class:`NotImplementedError`; subclasses
        that support subsetting override.
        """
        raise NotImplementedError(
            "subsetting is not supported for this font subtype"
        )

    def subset(self) -> None:
        """Replace this font with a subset containing the registered codepoints.

        Mirrors upstream ``abstract void subset()``. The base
        implementation raises :class:`NotImplementedError`; subclasses
        that support subsetting override.
        """
        raise NotImplementedError(
            "subsetting is not supported for this font subtype"
        )

    # ---------- widths ----------

    def get_width(self, code: int) -> float:
        """Return the advance width of ``code`` in 1/1000 text-space units.

        Mirrors upstream ``PDFont.getWidth(int)``: tries (in order) the
        per-code cache, the dictionary's ``/Widths`` array offset by
        ``/FirstChar``, the descriptor's ``/MissingWidth``, the Standard
        14 AFM, and finally the embedded font program via
        :meth:`get_width_from_font`. Result is cached per code.

        Note: Acrobat (and PDFBOX-427) prefer the dictionary widths even
        when a font program is embedded, so this method consults the
        dictionary first.
        """
        cached = self._code_to_width.get(code)
        if cached is not None:
            return cached

        # Dictionary-driven widths first (Type 1 / Type 1C / Type 3, and
        # also embedded TrueType per PDFBOX-427).
        if (
            self._dict.get_dictionary_object(_WIDTHS) is not None
            or self._dict.contains_key(_MISSING_WIDTH)
        ):
            first_char = self._dict.get_int(_FIRST_CHAR, -1)
            last_char = self._dict.get_int(_LAST_CHAR, -1)
            widths = self.get_widths()
            idx = code - first_char
            if (
                widths
                and code >= first_char
                and code <= last_char
                and 0 <= idx < len(widths)
            ):
                # A null /Widths slot (non-numeric entry) reads back as 0.0 —
                # mirrors upstream's ``if (width == null) width = 0f`` after
                # ``widths.get(idx)`` (PDFont.getWidth).
                entry = widths[idx]
                width = float(entry) if entry is not None else 0.0
                self._code_to_width[code] = width
                return width
            fd = self.get_font_descriptor()
            if fd is not None:
                width = float(fd.get_missing_width())
                self._code_to_width[code] = width
                return width

        # Standard 14 fonts ship widths via their AFM.
        if self.is_standard14():
            try:
                width = float(self.get_standard14_width(code))
            except NotImplementedError:
                width = 0.0
            self._code_to_width[code] = width
            return width

        # Last resort: ask the embedded font program directly.
        width = float(self.get_width_from_font(code))
        self._code_to_width[code] = width
        return width

    def get_width_from_font(self, code: int) -> float:
        """Return the advance of ``code`` as read from the embedded font program.

        Mirrors upstream ``PDFontLike.getWidthFromFont``. Base
        implementation raises :class:`NotImplementedError`; subclasses
        bound to a concrete font program override.
        """
        raise NotImplementedError(
            "get_width_from_font must be implemented by a concrete subclass"
        )

    def get_height(self, code: int) -> float:
        """Return the height of the glyph at ``code`` in glyph space.

        Mirrors upstream ``PDFontLike.getHeight``. The method is
        deprecated upstream because no consistent value can be returned;
        callers should prefer the bounding-box height. Base
        implementation raises :class:`NotImplementedError`.
        """
        raise NotImplementedError(
            "get_height must be implemented by a concrete subclass"
        )

    def has_explicit_width(self, code: int) -> bool:
        """``True`` iff the dictionary specifies an explicit width for ``code``.

        Mirrors upstream ``PDFontLike.hasExplicitWidth``: the font
        dictionary must carry ``/Widths`` and ``code`` must fall within
        ``[/FirstChar, /FirstChar + len(Widths))``. Default-width
        fallbacks (``/MissingWidth``, ``/DW``) do **not** count.
        """
        if self._dict.get_dictionary_object(_WIDTHS) is None:
            return False
        first_char = self._dict.get_int(_FIRST_CHAR, -1)
        if code < first_char:
            return False
        return code - first_char < len(self.get_widths())

    # ---------- encode / decode / read_code ----------

    def encode(self, text: str) -> bytes:
        """Encode ``text`` to its raw PDF content-stream byte form.

        Mirrors upstream ``public final byte[] encode(String)``: walks the
        codepoints (so surrogate pairs collapse into a single codepoint)
        and concatenates per-codepoint encodings produced by
        :meth:`encode_codepoint`. The base implementation is intended to
        be inherited; subclasses (``PDSimpleFont``, ``PDType0Font``)
        override the whole method when they have a faster bulk path.
        """
        out = bytearray()
        for ch in text:
            out.extend(self.encode_codepoint(ord(ch)))
        return bytes(out)

    def encode_codepoint(self, unicode: int) -> bytes:
        """Encode a single Unicode codepoint to PDF content-stream bytes.

        Mirrors upstream ``protected abstract byte[] encode(int unicode)``
        — renamed in the Python port to avoid colliding with
        :meth:`encode` (the public string-level entry point). Base
        implementation raises :class:`NotImplementedError`.
        """
        raise NotImplementedError(
            "encode_codepoint must be implemented by a concrete subclass"
        )

    def read_code(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
    ) -> tuple[int, int]:
        """Read one character code from ``data`` starting at ``offset``.

        Returns ``(code, bytes_consumed)``. Mirrors upstream
        ``abstract int readCode(InputStream)`` in spirit, but the Python
        port uses a buffer + offset (so the renderer can dispatch through
        a single uniform signature across composite and simple fonts).
        Codes may be 1–4 bytes long depending on the font subtype's CMap.
        Base implementation raises :class:`NotImplementedError`.
        """
        raise NotImplementedError(
            "read_code must be implemented by a concrete subclass"
        )

    def get_string_width(self, text: str) -> float:
        """Return the total advance of ``text`` in 1/1000 text-space units.

        Mirrors upstream ``PDFont.getStringWidth``: encodes ``text`` to
        bytes, then iterates ``read_code`` + ``get_width``. Subclasses
        that have a tight string-level shortcut may override.
        """
        data = self.encode(text)
        total = 0.0
        offset = 0
        n = len(data)
        while offset < n:
            code, consumed = self.read_code(data, offset)
            if consumed <= 0:
                break
            total += self.get_width(code)
            offset += consumed
        return total

    # ---------- to_unicode ----------

    def to_unicode(
        self, code: int, custom_glyph_list: GlyphList | None = None
    ) -> str | None:
        """Resolve ``code`` to its Unicode string via the ``/ToUnicode`` CMap.

        Mirrors upstream ``PDFont.toUnicode(int, GlyphList)``: when the
        font carries a ``/ToUnicode`` entry, the CMap drives the mapping;
        otherwise returns ``None`` so subclasses can plug in encoding-based
        glyph-list resolution. ``custom_glyph_list`` is accepted for
        signature parity with the Java overload — it is unused at this
        level (subclasses such as ``PDSimpleFont`` consume it).

        The Identity-H/V special case from upstream is preserved:
        when the CMap is named ``Identity-*`` the code is returned as a
        single ``chr(code)`` so the undocumented "Identity as ToUnicode"
        pattern keeps working (PDFBOX-3123 / PDFBOX-4322).
        """
        del custom_glyph_list  # base impl ignores; subclasses use it
        # The base resolver ignores ``custom_glyph_list``, so its result is a
        # pure function of ``code`` and the (immutable-after-load) CMap —
        # safe to memoise per code. ``None`` is a real result, so test
        # membership rather than truthiness (mirrors ``_code_to_width`` but
        # caches the miss too).
        if code in self._code_to_unicode:
            return self._code_to_unicode[code]
        result = self._compute_to_unicode(code)
        self._code_to_unicode[code] = result
        return result

    def _compute_to_unicode(self, code: int) -> str | None:
        """Uncached ``/ToUnicode`` CMap resolution for ``code`` — the body of
        the base :meth:`to_unicode`, split out so the cache wrapper stays
        trivial (and so subclasses can reuse it without the cache)."""
        cmap = self.get_to_unicode_cmap()
        if cmap is None:
            return None
        cmap_name = cmap.get_name() if hasattr(cmap, "get_name") else None
        encoding = self._dict.get_dictionary_object(_ENCODING)
        identity_encoded = encoding in (_IDENTITY_H, _IDENTITY_V)
        if (
            cmap_name is not None
            and cmap_name.startswith("Identity-")
            and (
                isinstance(self._dict.get_dictionary_object(_TO_UNICODE), COSName)
                or not cmap.has_unicode_mappings()
                or identity_encoded
            )
        ):
            # Treat the code as a raw UTF-16 code unit — matches upstream's
            # ``new String(new char[] { (char) code })``.
            try:
                return chr(code)
            except ValueError:
                return None
        return cmap.to_unicode(code)

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

    # ---------- upstream-faithful Java spellings ----------

    def equals(self, other: object) -> bool:
        """Snake_case mirror of upstream ``PDFont.equals(Object)`` — see
        ``PDFont.java`` lines 672-676.

        Delegates to :meth:`__eq__`, so ``font.equals(other)`` and
        ``font == other`` always agree. Provided so callers porting from
        PDFBox can use the upstream spelling directly without reaching for
        the Python ``==`` operator.
        """
        return self.__eq__(other) is True

    def hash_code(self) -> int:
        """Snake_case mirror of upstream ``PDFont.hashCode()`` — see
        ``PDFont.java`` lines 678-682.

        Delegates to :meth:`__hash__`. Upstream returns
        ``getCOSObject().hashCode()`` which keys off the dictionary's Java
        reference identity; we key off ``id(self._dict)`` so the same
        identity-based equality is preserved.
        """
        return self.__hash__()

    def to_string(self) -> str:
        """Snake_case mirror of upstream ``PDFont.toString()`` — see
        ``PDFont.java`` lines 684-688.

        Delegates to :meth:`__repr__` so ``font.to_string()`` matches
        ``str(font)``. Format: ``"<ClassName> <BaseFont>"``, falling back
        to the bare class name when ``/BaseFont`` is absent.
        """
        return self.__repr__()


__all__ = ["PDFont"]
