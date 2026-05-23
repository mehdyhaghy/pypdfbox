"""Wave 1305 — bundled DejaVu Sans substitute for Symbol / ZapfDingbats.

When a PDF references Symbol or ZapfDingbats by name without embedding the
font program, the renderer falls back to a bundled DejaVu Sans (Bitstream
Vera derivative; DejaVu changes in public domain). DejaVu Sans covers:

* The full Zapf Dingbats Unicode block (U+2700-U+27BF) — 100% of the
  ZapfDingbatsEncoding glyph set, both by name and via the AGL → Unicode
  cmap fallback.
* The Greek-letter and mathematical-operator portions of the Adobe
  Symbol encoding (~84% glyph coverage). The remaining names are PUA-
  encoded variants for bracket-extending pieces / serif-style register
  marks that are visually inconsequential — the core math + Greek
  glyphs all render correctly.

This test module guards both branches: the per-name TTF lookup that
catches simple cases like ``alpha`` / ``beta`` directly, and the
GlyphList → Unicode codepoint fallback that catches names like
``universal`` (Symbol code 0x22 → "alpha-symbol" in DejaVu).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.fontbox.encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# ---------- substitute TTF lookup ----------


def test_symbol_resolves_to_bundled_dejavu_sans() -> None:
    """``Standard14Fonts.get_substitute_ttf("Symbol")`` returns the
    parsed DejaVu Sans TTF (Bitstream Vera + public-domain DejaVu)."""
    ttf = Standard14Fonts.get_substitute_ttf("Symbol")
    assert ttf is not None
    assert ttf.get_name() == "DejaVuSans"


def test_zapf_dingbats_resolves_to_bundled_dejavu_sans() -> None:
    """``Standard14Fonts.get_substitute_ttf("ZapfDingbats")`` returns the
    same DejaVu Sans TTF — one file covers both symbolic Standard 14
    names."""
    ttf = Standard14Fonts.get_substitute_ttf("ZapfDingbats")
    assert ttf is not None
    assert ttf.get_name() == "DejaVuSans"


def test_symbol_and_zapf_load_the_same_underlying_dejavu_font() -> None:
    """Both names route through the same on-disk ``DejaVuSans.ttf``
    resource. The per-canonical-name TTF cache parses one instance per
    canonical name (Symbol and ZapfDingbats are distinct keys), so the
    objects are not ``is``-identical, but they expose the same font
    name and glyph repertoire."""
    sym = Standard14Fonts.get_substitute_ttf("Symbol")
    zdb = Standard14Fonts.get_substitute_ttf("ZapfDingbats")
    assert sym is not None and zdb is not None
    assert sym.get_name() == zdb.get_name() == "DejaVuSans"
    # Identical cached instance for repeat lookups on the same name.
    assert Standard14Fonts.get_substitute_ttf("Symbol") is sym
    assert Standard14Fonts.get_substitute_ttf("ZapfDingbats") is zdb


def test_symbol_alias_resolves_through_dejavu() -> None:
    """Acrobat-style ``Symbol,Bold`` / ``Symbol,Italic`` aliases canonicalise
    to ``Symbol`` and reach the same DejaVu substitute."""
    assert (
        Standard14Fonts.get_substitute_ttf("Symbol,Bold")
        is Standard14Fonts.get_substitute_ttf("Symbol")
    )
    assert (
        Standard14Fonts.get_substitute_ttf("Symbol,Italic")
        is Standard14Fonts.get_substitute_ttf("Symbol")
    )


# ---------- direct by-name glyph lookups ----------


@pytest.mark.parametrize(
    "glyph_name",
    [
        # Greek (uppercase + lowercase) — present by PostScript name in DejaVu Sans.
        "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Lambda",
        "Pi", "Sigma", "Omega",
        "alpha", "beta", "gamma", "delta", "epsilon", "lambda",
        "pi", "sigma", "omega",
        # Math operators / arrows — present by name in DejaVu Sans.
        "infinity", "integral", "partialdiff", "minus", "plus",
        "arrowleft", "arrowright", "lessequal", "greaterequal",
    ],
)
def test_symbol_glyph_path_non_empty_by_name(glyph_name: str) -> None:
    """Every common Symbol-encoded PostScript name must resolve to a
    drawable outline through the DejaVu Sans substitute."""
    path = Standard14Fonts.get_glyph_path("Symbol", glyph_name)
    assert path, f"Symbol/{glyph_name} should resolve to a non-empty path"
    assert any(cmd[0] == "moveto" for cmd in path), (
        f"Symbol/{glyph_name} path missing moveto: {path[:3]}"
    )


# ---------- AGL → Unicode codepoint fallback ----------


def test_symbol_universal_quantifier_via_agl_unicode_fallback() -> None:
    """``universal`` (Symbol code 0x22 — Adobe Symbol's forall) maps via
    the AGL to U+2200 (FOR ALL), which DejaVu Sans carries. Exercises
    the cmap-based fallback in :meth:`Standard14Fonts.get_glyph_path`.
    """
    path = Standard14Fonts.get_glyph_path("Symbol", "universal")
    assert path
    assert any(cmd[0] == "moveto" for cmd in path)


def test_symbol_existential_quantifier_via_agl_unicode_fallback() -> None:
    """``existential`` (Symbol code 0x24) maps via AGL to U+2203 (THERE
    EXISTS), which DejaVu Sans carries."""
    path = Standard14Fonts.get_glyph_path("Symbol", "existential")
    assert path


# ---------- Zapf Dingbats (full coverage expected) ----------


def test_zapf_dingbats_all_named_glyphs_resolve_to_outlines() -> None:
    """The full ZapfDingbats encoding (188 named glyphs, excluding
    .notdef) must resolve through the DejaVu Sans Unicode-block coverage.

    The lone exception is the ``space`` glyph (code 0x20) which carries
    no contours by design — that's not a missing glyph, just an empty
    outline (same as it is in the original Adobe Zapf Dingbats font).
    """
    misses = []
    seen = 0
    for code in range(256):
        name = ZapfDingbatsEncoding.INSTANCE.get_name(code)
        if name == ".notdef":
            continue
        seen += 1
        if name == "space":
            # Whitespace glyph — zero-contour by design.
            continue
        path = Standard14Fonts.get_glyph_path("ZapfDingbats", name)
        if not path:
            misses.append((code, name))
    assert seen == 188, f"expected 188 ZapfDingbats-named entries, saw {seen}"
    assert not misses, (
        f"DejaVu Sans should cover the entire Zapf Dingbats Unicode block "
        f"but {len(misses)} glyph(s) missed: {misses[:10]}"
    )


# ---------- Symbol coverage threshold ----------


def test_symbol_encoding_coverage_is_above_eighty_percent() -> None:
    """Pre-wave-1387 the DejaVu Sans substitute covered 158/189 = 83.6%
    of Adobe Symbol glyphs; wave 1387 added a PUA-name → DejaVu-codepoint
    synthesis table (see ``_SYMBOL_PUA_FALLBACKS``) which raised the
    floor to 188/189 (the one residual miss is the zero-contour
    ``space`` glyph, correct by design).

    The 80% threshold is kept as a regression guard against catastrophic
    breakage; the stricter 100% floor lives in
    ``tests/pdmodel/font/test_symbol_zapfdingbats_coverage_wave1387.py``.
    """
    total = 0
    covered = 0
    for code in range(256):
        name = SymbolEncoding.INSTANCE.get_name(code)
        if name == ".notdef":
            continue
        total += 1
        if Standard14Fonts.get_glyph_path("Symbol", name):
            covered += 1
    assert total == 189, f"expected 189 Symbol-encoded names, saw {total}"
    ratio = covered / total
    assert ratio >= 0.80, (
        f"Symbol coverage dropped below 80%: {covered}/{total} = {ratio:.1%}"
    )


# ---------- integration: PDType1Font rendering uses the substitute ----------


def test_pd_type1_symbol_glyph_path_uses_dejavu() -> None:
    """A Symbol-named :class:`PDType1Font` with no embedded ``/FontFile``
    routes ``get_glyph_path(code)`` through the Standard 14 substitution
    chain and returns a non-empty path for the Greek-letter codepoints.
    """
    from pypdfbox.cos import COSDictionary, COSName  # noqa: PLC0415
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font  # noqa: PLC0415

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("Symbol"),
    )
    font = PDType1Font(font_dict)
    # SymbolEncoding maps code 0x41 -> "Alpha" (capital Greek alpha).
    path = font.get_glyph_path(0x41)
    assert path, "Symbol code 0x41 should resolve to a real DejaVu glyph"
    assert any(cmd[0] == "moveto" for cmd in path)


def test_pd_type1_zapf_dingbats_glyph_path_uses_dejavu() -> None:
    """A ZapfDingbats :class:`PDType1Font` with no embedded program also
    routes through DejaVu Sans for the full dingbat range."""
    from pypdfbox.cos import COSDictionary, COSName  # noqa: PLC0415
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font  # noqa: PLC0415

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("ZapfDingbats"),
    )
    font = PDType1Font(font_dict)
    # ZapfDingbatsEncoding maps code 0x21 -> "a1" (UPPER BLADE SCISSORS,
    # U+2701) — covered by DejaVu Sans' Dingbats Unicode block.
    path = font.get_glyph_path(0x21)
    assert path, "ZapfDingbats code 0x21 should resolve to a real DejaVu glyph"
    assert any(cmd[0] == "moveto" for cmd in path)
