from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Per-family rough font-descriptor metrics.
#
# Numbers are taken from the published Adobe AFM files for the 14 Standard
# fonts (Helvetica, Times, Courier, Symbol, ZapfDingbats). Per-glyph widths
# and kerning pairs are intentionally NOT included here; this module ships a
# compact placeholder until the dedicated AFM bundling cluster lands.
# ---------------------------------------------------------------------------

# Font-descriptor flag bits (PDF 32000-1:2008 §9.8.2).
_FLAG_FIXED_PITCH = 1 << 0
_FLAG_SERIF = 1 << 1
_FLAG_SYMBOLIC = 1 << 2
_FLAG_SCRIPT = 1 << 3
_FLAG_NONSYMBOLIC = 1 << 5
_FLAG_ITALIC = 1 << 6


# Map canonical Standard 14 name -> family-level metrics. Per-glyph widths
# are deferred; ``avg_width`` is reused 256 times by ``get_average_widths``.
_FAMILY_METRICS: dict[str, dict[str, Any]] = {
    "Helvetica": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC,
        "font_b_box": [-166.0, -225.0, 1000.0, 931.0],
        "italic_angle": 0.0,
        "ascent": 718.0,
        "descent": -207.0,
        "cap_height": 718.0,
        "x_height": 523.0,
        "stem_v": 88.0,
    },
    "Helvetica-Bold": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC,
        "font_b_box": [-170.0, -228.0, 1003.0, 962.0],
        "italic_angle": 0.0,
        "ascent": 718.0,
        "descent": -207.0,
        "cap_height": 718.0,
        "x_height": 532.0,
        "stem_v": 140.0,
    },
    "Helvetica-Oblique": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_ITALIC,
        "font_b_box": [-170.0, -225.0, 1116.0, 931.0],
        "italic_angle": -12.0,
        "ascent": 718.0,
        "descent": -207.0,
        "cap_height": 718.0,
        "x_height": 523.0,
        "stem_v": 88.0,
    },
    "Helvetica-BoldOblique": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_ITALIC,
        "font_b_box": [-174.0, -228.0, 1114.0, 962.0],
        "italic_angle": -12.0,
        "ascent": 718.0,
        "descent": -207.0,
        "cap_height": 718.0,
        "x_height": 532.0,
        "stem_v": 140.0,
    },
    "Times-Roman": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_SERIF,
        "font_b_box": [-168.0, -218.0, 1000.0, 898.0],
        "italic_angle": 0.0,
        "ascent": 683.0,
        "descent": -217.0,
        "cap_height": 662.0,
        "x_height": 450.0,
        "stem_v": 84.0,
    },
    "Times-Bold": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_SERIF,
        "font_b_box": [-168.0, -218.0, 1000.0, 935.0],
        "italic_angle": 0.0,
        "ascent": 683.0,
        "descent": -217.0,
        "cap_height": 676.0,
        "x_height": 461.0,
        "stem_v": 139.0,
    },
    "Times-Italic": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_SERIF | _FLAG_ITALIC,
        "font_b_box": [-169.0, -217.0, 1010.0, 883.0],
        "italic_angle": -15.5,
        "ascent": 683.0,
        "descent": -217.0,
        "cap_height": 653.0,
        "x_height": 441.0,
        "stem_v": 76.0,
    },
    "Times-BoldItalic": {
        "avg_width": 500.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_SERIF | _FLAG_ITALIC,
        "font_b_box": [-200.0, -218.0, 996.0, 921.0],
        "italic_angle": -15.0,
        "ascent": 683.0,
        "descent": -217.0,
        "cap_height": 669.0,
        "x_height": 462.0,
        "stem_v": 121.0,
    },
    "Courier": {
        "avg_width": 600.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF,
        "font_b_box": [-23.0, -250.0, 715.0, 805.0],
        "italic_angle": 0.0,
        "ascent": 629.0,
        "descent": -157.0,
        "cap_height": 562.0,
        "x_height": 426.0,
        "stem_v": 51.0,
    },
    "Courier-Bold": {
        "avg_width": 600.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF,
        "font_b_box": [-113.0, -250.0, 749.0, 801.0],
        "italic_angle": 0.0,
        "ascent": 629.0,
        "descent": -157.0,
        "cap_height": 562.0,
        "x_height": 439.0,
        "stem_v": 106.0,
    },
    "Courier-Oblique": {
        "avg_width": 600.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF | _FLAG_ITALIC,
        "font_b_box": [-27.0, -250.0, 849.0, 805.0],
        "italic_angle": -12.0,
        "ascent": 629.0,
        "descent": -157.0,
        "cap_height": 562.0,
        "x_height": 426.0,
        "stem_v": 51.0,
    },
    "Courier-BoldOblique": {
        "avg_width": 600.0,
        "flags": _FLAG_NONSYMBOLIC | _FLAG_FIXED_PITCH | _FLAG_SERIF | _FLAG_ITALIC,
        "font_b_box": [-57.0, -250.0, 869.0, 801.0],
        "italic_angle": -12.0,
        "ascent": 629.0,
        "descent": -157.0,
        "cap_height": 562.0,
        "x_height": 439.0,
        "stem_v": 106.0,
    },
    "Symbol": {
        "avg_width": 500.0,
        "flags": _FLAG_SYMBOLIC,
        "font_b_box": [-180.0, -293.0, 1090.0, 1010.0],
        "italic_angle": 0.0,
        "ascent": 0.0,
        "descent": 0.0,
        "cap_height": 0.0,
        "x_height": 0.0,
        "stem_v": 85.0,
    },
    "ZapfDingbats": {
        "avg_width": 500.0,
        "flags": _FLAG_SYMBOLIC,
        "font_b_box": [-1.0, -143.0, 981.0, 820.0],
        "italic_angle": 0.0,
        "ascent": 0.0,
        "descent": 0.0,
        "cap_height": 0.0,
        "x_height": 0.0,
        "stem_v": 90.0,
    },
}


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
for _canonical in _FAMILY_METRICS:
    _NAME_LOOKUP[_canonical.lower()] = _canonical
