from __future__ import annotations

from typing import Any

from .afm_loader import AfmMetrics, load_standard14
from .encoding.encoding import Encoding
from .encoding.standard_encoding import StandardEncoding
from .encoding.symbol_encoding import SymbolEncoding
from .encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding

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
# case-insensitively by ``getMappedFontName`` / ``containsName``.
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

    # camelCase alias kept for legacy callers; prefer ``contains_name``.
    @classmethod
    def containsName(cls, name: str | None) -> bool:  # noqa: N802 - upstream name
        return cls.contains_name(name)

    @classmethod
    def is_standard_14(cls, name: str | None) -> bool:
        """Upstream alias for :meth:`contains_name`.

        PDFBox exposes both ``containsName`` and ``isStandard14`` on
        ``Standard14Fonts``; the two have identical semantics.
        """
        return cls.contains_name(name)

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

    # camelCase alias kept for legacy callers; prefer ``get_mapped_font_name``.
    @classmethod
    def getMappedFontName(cls, name: str | None) -> str | None:  # noqa: N802 - upstream name
        return cls.get_mapped_font_name(name)

    @classmethod
    def get_names(cls) -> set[str]:
        """Return the 14 canonical PostScript names.

        Mirrors upstream ``Standard14Fonts.getNames`` — set semantics, no
        ordering guarantee, exactly the canonical names (aliases excluded).
        """
        return set(_FAMILY_FLAGS)

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


__all__ = ["Standard14Fonts"]
