from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# The 14 canonical names from PDF 32000-1:2008 §9.6.2.2.
_BASE_14 = [
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Symbol",
    "ZapfDingbats",
]


# ---------- class constants ----------


def test_class_constants_match_canonical_names() -> None:
    assert Standard14Fonts.HELVETICA == "Helvetica"
    assert Standard14Fonts.HELVETICA_BOLD == "Helvetica-Bold"
    assert Standard14Fonts.HELVETICA_OBLIQUE == "Helvetica-Oblique"
    assert Standard14Fonts.HELVETICA_BOLD_OBLIQUE == "Helvetica-BoldOblique"
    assert Standard14Fonts.TIMES_ROMAN == "Times-Roman"
    assert Standard14Fonts.TIMES_BOLD == "Times-Bold"
    assert Standard14Fonts.TIMES_ITALIC == "Times-Italic"
    assert Standard14Fonts.TIMES_BOLD_ITALIC == "Times-BoldItalic"
    assert Standard14Fonts.COURIER == "Courier"
    assert Standard14Fonts.COURIER_BOLD == "Courier-Bold"
    assert Standard14Fonts.COURIER_OBLIQUE == "Courier-Oblique"
    assert Standard14Fonts.COURIER_BOLD_OBLIQUE == "Courier-BoldOblique"
    assert Standard14Fonts.SYMBOL == "Symbol"
    assert Standard14Fonts.ZAPF_DINGBATS == "ZapfDingbats"


# ---------- contains_name / get_mapped_font_name ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_contains_name_recognises_all_14_base_names(name: str) -> None:
    assert Standard14Fonts.contains_name(name) is True


@pytest.mark.parametrize("name", _BASE_14)
def test_get_mapped_font_name_is_identity_for_canonical_names(name: str) -> None:
    assert Standard14Fonts.get_mapped_font_name(name) == name


def test_contains_name_recognises_arial_alias() -> None:
    assert Standard14Fonts.contains_name("Arial") is True


def test_get_mapped_font_name_resolves_arial_to_helvetica() -> None:
    assert Standard14Fonts.get_mapped_font_name("Arial") == "Helvetica"


def test_get_mapped_font_name_resolves_microsoft_aliases() -> None:
    assert Standard14Fonts.get_mapped_font_name("TimesNewRoman") == "Times-Roman"
    assert Standard14Fonts.get_mapped_font_name("CourierNew") == "Courier"
    assert Standard14Fonts.get_mapped_font_name("ArialMT") == "Helvetica"
    assert Standard14Fonts.get_mapped_font_name("CourierNewPS-BoldMT") == "Courier-Bold"


def test_lookup_is_case_insensitive_on_input() -> None:
    assert Standard14Fonts.contains_name("helvetica") is True
    assert Standard14Fonts.contains_name("ARIAL") is True
    # Output is always the exactly-cased canonical name.
    assert Standard14Fonts.get_mapped_font_name("helvetica-bold") == "Helvetica-Bold"
    assert Standard14Fonts.get_mapped_font_name("zapfdingbats") == "ZapfDingbats"


def test_unknown_names_are_rejected() -> None:
    assert Standard14Fonts.contains_name("NotAFont") is False
    assert Standard14Fonts.contains_name(None) is False
    assert Standard14Fonts.get_mapped_font_name("NotAFont") is None
    assert Standard14Fonts.get_mapped_font_name(None) is None


# ---------- get_average_widths ----------


def test_courier_widths_are_600_across_256_slots() -> None:
    """Encoded slots are 600 (monospace); unmapped slots are 0."""
    widths = Standard14Fonts.get_average_widths("Courier")
    assert isinstance(widths, list)
    assert len(widths) == 256
    nonzero = {w for w in widths if w > 0}
    assert nonzero == {600.0}


@pytest.mark.parametrize("name", ["Courier-Bold", "Courier-Oblique", "Courier-BoldOblique"])
def test_all_courier_variants_are_monospace_600(name: str) -> None:
    widths = Standard14Fonts.get_average_widths(name)
    assert len(widths) == 256
    nonzero = {w for w in widths if w > 0}
    assert nonzero == {600.0}


