from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .afm_loader import AfmMetrics, load_standard14
from .encoding.encoding import Encoding
from .encoding.standard_encoding import StandardEncoding
from .encoding.symbol_encoding import SymbolEncoding
from .encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding

if TYPE_CHECKING:
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList
    from pypdfbox.fontbox.font_mapper import Standard14FontWrapper

# ---------------------------------------------------------------------------
# Per-family flag bits + default-encoding map.
#
# Per-glyph widths and descriptor numerics (FontBBox, ItalicAngle, Ascender,
# Descender, CapHeight, XHeight, StemV) come from the bundled Adobe AFM files
# via ``afm_loader.load_standard14``. The static map below carries only the
# bits that aren't recorded in the AFM: the ``Flags`` integer (a mix of AFM
# ``IsFixedPitch``, ``CharacterSet``, ``ItalicAngle``, family heuristics) and
# the default 1-byte encoding the Standard 14 use when the PDF doesn't
# override ``/Encoding`` (PDF 32000-1 §9.6.2.4).
# ---------------------------------------------------------------------------

# Font-descriptor flag bits (PDF 32000-1:2008 §9.8.2 Table 123).
_FLAG_FIXED_PITCH = 1 << 0
_FLAG_SERIF = 1 << 1
_FLAG_SYMBOLIC = 1 << 2
_FLAG_SCRIPT = 1 << 3
_FLAG_NONSYMBOLIC = 1 << 5
_FLAG_ITALIC = 1 << 6


# Per-canonical-name (flags, default-encoding-factory) lookup. The encoding
# factory is invoked lazily — the singletons live on the encoding modules.
_FAMILY_FLAGS: dict[str, int] = {
    "Helvetica": _FLAG_NONSYMBOLIC,
    "Helvetica-Bold": _FLAG_NONSYMBOLIC,
    "Helvetica-Oblique": _FLAG_NONSYMBOLIC | _FLAG_ITALIC,
    "Helvetica-BoldOblique": _FLAG_NONSYMBOLIC | _FLAG_ITALIC,
    "Times-Roman": _FLAG_NONSYMBOLIC | _FLAG_SERIF,
    "Times-Bold": _FLAG_NONSYMBOLIC | _FLAG_SERIF,
    "Times-Italic": _FLAG_NONSYMBOLIC | _FLAG_SERIF | _FLAG_ITALIC,
    "Times-BoldItalic": _FLAG_NONSYMBOLIC | _FLAG_SERIF | _FLAG_ITALIC,
    "Courier": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF,
    "Courier-Bold": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF,
    "Courier-Oblique": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF | _FLAG_ITALIC,
    "Courier-BoldOblique": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF | _FLAG_ITALIC,
    "Symbol": _FLAG_SYMBOLIC,
    "ZapfDingbats": _FLAG_SYMBOLIC,
}


def _default_encoding(name: str) -> Encoding:
    """Return the predefined 1-byte encoding the named Standard 14 font uses
    when the PDF dictionary doesn't supply ``/Encoding`` (PDF 32000-1 §9.6.2.4).

    - Symbol → SymbolEncoding (built-in symbol set)
    - ZapfDingbats → ZapfDingbatsEncoding (built-in dingbats set)
    - everything else → StandardEncoding (Adobe Standard Latin)
    """
    if name == "Symbol":
        return SymbolEncoding.INSTANCE
    if name == "ZapfDingbats":
        return ZapfDingbatsEncoding.INSTANCE
    return StandardEncoding.INSTANCE


