from __future__ import annotations

import logging
import weakref
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList

from .encoding import (
    DictionaryEncoding,
    Encoding,
    MacRomanEncoding,
    StandardEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)
from .pd_font import PDFont
from .pd_font_descriptor import (
    FLAG_ALL_CAP,
    FLAG_FIXED_PITCH,
    FLAG_FORCE_BOLD,
    FLAG_ITALIC,
    FLAG_SCRIPT,
    FLAG_SERIF,
    FLAG_SMALL_CAP,
    FLAG_SYMBOLIC,
)
from .standard14_fonts import Standard14Fonts

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_BASE_ENCODING: COSName = COSName.get_pdf_name("BaseEncoding")

_LOG = logging.getLogger(__name__)

# Per-encoding (unicode -> code) reverse cache. Keyed by the typed Encoding
# instance itself (via a WeakKeyDictionary) so the same singleton is shared
# across PDSimpleFont instances and DictionaryEncoding instances naturally get
# their own entry. A plain ``id(encoding)`` key is unsafe: CPython recycles
# id() values once an object is garbage-collected, so a GC'd encoding whose
# address is reused by a new encoding would return the stale reverse map.
# WeakKeyDictionary auto-evicts the entry when the encoding is collected.
_REVERSE_CACHE: weakref.WeakKeyDictionary[Encoding, dict[str, int]] = (
    weakref.WeakKeyDictionary()
)


def _glyph_list_for(encoding: Encoding) -> GlyphList:
    """Pick the glyph-list flavour matching the encoding (Zapf vs AGL)."""
    if isinstance(encoding, ZapfDingbatsEncoding):
        return GlyphList.ZAPF_DINGBATS
    return GlyphList.DEFAULT


def _build_unicode_to_code(encoding: Encoding) -> dict[str, int]:
    glyph_list = _glyph_list_for(encoding)
    out: dict[str, int] = {}
    # Iterate code -> name (rather than name -> code) so that the *first*
    # code wins when several names map to the same unicode point — this
    # matches the lowest-code-first behaviour expected by writers.
    for code, name in sorted(encoding.get_code_to_name_map().items()):
        unicode = glyph_list.to_unicode(name)
        if unicode is None:
            continue
        out.setdefault(unicode, code)
    return out


def _unicode_to_code_map(encoding: Encoding) -> dict[str, int]:
    cached = _REVERSE_CACHE.get(encoding)
    if cached is None:
        cached = _build_unicode_to_code(encoding)
        _REVERSE_CACHE[encoding] = cached
    return cached