@pytest.mark.parametrize(
    "name",
    [
        "Helvetica",
        "Helvetica-Bold",
        "Times-Roman",
        "Times-BoldItalic",
        "Symbol",
        "ZapfDingbats",
    ],
)
def test_proportional_families_have_full_256_table_with_real_afm_widths(name: str) -> None:
    """With AFM bundling, the table is real per-glyph data, not a flat 500.

    Encoded slots carry the AFM advance width (a positive number); unmapped
    or ``.notdef`` slots carry ``0.0``. At least one slot must be non-zero
    or the encoding/AFM wiring is broken.
    """
    widths = Standard14Fonts.get_average_widths(name)
    assert len(widths) == 256
    assert any(w > 0.0 for w in widths)
    assert all(w >= 0.0 for w in widths)


def test_get_average_widths_resolves_alias() -> None:
    # Arial alias should reach Helvetica's table.
    arial = Standard14Fonts.get_average_widths("Arial")
    helvetica = Standard14Fonts.get_average_widths("Helvetica")
    assert arial == helvetica


def test_get_average_widths_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_average_widths("NotAFont")


# ---------- get_font_descriptor ----------


def test_get_font_descriptor_for_times_roman_has_expected_shape() -> None:
    fd = Standard14Fonts.get_font_descriptor("Times-Roman")
    assert isinstance(fd, dict)
    assert fd["FontName"] == "Times-Roman"
    assert isinstance(fd["Flags"], int) and fd["Flags"] > 0
    assert isinstance(fd["FontBBox"], list) and len(fd["FontBBox"]) == 4
    assert all(isinstance(v, float) for v in fd["FontBBox"])
    # Numeric metrics are floats.
    for key in ("ItalicAngle", "Ascent", "Descent", "CapHeight", "XHeight", "StemV"):
        assert isinstance(fd[key], float), key
    # Times-Roman has positive ascent and a sane descent.
    assert fd["Ascent"] > 0
    assert fd["Descent"] < 0


def test_get_font_descriptor_resolves_alias_to_canonical_font_name() -> None:
    fd = Standard14Fonts.get_font_descriptor("Arial")
    assert fd["FontName"] == "Helvetica"


def test_get_font_descriptor_courier_is_fixed_pitch() -> None:
    fd = Standard14Fonts.get_font_descriptor("Courier")
    # Bit 0 of Flags is FixedPitch (PDF 32000-1:2008 §9.8.2 Table 123).
    assert fd["Flags"] & 0b1 == 0b1


def test_get_font_descriptor_symbol_is_symbolic() -> None:
    fd = Standard14Fonts.get_font_descriptor("Symbol")
    # Bit 2 of Flags is Symbolic.
    assert fd["Flags"] & 0b100 == 0b100


def test_get_font_descriptor_italic_variants_have_negative_italic_angle() -> None:
    for name in ("Helvetica-Oblique", "Times-Italic", "Times-BoldItalic", "Courier-Oblique"):
        fd = Standard14Fonts.get_font_descriptor(name)
        assert fd["ItalicAngle"] < 0, name


def test_get_font_descriptor_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_font_descriptor("NotAFont")


# ---------- upstream-only aliases (round-out parity) ----------


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        # Adobe Supplement to ISO 32000 — bare "Times" family (Apple-style
        # naming) and the "Symbol,*" pseudo-italic/bold variants Acrobat
        # treats as Standard 14 even though only upright Symbol exists.
        ("Times", "Times-Roman"),
        ("Times,Bold", "Times-Bold"),
        ("Times,Italic", "Times-Italic"),
        ("Times,BoldItalic", "Times-BoldItalic"),
        ("Symbol,Bold", "Symbol"),
        ("Symbol,Italic", "Symbol"),
        ("Symbol,BoldItalic", "Symbol"),
        # Acrobat-only "CourierCourierNew" double-prefix substitution.
        ("CourierCourierNew", "Courier"),
    ],
)
def test_upstream_only_aliases_resolve_to_canonical_names(
    alias: str, canonical: str
) -> None:
    assert Standard14Fonts.contains_name(alias) is True
    assert Standard14Fonts.get_mapped_font_name(alias) == canonical


