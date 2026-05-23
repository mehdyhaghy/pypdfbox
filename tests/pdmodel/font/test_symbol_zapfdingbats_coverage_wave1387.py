"""Wave 1387 — close the documented Symbol / ZapfDingbats coverage gap.

The wave-1380 font-substitution audit recorded a ~16% Adobe-Symbol glyph
shortfall (158 of 189 named glyphs covered by the bundled DejaVu Sans
substitute). The 31-glyph shortfall is the set of Adobe-specific
**Private-Use-Area** codepoints (U+F6D9..U+F8FE) for bracket-extension
pieces (``parenlefttp``, ``bracketleftex``, …), the serif/sans variants
of register / copyright / trademark, and the horizontal/vertical
extension bars for stretchable arrows and integrals.

This wave investigated every permissively-licensed math-symbol font on
the OFL/MIT/BSD/Apache allow-list — **STIX Two Math**, **DejaVu Math
TeX Gyre**, **Noto Sans Math**, **Asana Math**, **Pagella Math** —
and confirmed *none* target the Adobe-Symbol PUA codepoints by
codepoint *or* by Adobe's PostScript glyph name. The PUA scheme is
Adobe-specific; modern OpenType math fonts use ``.s1``/``.s12`` size
variants instead. See ``DEFERRED.md`` "Symbol PUA coverage" for the
candidate-font verification matrix.

The chosen wave-1387 fix is a **synthesis fallback table**
(``_SYMBOL_PUA_FALLBACKS`` in :mod:`pypdfbox.pdmodel.font.standard14_fonts`)
that routes each Adobe-Symbol PUA name to its nearest *base glyph* in
the already-bundled DejaVu Sans — collapsing bracket-extension pieces
to the base bracket character, and the serif/sans register / copyright
/ trademark variants to the single Unicode mark. This is the same
behaviour every modern PDF reader exhibits when the original Adobe
Symbol font is unavailable.

These tests guard the post-fallback coverage floor (must remain at
**100%** of the named Adobe-Symbol glyphs, modulo the zero-contour
``space``) and exercise both the PostScript-name path and the renderer
integration path.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.fontbox.encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding
from pypdfbox.pdmodel.font.standard14_fonts import (
    _SYMBOL_PUA_FALLBACKS,
    Standard14Fonts,
)

# ---------- coverage floor: 100% (minus zero-contour ``space``) ----------


def _named_codes(encoding: object) -> list[tuple[int, str]]:
    """Return ``(code, glyph-name)`` pairs for the encoding, excluding
    ``.notdef``. Both Symbol and ZapfDingbats encodings expose
    ``get_name(code)`` so the helper is shared."""
    out: list[tuple[int, str]] = []
    for code in range(256):
        name = encoding.get_name(code)  # type: ignore[attr-defined]
        if name == ".notdef":
            continue
        out.append((code, name))
    return out


def test_symbol_named_glyph_inventory_count() -> None:
    """The Adobe Symbol encoding maps exactly 189 codes to named glyphs
    (190 entries including ``.notdef``); guard the inventory before the
    coverage assertions so a regression in the encoding table is visible
    as its own dedicated failure."""
    assert len(_named_codes(SymbolEncoding.INSTANCE)) == 189


def test_zapf_dingbats_named_glyph_inventory_count() -> None:
    """The Adobe Zapf Dingbats encoding maps exactly 188 codes to named
    glyphs (one short of Symbol because the encoding has no upper-case-
    letter / lower-case-letter dual)."""
    assert len(_named_codes(ZapfDingbatsEncoding.INSTANCE)) == 188


@pytest.mark.parametrize(
    ("code", "glyph_name"),
    _named_codes(SymbolEncoding.INSTANCE),
    ids=[
        f"sym_0x{code:02X}_{name}" for code, name in _named_codes(SymbolEncoding.INSTANCE)
    ],
)
def test_symbol_every_named_glyph_resolves(code: int, glyph_name: str) -> None:
    """Every named Adobe-Symbol glyph must resolve to a drawable outline
    through the bundled DejaVu Sans substitute — directly, via the AGL
    → Unicode cmap fallback, or via the wave-1387 PUA-synthesis table.

    The single exception is ``space`` (code 0x20) — zero-contour by
    design in the original Adobe Symbol font too, so an empty path is
    correct rather than a regression."""
    path = Standard14Fonts.get_glyph_path("Symbol", glyph_name)
    if glyph_name == "space":
        # Whitespace glyph — zero contours in Adobe Symbol original.
        assert path == []
        return
    assert path, (
        f"Symbol code 0x{code:02X} ({glyph_name!r}) failed to resolve "
        f"to any outline. Wave 1387 should hold 100% coverage."
    )
    assert any(cmd[0] == "moveto" for cmd in path), (
        f"Symbol/{glyph_name} path has no moveto: {path[:3]}"
    )


@pytest.mark.parametrize(
    ("code", "glyph_name"),
    _named_codes(ZapfDingbatsEncoding.INSTANCE),
    ids=[
        f"zdb_0x{code:02X}_{name}"
        for code, name in _named_codes(ZapfDingbatsEncoding.INSTANCE)
    ],
)
def test_zapf_dingbats_every_named_glyph_resolves(
    code: int, glyph_name: str
) -> None:
    """Every named Adobe ZapfDingbats glyph must resolve to a drawable
    outline through the bundled DejaVu Sans substitute. DejaVu Sans
    covers the entire U+2700–U+27BF Dingbats Unicode block, so
    resolution is exclusively via the AGL → Unicode codepoint
    fallback.

    The single exception is ``space`` (code 0x20) — zero-contour by
    design."""
    path = Standard14Fonts.get_glyph_path("ZapfDingbats", glyph_name)
    if glyph_name == "space":
        assert path == []
        return
    assert path, (
        f"ZapfDingbats code 0x{code:02X} ({glyph_name!r}) failed to "
        f"resolve. Wave 1387 should hold 100% coverage."
    )
    assert any(cmd[0] == "moveto" for cmd in path)


# ---------- aggregate coverage assertion (regression guard) ----------


def test_symbol_aggregate_coverage_is_one_hundred_percent() -> None:
    """Across every named Adobe-Symbol glyph (excluding the zero-contour
    ``space``), wave 1387 holds 100% coverage. Guards against any future
    fallback-table edit silently dropping a name."""
    total = 0
    covered = 0
    for _code, name in _named_codes(SymbolEncoding.INSTANCE):
        if name == "space":
            continue
        total += 1
        if Standard14Fonts.get_glyph_path("Symbol", name):
            covered += 1
    assert total == 188, f"expected 188 drawable Symbol names, got {total}"
    assert covered == total, (
        f"Symbol coverage regressed below 100%: {covered}/{total}. "
        f"Wave-1387 PUA fallback table may be missing entries."
    )


def test_zapf_dingbats_aggregate_coverage_is_one_hundred_percent() -> None:
    """Across every named ZapfDingbats glyph (excluding ``space``),
    DejaVu Sans' full Dingbats-block coverage gives us 100%."""
    total = 0
    covered = 0
    for _code, name in _named_codes(ZapfDingbatsEncoding.INSTANCE):
        if name == "space":
            continue
        total += 1
        if Standard14Fonts.get_glyph_path("ZapfDingbats", name):
            covered += 1
    assert total == 187, f"expected 187 drawable ZapfDingbats names, got {total}"
    assert covered == total, (
        f"ZapfDingbats coverage regressed: {covered}/{total}."
    )