class PDSimpleFont(PDFont):
    """Abstract intermediate base for Type1 / TrueType / Type3 fonts.

    Mirrors PDFBox ``PDSimpleFont``. Adds ``/FirstChar``, ``/LastChar``,
    ``/Widths``, and ``/Encoding`` accessors plus the ``encode`` / ``decode``
    helpers that round-trip Python ``str`` <-> raw byte strings via the
    typed ``Encoding`` and the Adobe glyph list.
    """

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        self._encoding_typed: Encoding | None = None
        self._encoding_resolved: bool = False
        # Track codes we have already warned about — avoids spamming the
        # log when the same unmapped code is seen many times. Mirrors
        # upstream's ``noUnicode`` set in ``PDSimpleFont``.
        self._no_unicode: set[int] = set()
        # Glyph-list flavour used by ``to_unicode``; populated by
        # ``read_encoding`` / ``assign_glyph_list`` (mirrors upstream's
        # protected ``glyphList`` field). ``None`` here specifically means
        # "not explicitly assigned" — ``get_glyph_list`` keys off that — so
        # the *derived* memo (below) lives in a separate field to preserve
        # the distinction.
        self._glyph_list: GlyphList | None = None
        # Memo for the value ``get_glyph_list`` derives when ``_glyph_list``
        # was never explicitly assigned. Upstream stores the assignGlyphList
        # result once and never recomputes; the derived branch here is called
        # per glyph from ``to_unicode``, so cache it too. ``None`` = not yet
        # derived.
        self._derived_glyph_list: GlyphList | None = None

    # ---------- char-range / widths ----------

    def get_first_char(self) -> int:
        return self._dict.get_int(_FIRST_CHAR, -1)

    def get_last_char(self) -> int:
        return self._dict.get_int(_LAST_CHAR, -1)

    def get_widths(self) -> list[float | None]:
        # Mirrors upstream ``PDFont.getWidths`` via
        # ``COSArray.toCOSNumberFloatList``: a non-numeric entry maps to
        # ``None`` in place so the list keeps its length and the index of
        # every later entry stays aligned with ``/FirstChar``.
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

    def set_first_char(self, value: int | None) -> None:
        """Set or clear ``/FirstChar`` on the font dictionary."""
        if value is None:
            self._dict.remove_item(_FIRST_CHAR)
            return
        self._dict.set_int(_FIRST_CHAR, int(value))

    def set_last_char(self, value: int | None) -> None:
        """Set or clear ``/LastChar`` on the font dictionary."""
        if value is None:
            self._dict.remove_item(_LAST_CHAR)
            return
        self._dict.set_int(_LAST_CHAR, int(value))

    def set_widths(self, values: list[float] | None) -> None:
        """Replace or clear the ``/Widths`` array."""
        if values is None:
            self._dict.remove_item(_WIDTHS)
            return
        self._dict.set_item(_WIDTHS, COSArray([COSFloat(float(v)) for v in values]))

    # ---------- /FontDescriptor /Flags accessors ----------
    #
    # Thin wrappers around ``get_font_descriptor()`` + the flag-bit constants
    # in :mod:`pd_font_descriptor`. Mirrors the convenience accessors on
    # upstream ``PDFontLike`` / ``PDFontDescriptor``. Each returns ``False``
    # when the font has no ``/FontDescriptor`` (i.e. defaults are absent =
    # nonsymbolic / non-italic / non-bold per PDF 32000-1 §9.8.2).
    #
    # ``is_symbolic`` is the only bit upstream documents as defaulting to
    # *True* when ambiguous (some viewers assume nonsymbolic when /Flags is
    # missing); we follow the user contract here and return False when no
    # descriptor is present.
    #
    # ``is_bold`` has no dedicated /Flags bit in PDF 32000-1 — boldness is
    # signalled via the font name (e.g. ``-Bold``) or ``/FontWeight >= 700``
    # on the descriptor. ``is_force_bold`` reads the dedicated bit 19
    # (1<<18 = 262144) which forces bold rendering at small sizes.

    def _flag(self, mask: int) -> bool:
        fd = self.get_font_descriptor()
        if fd is None:
            return False
        return bool(fd.get_flags() & mask)

    def is_symbolic(self) -> bool:
        return self._flag(FLAG_SYMBOLIC)

    def is_italic(self) -> bool:
        return self._flag(FLAG_ITALIC)

    def is_bold(self) -> bool:
        # No dedicated /Flags bit — derive from /FontWeight (>=700 = bold)
        # per PDF 32000-1 §9.8.1 Table 122.
        fd = self.get_font_descriptor()
        if fd is None:
            return False
        return fd.get_font_weight() >= 700

    def is_fixed_pitch(self) -> bool:
        return self._flag(FLAG_FIXED_PITCH)

    def is_serif(self) -> bool:
        return self._flag(FLAG_SERIF)

    def is_script(self) -> bool:
        return self._flag(FLAG_SCRIPT)

    def is_force_bold(self) -> bool:
        return self._flag(FLAG_FORCE_BOLD)

    def is_all_cap(self) -> bool:
        return self._flag(FLAG_ALL_CAP)

    def is_small_cap(self) -> bool:
        return self._flag(FLAG_SMALL_CAP)

    # ---------- Standard 14 ----------

    def is_standard_14(self) -> bool:
        """``True`` iff this font is one of the 14 PDF Standard fonts.

        Mirrors PDFBox ``PDSimpleFont.isStandard14``: in addition to the
        base ``PDFont`` check (not embedded + ``/BaseFont`` matches a
        canonical / alias name), an ``/Encoding`` carrying a non-trivial
        ``/Differences`` overlay disqualifies the font — see PDFBOX-2372,
        PDFBOX-1900, and the PDFBOX-2192 file. ``/Differences`` entries
        that simply restate the base encoding's mapping are ignored.
        """
        if not super().is_standard14():
            return False
        encoding = self.get_encoding_typed()
        if isinstance(encoding, DictionaryEncoding):
            differences = encoding.get_differences()
            if differences:
                base = encoding.get_base_encoding()
                if base is None:
                    return False
                for code, name in differences.items():
                    if name != base.get_name(code):
                        return False
        return True

    # Upstream's canonical name is ``isStandard14`` (no underscore between
    # 14 and the rest); expose both spellings so callers porting from
    # PDFBox find what they expect. Snake-cased per house style.
    def is_standard14(self) -> bool:
        return self.is_standard_14()

    def get_average_font_width(self) -> float:
        """Return the average glyph advance for this font in *thousandths
        of an em* (the same scale upstream's ``getAverageFontWidth``
        returns). Computed as the arithmetic mean of the entries in
        ``/Widths``; zero-width entries (typically ``.notdef`` slots) are
        skipped because they would otherwise drag the mean toward zero
        for sparsely-mapped fonts. Returns ``0.0`` when the font has no
        ``/Widths`` array or every entry is zero — callers should use
        their own fallback in that case.
        """
        widths = self.get_widths()
        non_zero = [w for w in widths if w is not None and w > 0.0]
        if not non_zero:
            return 0.0
        return sum(non_zero) / len(non_zero)

    # ---------- encoding ----------

    def get_encoding(self) -> COSBase | None:
        """Raw ``/Encoding`` entry — a ``COSName`` for predefined encodings,
        a ``COSDictionary`` for ``/Differences``-style overrides, or ``None``."""
        return self._dict.get_dictionary_object(_ENCODING)

    def get_encoding_typed(self) -> Encoding | None:
        """Resolve ``/Encoding`` to a typed :class:`Encoding`.

        Returns ``None`` when the font has no ``/Encoding`` entry. The
        resolved instance is cached on first access.
        """
        if self._encoding_resolved:
            return self._encoding_typed
        raw = self.get_encoding()
        if isinstance(raw, COSName):
            # Mirror upstream PDSimpleFont.readEncoding for the name branch:
            # a non-embedded ZapfDingbats ignores the declared name and uses
            # its built-in (PDFBOX-/PDF.js 16464), and an UNKNOWN name falls
            # back to the font program's built-in encoding via
            # ``read_encoding_from_font`` (it does NOT leave the encoding
            # null). Both carve-outs were already present in the eager
            # ``read_encoding`` path; the lazy accessor used to set
            # ``Encoding.get_instance(raw)`` directly, leaving every unknown
            # name (e.g. /PDFDocEncoding, a typo'd name) resolving to None —
            # which diverged from Java (verified live, wave 1516).
            if (
                self.get_name() == Standard14Fonts.ZAPF_DINGBATS
                and not self.is_embedded()
            ):
                self._encoding_typed = ZapfDingbatsEncoding.INSTANCE
            else:
                resolved = Encoding.get_instance(raw)
                if resolved is None:
                    _LOG.warning("Unknown encoding: %s", raw.name)
                    # Guard re-entrancy the same way the ``raw is None``
                    # branch does: ``read_encoding_from_font`` may consult
                    # ``is_standard14()`` -> ``get_encoding_typed``.
                    self._encoding_resolved = True
                    resolved = self.read_encoding_from_font()
                self._encoding_typed = resolved
        elif isinstance(raw, COSDictionary):
            # Mirror upstream PDSimpleFont.readEncoding for the dictionary
            # branch: a /Differences encoding without a (valid) /BaseEncoding
            # must still resolve a base — StandardEncoding for non-symbolic
            # fonts, the font program's built-in for symbolic fonts. Passing
            # only ``font_encoding=`` selects DictionaryEncoding's Type-3
            # form (base == None), which is wrong for Type1/TrueType simple
            # fonts and left every non-overridden code as ".notdef".
            symbolic = self.get_symbolic_flag()
            base_encoding_raw = raw.get_dictionary_object(_BASE_ENCODING)
            base_encoding = (
                base_encoding_raw if isinstance(base_encoding_raw, COSName) else None
            )
            has_valid_base = (
                base_encoding is not None
                and Encoding.get_instance(base_encoding) is not None
            )
            built_in: Encoding | None = None
            if not has_valid_base and symbolic is True:
                built_in = self.read_encoding_from_font()
            is_non_symbolic = not bool(symbolic) if symbolic is not None else True
            self._encoding_typed = DictionaryEncoding(
                font_encoding=raw,
                is_non_symbolic=is_non_symbolic,
                built_in=built_in,
            )
        elif raw is None:
            # No /Encoding entry at all. Upstream PDFBox's
            # PDSimpleFont.readEncoding falls back to readEncodingFromFont()
            # here for *every* such font — embedded or not — so the font
            # program's built-in encoding surfaces through getEncoding(). This
            # matters in two distinct ways:
            #
            #   * Non-embedded Standard 14 (the wave-1431 case): the AFM
            #     metric path (PDType1Font.getStandard14Width) reads the
            #     per-glyph advance through that encoding, so without it every
            #     code collapses to the 250-unit substitute width.
            #   * Embedded simple fonts (the wave-1434 case): every code
            #     resolved to ``None`` glyph name, so PDType1Font's render
            #     path dropped the glyph and the page came out blank. PDFBox
            #     surfaces the program's built-in (Type1Encoding for an
            #     embedded Type1, the post-table-derived BuiltInEncoding —
            #     or StandardEncoding for non-symbolic — for an embedded
            #     TrueType), verified against the live oracle
            #     (BuiltinEncodingProbe): 65->A, 66->B, 67->C for both.
            #
            # ``read_encoding_from_font`` still returns ``None`` for the
            # genuinely-encoding-less cases PDFBox also leaves null (e.g. a
            # non-embedded TrueType whose only fallback would be a
            # Type1Encoding-from-AFM we don't port); the None contract is
            # preserved by deferring entirely to the per-subclass helper
            # rather than gating on font identity here.
            #
            # Set ``_encoding_resolved`` *before* the call: TrueType's
            # ``read_encoding_from_font`` consults ``is_standard14()`` for the
            # symbolic branch, which re-enters ``get_encoding_typed`` — the
            # flag makes the re-entrant call return the in-progress value
            # instead of recursing. (For embedded fonts the PDSimpleFont
            # ``is_standard_14`` override short-circuits on the not-embedded
            # base check before it ever reads the encoding, but the guard
            # keeps the contract robust for every path.)
            self._encoding_resolved = True
            self._encoding_typed = self.read_encoding_from_font()
            return self._encoding_typed
        else:
            # /Encoding is present but neither a COSName nor a COSDictionary
            # (e.g. a stray COSInteger). Upstream PDSimpleFont.readEncoding
            # nests the name/dictionary tests inside ``if (encoding != null)``
            # with no else, so a present-but-malformed /Encoding leaves
            # ``encoding`` null — it does NOT fall back to the font program.
            # Mirror that: return None rather than synthesising a built-in.
            self._encoding_typed = None
        self._encoding_resolved = True
        return self._encoding_typed

    def assign_glyph_list(self, font_name: str | None) -> None:
        """Pick the glyph-list flavour for ``font_name``.

        Mirrors upstream ``PDSimpleFont.assignGlyphList(FontName)``: a
        Standard 14 ``ZapfDingbats`` (after canonical-name mapping)
        selects the Zapf glyph list, anything else uses the Adobe Glyph
        List (AGL). Stores the result on the instance so subsequent
        ``to_unicode`` / ``get_glyph_list`` calls reuse it.
        """
        mapped = Standard14Fonts.get_mapped_font_name(font_name) if font_name else None
        if mapped == Standard14Fonts.ZAPF_DINGBATS:
            self._glyph_list = GlyphList.ZAPF_DINGBATS
        else:
            self._glyph_list = GlyphList.DEFAULT

    def read_encoding(self) -> None:
        """Resolve ``/Encoding`` from the dict, the embedded program, or
        a synthetic fallback.

        Mirrors upstream ``PDSimpleFont.readEncoding``: subclass
        constructors call this at the end of their init so that
        ``getName()`` / ``isEmbedded()`` are already populated. The
        method:

        * Resolves a name-only ``/Encoding`` via :class:`Encoding` (with
          the ZapfDingbats-when-not-embedded carve-out from PDFBOX issue
          16464 / PDF.js 16464).
        * Resolves a dictionary ``/Encoding`` to a
          :class:`DictionaryEncoding`, asking the embedded program for a
          built-in encoding when the descriptor is symbolic and the
          ``/BaseEncoding`` is missing or unknown.
        * Falls back to ``read_encoding_from_font`` when no ``/Encoding``
          entry is present.
        * Always finishes by calling :meth:`assign_glyph_list` with the
          canonical Standard 14 name (e.g. ``"Symbol,Italic"`` →
          ``"Symbol"``).
        """
        encoding_base = self._dict.get_dictionary_object(_ENCODING)
        if isinstance(encoding_base, COSName):
            if (
                self.get_name() == Standard14Fonts.ZAPF_DINGBATS
                and not self.is_embedded()
            ):
                # PDFBOX-/PDF.js issue 16464: ignore the declared encoding
                # for a non-embedded ZapfDingbats and use the built-in.
                self._encoding_typed = ZapfDingbatsEncoding.INSTANCE
            else:
                resolved = Encoding.get_instance(encoding_base)
                if resolved is None:
                    _LOG.warning("Unknown encoding: %s", encoding_base.name)
                    resolved = self.read_encoding_from_font()
                self._encoding_typed = resolved
        elif isinstance(encoding_base, COSDictionary):
            built_in: Encoding | None = None
            symbolic = self.get_symbolic_flag()
            base_encoding_raw = encoding_base.get_dictionary_object(_BASE_ENCODING)
            base_encoding = (
                base_encoding_raw if isinstance(base_encoding_raw, COSName) else None
            )
            has_valid_base = (
                base_encoding is not None
                and Encoding.get_instance(base_encoding) is not None
            )
            if not has_valid_base and symbolic is True:
                built_in = self.read_encoding_from_font()
            is_non_symbolic = not bool(symbolic) if symbolic is not None else True
            self._encoding_typed = DictionaryEncoding(
                font_encoding=encoding_base,
                is_non_symbolic=is_non_symbolic,
                built_in=built_in,
            )
        else:
            self._encoding_typed = self.read_encoding_from_font()
        self._encoding_resolved = True
        # Normalise the Standard 14 name and pick the glyph list.
        standard14_name = Standard14Fonts.get_mapped_font_name(self.get_name())
        self.assign_glyph_list(standard14_name)

    @abstractmethod
    def read_encoding_from_font(self) -> Encoding | None:
        """Synthesise an :class:`Encoding` from the embedded font program.

        Mirrors upstream ``protected abstract Encoding
        readEncodingFromFont()``: called by :meth:`read_encoding` when
        the font dict has no ``/Encoding`` entry, an unknown encoding
        name, or a symbolic-with-no-base-encoding ``/Differences`` dict.
        Concrete subclasses (Type1 / TrueType / Type3) override.
        """
        raise NotImplementedError(
            "read_encoding_from_font must be implemented by a concrete subclass"
        )

    @abstractmethod
    def get_path(self, name: str) -> Any:  # noqa: ANN401  (upstream returns GeneralPath)
        """Return the glyph outline for ``name``.

        Mirrors upstream ``public abstract GeneralPath getPath(String)``.
        Concrete subclasses return a list of contour tuples (Type1),
        TrueType glyph paths, or a Type3 ``PDType3CharProc`` rendering
        — see each subclass for the concrete return type.
        """
        raise NotImplementedError(
            "get_path must be implemented by a concrete subclass"
        )

    @abstractmethod
    def has_glyph(self, name: str) -> bool:
        """Return ``True`` when the font program contains ``name``.

        Mirrors upstream ``public abstract boolean hasGlyph(String)``.
        Subclasses may also accept an integer code (Type 3 keys glyphs by
        code, TrueType keys by GID); the canonical signature mirrored
        here uses the glyph name.
        """
        raise NotImplementedError(
            "has_glyph must be implemented by a concrete subclass"
        )

    @abstractmethod
    def get_font_box_font(self) -> Any:  # noqa: ANN401  (upstream returns FontBoxFont)
        """Return the embedded or system font used for rendering.

        Mirrors upstream ``public abstract FontBoxFont getFontBoxFont()``.
        Concrete subclasses surface the parsed ``Type1Font`` /
        ``CFFFont`` / ``TrueTypeFont`` for the program backing this PDF
        font. Never ``None`` upstream — callers that need a tri-state
        should use the subclass-typed accessors.
        """
        raise NotImplementedError(
            "get_font_box_font must be implemented by a concrete subclass"
        )

    def get_standard14_width(self, code: int) -> float:
        """Glyph advance for ``code`` taken from the Standard 14 AFM.

        Mirrors upstream ``protected final float getStandard14Width(int)``:

        * Looks up the glyph name for ``code`` via :meth:`get_encoding`.
        * Maps PDFBox-2334's ``.notdef`` to the Acrobat-observed 250 (the
          Adobe AFMs do not declare ``.notdef``).
        * Maps PDFBox-4944 ``nbspace`` → ``space`` and PDFBox-5115
          ``sfthyphen`` → ``hyphen`` (both glyphs have the typographic
          width of their counterparts but are missing from the AFMs).

        Raises :class:`RuntimeError` when the font is not Standard 14
        (mirrors upstream's ``IllegalStateException``).
        """
        afm = self.get_standard14_afm()
        if afm is None:
            raise RuntimeError("No AFM")
        encoding = self.get_encoding_typed()
        name = encoding.get_name(code) if encoding is not None else ".notdef"
        if name == ".notdef":
            return 250.0
        if name == "nbspace":
            name = "space"
        elif name == "sfthyphen":
            name = "hyphen"
        return float(afm.get_character_width(name))

    def get_glyph_list(self) -> GlyphList:
        """Return the glyph-list flavour the font should use.

        Mirrors upstream ``PDSimpleFont.getGlyphList`` together with
        ``assignGlyphList(FontName)``: ``ZapfDingbats`` (canonical name or
        alias) and a ``ZapfDingbatsEncoding`` both select the Zapf list,
        anything else uses the Adobe Glyph List (AGL). Returning the
        public AGL singleton when no encoding is resolved keeps callers
        from having to test for ``None``.
        """
        # Honour an explicit ``assign_glyph_list`` call (upstream stores
        # the result on the instance and never recomputes).
        if self._glyph_list is not None:
            return self._glyph_list
        # Reuse the previously-derived value — this branch is hit per glyph
        # from ``to_unicode`` and the inputs (font name + typed encoding)
        # never change after load, so the result is stable.
        if self._derived_glyph_list is not None:
            return self._derived_glyph_list
        # Standard 14 ZapfDingbats wins regardless of /Encoding (matches
        # upstream's name-based ``assignGlyphList``).
        mapped = Standard14Fonts.get_mapped_font_name(self.get_name())
        if mapped == Standard14Fonts.ZAPF_DINGBATS:
            derived = GlyphList.ZAPF_DINGBATS
        else:
            encoding = self.get_encoding_typed()
            if isinstance(encoding, ZapfDingbatsEncoding):
                derived = GlyphList.ZAPF_DINGBATS
            else:
                derived = GlyphList.DEFAULT
        self._derived_glyph_list = derived
        return derived

    # ---------- symbolic detection ----------

    def get_symbolic_flag(self) -> bool | None:
        """Return the ``/Symbolic`` flag from ``/FontDescriptor`` or
        ``None`` when the font has no descriptor.

        Mirrors upstream ``PDSimpleFont.getSymbolicFlag``: the Java
        method returns ``Boolean`` (a tri-state) so callers can
        distinguish "definitely nonsymbolic" from "no descriptor at all"
        — the latter is a hint to inspect the encoding instead. The
        upstream comment notes the flag itself defaults to ``false`` when
        absent so a ``False`` result is not always trustworthy; that is a
        property of the descriptor, not this method.
        """
        fd = self.get_font_descriptor()
        if fd is None:
            return None
        return fd.is_symbolic()

    def is_font_symbolic(self) -> bool | None:
        """Tri-state symbolic detection.

        Mirrors upstream ``PDSimpleFont.isFontSymbolic``: returns the
        descriptor's ``/Symbolic`` flag when present; otherwise inspects
        the font name (Standard 14 ``Symbol`` / ``ZapfDingbats`` are
        always symbolic) and the encoding (the three Latin encodings —
        WinAnsi, MacRoman, Standard — guarantee nonsymbolic; a
        ``DictionaryEncoding`` whose ``/Differences`` only references
        names from the Latin character sets is also nonsymbolic).
        Returns ``None`` when no determination can be made — the caller
        should default conservatively (upstream's ``isSymbolic``
        defaults to ``True``).
        """
        flag = self.get_symbolic_flag()
        if flag is not None:
            return flag
        if self.is_standard14():
            mapped = Standard14Fonts.get_mapped_font_name(self.get_name())
            return mapped in (Standard14Fonts.SYMBOL, Standard14Fonts.ZAPF_DINGBATS)
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        if isinstance(encoding, (WinAnsiEncoding, MacRomanEncoding, StandardEncoding)):
            return False
        if isinstance(encoding, DictionaryEncoding):
            for name in encoding.get_differences().values():
                if name == ".notdef":
                    continue
                if not (
                    WinAnsiEncoding.INSTANCE.contains_name(name)
                    and MacRomanEncoding.INSTANCE.contains_name(name)
                    and StandardEncoding.INSTANCE.contains_name(name)
                ):
                    return True
            return False
        return None

    # ---------- code -> unicode (per character) ----------

    def to_unicode(
        self, code: int, custom_glyph_list: GlyphList | None = None
    ) -> str | None:
        """Resolve a single character code to its unicode string.

        Mirrors upstream ``PDSimpleFont.toUnicode(int)`` and
        ``toUnicode(int, GlyphList)``: tries the font's ``/ToUnicode``
        CMap first (so explicit CMap overrides win), then maps the code
        to a glyph name via the font's encoding and looks the name up in
        the glyph list. ``custom_glyph_list`` overrides the AGL but is
        ignored when this font is bound to the Zapf glyph list (matches
        upstream's "don't break Zapf Dingbats" guard). Returns ``None``
        when no mapping can be produced.
        """
        # Per-code memo for the default (no custom glyph list) path — the
        # hot text-extraction case. ``custom_glyph_list`` changes the result
        # and is not part of the key, so only the default call is cached;
        # ``None`` is a real result so membership distinguishes miss from
        # cached-None (mirrors ``PDFont._code_to_unicode`` / ``_code_to_width``).
        if custom_glyph_list is None and code in self._code_to_unicode:
            return self._code_to_unicode[code]
        result = self._resolve_unicode(code, custom_glyph_list)
        if custom_glyph_list is None:
            self._code_to_unicode[code] = result
        return result

    def _resolve_unicode(
        self, code: int, custom_glyph_list: GlyphList | None
    ) -> str | None:
        """Uncached body of :meth:`to_unicode` — factored out so the cache
        wrapper stays trivial and the default path shares one code walk."""
        # /ToUnicode CMap wins when present. Reuse the base font's uncached
        # CMap resolver rather than calling ``cmap.to_unicode`` directly: it
        # carries upstream's Identity-as-ToUnicode fixup (PDFBOX-3123 /
        # PDFBOX-4322 / PDFBOX-3550) where a ``/ToUnicode`` that is an Identity
        # CMap — a ``COSName`` /Identity-H or a stream whose CMap has no Unicode
        # mappings — maps each code to itself (``chr(code)``) rather than
        # falling through to the encoding. Upstream ``PDSimpleFont.toUnicode``
        # likewise starts with ``super.toUnicode``.
        mapped = self._compute_to_unicode(code)
        if mapped is not None:
            return mapped
        # Don't override Zapf's glyph list — upstream guard.
        font_glyph_list = self.get_glyph_list()
        if custom_glyph_list is not None and font_glyph_list is GlyphList.DEFAULT:
            unicode_glyph_list = custom_glyph_list
        else:
            unicode_glyph_list = font_glyph_list
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        name = encoding.get_name(code)
        return unicode_glyph_list.to_unicode(name)

    # ---------- text <-> bytes ----------

    def encode(self, text: str) -> bytes:
        """Encode a Python string to the font's raw byte representation.

        Per Unicode code point: glyph-list lookup gives the PostScript glyph
        name, the typed encoding gives the byte. Code points outside the
        encoding fall back to ``?`` (matches PDFBox's ``encode`` fallback
        for unmapped glyphs in simple-font writers). When the font has no
        ``/Encoding`` at all, encode as Latin-1.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return text.encode("latin-1", errors="replace")

        unicode_to_code = _unicode_to_code_map(encoding)
        glyph_list = _glyph_list_for(encoding)
        out = bytearray()
        for ch in text:
            code = unicode_to_code.get(ch)
            if code is None:
                # Try a glyph-list round-trip in case the unicode normalises
                # through one of the synthesised uniXXXX / .suffix entries.
                derived = glyph_list.to_unicode(ch)
                if derived is not None:
                    code = unicode_to_code.get(derived)
            if code is None:
                out.append(ord("?"))
            else:
                out.append(code & 0xFF)
        return bytes(out)

    # ---------- writing-mode / widths / subsetting (PDFontLike) ----------

    def is_vertical(self) -> bool:
        """Simple fonts never write vertically.

        Mirrors upstream ``PDSimpleFont.isVertical`` which is hard-coded
        to ``false`` — vertical writing in PDF is only available via
        Type0 / CIDFont (``PDType0Font``).
        """
        return False

    def has_explicit_width(self, code: int) -> bool:
        """``True`` when ``/Widths`` carries an explicit advance for ``code``.

        Mirrors upstream ``PDSimpleFont.hasExplicitWidth(int)``: the
        font dictionary must contain a ``/Widths`` key, and ``code`` must
        fall within ``[FirstChar, FirstChar + len(Widths))``. Default
        widths (the descriptor's ``/MissingWidth``) do not count.
        """
        if self._dict.get_dictionary_object(_WIDTHS) is None:
            return False
        first_char = self._dict.get_int(_FIRST_CHAR, -1)
        if code < first_char:
            return False
        return code - first_char < len(self.get_widths())

    def will_be_subset(self) -> bool:
        """``False`` for simple fonts.

        Mirrors upstream ``PDSimpleFont.willBeSubset``: only TrueType
        subsetting via ``PDType0Font`` is supported. ``PDTrueTypeFont``
        overrides this when subsetting has been requested.
        """
        return False

    def add_to_subset(self, code_point: int) -> None:
        """Register a codepoint for subsetting.

        Mirrors upstream ``PDSimpleFont.addToSubset(int)`` which raises
        ``UnsupportedOperationException``. Concrete subclasses that
        actually support subsetting (``PDTrueTypeFont``) override this.
        """
        raise NotImplementedError(
            "subsetting is not supported for this simple-font subtype"
        )

    def subset(self) -> None:
        """Run subsetting on this font.

        Mirrors upstream ``PDSimpleFont.subset()`` which raises
        ``UnsupportedOperationException``. Concrete subclasses that
        actually support subsetting (``PDTrueTypeFont``) override this.
        """
        raise NotImplementedError(
            "subsetting is not supported for this simple-font subtype"
        )

    @staticmethod
    def is_non_zero_bounding_box(bbox: PDRectangle | None) -> bool:
        """``True`` when ``bbox`` has at least one non-zero corner.

        Mirrors upstream ``PDSimpleFont.isNonZeroBoundingBox(PDRectangle)``
        — used by font-descriptor sanity checks: an all-zero bbox is the
        defaulted / unset case, any non-zero corner means a real bbox is
        present. Returns ``False`` for ``None``.
        """
        if bbox is None:
            return False
        return (
            bbox.get_lower_left_x() != 0.0
            or bbox.get_lower_left_y() != 0.0
            or bbox.get_upper_right_x() != 0.0
            or bbox.get_upper_right_y() != 0.0
        )

    def decode(self, data: bytes) -> str:
        """Decode the font's raw byte representation back to a Python string.

        Per byte: typed encoding gives the glyph name, glyph list gives the
        unicode string. Bytes mapped to ``.notdef`` (or to a glyph the
        glyph-list cannot resolve) are replaced with U+FFFD. When the font
        has no ``/Encoding`` at all, decode as Latin-1.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return data.decode("latin-1", errors="replace")

        glyph_list = _glyph_list_for(encoding)
        out: list[str] = []
        for byte in data:
            name = encoding.get_name(byte)
            unicode = glyph_list.to_unicode(name)
            out.append(unicode if unicode is not None else "�")
        return "".join(out)


__all__ = ["PDSimpleFont"]