def test_upstream_only_aliases_appear_in_get_aliases() -> None:
    aliases = Standard14Fonts.get_aliases()
    assert aliases["Times"] == "Times-Roman"
    assert aliases["Symbol,Bold"] == "Symbol"
    assert aliases["Symbol,BoldItalic"] == "Symbol"
    assert aliases["CourierCourierNew"] == "Courier"


def test_upstream_only_aliases_route_average_widths_to_canonical_table() -> None:
    # All "Times" aliases must produce the same width table as Times-Roman.
    times = Standard14Fonts.get_average_widths("Times")
    times_roman = Standard14Fonts.get_average_widths("Times-Roman")
    assert times == times_roman
    # Symbol,Italic must map to plain Symbol's table.
    symbol_italic = Standard14Fonts.get_average_widths("Symbol,Italic")
    symbol = Standard14Fonts.get_average_widths("Symbol")
    assert symbol_italic == symbol


# ---------- is_canonical_name (Wave 202) ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_is_canonical_name_true_for_each_of_the_14_base_names(name: str) -> None:
    assert Standard14Fonts.is_canonical_name(name) is True


@pytest.mark.parametrize(
    "alias",
    ["Arial", "ArialMT", "TimesNewRoman", "CourierNew", "Times", "Symbol,Bold"],
)
def test_is_canonical_name_false_for_aliases(alias: str) -> None:
    """Aliases are recognised by ``contains_name`` but not ``is_canonical_name``."""
    assert Standard14Fonts.contains_name(alias) is True
    assert Standard14Fonts.is_canonical_name(alias) is False


def test_is_canonical_name_is_case_insensitive() -> None:
    assert Standard14Fonts.is_canonical_name("helvetica") is True
    assert Standard14Fonts.is_canonical_name("HELVETICA-BOLD") is True
    assert Standard14Fonts.is_canonical_name("zapfdingbats") is True


def test_is_canonical_name_handles_none_and_unknown() -> None:
    assert Standard14Fonts.is_canonical_name(None) is False
    assert Standard14Fonts.is_canonical_name("") is False
    assert Standard14Fonts.is_canonical_name("NotAFont") is False


# ---------- has_alias (Wave 202) ----------


@pytest.mark.parametrize(
    "alias",
    [
        "Arial",
        "ArialMT",
        "TimesNewRoman",
        "TimesNewRomanPS-BoldMT",
        "CourierNew",
        "CourierCourierNew",
        "Times",
        "Times,Bold",
        "Symbol,Italic",
    ],
)
def test_has_alias_true_for_registered_aliases(alias: str) -> None:
    assert Standard14Fonts.has_alias(alias) is True


@pytest.mark.parametrize("name", _BASE_14)
def test_has_alias_false_for_canonical_names(name: str) -> None:
    """Canonical names are not aliases of themselves."""
    assert Standard14Fonts.has_alias(name) is False


def test_has_alias_handles_none_and_unknown() -> None:
    assert Standard14Fonts.has_alias(None) is False
    assert Standard14Fonts.has_alias("") is False
    assert Standard14Fonts.has_alias("NotAFont") is False


def test_has_alias_is_case_insensitive() -> None:
    assert Standard14Fonts.has_alias("arial") is True
    assert Standard14Fonts.has_alias("ARIALMT") is True


def test_is_canonical_name_and_has_alias_partition_known_names() -> None:
    """Every known name is exactly one of: canonical or alias (never both, never neither)."""
    for known in Standard14Fonts.get_all_names():
        is_canonical = Standard14Fonts.is_canonical_name(known)
        is_alias = Standard14Fonts.has_alias(known)
        assert is_canonical ^ is_alias, known  # exclusive-or: exactly one
        assert Standard14Fonts.contains_name(known) is True


# ---------- resolve (Wave 202) ----------


def test_resolve_returns_canonical_for_known_canonical_name() -> None:
    assert Standard14Fonts.resolve("Helvetica") == "Helvetica"


def test_resolve_returns_canonical_for_known_alias() -> None:
    assert Standard14Fonts.resolve("ArialMT") == "Helvetica"