for _alias, _target in _ALIASES.items():
    _NAME_LOOKUP[_alias.lower()] = _target


class Standard14Fonts:
    """Names and rough metrics for the 14 PDF Standard fonts.

    Mirrors PDFBox ``Standard14Fonts``. The 14 names are defined in
    PDF 32000-1:2008 §9.6.2.2 — viewers are required to ship metrics
    for these without an embedded font program.

    This is the **lite** implementation: full per-glyph AFM widths,
    kerning pairs, and glyph-name -> Unicode tables are deferred to a
    dedicated AFM bundling cluster. Until then, ``get_average_widths``
    returns a flat 256-element width table (600 for Courier, 500 for
    every other family) and ``get_font_descriptor`` returns rough
    family-average metrics taken from the published Adobe AFM files.
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
    def containsName(cls, name: str | None) -> bool:
        """Return True for any of the 14 canonical names or a known alias."""
        if name is None:
            return False
        return name.lower() in _NAME_LOOKUP

    @classmethod
    def getMappedFontName(cls, name: str | None) -> str | None:
        """Resolve ``name`` (canonical or alias) to its canonical form.

        Returns ``None`` if the name is not one of the Standard 14 or a
        known substitute alias.
        """
        if name is None:
            return None
        return _NAME_LOOKUP.get(name.lower())

    # ---- Metrics ------------------------------------------------------

    @classmethod
    def get_average_widths(cls, name: str) -> list[float]:
        """Return a 256-element glyph-width table for ``name``.

        Lite — this is a single-value-per-font placeholder (600.0 for
        Courier, 500.0 for the Helvetica/Times/Symbol/ZapfDingbats
        families). Full per-glyph widths land with the AFM bundling
        cluster.

        Raises ``ValueError`` if ``name`` is not a Standard 14 font or
        a known alias.
        """
        canonical = cls.getMappedFontName(name)
        if canonical is None:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        avg = float(_FAMILY_METRICS[canonical]["avg_width"])
        return [avg] * 256

    @classmethod
    def get_font_descriptor(cls, name: str) -> dict[str, Any]:
        """Return a stock font-descriptor dict for ``name``.

        Keys mirror the PDF font-descriptor entry names: ``FontName``,
        ``Flags``, ``FontBBox`` (4-element list), ``ItalicAngle``,
        ``Ascent``, ``Descent``, ``CapHeight``, ``XHeight``, ``StemV``.
        Values are family-level averages from the Adobe AFM files; the
        per-instance accuracy that AFM bundling will provide is deferred.

        Raises ``ValueError`` if ``name`` is not a Standard 14 font or
        a known alias.
        """
        canonical = cls.getMappedFontName(name)
        if canonical is None:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        m = _FAMILY_METRICS[canonical]
        return {
            "FontName": canonical,
            "Flags": int(m["flags"]),
            "FontBBox": list(m["font_b_box"]),
            "ItalicAngle": float(m["italic_angle"]),
            "Ascent": float(m["ascent"]),
            "Descent": float(m["descent"]),
            "CapHeight": float(m["cap_height"]),
            "XHeight": float(m["x_height"]),
            "StemV": float(m["stem_v"]),
        }


__all__ = ["Standard14Fonts"]