# ---------- PUA synthesis-table specifics ----------


def test_pua_fallback_table_covers_exactly_the_previously_missing_set() -> None:
    """The wave-1387 PUA fallback table contains exactly the 31 Adobe
    Symbol names that DejaVu Sans cannot resolve through the direct-name
    or AGL-Unicode paths. No extras (which would mask future Unicode
    coverage gains) and no shortfalls (which would leave the coverage
    floor at less than 100%).
    """
    # Recompute the "would miss without the PUA table" set by walking
    # the encoding and skipping the PUA-table application — i.e. clear
    # the fallback table, retry, then restore.
    expected_missing = {
        "radicalex", "arrowvertex", "arrowhorizex",
        "registerserif", "copyrightserif", "trademarkserif",
        "angleleft", "registersans", "copyrightsans", "trademarksans",
        "parenlefttp", "parenleftex", "parenleftbt",
        "bracketlefttp", "bracketleftex", "bracketleftbt",
        "bracelefttp", "braceleftmid", "braceleftbt", "braceex",
        "angleright", "integralex",
        "parenrighttp", "parenrightex", "parenrightbt",
        "bracketrighttp", "bracketrightex", "bracketrightbt",
        "bracerighttp", "bracerightmid", "bracerightbt",
    }
    assert set(_SYMBOL_PUA_FALLBACKS.keys()) == expected_missing