def test_resolve_returns_default_for_unknown_name() -> None:
    assert Standard14Fonts.resolve("NotAFont") is None
    assert Standard14Fonts.resolve("NotAFont", default="Helvetica") == "Helvetica"
    assert Standard14Fonts.resolve("NotAFont", default="fallback") == "fallback"


def test_resolve_returns_default_for_none_input() -> None:
    assert Standard14Fonts.resolve(None) is None
    assert Standard14Fonts.resolve(None, default="Helvetica") == "Helvetica"


def test_resolve_can_echo_input_via_default() -> None:
    """Common pattern: ``resolve(name, default=name)`` keeps unknown names as-is."""
    assert Standard14Fonts.resolve("MyCustomFont", default="MyCustomFont") == "MyCustomFont"
    assert Standard14Fonts.resolve("Arial", default="Arial") == "Helvetica"


def test_resolve_is_case_insensitive() -> None:
    assert Standard14Fonts.resolve("arial") == "Helvetica"
    assert Standard14Fonts.resolve("HELVETICA-BOLD") == "Helvetica-Bold"


# ---------- get_all_names (Wave 202) ----------


def test_get_all_names_includes_every_canonical_name() -> None:
    all_names = Standard14Fonts.get_all_names()
    assert isinstance(all_names, set)
    for canonical in _BASE_14:
        assert canonical in all_names


def test_get_all_names_includes_every_alias() -> None:
    all_names = Standard14Fonts.get_all_names()
    aliases = Standard14Fonts.get_aliases()
    for alias in aliases:
        assert alias in all_names, alias


def test_get_all_names_size_matches_canonical_plus_aliases() -> None:
    all_names = Standard14Fonts.get_all_names()
    # 14 canonical + the alias map's keys (no canonical/alias collisions).
    assert len(all_names) == 14 + len(Standard14Fonts.get_aliases())


def test_get_all_names_returns_a_defensive_copy() -> None:
    a = Standard14Fonts.get_all_names()
    a.add("BogusFont")
    # A second call must not see the mutation.
    assert "BogusFont" not in Standard14Fonts.get_all_names()


def test_get_names_and_get_all_names_differ_by_alias_set() -> None:
    """Pypdfbox extension: ``get_names`` is canonical-only; ``get_all_names`` matches upstream."""
    canonical = Standard14Fonts.get_names()
    all_names = Standard14Fonts.get_all_names()
    assert canonical < all_names  # strict subset
    assert all_names - canonical == set(Standard14Fonts.get_aliases())


# ---------- map_name / load_metrics / get_mapped_font / get_glyph_list / get_glyph_path ----------


def test_load_metrics_for_each_canonical_returns_metrics() -> None:
    from pypdfbox.pdmodel.font.afm_loader import AfmMetrics

    for name in _BASE_14:
        metrics = Standard14Fonts.load_metrics(name)
        assert isinstance(metrics, AfmMetrics)
        assert metrics.get_font_name() == name


def test_load_metrics_caches_result() -> None:
    first = Standard14Fonts.load_metrics("Times-Roman")
    second = Standard14Fonts.load_metrics("Times-Roman")
    assert first is second


def test_load_metrics_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.load_metrics("NotAFont")


def test_load_metrics_rejects_alias_input() -> None:
    """``load_metrics`` mirrors the upstream private ``FontName``-typed form
    — aliases must go through :meth:`get_afm`."""
    with pytest.raises(ValueError):
        Standard14Fonts.load_metrics("Arial")


def test_map_name_extends_alias_table() -> None:
    try:
        Standard14Fonts.map_name("HelveticaWaveAlias", "Helvetica")
        assert Standard14Fonts.contains_name("HelveticaWaveAlias") is True
        assert (
            Standard14Fonts.get_mapped_font_name("HelveticaWaveAlias")
            == "Helvetica"
        )
        assert "HelveticaWaveAlias" in Standard14Fonts.get_aliases()
    finally:
        from pypdfbox.pdmodel.font.standard14_fonts import (
            _ALIASES,
            _NAME_LOOKUP,
        )

        _ALIASES.pop("HelveticaWaveAlias", None)
        _NAME_LOOKUP.pop("helveticawavealias", None)


