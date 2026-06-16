"""Fuzz / edge-case parity sweep for ``AFMParser`` + ``FontMetrics`` +
``CharMetric`` + ``KernPair`` and the ``Standard14Fonts`` name surface
(wave 1570, agent D).

Every assertion below was pinned against Apache PDFBox 3.0.7's actual
behaviour via a throwaway probe (``EdgeProbe`` / ``KernProbe`` /
``AliasDump``) run against ``oracle/jars/pdfbox-app-3.0.7.jar``. The
notable upstream behaviours captured here:

* A ``CharMetrics`` line that omits the ``C`` / ``CH`` entry leaves the
  character code at the Java field default ``0`` (not ``-1``). This was a
  real pypdfbox divergence fixed in this wave (``CharMetric.__init__``).
* ``WX`` is parsed as a float (``500.5`` survives), the bbox is read in
  ``llx lly urx ury`` order, and a missing ``WX`` defaults to ``0.0``.
* ``IsFixedPitch`` is a case-insensitive ``true`` test — ``True`` is true,
  ``yes`` / ``1`` are false (``Boolean.parseBoolean`` semantics).
* ``KPX`` yields ``y == 0``, ``KPY`` yields ``x == 0``, ``KP`` carries
  both, and negative kern displacements keep their sign.
* The reduced-dataset overload skips the whole kern / composite block.
* ``Standard14Fonts`` never mis-maps an alias upstream knows — pypdfbox's
  superset of ``-PS`` / ``-MT`` aliases and its case-insensitive lookup
  are a documented intentional leniency (CHANGES.md wave 1570); the
  canonical resolution of every name upstream *does* know is identical.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.afm import (
    AFMParser,
    CharMetric,
    FontMetrics,
    KernPair,
)
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADER = "StartFontMetrics 4.1\nFontName FuzzFont\n"


def _wrap(body: str) -> bytes:
    return (_HEADER + body + "EndFontMetrics\n").encode("latin-1")


def _parse(body: str, reduced: bool = False) -> FontMetrics:
    return AFMParser(_wrap(body)).parse(reduced_dataset=reduced)


def _cm(body: str) -> str:
    return f"StartCharMetrics 1\n{body}\nEndCharMetrics\n"


# ===========================================================================
# CharMetrics block — C / WX / N / B and the unencoded / missing-field cases
# ===========================================================================


def test_basic_char_metric_line() -> None:
    fm = _parse(_cm("C 65 ; WX 600 ; N A ; B 10 0 590 700 ;"))
    cm = fm.get_char_metrics()[0]
    assert cm.get_character_code() == 65
    assert cm.get_wx() == 600.0
    assert cm.get_name() == "A"
    bbox = cm.get_bounding_box()
    assert bbox is not None
    # bbox is read in llx lly urx ury order.
    assert (
        bbox.get_lower_left_x(),
        bbox.get_lower_left_y(),
        bbox.get_upper_right_x(),
        bbox.get_upper_right_y(),
    ) == (10.0, 0.0, 590.0, 700.0)


def test_unencoded_glyph_c_minus_one() -> None:
    # C -1 is the canonical "unencoded glyph" form; the code is -1.
    fm = _parse(_cm("C -1 ; WX 250 ; N space ;"))
    assert fm.get_char_metrics()[0].get_character_code() == -1


def test_char_metric_missing_c_defaults_to_zero() -> None:
    # Upstream CharMetric.characterCode is a plain int field -> default 0.
    # A line that omits C/CH leaves it at 0 (NOT -1). Pinned via EdgeProbe.
    fm = _parse(_cm("WX 500 ; N foo ;"))
    cm = fm.get_char_metrics()[0]
    assert cm.get_character_code() == 0
    assert cm.get_name() == "foo"


def test_default_char_metric_code_is_zero() -> None:
    assert CharMetric().get_character_code() == 0


def test_char_metric_missing_wx_defaults_to_zero() -> None:
    fm = _parse(_cm("C 65 ; N A ;"))
    cm = fm.get_char_metrics()[0]
    assert cm.get_wx() == 0.0
    assert cm.get_character_code() == 65


def test_char_metric_missing_name_is_empty_string() -> None:
    fm = _parse(_cm("C 65 ; WX 500 ;"))
    assert fm.get_char_metrics()[0].get_name() == ""


def test_wx_parsed_as_float_keeps_fraction() -> None:
    fm = _parse(_cm("C 65 ; WX 500.5 ; N A ;"))
    assert fm.get_char_metrics()[0].get_wx() == 500.5


def test_wx_negative_keeps_sign() -> None:
    fm = _parse(_cm("C 66 ; WX -50 ; N B ;"))
    assert fm.get_char_metrics()[0].get_wx() == -50.0


def test_char_metric_trailing_semicolon_optional() -> None:
    # No trailing ';' on the final entry — upstream tolerates either.
    fm = _parse(_cm("C 65 ; WX 500 ; N A"))
    assert fm.get_char_metrics()[0].get_name() == "A"


def test_char_metric_hex_code_bare() -> None:
    # CH 41 -> bare hex, parity with upstream parseInt(token, 16).
    fm = _parse(_cm("CH 41 ; WX 500 ; N A ;"))
    assert fm.get_char_metrics()[0].get_character_code() == 0x41


def test_char_metric_hex_code_bracketed_is_lenient_accept() -> None:
    # Upstream REJECTS <41> (NumberFormatException). pypdfbox deliberately
    # accepts the angle-bracketed form (documented leniency, CHANGES wave316).
    fm = _parse(_cm("CH <41> ; WX 500 ; N A ;"))
    assert fm.get_char_metrics()[0].get_character_code() == 0x41


def test_char_metric_wy_field() -> None:
    fm = _parse(_cm("C 65 ; WX 500 ; WY 300 ; N A ;"))
    assert fm.get_char_metrics()[0].get_wy() == 300.0


def test_char_metric_w_pair() -> None:
    fm = _parse(_cm("C 65 ; W 500 0 ; N A ;"))
    w = fm.get_char_metrics()[0].get_w()
    assert w == (500.0, 0.0)


def test_char_metric_ligature() -> None:
    fm = _parse(_cm("C 102 ; WX 333 ; N f ; L i fi ; L l fl ;"))
    ligs = fm.get_char_metrics()[0].get_ligatures()
    assert [(lig.get_successor(), lig.get_ligature()) for lig in ligs] == [
        ("i", "fi"),
        ("l", "fl"),
    ]


def test_multiple_char_metrics_count() -> None:
    body = (
        "StartCharMetrics 3\n"
        "C 65 ; WX 600 ; N A ;\n"
        "C 66 ; WX 600 ; N B ;\n"
        "C 67 ; WX 600 ; N C ;\n"
        "EndCharMetrics\n"
    )
    fm = _parse(body)
    assert len(fm.get_char_metrics()) == 3
    assert fm.get_char_metric("B") is not None
    assert fm.has_char_metric("C") is True
    assert fm.has_char_metric("Z") is False


# ---------------------------------------------------------------------------
# Malformed CharMetrics — error vs lenient skip
# ---------------------------------------------------------------------------


def test_unknown_char_metric_command_raises() -> None:
    with pytest.raises(OSError):
        _parse(_cm("C 65 ; ZZ 9 ; N A ;"))


def test_char_metric_nonnumeric_wx_raises() -> None:
    with pytest.raises(OSError):
        _parse(_cm("C 65 ; WX notanumber ; N A ;"))


def test_char_metric_count_too_high_runs_into_terminator() -> None:
    # Declaring more metrics than present makes the parser consume the
    # EndCharMetrics line as a metric -> unknown command. Pinned upstream.
    body = (
        "StartCharMetrics 2\n"
        "C 65 ; WX 500 ; N A ;\n"
        "EndCharMetrics\n"
    )
    with pytest.raises(OSError):
        _parse(body)


def test_missing_semicolon_between_items_raises() -> None:
    # verify_semicolon: a non-';' token where a ';' is expected is an error.
    with pytest.raises(OSError):
        _parse(_cm("C 65 WX 500 ; N A ;"))


# ===========================================================================
# Header fields
# ===========================================================================


def test_header_font_name_and_bbox() -> None:
    fm = _parse(
        "FontBBox -100 -200 1000 900\n"
        "CapHeight 718\n"
        "Ascender 683\n"
        "Descender -217\n"
        "ItalicAngle -12.5\n"
        "IsFixedPitch false\n"
        "StartCharMetrics 0\nEndCharMetrics\n"
    )
    assert fm.get_font_name() == "FuzzFont"
    bbox = fm.get_font_b_box()
    assert bbox is not None
    assert (
        bbox.get_lower_left_x(),
        bbox.get_lower_left_y(),
        bbox.get_upper_right_x(),
        bbox.get_upper_right_y(),
    ) == (-100.0, -200.0, 1000.0, 900.0)
    assert fm.get_cap_height() == 718.0
    assert fm.get_ascender() == 683.0
    assert fm.get_descender() == -217.0
    assert fm.get_italic_angle() == -12.5
    assert fm.get_is_fixed_pitch() is False


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("false", False),
        ("False", False),
        ("yes", False),
        ("1", False),
    ],
    ids=["true", "True", "TRUE", "false", "False", "yes", "one"],
)
def test_is_fixed_pitch_boolean_parse(token: str, expected: bool) -> None:
    # Boolean.parseBoolean — only case-insensitive "true" is True.
    fm = _parse(
        f"IsFixedPitch {token}\nStartCharMetrics 0\nEndCharMetrics\n"
    )
    assert fm.get_is_fixed_pitch() is expected


def test_header_afm_version() -> None:
    fm = _parse("StartCharMetrics 0\nEndCharMetrics\n")
    assert fm.get_afm_version() == 4.1


def test_header_string_fields_use_rest_of_line() -> None:
    fm = _parse(
        "FullName Fuzz Font Regular\n"
        "FamilyName Fuzz Font\n"
        "Weight Medium\n"
        "Notice Copyright (c) nobody\n"
        "EncodingScheme AdobeStandardEncoding\n"
        "StartCharMetrics 0\nEndCharMetrics\n"
    )
    assert fm.get_full_name() == "Fuzz Font Regular"
    assert fm.get_family_name() == "Fuzz Font"
    assert fm.get_weight() == "Medium"
    assert fm.get_notice() == "Copyright (c) nobody"
    assert fm.get_encoding_scheme() == "AdobeStandardEncoding"


def test_comment_lines_collected() -> None:
    fm = _parse(
        "Comment first comment\n"
        "Comment second comment\n"
        "StartCharMetrics 0\nEndCharMetrics\n"
    )
    assert fm.get_comments() == ["first comment", "second comment"]


def test_unknown_header_key_raises_in_full_mode() -> None:
    with pytest.raises(OSError):
        _parse("BogusKey whatever\nStartCharMetrics 0\nEndCharMetrics\n")


def test_metric_sets_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        _parse("MetricSets 5\nStartCharMetrics 0\nEndCharMetrics\n")


def test_missing_start_font_metrics_raises() -> None:
    with pytest.raises(OSError):
        AFMParser(b"FontName X\nEndFontMetrics\n").parse()


# ===========================================================================
# Kern data — KP / KPX / KPY / KPH
# ===========================================================================


def _kern(body: str) -> FontMetrics:
    full = (
        "StartCharMetrics 2\n"
        "C 65 ; WX 600 ; N A ;\n"
        "C 66 ; WX 600 ; N B ;\n"
        "EndCharMetrics\n"
        "StartKernData\n"
        f"{body}"
        "EndKernData\n"
    )
    return _parse(full)


def test_kern_kpx_y_is_zero_and_sign_preserved() -> None:
    fm = _kern("StartKernPairs 1\nKPX A B -80\nEndKernPairs\n")
    kp = fm.get_kern_pairs()[0]
    assert (kp.get_first_kern_character(), kp.get_second_kern_character()) == (
        "A",
        "B",
    )
    assert kp.get_x() == -80.0
    assert kp.get_y() == 0.0


def test_kern_kpy_x_is_zero() -> None:
    fm = _kern("StartKernPairs 1\nKPY A B 40\nEndKernPairs\n")
    kp = fm.get_kern_pairs()[0]
    assert kp.get_x() == 0.0
    assert kp.get_y() == 40.0


def test_kern_kp_carries_both_axes() -> None:
    fm = _kern("StartKernPairs 1\nKP A B 10 20\nEndKernPairs\n")
    kp = fm.get_kern_pairs()[0]
    assert (kp.get_x(), kp.get_y()) == (10.0, 20.0)


def test_kern_kph_hex_pair_decodes() -> None:
    fm = _kern("StartKernPairs 1\nKPH <0041> <0042> -55 0\nEndKernPairs\n")
    kp = fm.get_kern_pairs()[0]
    # <0041> decodes (latin-1) to two chars \x00 A; sign preserved.
    assert kp.get_x() == -55.0


def test_kph_missing_second_number_raises() -> None:
    # KPH reads TWO floats; only one present -> EndKernPairs parsed as float.
    with pytest.raises(OSError):
        _kern("StartKernPairs 1\nKPH <0041> <0042> -55\nEndKernPairs\n")


def test_reduced_dataset_skips_kern_block() -> None:
    full = (
        "StartCharMetrics 2\n"
        "C 65 ; WX 600 ; N A ;\n"
        "C 66 ; WX 600 ; N B ;\n"
        "EndCharMetrics\n"
        "StartKernData\n"
        "StartKernPairs 1\nKPX A B -80\nEndKernPairs\n"
        "EndKernData\n"
    )
    fm = AFMParser(_wrap(full)).parse(reduced_dataset=True)
    assert fm.get_total_kern_pair_count() == 0
    # char metrics still parsed in reduced mode.
    assert len(fm.get_char_metrics()) == 2


def test_unknown_kern_data_type_raises() -> None:
    with pytest.raises(OSError):
        _kern("BogusKern 1\nKPX A B -80\nEndKernPairs\n")


def test_bad_kern_pair_command_raises() -> None:
    with pytest.raises(OSError):
        _kern("StartKernPairs 1\nZZ A B -80\nEndKernPairs\n")


# ===========================================================================
# FontMetrics width / height helpers
# ===========================================================================


def test_get_character_width_by_name() -> None:
    fm = _parse(_cm("C 65 ; WX 722 ; N A ;"))
    assert fm.get_character_width("A") == 722.0
    assert fm.get_character_width("missing") == 0.0


def test_get_character_height_uses_wy_when_nonzero() -> None:
    fm = _parse(_cm("C 65 ; WX 600 ; WY 300 ; N A ; B 0 0 500 700 ;"))
    # WY non-zero -> WY wins over bbox height.
    assert fm.get_character_height("A") == 300.0


def test_get_character_height_falls_back_to_bbox() -> None:
    fm = _parse(_cm("C 65 ; WX 600 ; N A ; B 0 -10 500 700 ;"))
    # No WY -> bbox height = 700 - (-10) = 710.
    assert fm.get_character_height("A") == 710.0


def test_get_character_height_unknown_glyph_zero() -> None:
    fm = _parse(_cm("C 65 ; WX 600 ; N A ;"))
    assert fm.get_character_height("missing") == 0.0
    # No WY and no bbox -> 0.
    assert fm.get_character_height("A") == 0.0


def test_average_character_width_ignores_nonpositive() -> None:
    body = (
        "StartCharMetrics 2\n"
        "C 65 ; WX 600 ; N A ;\n"
        "C 66 ; WX -50 ; N B ;\n"
        "EndCharMetrics\n"
    )
    fm = _parse(body)
    # Only the positive WX counts.
    assert fm.get_average_character_width() == 600.0


def test_get_char_metric_none_name_returns_none() -> None:
    fm = _parse(_cm("C 65 ; WX 600 ; N A ;"))
    assert fm.get_char_metric(None) is None  # type: ignore[arg-type]
    assert fm.has_char_metric(None) is False  # type: ignore[arg-type]


def test_parse_accepts_stream_input() -> None:
    fm = AFMParser(io.BytesIO(_wrap(_cm("C 65 ; WX 500 ; N A ;")))).parse()
    assert fm.get_character_width("A") == 500.0


# ===========================================================================
# KernPair value object
# ===========================================================================


def test_kern_pair_equality_and_hash() -> None:
    a = KernPair("A", "B", -80.0, 0.0)
    b = KernPair("A", "B", -80.0, 0.0)
    c = KernPair("A", "B", -80.0, 5.0)
    assert a == b
    assert a != c
    assert hash(a) == hash(b)


# ===========================================================================
# Standard14Fonts — name normalisation, get_afm, get_font_metrics
# ===========================================================================

_CANONICAL_14 = {
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
}

# Every alias upstream PDFBox 3.0.7 knows (AliasDump probe), mapped to its
# canonical name. pypdfbox must resolve each of these identically.
_UPSTREAM_ALIASES = {
    "Arial": "Helvetica",
    "Arial,Bold": "Helvetica-Bold",
    "Arial,BoldItalic": "Helvetica-BoldOblique",
    "Arial,Italic": "Helvetica-Oblique",
    "Arial-BoldItalicMT": "Helvetica-BoldOblique",
    "Arial-BoldMT": "Helvetica-Bold",
    "Arial-ItalicMT": "Helvetica-Oblique",
    "ArialMT": "Helvetica",
    "CourierCourierNew": "Courier",
    "CourierNew": "Courier",
    "CourierNew,Bold": "Courier-Bold",
    "CourierNew,BoldItalic": "Courier-BoldOblique",
    "CourierNew,Italic": "Courier-Oblique",
    "Symbol,Bold": "Symbol",
    "Symbol,BoldItalic": "Symbol",
    "Symbol,Italic": "Symbol",
    "Times": "Times-Roman",
    "Times,Bold": "Times-Bold",
    "Times,BoldItalic": "Times-BoldItalic",
    "Times,Italic": "Times-Italic",
    "TimesNewRoman": "Times-Roman",
    "TimesNewRoman,Bold": "Times-Bold",
    "TimesNewRoman,BoldItalic": "Times-BoldItalic",
    "TimesNewRoman,Italic": "Times-Italic",
}


@pytest.mark.parametrize("name", sorted(_CANONICAL_14))
def test_canonical_name_maps_to_itself(name: str) -> None:
    assert Standard14Fonts.get_mapped_font_name(name) == name
    assert Standard14Fonts.contains_name(name) is True


@pytest.mark.parametrize(
    ("alias", "canonical"),
    sorted(_UPSTREAM_ALIASES.items()),
    ids=sorted(a.replace(",", "_") for a in _UPSTREAM_ALIASES),
)
def test_upstream_alias_resolves_identically(
    alias: str, canonical: str
) -> None:
    # pypdfbox must never mis-map a name upstream PDFBox knows.
    assert Standard14Fonts.get_mapped_font_name(alias) == canonical
    assert Standard14Fonts.contains_name(alias) is True


def test_unknown_name_returns_none() -> None:
    assert Standard14Fonts.get_mapped_font_name("NoSuchFont-XYZ") is None
    assert Standard14Fonts.get_mapped_font_name(None) is None
    assert Standard14Fonts.contains_name("Wingdings") is False
    assert Standard14Fonts.contains_name("") is False


def test_case_insensitive_lookup_is_intentional_leniency() -> None:
    # Upstream lookup is case-SENSITIVE ("arial" -> null). pypdfbox is
    # case-insensitive by design (CHANGES.md wave 1570) — a documented
    # superset, never a wrong mapping.
    assert Standard14Fonts.get_mapped_font_name("arial") == "Helvetica"
    assert Standard14Fonts.get_mapped_font_name("HELVETICA-BOLD") == (
        "Helvetica-Bold"
    )


def test_extended_aliases_are_intentional_superset() -> None:
    # These -PS / -MT / hyphenated variants are NOT in upstream's map
    # (upstream returns null) but pypdfbox accepts them (CHANGES wave 1570).
    for extra in (
        "TimesNewRomanPSMT",
        "CourierNewPS-BoldMT",
        "Arial-Bold",
    ):
        assert Standard14Fonts.get_mapped_font_name(extra) is not None


def test_is_canonical_vs_has_alias() -> None:
    assert Standard14Fonts.is_canonical_name("Helvetica") is True
    assert Standard14Fonts.is_canonical_name("Arial") is False
    assert Standard14Fonts.has_alias("Arial") is True
    assert Standard14Fonts.has_alias("Helvetica") is False


@pytest.mark.parametrize("name", sorted(_CANONICAL_14))
def test_get_afm_for_each_of_the_14(name: str) -> None:
    afm = Standard14Fonts.get_afm(name)
    assert afm is not None
    assert afm.get_font_name() == name


def test_get_afm_returns_none_for_unknown() -> None:
    # Upstream getAFM returns null (never throws) for an unmapped name.
    assert Standard14Fonts.get_afm("NoSuchFont-XYZ") is None


def test_get_afm_resolves_alias_to_same_instance() -> None:
    helv = Standard14Fonts.get_afm("Helvetica")
    arial = Standard14Fonts.get_afm("ArialMT")
    assert arial is helv


def test_get_font_metrics_returns_descriptor_numerics() -> None:
    fm = Standard14Fonts.get_font_metrics("Helvetica")
    assert fm is not None
    assert fm["FontName"] == "Helvetica"
    assert len(fm["FontBBox"]) == 4
    assert isinstance(fm["IsFixedPitch"], bool)
    assert fm["IsFixedPitch"] is False


def test_get_font_metrics_fixed_pitch_true_for_courier() -> None:
    fm = Standard14Fonts.get_font_metrics("Courier")
    assert fm is not None
    assert fm["IsFixedPitch"] is True


def test_get_font_metrics_none_for_unknown() -> None:
    assert Standard14Fonts.get_font_metrics("NoSuchFont-XYZ") is None


@pytest.mark.parametrize(
    ("font", "glyph", "positive"),
    [
        ("Helvetica", "A", True),
        ("Helvetica", "space", True),
        ("Helvetica", "thisGlyphDoesNotExist", False),
        ("Courier", "i", True),
        ("Symbol", "alpha", True),
        ("ZapfDingbats", "a1", True),
        ("Arial", "A", True),
    ],
    ids=[
        "helv_A",
        "helv_space",
        "helv_missing",
        "courier_i",
        "symbol_alpha",
        "zapf_a1",
        "arial_A",
    ],
)
def test_get_glyph_width_by_name(
    font: str, glyph: str, positive: bool
) -> None:
    width = Standard14Fonts.get_glyph_width(font, glyph)
    if positive:
        assert width > 0.0
    else:
        assert width == 0.0


def test_courier_is_monospaced_uniform_widths() -> None:
    # Courier is fixed-pitch: every encoded glyph is 600 units wide.
    assert Standard14Fonts.get_glyph_width("Courier", "i") == 600.0
    assert Standard14Fonts.get_glyph_width("Courier", "W") == 600.0
    assert Standard14Fonts.get_glyph_width("Courier", "space") == 600.0


def test_alias_glyph_width_matches_canonical() -> None:
    assert Standard14Fonts.get_glyph_width(
        "Arial", "A"
    ) == Standard14Fonts.get_glyph_width("Helvetica", "A")