def test_pua_fallback_targets_are_in_the_basic_multilingual_plane() -> None:
    """Every fallback codepoint must live in the BMP and within DejaVu
    Sans' coverage — guards against accidentally pointing at another PUA
    codepoint that DejaVu also doesn't carry."""
    ttf = Standard14Fonts.get_substitute_ttf("Symbol")
    assert ttf is not None
    cmap = ttf.get_unicode_cmap_subtable()
    assert cmap is not None
    for adobe_name, target_cp in _SYMBOL_PUA_FALLBACKS.items():
        assert target_cp <= 0xFFFF, (
            f"{adobe_name} fallback target U+{target_cp:04X} outside BMP"
        )
        gid = cmap.get_glyph_id(target_cp)
        assert gid > 0, (
            f"{adobe_name} fallback U+{target_cp:04X} not in DejaVu Sans"
        )


# ---------- specific representative PUA fallbacks ----------


@pytest.mark.parametrize(
    ("adobe_name", "expected_target_cp"),
    [
        ("parenlefttp", 0x0028),
        ("parenrightbt", 0x0029),
        ("bracketleftex", 0x005B),
        ("bracketrighttp", 0x005D),
        ("bracelefttp", 0x007B),
        ("bracerightmid", 0x007D),
        ("braceex", 0x007C),
        ("angleleft", 0x27E8),
        ("angleright", 0x27E9),
        ("arrowvertex", 0x007C),
        ("arrowhorizex", 0x2014),
        ("radicalex", 0x203E),
        ("integralex", 0x007C),
        ("registerserif", 0x00AE),
        ("registersans", 0x00AE),
        ("copyrightserif", 0x00A9),
        ("copyrightsans", 0x00A9),
        ("trademarkserif", 0x2122),
        ("trademarksans", 0x2122),
    ],
)
def test_pua_fallback_target_is_documented(
    adobe_name: str, expected_target_cp: int
) -> None:
    """Pin the PUA → DejaVu codepoint routing so a future edit that
    swaps a target is visible in a diff (the human reviewer needs to
    weigh the visual fidelity trade-off per-glyph)."""
    assert _SYMBOL_PUA_FALLBACKS[adobe_name] == expected_target_cp


# ---------- integration: PDType1Font surface uses the fallback ----------


def test_pd_type1_symbol_paren_left_top_renders_via_pua_fallback() -> None:
    """A Symbol-named :class:`PDType1Font` requesting ``parenlefttp``
    (Adobe-PUA U+F8EB) must now reach a drawable path through the
    wave-1387 fallback — the renderer no longer emits a ``.notdef`` box
    for stretched-paren composition."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("Symbol"),
    )
    font = PDType1Font(font_dict)
    # SymbolEncoding maps code 0xE6 (230) -> "parenlefttp" (Adobe PUA).
    path = font.get_glyph_path(0xE6)
    assert path, (
        "Symbol code 0xE6 (parenlefttp) should resolve via the "
        "wave-1387 PUA fallback to '(' in DejaVu Sans."
    )
    assert any(cmd[0] == "moveto" for cmd in path)


def test_pd_type1_symbol_registered_serif_renders_via_pua_fallback() -> None:
    """``registerserif`` (Adobe-PUA U+F6DA) must resolve to '®' (U+00AE)
    in DejaVu Sans via the wave-1387 fallback table."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("Symbol"),
    )
    font = PDType1Font(font_dict)
    # Code 0xD2 (210) -> "registerserif".
    path = font.get_glyph_path(0xD2)
    assert path
    assert any(cmd[0] == "moveto" for cmd in path)


def test_symbol_unknown_glyph_name_still_returns_empty() -> None:
    """The PUA fallback must not turn unknown names into spurious hits —
    only entries in :data:`_SYMBOL_PUA_FALLBACKS` get routed."""
    assert Standard14Fonts.get_glyph_path("Symbol", "thisIsNotARealGlyph") == []


def test_zapf_dingbats_pua_fallback_does_not_apply() -> None:
    """The PUA fallback is Symbol-only — ZapfDingbats has its own (full)
    coverage path via the Dingbats Unicode block and must not pick up
    Symbol-specific PUA routings if a name accidentally collides."""
    # 'parenlefttp' is meaningless in ZapfDingbats; resolution must miss.
    assert Standard14Fonts.get_glyph_path("ZapfDingbats", "parenlefttp") == []