def test_map_name_self_seed_form() -> None:
    """The single-argument form (mirror of upstream's ``mapName(FontName)``)
    seeds a self-mapping for a canonical name without altering the alias map."""
    aliases_before = dict(Standard14Fonts.get_aliases())
    Standard14Fonts.map_name("Helvetica")
    assert Standard14Fonts.contains_name("Helvetica") is True
    # No alias added — self-mapping is canonical-only.
    assert Standard14Fonts.get_aliases() == aliases_before


def test_map_name_rejects_unknown_target() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.map_name("MyAlias", "NotAFont")


def test_get_mapped_font_returns_wrapper_with_canonical_name() -> None:
    wrapper = Standard14Fonts.get_mapped_font("Helvetica")
    assert wrapper.get_name() == "Helvetica"
    # Wrapper exposes the FontBoxFont protocol.
    assert hasattr(wrapper, "has_glyph")
    assert hasattr(wrapper, "get_path")
    assert hasattr(wrapper, "get_width")


def test_get_mapped_font_caches() -> None:
    a = Standard14Fonts.get_mapped_font("Times-Roman")
    b = Standard14Fonts.get_mapped_font("Times-Roman")
    assert a is b


def test_get_mapped_font_through_alias_returns_canonical_wrapper() -> None:
    via_alias = Standard14Fonts.get_mapped_font("ArialMT")
    via_canonical = Standard14Fonts.get_mapped_font("Helvetica")
    assert via_alias is via_canonical


def test_get_mapped_font_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_mapped_font("NotAFont")


def test_get_glyph_list_zapf_picks_zapf_list() -> None:
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList

    assert (
        Standard14Fonts.get_glyph_list("ZapfDingbats")
        is GlyphList.get_zapf_dingbats()
    )


@pytest.mark.parametrize(
    "name",
    ["Helvetica", "Helvetica-Bold", "Times-Italic", "Courier", "Symbol"],
)
def test_get_glyph_list_non_zapf_picks_adobe_list(name: str) -> None:
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList

    assert (
        Standard14Fonts.get_glyph_list(name) is GlyphList.get_adobe_glyph_list()
    )


def test_get_glyph_list_resolves_alias() -> None:
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList

    # ArialMT -> Helvetica, which uses the AGL (not Zapf).
    assert (
        Standard14Fonts.get_glyph_list("ArialMT")
        is GlyphList.get_adobe_glyph_list()
    )


def test_get_glyph_list_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_glyph_list("NotAFont")


def test_get_glyph_path_notdef_returns_empty() -> None:
    assert Standard14Fonts.get_glyph_path("Helvetica", ".notdef") == []


def test_get_glyph_path_unknown_font_returns_empty() -> None:
    """Upstream raises ``IllegalArgumentException``; pypdfbox draws nothing
    rather than aborting the rendering pipeline."""
    assert Standard14Fonts.get_glyph_path("NotAFont", "A") == []


def test_get_glyph_path_returns_list_type() -> None:
    """Wave 1303 wired up Liberation substitution — the result is a
    non-empty list of segment tuples for any glyph that exists in the
    Liberation TTF (the upstream ``GeneralPath`` analogue)."""
    path = Standard14Fonts.get_glyph_path("Helvetica", "A")
    assert isinstance(path, list)
    assert path  # Liberation has 'A' — Helvetica path is non-empty.
    # Each segment is a tagged tuple ("moveto", x, y) / ("lineto", ...)
    # / ("curveto", ...) / ("closepath",).
    tags = {cmd[0] for cmd in path}
    assert tags.issubset({"moveto", "lineto", "curveto", "closepath"})


def test_get_glyph_path_resolves_alias() -> None:
    """``ArialMT`` lookup goes through the canonical Helvetica wrapper
    and hits the same Liberation substitute outline."""
    direct = Standard14Fonts.get_glyph_path("Helvetica", "A")
    alias = Standard14Fonts.get_glyph_path("ArialMT", "A")
    assert isinstance(alias, list)
    assert alias == direct


# ---------- Liberation TTF substitution (wave 1303) ----------


