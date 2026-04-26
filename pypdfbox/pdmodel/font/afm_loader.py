from __future__ import annotations

from importlib import resources
from typing import Any

from fontTools.afmLib import AFM

# Canonical PostScript names of the 14 Standard fonts (PDF 32000-1 §9.6.2.2).
_STANDARD14: tuple[str, ...] = (
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Symbol",
    "ZapfDingbats",
)


class AfmMetrics:
    """Typed wrapper over a parsed Adobe AFM file.

    Mirrors what ``org.apache.pdfbox.pdmodel.font.PDType1Font`` consumes from
    its bundled ``FontMetrics`` object: per-glyph advance widths, font-bbox,
    italic angle, ascender / descender / cap-height / x-height, and the
    average advance width across the encoded glyph set.

    Construction takes the canonical font name (one of the Standard 14) and
    the parsed :class:`fontTools.afmLib.AFM`. Instances are immutable; the
    module-level cache returns the same instance per font name.
    """

    __slots__ = ("_name", "_afm", "_widths_by_name", "_average_width")

    def __init__(self, name: str, afm: AFM) -> None:
        self._name: str = name
        self._afm: AFM = afm
        # Build the (glyph-name -> advance width) map once at construction so
        # ``get_glyph_width`` is a pure dict lookup. ``afm._chars`` values are
        # tuples of ``(charnum, width, bbox)``; we keep just the width.
        self._widths_by_name: dict[str, float] = {
            name: float(meta[1]) for name, meta in afm._chars.items()
        }
        non_zero = [w for w in self._widths_by_name.values() if w > 0.0]
        self._average_width: float = (
            sum(non_zero) / len(non_zero) if non_zero else 0.0
        )

    # ---------- identity ----------

    def get_font_name(self) -> str:
        """Canonical PostScript name (e.g. ``"Times-Roman"``)."""
        return self._name

    # ---------- per-glyph widths ----------

    def get_glyph_width(self, glyph_name: str) -> float:
        """Return the advance width for ``glyph_name`` in 1/1000 em.

        Returns ``0.0`` for unknown / ``.notdef`` slots — matches PDFBox's
        ``FontMetrics.getCharacterWidth`` fallback for missing glyphs.
        """
        return self._widths_by_name.get(glyph_name, 0.0)

    def has_glyph(self, glyph_name: str) -> bool:
        """``True`` when the AFM defines a real entry for ``glyph_name``."""
        return glyph_name in self._widths_by_name

    def get_average_width(self) -> float:
        """Mean of non-zero advance widths across the AFM's glyph set."""
        return self._average_width

    # ---------- font-descriptor metrics ----------

    def get_font_metrics(self) -> dict[str, Any]:
        """Return PDF font-descriptor entries derived from the AFM.

        Keys mirror the PDF font-descriptor entry names: ``FontName``,
        ``FontBBox`` (4-element tuple of ints), ``ItalicAngle`` (float),
        ``Ascent`` / ``Descent`` / ``CapHeight`` / ``XHeight`` / ``StemV``
        (floats; ``0.0`` when the AFM omits the entry, e.g. Symbol /
        ZapfDingbats), and ``IsFixedPitch`` (bool).
        """
        a = self._afm
        attrs = a._attrs
        bbox = attrs.get("FontBBox", (0, 0, 0, 0))
        return {
            "FontName": attrs.get("FontName", self._name),
            "FontBBox": tuple(int(v) for v in bbox),
            "ItalicAngle": float(attrs.get("ItalicAngle", 0)),
            "Ascent": float(attrs.get("Ascender", 0)),
            "Descent": float(attrs.get("Descender", 0)),
            "CapHeight": float(attrs.get("CapHeight", 0)),
            "XHeight": float(attrs.get("XHeight", 0)),
            # AFM ships StdVW (vertical stem); PDF descriptors call it StemV.
            "StemV": float(attrs.get("StdVW", 0)),
            "IsFixedPitch": str(attrs.get("IsFixedPitch", "false")).lower() == "true",
        }


# ---------------------------------------------------------------------------
# Cached loader
# ---------------------------------------------------------------------------

# Per-font cache. Keyed by canonical name; entries are created on first call
# to ``load_standard14`` and reused for the lifetime of the process.
_CACHE: dict[str, AfmMetrics] = {}


def _afm_path_for(name: str) -> str:
    """Return the on-disk path of the bundled ``<name>.afm`` resource.

    Uses :mod:`importlib.resources` so the lookup works whether ``pypdfbox``
    is installed as a wheel, an editable install, or run from a source
    checkout. Returns the resolved filesystem path string because
    :class:`fontTools.afmLib.AFM` opens the file by path with text mode.
    """
    pkg = resources.files("pypdfbox.pdmodel.font.afm")
    res = pkg.joinpath(f"{name}.afm")
    return str(res)


def load_standard14(name: str) -> AfmMetrics:
    """Return the parsed :class:`AfmMetrics` for one of the Standard 14 fonts.

    Calling this twice for the same canonical name returns the same instance
    (PDFBox parity — upstream caches its parsed ``FontMetrics`` on first
    access via ``Standard14Fonts.getAFM``).

    Raises ``ValueError`` when ``name`` is not one of the 14 canonical
    PostScript names; alias resolution (e.g. ``"Arial"`` → ``"Helvetica"``)
    happens upstream in :class:`Standard14Fonts`.
    """
    if name not in _CACHE:
        if name not in _STANDARD14:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        afm = AFM(_afm_path_for(name))
        _CACHE[name] = AfmMetrics(name, afm)
    return _CACHE[name]


def standard14_names() -> tuple[str, ...]:
    """The 14 canonical PostScript names, in PDF 32000-1 §9.6.2.2 order."""
    return _STANDARD14


__all__ = ["AfmMetrics", "load_standard14", "standard14_names"]
