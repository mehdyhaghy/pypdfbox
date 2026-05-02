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
