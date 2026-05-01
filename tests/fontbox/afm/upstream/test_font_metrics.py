"""Ported from upstream's ``FontMetricsTest.java``.

Source:
``pdfbox/fontbox/src/test/java/org/apache/fontbox/afm/FontMetricsTest.java``
(Apache PDFBox 3.0.x).

Java's ``Collections.unmodifiableList(...)`` semantics are translated to
"the returned list is a copy and mutating it does not affect the
underlying ``FontMetrics`` state" — Python has no first-class read-only
list, so the parity assertion exercises the behavioural intent.
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.afm import (
    CharMetric,
    Composite,
    FontMetrics,
    KernPair,
    TrackKern,
)
from pypdfbox.fontbox.ttf.glyph_data import BoundingBox


def test_font_metrics_names() -> None:
    fm = FontMetrics()
    fm.set_font_name("fontName")
    fm.set_family_name("familyName")
    fm.set_full_name("fullName")
    fm.set_font_version("fontVersion")
    fm.set_notice("notice")
    assert fm.get_font_name() == "fontName"
    assert fm.get_family_name() == "familyName"
    assert fm.get_full_name() == "fullName"
    assert fm.get_font_version() == "fontVersion"
    assert fm.get_notice() == "notice"

    assert len(fm.get_comments()) == 0
    fm.add_comment("comment")
    comments = fm.get_comments()
    assert len(comments) == 1
    # Mutating the snapshot must not affect FontMetrics' own list.
    comments.append("comment")
    assert len(fm.get_comments()) == 1


def test_font_metrics_simple_values() -> None:
    fm = FontMetrics()
    fm.set_afm_version(4.3)
    fm.set_weight("weight")
    fm.set_encoding_scheme("encodingScheme")
    fm.set_mapping_scheme(0)
    fm.set_esc_char(0)
    fm.set_character_set("characterSet")
    fm.set_characters(10)
    fm.set_is_base_font(True)
    fm.set_is_fixed_v(True)
    fm.set_cap_height(10)
    fm.set_x_height(20)
    fm.set_ascender(30)
    fm.set_descender(40)
    fm.set_standard_horizontal_width(50)
    fm.set_standard_vertical_width(60)
    fm.set_underline_position(70)
    fm.set_underline_thickness(80)
    fm.set_italic_angle(90)
    fm.set_fixed_pitch(True)

    assert fm.get_afm_version() == pytest.approx(4.3)
    assert fm.get_weight() == "weight"
    assert fm.get_encoding_scheme() == "encodingScheme"
    assert fm.get_mapping_scheme() == 0
    assert fm.get_esc_char() == 0
    assert fm.get_character_set() == "characterSet"
    assert fm.get_characters() == 10
    assert fm.get_is_base_font() is True
    assert fm.get_is_fixed_v() is True
    assert fm.get_cap_height() == 10.0
    assert fm.get_x_height() == 20.0
    assert fm.get_ascender() == 30.0
    assert fm.get_descender() == 40.0
    assert fm.get_standard_horizontal_width() == 50.0
    assert fm.get_standard_vertical_width() == 60.0
    assert fm.get_underline_position() == 70.0
    assert fm.get_underline_thickness() == 80.0
    assert fm.get_italic_angle() == 90.0
    assert fm.get_is_fixed_pitch() is True


def test_font_metrics_complex_values() -> None:
    fm = FontMetrics()
    fm.set_font_b_box(BoundingBox(10, 20, 30, 40))
    fm.set_v_vector([10, 20])
    fm.set_char_width([30, 40])
    bbox = fm.get_font_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 10
    assert bbox.get_lower_left_y() == 20
    assert bbox.get_upper_right_x() == 30
    assert bbox.get_upper_right_y() == 40
    v_vector = fm.get_v_vector()
    assert v_vector is not None
    assert v_vector[0] == 10
    assert v_vector[1] == 20
    char_width = fm.get_char_width()
    assert char_width is not None
    assert char_width[0] == 30
    assert char_width[1] == 40


def test_metric_sets() -> None:
    fm = FontMetrics()
    fm.set_metric_sets(1)
    assert fm.get_metric_sets() == 1
    with pytest.raises(ValueError):
        fm.set_metric_sets(-1)
    with pytest.raises(ValueError):
        fm.set_metric_sets(3)


def test_char_metrics() -> None:
    fm = FontMetrics()
    assert len(fm.get_char_metrics()) == 0
    char_metric = CharMetric()
    fm.add_char_metric(char_metric)
    char_metrics = fm.get_char_metrics()
    assert len(char_metrics) == 1
    char_metrics.append(char_metric)
    assert len(fm.get_char_metrics()) == 1


def test_composites() -> None:
    fm = FontMetrics()
    assert len(fm.get_composites()) == 0
    composite = Composite("name")
    fm.add_composite(composite)
    composites = fm.get_composites()
    assert len(composites) == 1
    composites.append(composite)
    assert len(fm.get_composites()) == 1


def test_kern_data() -> None:
    fm = FontMetrics()
    # KernPairs
    assert len(fm.get_kern_pairs()) == 0
    kp = KernPair("first", "second", 10, 20)
    fm.add_kern_pair(kp)
    kern_pairs = fm.get_kern_pairs()
    assert len(kern_pairs) == 1
    kern_pairs.append(kp)
    assert len(fm.get_kern_pairs()) == 1
    # KernPairs0
    assert len(fm.get_kern_pairs0()) == 0
    fm.add_kern_pair0(kp)
    kern_pairs0 = fm.get_kern_pairs0()
    assert len(kern_pairs0) == 1
    kern_pairs0.append(kp)
    assert len(fm.get_kern_pairs0()) == 1
    # KernPairs1
    assert len(fm.get_kern_pairs1()) == 0
    fm.add_kern_pair1(kp)
    kern_pairs1 = fm.get_kern_pairs1()
    assert len(kern_pairs1) == 1
    kern_pairs1.append(kp)
    assert len(fm.get_kern_pairs1()) == 1
    # TrackKern
    assert len(fm.get_track_kern()) == 0
    track_kern = TrackKern(0, 1, 1, 10, 10)
    fm.add_track_kern(track_kern)
    track_kerns = fm.get_track_kern()
    assert len(track_kerns) == 1
    track_kerns.append(track_kern)
    assert len(fm.get_track_kern()) == 1


def test_char_metric_dimensions() -> None:
    fm = FontMetrics()
    assert fm.get_average_character_width() == 0.0

    cm10 = CharMetric()
    cm10.set_name("ten")
    cm10.set_wx(10)
    cm10.set_wy(20)
    fm.add_char_metric(cm10)
    cm20 = CharMetric()
    cm20.set_name("twenty")
    cm20.set_wx(20)
    cm20.set_wy(40)
    fm.add_char_metric(cm20)
    cm30 = CharMetric()
    cm30.set_name("thirty")
    cm30.set_wx(30)
    cm30.set_wy(60)
    fm.add_char_metric(cm30)
    cm40 = CharMetric()
    cm40.set_name("forty")
    cm40.set_wx(40)
    cm40.set_wy(80)
    fm.add_char_metric(cm40)

    assert fm.get_character_width("ten") == 10.0
    assert fm.get_character_width("thirty") == 30.0
    assert fm.get_character_width("unknown") == 0.0

    assert fm.get_character_height("twenty") == 40.0
    assert fm.get_character_height("forty") == 80.0
    assert fm.get_character_height("unknown") == 0.0

    assert fm.get_average_character_width() == 25.0
