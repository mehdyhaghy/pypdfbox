"""Ported from upstream's ``AFMParserTest.java``.

Source:
``pdfbox/fontbox/src/test/java/org/apache/fontbox/afm/AFMParserTest.java``
(Apache PDFBox 3.0.x).

Some upstream tests reference fixture AFMs that are not bundled here
(``NoEndFontMetrics.afm``, ``MalformedFloat.afm``, ``MalformedInteger.afm``).
We synthesise equivalent inputs in-process so the tests still cover the
parser branches they were written for.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.afm import AFMParser, FontMetrics, KernPair


_HELVETICA_AFM = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "pdmodel"
    / "font"
    / "afm"
    / "Helvetica.afm"
)


def _open_helvetica() -> AFMParser:
    return AFMParser(_HELVETICA_AFM.read_bytes())


# ---- error paths ----------------------------------------------------------


def test_start_font_metrics() -> None:
    """Missing StartFontMetrics keyword raises ``OSError``."""
    with pytest.raises(OSError):
        AFMParser(b"huhu").parse()


def test_end_font_metrics() -> None:
    """Truncated AFM (no EndFontMetrics) trips the unknown-key fallback."""
    truncated = (
        b"StartFontMetrics 4.1\n"
        b"FontName Test\n"
        b"NotAValidKey nothing\n"
    )
    with pytest.raises(OSError) as exc:
        AFMParser(truncated).parse()
    assert "Unknown AFM key" in str(exc.value)


def test_malformed_float() -> None:
    """A non-numeric float value raises ``OSError``."""
    bad = (
        b"StartFontMetrics 4.1\n"
        b"ItalicAngle 4,1ab\n"
        b"EndFontMetrics\n"
    )
    with pytest.raises(OSError) as exc:
        AFMParser(bad).parse()
    assert "4,1ab" in str(exc.value)


def test_malformed_integer() -> None:
    """A non-numeric int value raises ``OSError``."""
    bad = (
        b"StartFontMetrics 4.1\n"
        b"EscChar 3.4\n"
        b"EndFontMetrics\n"
    )
    with pytest.raises(OSError) as exc:
        AFMParser(bad).parse()
    assert "3.4" in str(exc.value)


# ---- happy path: Helvetica.afm headers ------------------------------------


def _check_bbox(bbox, lower_x: float, lower_y: float, upper_x: float, upper_y: float) -> None:
    assert bbox is not None
    assert bbox.get_lower_left_x() == lower_x
    assert bbox.get_lower_left_y() == lower_y
    assert bbox.get_upper_right_x() == upper_x
    assert bbox.get_upper_right_y() == upper_y


def _check_helvetica_font_metrics(font_metrics: FontMetrics) -> None:
    assert font_metrics.get_afm_version() == 4.1
    assert font_metrics.get_font_name() == "Helvetica"
    assert font_metrics.get_full_name() == "Helvetica"
    assert font_metrics.get_family_name() == "Helvetica"
    assert font_metrics.get_weight() == "Medium"
    _check_bbox(font_metrics.get_font_b_box(), -166.0, -225.0, 1000.0, 931.0)
    assert font_metrics.get_font_version() == "002.000"
    expected_notice = (
        "Copyright (c) 1985, 1987, 1989, 1990, 1997 Adobe Systems Incorporated.  "
        "All Rights Reserved.Helvetica is a trademark of Linotype-Hell AG and/or "
        "its subsidiaries."
    )
    assert font_metrics.get_notice() == expected_notice
    assert font_metrics.get_encoding_scheme() == "AdobeStandardEncoding"
    assert font_metrics.get_mapping_scheme() == 0
    assert font_metrics.get_esc_char() == 0
    assert font_metrics.get_character_set() == "ExtendedRoman"
    assert font_metrics.get_characters() == 0
    assert font_metrics.get_is_base_font() is True
    assert font_metrics.get_v_vector() is None
    assert font_metrics.get_is_fixed_v() is False
    assert font_metrics.get_cap_height() == 718.0
    assert font_metrics.get_x_height() == 523.0
    assert font_metrics.get_ascender() == 718.0
    assert font_metrics.get_descender() == -207.0
    assert font_metrics.get_standard_horizontal_width() == 76.0
    assert font_metrics.get_standard_vertical_width() == 88.0

    comments = font_metrics.get_comments()
    assert len(comments) == 4
    assert comments[0] == (
        "Copyright (c) 1985, 1987, 1989, 1990, 1997 Adobe Systems Incorporated.  "
        "All Rights Reserved."
    )
    assert comments[2] == "UniqueID 43054"

    assert font_metrics.get_underline_position() == -100.0
    assert font_metrics.get_underline_thickness() == 50.0
    assert font_metrics.get_italic_angle() == 0.0
    assert font_metrics.get_char_width() is None
    assert font_metrics.get_is_fixed_pitch() is False


def _check_helvetica_char_metrics(char_metrics) -> None:
    assert len(char_metrics) == 315

    # "space" metrics
    space = next((c for c in char_metrics if c.get_name() == "space"), None)
    assert space is not None
    assert space.get_wx() == 278.0
    assert space.get_character_code() == 32
    _check_bbox(space.get_bounding_box(), 0.0, 0.0, 0.0, 0.0)
    assert space.get_ligatures() == []
    assert space.get_w() is None
    assert space.get_w0() is None
    assert space.get_w1() is None
    assert space.get_vv() is None

    # "ring" metrics
    ring = next((c for c in char_metrics if c.get_name() == "ring"), None)
    assert ring is not None
    assert ring.get_wx() == 333.0
    assert ring.get_character_code() == 202
    _check_bbox(ring.get_bounding_box(), 75.0, 572.0, 259.0, 756.0)
    assert ring.get_ligatures() == []
    assert ring.get_w() is None
    assert ring.get_w0() is None
    assert ring.get_w1() is None
    assert ring.get_vv() is None


def _check_kern_pair(
    kern_pairs: list[KernPair],
    first: str,
    second: str,
    x: float,
    y: float,
) -> None:
    found = next(
        (k for k in kern_pairs
         if k.get_first_kern_character() == first
         and k.get_second_kern_character() == second),
        None,
    )
    assert found is not None
    assert found.get_x() == x
    assert found.get_y() == y


def test_helvetica_font_metrics() -> None:
    _check_helvetica_font_metrics(_open_helvetica().parse())


def test_helvetica_char_metrics() -> None:
    fm = _open_helvetica().parse()
    _check_helvetica_char_metrics(fm.get_char_metrics())


def test_helvetica_kern_pairs() -> None:
    fm = _open_helvetica().parse()
    kern_pairs = fm.get_kern_pairs()
    assert len(kern_pairs) == 2705
    _check_kern_pair(kern_pairs, "A", "Ucircumflex", -50.0, 0.0)
    _check_kern_pair(kern_pairs, "W", "agrave", -40.0, 0.0)
    assert fm.get_kern_pairs0() == []
    assert fm.get_kern_pairs1() == []
    assert fm.get_composites() == []


def test_helvetica_font_metrics_reduced_dataset() -> None:
    _check_helvetica_font_metrics(_open_helvetica().parse(reduced_dataset=True))


def test_helvetica_char_metrics_reduced_dataset() -> None:
    fm = _open_helvetica().parse(reduced_dataset=True)
    _check_helvetica_char_metrics(fm.get_char_metrics())


def test_helvetica_kern_pairs_reduced_dataset() -> None:
    """``reduced_dataset=True`` skips kern + composite blocks."""
    fm = _open_helvetica().parse(reduced_dataset=True)
    assert fm.get_kern_pairs() == []
    assert fm.get_kern_pairs0() == []
    assert fm.get_kern_pairs1() == []
    assert fm.get_composites() == []