# Common alias -> canonical Standard 14 name. Aliases are matched
# case-insensitively by ``get_mapped_font_name`` / ``contains_name``.
_ALIASES: dict[str, str] = {
    # Helvetica family substitutes (Microsoft "Arial" branch).
    "Arial": "Helvetica",
    "Arial,Bold": "Helvetica-Bold",
    "Arial,Italic": "Helvetica-Oblique",
    "Arial,BoldItalic": "Helvetica-BoldOblique",
    "Arial-Bold": "Helvetica-Bold",
    "Arial-Italic": "Helvetica-Oblique",
    "Arial-BoldItalic": "Helvetica-BoldOblique",
    "Arial-BoldItalicMT": "Helvetica-BoldOblique",
    "Arial-BoldMT": "Helvetica-Bold",
    "Arial-ItalicMT": "Helvetica-Oblique",
    "ArialMT": "Helvetica",
    # Times family substitutes (Microsoft "Times New Roman" branch).
    "TimesNewRoman": "Times-Roman",
    "TimesNewRoman,Bold": "Times-Bold",
    "TimesNewRoman,BoldItalic": "Times-BoldItalic",
    "TimesNewRoman,Italic": "Times-Italic",
    "TimesNewRoman-Bold": "Times-Bold",
    "TimesNewRoman-BoldItalic": "Times-BoldItalic",
    "TimesNewRoman-Italic": "Times-Italic",
    "TimesNewRomanPS": "Times-Roman",
    "TimesNewRomanPS-Bold": "Times-Bold",
    "TimesNewRomanPS-BoldItalic": "Times-BoldItalic",
    "TimesNewRomanPS-BoldItalicMT": "Times-BoldItalic",
    "TimesNewRomanPS-BoldMT": "Times-Bold",
    "TimesNewRomanPS-Italic": "Times-Italic",
    "TimesNewRomanPS-ItalicMT": "Times-Italic",
    "TimesNewRomanPSMT": "Times-Roman",
    # Courier family substitutes (Microsoft "Courier New" branch).
    "CourierCourierNew": "Courier",
    "CourierNew": "Courier",
    "CourierNew,Bold": "Courier-Bold",
    "CourierNew,BoldItalic": "Courier-BoldOblique",
    "CourierNew,Italic": "Courier-Oblique",
    "CourierNew-Bold": "Courier-Bold",
    "CourierNew-BoldItalic": "Courier-BoldOblique",
    "CourierNew-Italic": "Courier-Oblique",
    "CourierNewPS-BoldItalicMT": "Courier-BoldOblique",
    "CourierNewPS-BoldMT": "Courier-Bold",
    "CourierNewPS-ItalicMT": "Courier-Oblique",
    "CourierNewPSMT": "Courier",
    # Acrobat treats these "Symbol,*" names as Standard 14 too — Acrobat
    # preflight reports them as such even though only the upright Symbol
    # font exists in the Adobe AFM set.
    "Symbol,Bold": "Symbol",
    "Symbol,BoldItalic": "Symbol",
    "Symbol,Italic": "Symbol",
    # Acrobat also accepts the bare "Times" family name (Apple-style)
    # alongside Adobe's "Times-Roman" canonical family.
    "Times": "Times-Roman",
    "Times,Bold": "Times-Bold",
    "Times,BoldItalic": "Times-BoldItalic",
    "Times,Italic": "Times-Italic",
}


# Build the canonical lookup map: every Standard 14 name maps to itself,
# every alias maps to its canonical name. Lookup is case-insensitive on
# the input but always returns the exactly-cased canonical name.
_NAME_LOOKUP: dict[str, str] = {}
for _canonical in _FAMILY_FLAGS:
    _NAME_LOOKUP[_canonical.lower()] = _canonical
for _alias, _target in _ALIASES.items():
    _NAME_LOOKUP[_alias.lower()] = _target


# Per-name (256-element width table) cache. The table maps character code
# 0..255 → advance width in 1/1000 em, derived from the font's default
# encoding (StandardEncoding / SymbolEncoding / ZapfDingbatsEncoding) plus
# the bundled AFM. Built once on first access.
_AVG_WIDTHS_CACHE: dict[str, list[float]] = {}


# Per-canonical-name cache for the substitute :class:`Standard14FontWrapper`
# returned by :meth:`Standard14Fonts.get_mapped_font`. Mirrors upstream's
# ``GENERIC_FONTS`` ``EnumMap`` (Standard14Fonts.java line 67) — the wrapper
# is built once on first access and reused for the lifetime of the process.
_GENERIC_FONTS_CACHE: dict[str, Standard14FontWrapper] = {}


def _uni_name_of_code_point(code_point: int) -> str:
    """Synthesize the ``uniXXXX`` glyph name for ``code_point``.

    Mirrors upstream ``UniUtil.getUniNameOfCodePoint`` — pads the
    uppercase hex to a minimum width of four. Used by
    :meth:`Standard14Fonts.get_glyph_path` for the AGL-fallback branch.
    """
    hex_str = format(code_point, "X")
    if len(hex_str) < 4:
        hex_str = hex_str.rjust(4, "0")
    return "uni" + hex_str


