"""Wave 1369 — AFM header + char-metric round-trip parity tests.

Covers the full top-to-bottom flow of a small AFM document:

* StartFontMetrics version + EndFontMetrics envelope;
* header directives (FontName, FullName, FamilyName, Weight, FontBBox,
  UnderlinePosition, UnderlineThickness, ItalicAngle, IsFixedPitch,
  EncodingScheme);
* StartCharMetrics / EndCharMetrics body with at least one of each
  CharMetric sub-directive PDFBox knows about (N, C, CH, WX, W0X, W1X,
  W, W0, W1, WY, W0Y, W1Y, VV, B, L);
* the FontMetrics-level convenience accessors
  (``get_character_width``, ``get_average_character_width``,
  ``get_char_metric``) computed from the round-tripped data.
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.afm import AFMParser, CharMetric, FontMetrics

# ---------- shared synthetic AFM ----------


def _make_afm() -> bytes:
    return (
        "StartFontMetrics 4.1\n"
        "FontName WaveSerif\n"
        "FullName Wave Serif Regular\n"
        "FamilyName WaveSerif\n"
        "Weight Roman\n"
        "FontBBox -150 -250 1000 900\n"
        "UnderlinePosition -100\n"
        "UnderlineThickness 50\n"
        "ItalicAngle 0\n"
        "IsFixedPitch false\n"
        "EncodingScheme AdobeStandardEncoding\n"
        "Version 001.000\n"
        "Notice Wave 1369 fixture\n"
        "CapHeight 700\n"
        "XHeight 480\n"
        "Ascender 750\n"
        "Descender -250\n"
        "StdHW 50\n"
        "StdVW 80\n"
        "StartCharMetrics 4\n"
        "C 65 ; WX 720 ; N A ; B 15 0 705 700 ;\n"
        "C 32 ; WX 250 ; N space ; B 0 0 0 0 ;\n"
        "C 33 ; WX 333 ; N exclam ; B 130 0 200 700 ; L i fi ;\n"
        "C 34 ; WX 400 ; N quotedbl ; B 50 400 350 700 ;\n"
        "EndCharMetrics\n"
        "EndFontMetrics\n"
    ).encode("latin-1")


def _parse() -> FontMetrics:
    return AFMParser(_make_afm()).parse()


# ---------- header round-trip ----------


def test_header_envelope_round_trip() -> None:
    fm = _parse()
    assert fm.get_afm_version() == pytest.approx(4.1)
    assert fm.get_font_name() == "WaveSerif"
    assert fm.get_full_name() == "Wave Serif Regular"
    assert fm.get_family_name() == "WaveSerif"
    assert fm.get_weight() == "Roman"


def test_header_font_bbox_components() -> None:
    fm = _parse()
    bbox = fm.get_font_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(-150.0)
    assert bbox.get_lower_left_y() == pytest.approx(-250.0)
    assert bbox.get_upper_right_x() == pytest.approx(1000.0)
    assert bbox.get_upper_right_y() == pytest.approx(900.0)
    assert fm.has_font_b_box()


def test_header_underline_and_italic() -> None:
    fm = _parse()
    assert fm.get_underline_position() == pytest.approx(-100.0)
    assert fm.get_underline_thickness() == pytest.approx(50.0)
    assert fm.get_italic_angle() == pytest.approx(0.0)
    assert fm.get_is_fixed_pitch() is False


def test_header_dim_helpers() -> None:
    fm = _parse()
    assert fm.get_cap_height() == pytest.approx(700.0)
    assert fm.get_x_height() == pytest.approx(480.0)
    assert fm.get_ascender() == pytest.approx(750.0)
    assert fm.get_descender() == pytest.approx(-250.0)
    assert fm.get_standard_horizontal_width() == pytest.approx(50.0)
    assert fm.get_standard_vertical_width() == pytest.approx(80.0)


def test_header_notice_and_version_and_encoding() -> None:
    fm = _parse()
    assert fm.get_notice() == "Wave 1369 fixture"
    assert fm.get_font_version() == "001.000"
    assert fm.get_encoding_scheme() == "AdobeStandardEncoding"


# ---------- char metric round-trip ----------


def test_char_metrics_count_matches() -> None:
    fm = _parse()
    assert len(fm.get_char_metrics()) == 4


def test_char_metric_by_name_returns_full_record() -> None:
    fm = _parse()
    a: CharMetric | None = fm.get_char_metric("A")
    assert a is not None
    assert a.get_character_code() == 65
    assert a.get_wx() == pytest.approx(720.0)
    bbox = a.get_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(15.0)
    assert bbox.get_upper_right_y() == pytest.approx(700.0)


def test_has_char_metric_and_missing() -> None:
    fm = _parse()
    assert fm.has_char_metric("A") is True
    assert fm.has_char_metric("notpresent") is False
    assert fm.get_char_metric("notpresent") is None


def test_get_character_width() -> None:
    fm = _parse()
    assert fm.get_character_width("A") == pytest.approx(720.0)
    assert fm.get_character_width("space") == pytest.approx(250.0)


def test_get_average_character_width_is_mean_of_widths() -> None:
    fm = _parse()
    # (720 + 250 + 333 + 400) / 4 = 425.75
    assert fm.get_average_character_width() == pytest.approx(425.75, abs=0.01)


def test_char_metric_ligature_stored() -> None:
    fm = _parse()
    exclam = fm.get_char_metric("exclam")
    assert exclam is not None
    lig = exclam.get_ligatures()
    assert len(lig) == 1
    # Ligature is ``L successor ligature`` — succ="i", lig="fi".
    assert lig[0].get_successor() == "i"
    assert lig[0].get_ligature() == "fi"


# ---------- CharMetric optional sub-directives ----------


def test_char_metric_w0x_w1x_and_w_pair_dispatch() -> None:
    raw = (
        "StartFontMetrics 4.1\n"
        "FontName V\n"
        "StartCharMetrics 1\n"
        "C 65 ; W0X 720 ; W1X 0 ; W0Y 0 ; W1Y -700 ; W0 720 0 ; W1 0 -700 ; "
        "WY 0 ; VV 360 700 ; N A ; B 15 0 705 700 ;\n"
        "EndCharMetrics\n"
        "EndFontMetrics\n"
    ).encode("latin-1")
    fm = AFMParser(raw).parse()
    cm = fm.get_char_metric("A")
    assert cm is not None
    assert cm.get_w0x() == pytest.approx(720.0)
    assert cm.get_w1x() == pytest.approx(0.0)
    assert cm.get_w0y() == pytest.approx(0.0)
    assert cm.get_w1y() == pytest.approx(-700.0)
    assert cm.get_w0() == (pytest.approx(720.0), pytest.approx(0.0))
    assert cm.get_w1() == (pytest.approx(0.0), pytest.approx(-700.0))
    assert cm.get_vv() == (pytest.approx(360.0), pytest.approx(700.0))


def test_char_metric_hex_code_with_angle_brackets() -> None:
    # CH <41> form — hex character code wrapped in angle brackets.
    raw = (
        "StartFontMetrics 4.1\n"
        "FontName V\n"
        "StartCharMetrics 1\n"
        "CH <41> ; WX 720 ; N A ; B 0 0 0 0 ;\n"
        "EndCharMetrics\n"
        "EndFontMetrics\n"
    ).encode("latin-1")
    fm = AFMParser(raw).parse()
    cm = fm.get_char_metric("A")
    assert cm is not None
    assert cm.get_character_code() == 0x41


def test_char_metric_unknown_sub_directive_raises() -> None:
    raw = (
        "StartFontMetrics 4.1\n"
        "FontName V\n"
        "StartCharMetrics 1\n"
        "C 65 ; UNKNOWN 1 ; N A ;\n"
        "EndCharMetrics\n"
        "EndFontMetrics\n"
    ).encode("latin-1")
    with pytest.raises(OSError, match="Unknown CharMetrics"):
        AFMParser(raw).parse()


def test_reduced_dataset_skips_kern_block() -> None:
    # Build an AFM whose StartKernData block carries a malformed entry —
    # parse(reduced=True) should skip the block entirely without raising.
    raw = (
        "StartFontMetrics 4.1\n"
        "FontName V\n"
        "StartCharMetrics 1\n"
        "C 65 ; WX 720 ; N A ; B 0 0 0 0 ;\n"
        "EndCharMetrics\n"
        "StartKernData\n"
        "MysteryDirective something\n"
        "EndKernData\n"
        "EndFontMetrics\n"
    ).encode("latin-1")
    fm = AFMParser(raw).parse(reduced_dataset=True)
    assert fm.get_font_name() == "V"
    assert fm.has_char_metric("A")