_LIBERATION_MAPPED = [
    ("Helvetica", "LiberationSans"),
    ("Helvetica-Bold", "LiberationSans-Bold"),
    ("Helvetica-Oblique", "LiberationSans-Italic"),
    ("Helvetica-BoldOblique", "LiberationSans-BoldItalic"),
    ("Times-Roman", "LiberationSerif"),
    ("Times-Bold", "LiberationSerif-Bold"),
    ("Times-Italic", "LiberationSerif-Italic"),
    ("Times-BoldItalic", "LiberationSerif-BoldItalic"),
    ("Courier", "LiberationMono"),
    ("Courier-Bold", "LiberationMono-Bold"),
    ("Courier-Oblique", "LiberationMono-Italic"),
    ("Courier-BoldOblique", "LiberationMono-BoldItalic"),
]


@pytest.mark.parametrize(("canonical", "ttf_name"), _LIBERATION_MAPPED)
def test_get_substitute_ttf_maps_all_12_proportional_and_mono_families(
    canonical: str, ttf_name: str
) -> None:
    """Every Standard 14 name in the Helvetica / Times-Roman / Courier
    families must resolve to its bundled Liberation TTF substitute."""
    ttf = Standard14Fonts.get_substitute_ttf(canonical)
    assert ttf is not None, f"{canonical} should have a Liberation substitute"
    assert ttf.get_name() == ttf_name


@pytest.mark.parametrize("canonical", ["Symbol", "ZapfDingbats"])
def test_get_substitute_ttf_returns_none_for_symbol_and_zapf(
    canonical: str,
) -> None:
    """Symbol / ZapfDingbats have no Liberation equivalent — caller must
    keep using the placeholder rectangle for these two families."""
    assert Standard14Fonts.get_substitute_ttf(canonical) is None


def test_get_substitute_ttf_resolves_aliases() -> None:
    """Alias inputs (Arial / TimesNewRoman / CourierNew) resolve through
    the canonical-name table and reach the same TTF instance."""
    assert (
        Standard14Fonts.get_substitute_ttf("Arial")
        is Standard14Fonts.get_substitute_ttf("Helvetica")
    )
    assert (
        Standard14Fonts.get_substitute_ttf("TimesNewRoman")
        is Standard14Fonts.get_substitute_ttf("Times-Roman")
    )
    assert (
        Standard14Fonts.get_substitute_ttf("CourierNew")
        is Standard14Fonts.get_substitute_ttf("Courier")
    )


def test_get_substitute_ttf_is_cached() -> None:
    """Successive calls hand back the same parsed TTF instance — the
    SFNT parse cost is paid once."""
    first = Standard14Fonts.get_substitute_ttf("Helvetica")
    second = Standard14Fonts.get_substitute_ttf("Helvetica")
    assert first is second


def test_get_substitute_ttf_returns_none_for_unknown_name() -> None:
    """Names outside the Standard 14 / alias set return ``None`` rather
    than raising."""
    assert Standard14Fonts.get_substitute_ttf("CompletelyMadeUp") is None


def test_get_glyph_path_for_courier_returns_monospace_outline() -> None:
    """LiberationMono substitution covers Courier — 'A' resolves to a
    real outline, not the AFM-empty fallback."""
    path = Standard14Fonts.get_glyph_path("Courier", "A")
    assert path
    assert any(cmd[0] == "moveto" for cmd in path)


def test_get_glyph_path_for_symbol_returns_empty() -> None:
    """Symbol stays on the placeholder branch — Liberation has no
    matching glyph repertoire so we keep returning an empty list."""
    # Symbol's encoding has no 'A' glyph (it uses 'Alpha' instead);
    # check a name the Symbol AFM does carry but Liberation does not.
    assert Standard14Fonts.get_glyph_path("Symbol", "Alpha") == []


def test_uni_name_helper_pads_short_hex() -> None:
    """``_uni_name_of_code_point`` mirrors upstream ``UniUtil`` — pad to 4."""
    from pypdfbox.pdmodel.font.standard14_fonts import _uni_name_of_code_point

    assert _uni_name_of_code_point(0x41) == "uni0041"
    assert _uni_name_of_code_point(0x100) == "uni0100"
    assert _uni_name_of_code_point(0x1234) == "uni1234"
    assert _uni_name_of_code_point(0x10FFFF) == "uni10FFFF"