class Standard14Fonts:
    """Names and metrics for the 14 PDF Standard fonts.

    Mirrors PDFBox ``Standard14Fonts``. The 14 names are defined in
    PDF 32000-1:2008 §9.6.2.2 — viewers are required to ship metrics for
    these without an embedded font program.

    Per-glyph widths and font-descriptor numerics are loaded on demand from
    the bundled Adobe AFM files (``pypdfbox/pdmodel/font/afm/``) via
    :class:`pypdfbox.pdmodel.font.afm_loader.AfmMetrics`. The AFM is parsed
    once per font and cached for the lifetime of the process.
    """

    # ---- Class constants: canonical PostScript names ------------------

    HELVETICA = "Helvetica"
    HELVETICA_BOLD = "Helvetica-Bold"
    HELVETICA_OBLIQUE = "Helvetica-Oblique"
    HELVETICA_BOLD_OBLIQUE = "Helvetica-BoldOblique"

    TIMES_ROMAN = "Times-Roman"
    TIMES_BOLD = "Times-Bold"
    TIMES_ITALIC = "Times-Italic"
    TIMES_BOLD_ITALIC = "Times-BoldItalic"

    COURIER = "Courier"
    COURIER_BOLD = "Courier-Bold"
    COURIER_OBLIQUE = "Courier-Oblique"
    COURIER_BOLD_OBLIQUE = "Courier-BoldOblique"

    SYMBOL = "Symbol"
    ZAPF_DINGBATS = "ZapfDingbats"

    # ---- Lookup -------------------------------------------------------

    @classmethod
    def contains_name(cls, name: str | None) -> bool:
        """Return True for any of the 14 canonical names or a known alias.

        Mirrors upstream ``Standard14Fonts.containsName``.
        """
        if name is None:
            return False
        return name.lower() in _NAME_LOOKUP

    @classmethod
    def is_standard_14(cls, name: str | None) -> bool:
        """Upstream alias for :meth:`contains_name`.

        PDFBox exposes both ``containsName`` and ``isStandard14`` on
        ``Standard14Fonts``; the two have identical semantics.
        """
        return cls.contains_name(name)

    @classmethod
    def is_canonical_name(cls, name: str | None) -> bool:
        """Return True iff ``name`` is one of the 14 base PostScript names.

        Aliases (e.g. ``"Arial"``, ``"TimesNewRoman"``) return False — use
        :meth:`contains_name` to accept either form. Lookup is
        case-insensitive on the input.
        """
        if name is None:
            return False
        canonical = _NAME_LOOKUP.get(name.lower())
        return canonical is not None and canonical.lower() == name.lower()

    @classmethod
    def has_alias(cls, name: str | None) -> bool:
        """Return True iff ``name`` is a registered substitute alias.

        Returns False for the 14 canonical names (use
        :meth:`is_canonical_name` for those) and for unknown names.
        Lookup is case-insensitive on the input.
        """
        if name is None:
            return False
        canonical = _NAME_LOOKUP.get(name.lower())
        if canonical is None:
            return False
        return canonical.lower() != name.lower()

    @classmethod
    def get_mapped_font_name(cls, name: str | None) -> str | None:
        """Resolve ``name`` (canonical or alias) to its canonical form.

        Returns ``None`` if the name is not one of the Standard 14 or a
        known substitute alias. Mirrors upstream
        ``Standard14Fonts.getMappedFontName``.
        """
        if name is None:
            return None
        return _NAME_LOOKUP.get(name.lower())

    @classmethod
    def resolve(cls, name: str | None, default: str | None = None) -> str | None:
        """Like :meth:`get_mapped_font_name`, but with a caller-supplied default.

        Convenience for callers that want a fallback (the input itself, a
        sentinel, or ``"Helvetica"``) instead of ``None`` for unknown
        names. ``default`` is returned when ``name`` is ``None`` or not
        one of the Standard 14 / known aliases.
        """
        if name is None:
            return default
        return _NAME_LOOKUP.get(name.lower(), default)

    @classmethod
    def get_names(cls) -> set[str]:
        """Return the 14 canonical PostScript names.

        Pypdfbox extension — upstream ``Standard14Fonts.getNames`` returns
        the keys of the alias map (canonical names *and* aliases). Use
        :meth:`get_all_names` for upstream-strict semantics; this method
        is the common case (a 14-element set, aliases excluded).
        """
        return set(_FAMILY_FLAGS)

    @classmethod
    def get_all_names(cls) -> set[str]:
        """Return the canonical names *and* every registered alias.

        Mirrors upstream ``Standard14Fonts.getNames`` exactly — the result
        is the union of the 14 canonical PostScript names and every alias
        (Arial branch, TimesNewRoman branch, CourierNew branch, ``-PS`` /
        ``-MT`` variants, etc.). The set is freshly constructed; mutating
        it does not affect future lookups.
        """
        return set(_FAMILY_FLAGS) | set(_ALIASES)

    @classmethod
    def get_aliases(cls) -> dict[str, str]:
        """Return the alias -> canonical-name map (defensive copy).

        Mirrors upstream ``Standard14Fonts.getAliases``. Mutating the result
        does not affect future lookups.
        """
        return dict(_ALIASES)

    # ---- AFM access ---------------------------------------------------

    @classmethod
    def get_afm(cls, name: str) -> AfmMetrics:
        """Return the parsed :class:`AfmMetrics` for ``name``.

        Mirrors upstream ``Standard14Fonts.getAFM``. The same instance is
        returned on every call (per-name cache lives in ``afm_loader``).
        Aliases are resolved transparently.

        Raises ``ValueError`` if ``name`` is not a Standard 14 font or a
        known alias.
        """
        canonical = cls.get_mapped_font_name(name)
        if canonical is None:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        return load_standard14(canonical)

    # ---- Metrics ------------------------------------------------------

    @classmethod
    def get_glyph_width(cls, name: str, glyph_name: str) -> float:
        """Look up a per-glyph advance width by glyph name.

        Returns ``0.0`` for ``.notdef`` / unknown glyphs (matches PDFBox
        ``FontMetrics.getCharacterWidth``).
        """
        return cls.get_afm(name).get_glyph_width(glyph_name)

    @classmethod
    def get_average_widths(cls, name: str) -> list[float]:
        """Return a 256-element glyph-width table for ``name``.

        The table is indexed by character code and built by mapping each
        code through the font's default encoding (Standard / Symbol /
        ZapfDingbats per PDF 32000-1 §9.6.2.4) to a glyph name and looking
        the width up in the bundled AFM. Codes that resolve to ``.notdef``
        or to a glyph the AFM doesn't carry get ``0.0``.

        Raises ``ValueError`` if ``name`` is not a Standard 14 font or a
        known alias.
        """
        canonical = cls.get_mapped_font_name(name)
        if canonical is None:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        cached = _AVG_WIDTHS_CACHE.get(canonical)
        if cached is not None:
            return list(cached)
        afm = load_standard14(canonical)
        encoding = _default_encoding(canonical)
        table: list[float] = [0.0] * 256
        for code in range(256):
            glyph = encoding.get_name(code)
            if glyph == ".notdef":
                continue
            table[code] = afm.get_glyph_width(glyph)
        _AVG_WIDTHS_CACHE[canonical] = table
        # Hand back a copy so callers can mutate without poisoning the cache.
        return list(table)

    @classmethod
    def get_font_descriptor(cls, name: str) -> dict[str, Any]:
        """Return a stock font-descriptor dict for ``name``.

        Keys mirror the PDF font-descriptor entry names: ``FontName``,
        ``Flags``, ``FontBBox`` (4-element list), ``ItalicAngle``,
        ``Ascent``, ``Descent``, ``CapHeight``, ``XHeight``, ``StemV``.
        Values are loaded from the bundled Adobe AFM file via
        :func:`afm_loader.load_standard14`; ``Flags`` is computed from
        family-level heuristics (fixed-pitch / serif / italic / symbolic).

        Raises ``ValueError`` if ``name`` is not a Standard 14 font or a
        known alias.
        """
        canonical = cls.get_mapped_font_name(name)
        if canonical is None:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        afm_metrics = load_standard14(canonical).get_font_metrics()
        return {
            "FontName": canonical,
            "Flags": int(_FAMILY_FLAGS[canonical]),
            "FontBBox": [float(v) for v in afm_metrics["FontBBox"]],
            "ItalicAngle": float(afm_metrics["ItalicAngle"]),
            "Ascent": float(afm_metrics["Ascent"]),
            "Descent": float(afm_metrics["Descent"]),
            "CapHeight": float(afm_metrics["CapHeight"]),
            "XHeight": float(afm_metrics["XHeight"]),
            "StemV": float(afm_metrics["StemV"]),
        }

    @classmethod
    def get_font_metrics(cls, name: str) -> dict[str, Any] | None:
        """Return the raw AFM-derived font-descriptor numerics for ``name``.

        Mirrors upstream ``Standard14Fonts.getFontMetrics`` — the result is a
        plain dict of ``FontName / FontBBox / ItalicAngle / Ascent / Descent
        / CapHeight / XHeight / StemV / IsFixedPitch`` straight from the
        bundled AFM (no ``Flags`` synthesis; see :meth:`get_font_descriptor`
        for the full PDF font-descriptor shape).

        Returns ``None`` when ``name`` is not a Standard 14 font or a known
        alias (matches upstream's null-return contract).
        """
        canonical = cls.get_mapped_font_name(name)
        if canonical is None:
            return None
        return load_standard14(canonical).get_font_metrics()

    # ---- Internal helpers (port of private upstream methods) ----------

    @classmethod
    def map_name(cls, alias: str, base_name: str | None = None) -> None:
        """Register ``alias`` -> ``base_name`` in the alias table.

        Mirrors the upstream private overloads
        ``mapName(FontName)`` and ``mapName(String, FontName)`` on
        :class:`org.apache.pdfbox.pdmodel.font.Standard14Fonts` (lines
        153-168). When ``base_name`` is ``None`` the alias is treated as
        a self-mapping (the upstream single-argument form used to seed
        the 14 canonical names). The lookup map is rebuilt so future
        :meth:`contains_name` / :meth:`get_mapped_font_name` calls see
        the new entry.

        Raises ``ValueError`` when ``base_name`` is not one of the 14
        canonical PostScript names (mirrors upstream's reliance on a
        ``FontName`` enum constant).
        """
        target = base_name if base_name is not None else alias
        if target not in _FAMILY_FLAGS:
            raise ValueError(
                f"{target!r} is not one of the 14 canonical Standard 14 names"
            )
        if base_name is None:
            # Self-mapping — already covered by the canonical seed pass.
            _NAME_LOOKUP[alias.lower()] = alias
            return
        _ALIASES[alias] = target
        _NAME_LOOKUP[alias.lower()] = target

    @classmethod
    def load_metrics(cls, name: str) -> AfmMetrics:
        """Parse and cache the AFM metrics for ``name``.

        Mirrors the upstream private ``loadMetrics(FontName)`` helper
        (Standard14Fonts.java line 129) — exposed as a classmethod here so
        callers porting from Java can drive the cache priming explicitly.
        Returns the parsed :class:`AfmMetrics`; subsequent calls hit the
        same cache that backs :meth:`get_afm`.

        Raises ``ValueError`` when ``name`` is not one of the 14 canonical
        PostScript names (the upstream private form takes a ``FontName``
        enum, so aliases are intentionally rejected).
        """
        if name not in _FAMILY_FLAGS:
            raise ValueError(
                f"{name!r} is not one of the 14 canonical Standard 14 names"
            )
        return load_standard14(name)

    @classmethod
    def get_mapped_font(cls, base_name: str) -> Standard14FontWrapper:
        """Return the substitute font wrapper for the given canonical name.

        Mirrors upstream private ``getMappedFont(FontName)``
        (Standard14Fonts.java line 245) — caches a
        :class:`pypdfbox.fontbox.font_mapper.Standard14FontWrapper` per
        canonical name. The wrapper exposes the ``FontBoxFont`` protocol
        (``get_name`` / ``has_glyph`` / ``get_path`` / ``get_width``)
        backed by the bundled AFM metrics.

        Aliases are accepted on the input — they are normalised to their
        canonical form before the wrapper is created.

        Raises ``ValueError`` when ``base_name`` is not a Standard 14
        canonical name or known alias.
        """
        canonical = cls.get_mapped_font_name(base_name)
        if canonical is None:
            raise ValueError(
                f"{base_name!r} is not one of the 14 Standard fonts"
            )
        cached = _GENERIC_FONTS_CACHE.get(canonical)
        if cached is not None:
            return cached
        # Local import — :mod:`pypdfbox.fontbox.font_mapper` reaches back
        # into this module via :class:`DefaultFontMapper`, so import at
        # call time to break the cycle.
        from pypdfbox.fontbox.font_mapper import (  # noqa: PLC0415
            Standard14FontWrapper,
        )

        metrics = load_standard14(canonical)
        wrapper = Standard14FontWrapper(canonical, metrics)
        _GENERIC_FONTS_CACHE[canonical] = wrapper
        return wrapper

    @classmethod
    def get_glyph_list(cls, base_name: str) -> GlyphList:
        """Return the AGL / ZapfDingbats glyph list for ``base_name``.

        Mirrors the upstream private ``getGlyphList(FontName)`` selector
        (Standard14Fonts.java line 309): ZapfDingbats picks the dedicated
        Zapf list, every other Standard 14 picks the Adobe Glyph List.
        Aliases are normalised on the input.

        Raises ``ValueError`` when ``base_name`` is not a Standard 14
        canonical name or known alias.
        """
        canonical = cls.get_mapped_font_name(base_name)
        if canonical is None:
            raise ValueError(
                f"{base_name!r} is not one of the 14 Standard fonts"
            )
        from pypdfbox.fontbox.encoding.glyph_list import (  # noqa: PLC0415
            GlyphList,
        )

        if canonical == "ZapfDingbats":
            return GlyphList.get_zapf_dingbats()
        return GlyphList.get_adobe_glyph_list()

    @classmethod
    def get_glyph_path(cls, base_name: str, glyph_name: str) -> list[tuple[Any, ...]]:
        """Return the glyph outline for ``glyph_name`` in the named font.

        Mirrors upstream ``Standard14Fonts.getGlyphPath`` (line 271).
        Resolution order:

        1. ``.notdef`` short-circuits to an empty path (upstream returns
           ``new GeneralPath()``).
        2. If the substitute font already carries a glyph by that name,
           draw it directly.
        3. Otherwise, run ``glyph_name`` through the family's
           :class:`GlyphList` (Adobe Glyph List for everything except
           ZapfDingbats) and re-probe under the synthesized
           ``uniXXXX`` glyph name.
        4. As a final fallback, when the substitute reports its name as
           ``"SymbolMT"`` (the Microsoft alias for Symbol),
           re-probe under ``uniF0XX`` for codes 0x20-0xFF — matches
           upstream's PUA-shifted Symbol glyph naming.
        5. If none of the above hit, return an empty path.

        Returns a ``list`` of segment tuples (the pypdfbox shape — a
        Java ``GeneralPath`` is upstream's analogue).
        """
        if glyph_name == ".notdef":
            return []
        try:
            mapped_font = cls.get_mapped_font(base_name)
        except ValueError:
            return []
        if mapped_font.has_glyph(glyph_name):
            return list(mapped_font.get_path(glyph_name))
        # AGL / ZapfDingbats fallback — upstream re-probes under the
        # synthesized ``uniXXXX`` form when the direct name misses.
        unicodes = cls.get_glyph_list(base_name).to_unicode(glyph_name)
        if unicodes is not None and len(unicodes) == 1:
            uni_name = _uni_name_of_code_point(ord(unicodes))
            if mapped_font.has_glyph(uni_name):
                return list(mapped_font.get_path(uni_name))
        # PUA-shifted Symbol fallback — only fires for the Microsoft
        # ``SymbolMT`` substitute; pypdfbox's bundled wrapper reports
        # the canonical name (``Symbol``) so the branch is normally
        # inert here, but kept for upstream-symmetry when an external
        # mapper is plugged in.
        if mapped_font.get_name() == "SymbolMT":
            code = SymbolEncoding.INSTANCE.get_code(glyph_name)
            if code is not None:
                uni_name = _uni_name_of_code_point(code + 0xF000)
                if mapped_font.has_glyph(uni_name):
                    return list(mapped_font.get_path(uni_name))
        return []


__all__ = ["Standard14Fonts"]
