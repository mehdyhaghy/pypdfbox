"""Round-out tests for ``AFMParser`` covering directives and character
metric sub-directives less exercised by the upstream Helvetica fixture.

Each test feeds a small synthetic AFM snippet covering a single dispatch
branch (or a small cluster) of the parser's tag table, then asserts the
resulting :class:`FontMetrics` / :class:`CharMetric` graph reflects it.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.afm import (
    AFMParser,
    Composite,
    CompositePart,
    FontMetrics,
    KernPair,
    Ligature,
    TrackKern,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap(body: str) -> bytes:
    """Wrap ``body`` in the StartFontMetrics/EndFontMetrics envelope."""
    return (
        "StartFontMetrics 4.1\n"
        f"{body}"
        "EndFontMetrics\n"
    ).encode("latin-1")


def _parse(body: str, reduced: bool = False) -> FontMetrics:
    return AFMParser(_wrap(body)).parse(reduced_dataset=reduced)


# ---------------------------------------------------------------------------
# Construction-time input handling
# ---------------------------------------------------------------------------


def test_constructor_accepts_bytes() -> None:
    fm = AFMParser(_wrap("FontName Foo\n")).parse()
    assert fm.get_font_name() == "Foo"


def test_constructor_accepts_bytearray() -> None:
    raw = bytearray(_wrap("FontName Foo\n"))
    fm = AFMParser(raw).parse()
    assert fm.get_font_name() == "Foo"


def test_constructor_accepts_binary_stream() -> None:
    stream = io.BytesIO(_wrap("FontName Foo\n"))
    fm = AFMParser(stream).parse()
    assert fm.get_font_name() == "Foo"


# ---------------------------------------------------------------------------
# Header directives — one per dispatch branch
# ---------------------------------------------------------------------------


def test_metric_sets_directive() -> None:
    fm = _parse("MetricSets 2\n")
    assert fm.get_metric_sets() == 2


def test_metric_sets_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        _parse("MetricSets 9\n")


def test_full_name_and_family_and_weight() -> None:
    fm = _parse(
        "FullName Test Regular\n"
        "FamilyName TestFamily\n"
        "Weight Bold\n"
    )
    assert fm.get_full_name() == "Test Regular"
    assert fm.get_family_name() == "TestFamily"
    assert fm.get_weight() == "Bold"


def test_font_bbox_directive() -> None:
    fm = _parse("FontBBox -10 -20 100 200\n")
    bbox = fm.get_font_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -10.0
    assert bbox.get_lower_left_y() == -20.0
    assert bbox.get_upper_right_x() == 100.0
    assert bbox.get_upper_right_y() == 200.0


def test_version_and_notice_and_encoding_scheme() -> None:
    fm = _parse(
        "Version 001.234\n"
        "Notice Copyright (c) Test\n"
        "EncodingScheme AdobeStandardEncoding\n"
    )
    assert fm.get_font_version() == "001.234"
    assert fm.get_notice() == "Copyright (c) Test"
    assert fm.get_encoding_scheme() == "AdobeStandardEncoding"


def test_mapping_scheme_and_esc_char_and_character_set_and_characters() -> None:
    fm = _parse(
        "MappingScheme 3\n"
        "EscChar 27\n"
        "CharacterSet ExtendedRoman\n"
        "Characters 256\n"
    )
    assert fm.get_mapping_scheme() == 3
    assert fm.get_esc_char() == 27
    assert fm.get_character_set() == "ExtendedRoman"
    assert fm.get_characters() == 256


def test_is_base_font_false() -> None:
    fm = _parse("IsBaseFont false\n")
    assert fm.get_is_base_font() is False


def test_is_base_font_true_default() -> None:
    fm = _parse("FontName X\n")
    assert fm.get_is_base_font() is True


def test_v_vector_and_is_fixed_v_explicit() -> None:
    fm = _parse(
        "VVector 100 200\n"
        "IsFixedV true\n"
    )
    assert fm.get_v_vector() == (100.0, 200.0)
    assert fm.get_is_fixed_v() is True


def test_is_fixed_v_default_when_no_vvector() -> None:
    fm = _parse("FontName X\n")
    assert fm.get_is_fixed_v() is False


def test_is_fixed_v_default_when_vvector_present() -> None:
    fm = _parse("VVector 1 2\n")
    assert fm.get_is_fixed_v() is True


def test_cap_x_ascender_descender() -> None:
    fm = _parse(
        "CapHeight 700\n"
        "XHeight 500\n"
        "Ascender 750\n"
        "Descender -250\n"
    )
    assert fm.get_cap_height() == 700.0
    assert fm.get_x_height() == 500.0
    assert fm.get_ascender() == 750.0
    assert fm.get_descender() == -250.0


def test_underline_position_and_thickness() -> None:
    fm = _parse(
        "UnderlinePosition -90\n"
        "UnderlineThickness 60\n"
    )
    assert fm.get_underline_position() == -90.0
    assert fm.get_underline_thickness() == 60.0


def test_italic_angle() -> None:
    fm = _parse("ItalicAngle -12.5\n")
    assert fm.get_italic_angle() == -12.5


def test_char_width_directive() -> None:
    fm = _parse("CharWidth 600 0\n")
    assert fm.get_char_width() == (600.0, 0.0)


def test_is_fixed_pitch_true() -> None:
    fm = _parse("IsFixedPitch true\n")
    assert fm.get_is_fixed_pitch() is True


def test_std_hw_and_std_vw() -> None:
    fm = _parse(
        "StdHW 50\n"
        "StdVW 80\n"
    )
    assert fm.get_standard_horizontal_width() == 50.0
    assert fm.get_standard_vertical_width() == 80.0


def test_comment_directives_collected_in_order() -> None:
    fm = _parse(
        "Comment first comment line\n"
        "Comment second one\n"
    )
    comments = fm.get_comments()
    assert comments == ["first comment line", "second one"]


def test_unknown_global_directive_raises() -> None:
    with pytest.raises(OSError) as exc:
        _parse("BogusDirective nothing\n")
    assert "BogusDirective" in str(exc.value)


def test_reduced_dataset_tolerates_unknown_after_char_metrics() -> None:
    body = (
        "StartCharMetrics 1\n"
        "C 32 ; WX 250 ; N space ; B 0 0 0 0 ;\n"
        "EndCharMetrics\n"
        "BogusTrailing whatever\n"
    )
    fm = AFMParser(_wrap(body)).parse(reduced_dataset=True)
    assert len(fm.get_char_metrics()) == 1


# ---------------------------------------------------------------------------
# Char-metric sub-directives
# ---------------------------------------------------------------------------


def _parse_metric(line: str):
    body = (
        "StartCharMetrics 1\n"
        f"{line}\n"
        "EndCharMetrics\n"
    )
    metrics = _parse(body).get_char_metrics()
    assert len(metrics) == 1
    return metrics[0]


def test_char_metric_c_decimal_code() -> None:
    cm = _parse_metric("C 65 ; WX 500 ; N A ; B 0 0 0 0 ;")
    assert cm.get_character_code() == 65
    assert cm.get_name() == "A"
    assert cm.get_wx() == 500.0


def test_char_metric_ch_hex_code() -> None:
    cm = _parse_metric("CH 41 ; WX 500 ; N A ; B 0 0 0 0 ;")
    # 0x41 == 65
    assert cm.get_character_code() == 65


def test_char_metric_w0x_w1x_w0y_w1y() -> None:
    cm = _parse_metric(
        "C 65 ; W0X 500 ; W1X 600 ; W0Y 10 ; W1Y 20 ; N A ;"
    )
    assert cm.get_w0x() == 500.0
    assert cm.get_w1x() == 600.0
    assert cm.get_w0y() == 10.0
    assert cm.get_w1y() == 20.0


def test_char_metric_paired_w_w0_w1() -> None:
    cm = _parse_metric(
        "C 65 ; W 500 0 ; W0 510 5 ; W1 520 -5 ; N A ;"
    )
    assert cm.get_w() == (500.0, 0.0)
    assert cm.get_w0() == (510.0, 5.0)
    assert cm.get_w1() == (520.0, -5.0)


def test_char_metric_vv() -> None:
    cm = _parse_metric("C 65 ; WX 500 ; VV 250 750 ; N A ;")
    assert cm.get_vv() == (250.0, 750.0)


def test_char_metric_wy() -> None:
    cm = _parse_metric("C 65 ; WX 500 ; WY 800 ; N A ;")
    assert cm.get_wy() == 800.0


def test_char_metric_bounding_box_and_lookup() -> None:
    fm = _parse(
        "StartCharMetrics 1\n"
        "C 65 ; WX 500 ; N A ; B 10 -20 480 700 ;\n"
        "EndCharMetrics\n"
    )
    cm = fm.get_char_metrics()[0]
    bbox = cm.get_bounding_box()
    assert bbox is not None
    assert (bbox.get_lower_left_x(), bbox.get_lower_left_y()) == (10.0, -20.0)
    assert (bbox.get_upper_right_x(), bbox.get_upper_right_y()) == (480.0, 700.0)
    # height comes from bbox when WY is zero
    assert fm.get_character_height("A") == 720.0
    assert fm.get_character_width("A") == 500.0


def test_char_metric_height_uses_wy_when_nonzero() -> None:
    fm = _parse(
        "StartCharMetrics 1\n"
        "C 65 ; WX 500 ; WY 999 ; N A ; B 0 0 100 100 ;\n"
        "EndCharMetrics\n"
    )
    assert fm.get_character_height("A") == 999.0


def test_char_metric_ligature_l_directive() -> None:
    cm = _parse_metric("C 102 ; WX 250 ; N f ; B 0 0 0 0 ; L i fi ;")
    ligs = cm.get_ligatures()
    assert ligs == [Ligature("i", "fi")]


def test_char_metric_unknown_subkey_raises() -> None:
    body = (
        "StartCharMetrics 1\n"
        "C 65 ; ZZ 1 ;\n"
        "EndCharMetrics\n"
    )
    with pytest.raises(OSError) as exc:
        _parse(body)
    assert "Unknown CharMetrics command" in str(exc.value)


def test_char_metric_missing_semicolon_raises() -> None:
    body = (
        "StartCharMetrics 1\n"
        "C 65 WX 500\n"
        "EndCharMetrics\n"
    )
    with pytest.raises(OSError) as exc:
        _parse(body)
    assert "Expected semicolon" in str(exc.value)


def test_char_metric_trailing_semicolon_optional() -> None:
    # No trailing ';' — parser should still accept the line.
    cm = _parse_metric("C 65 ; WX 500 ; N A ; B 0 0 0 0")
    assert cm.get_wx() == 500.0


def test_average_character_width() -> None:
    fm = _parse(
        "StartCharMetrics 3\n"
        "C 32 ; WX 100 ; N space ;\n"
        "C 33 ; WX 200 ; N exclam ;\n"
        "C 34 ; WX 0 ; N nullw ;\n"
        "EndCharMetrics\n"
    )
    # Zero-width glyphs are excluded from the average.
    assert fm.get_average_character_width() == 150.0


def test_average_character_width_empty_returns_zero() -> None:
    fm = _parse("FontName X\n")
    assert fm.get_average_character_width() == 0.0


def test_get_character_width_unknown_glyph_returns_zero() -> None:
    fm = _parse(
        "StartCharMetrics 1\n"
        "C 65 ; WX 500 ; N A ; B 0 0 0 0 ;\n"
        "EndCharMetrics\n"
    )
    assert fm.get_character_width("does-not-exist") == 0.0
    assert fm.get_character_height("does-not-exist") == 0.0


# ---------------------------------------------------------------------------
# Kern data
# ---------------------------------------------------------------------------


def _kern(body: str) -> FontMetrics:
    return _parse(
        "StartKernData\n"
        f"{body}"
        "EndKernData\n"
    )


def test_kern_pairs_kp_with_x_and_y() -> None:
    fm = _kern(
        "StartKernPairs 1\n"
        "KP A B -50 5\n"
        "EndKernPairs\n"
    )
    pairs = fm.get_kern_pairs()
    assert pairs == [KernPair("A", "B", -50.0, 5.0)]


def test_kern_pairs_kpx_zero_y() -> None:
    fm = _kern(
        "StartKernPairs 1\n"
        "KPX A B -75\n"
        "EndKernPairs\n"
    )
    p = fm.get_kern_pairs()[0]
    assert (p.get_x(), p.get_y()) == (-75.0, 0.0)


def test_kern_pairs_kpy_zero_x() -> None:
    fm = _kern(
        "StartKernPairs 1\n"
        "KPY A B 33\n"
        "EndKernPairs\n"
    )
    p = fm.get_kern_pairs()[0]
    assert (p.get_x(), p.get_y()) == (0.0, 33.0)


def test_kern_pairs_kph_hex_decode() -> None:
    fm = _kern(
        "StartKernPairs 1\n"
        "KPH <41> <42> -10 0\n"
        "EndKernPairs\n"
    )
    p = fm.get_kern_pairs()[0]
    assert p.get_first_kern_character() == "A"
    assert p.get_second_kern_character() == "B"
    assert (p.get_x(), p.get_y()) == (-10.0, 0.0)


def test_kern_pairs0_and_1_routes_to_separate_lists() -> None:
    fm = _kern(
        "StartKernPairs0 1\n"
        "KPX A B -1\n"
        "EndKernPairs\n"
        "StartKernPairs1 1\n"
        "KPX C D -2\n"
        "EndKernPairs\n"
    )
    assert fm.get_kern_pairs() == []
    assert len(fm.get_kern_pairs0()) == 1
    assert len(fm.get_kern_pairs1()) == 1
    assert fm.get_kern_pairs0()[0].get_first_kern_character() == "A"
    assert fm.get_kern_pairs1()[0].get_first_kern_character() == "C"


def test_track_kern_block() -> None:
    fm = _kern(
        "StartTrackKern 1\n"
        "TrackKern 0 8 -1.5 32 -3.0\n"
        "EndTrackKern\n"
    )
    track = fm.get_track_kern()
    assert len(track) == 1
    tk: TrackKern = track[0]
    assert tk.get_degree() == 0
    assert tk.get_min_point_size() == 8.0
    assert tk.get_min_kern() == -1.5
    assert tk.get_max_point_size() == 32.0
    assert tk.get_max_kern() == -3.0


def test_unknown_kern_block_raises() -> None:
    body = (
        "StartKernData\n"
        "BogusKernBlock 1\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError) as exc:
        _parse(body)
    assert "BogusKernBlock" in str(exc.value)


def test_unknown_kern_pair_command_raises() -> None:
    body = (
        "StartKernData\n"
        "StartKernPairs 1\n"
        "ZZ A B 0\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError) as exc:
        _parse(body)
    assert "kern pair" in str(exc.value)


def test_kph_invalid_hex_raises() -> None:
    body = (
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPH <ZZ> <42> 0 0\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError):
        _parse(body)


def test_kph_missing_brackets_raises() -> None:
    body = (
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPH 41 42 0 0\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError):
        _parse(body)


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------


def test_composites_block() -> None:
    body = (
        "StartComposites 1\n"
        "CC Aacute 2 ; PCC A 0 0 ; PCC acute 100 250 ;\n"
        "EndComposites\n"
    )
    fm = _parse(body)
    composites = fm.get_composites()
    assert len(composites) == 1
    c: Composite = composites[0]
    assert c.get_name() == "Aacute"
    parts = c.get_parts()
    assert len(parts) == 2
    p0: CompositePart = parts[0]
    assert (p0.get_name(), p0.get_x_displacement(), p0.get_y_displacement()) == (
        "A",
        0,
        0,
    )
    p1: CompositePart = parts[1]
    assert (p1.get_name(), p1.get_x_displacement(), p1.get_y_displacement()) == (
        "acute",
        100,
        250,
    )


def test_composites_skipped_in_reduced_dataset() -> None:
    body = (
        "StartComposites 1\n"
        "CC Aacute 1 ; PCC A 0 0 ;\n"
        "EndComposites\n"
    )
    fm = _parse(body, reduced=True)
    assert fm.get_composites() == []


def test_kern_data_skipped_in_reduced_dataset() -> None:
    body = (
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPX A B -1\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    fm = _parse(body, reduced=True)
    assert fm.get_kern_pairs() == []


def test_composite_bad_cc_token_raises() -> None:
    body = (
        "StartComposites 1\n"
        "ZZ Bad 0 ;\n"
        "EndComposites\n"
    )
    with pytest.raises(OSError) as exc:
        _parse(body)
    assert "CC" in str(exc.value)


def test_composite_bad_pcc_token_raises() -> None:
    body = (
        "StartComposites 1\n"
        "CC Aacute 1 ; ZZZ A 0 0 ;\n"
        "EndComposites\n"
    )
    with pytest.raises(OSError) as exc:
        _parse(body)
    assert "PCC" in str(exc.value)


# ---------------------------------------------------------------------------
# Lexer / numeric parsing edge cases
# ---------------------------------------------------------------------------


def test_missing_start_font_metrics_raises() -> None:
    with pytest.raises(OSError):
        AFMParser(b"NotAValidStart\n").parse()


def test_skip_to_eof_before_terminator_raises() -> None:
    # reduced_dataset enters _skip_to via StartKernData; truncating before
    # EndKernData triggers the EOF guard.
    truncated = (
        b"StartFontMetrics 4.1\n"
        b"StartKernData\n"
        b"StartKernPairs 1\n"
        b"KPX A B -1\n"
        b"EndKernPairs\n"
    )
    with pytest.raises(OSError) as exc:
        AFMParser(truncated).parse(reduced_dataset=True)
    assert "EndKernData" in str(exc.value)


def test_boolean_case_insensitive() -> None:
    fm = _parse("IsBaseFont TRUE\n")
    assert fm.get_is_base_font() is True


def test_metric_sets_setter_validates() -> None:
    fm = FontMetrics()
    fm.set_metric_sets(0)
    fm.set_metric_sets(1)
    fm.set_metric_sets(2)
    with pytest.raises(ValueError):
        fm.set_metric_sets(3)
    with pytest.raises(ValueError):
        fm.set_metric_sets(-1)
