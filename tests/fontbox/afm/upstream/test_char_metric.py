"""Ported from upstream's ``CharMetricTest.java``.

Source:
``pdfbox/fontbox/src/test/java/org/apache/fontbox/afm/CharMetricTest.java``
(Apache PDFBox 3.0.x).

The upstream "unmodifiable list" assertion is translated to "the
returned list is a copy" — mutating it must not affect the
``CharMetric`` instance's own list.
"""
from __future__ import annotations

from pypdfbox.fontbox.afm import CharMetric, Ligature
from pypdfbox.fontbox.ttf.glyph_data import BoundingBox


def test_char_metric_simple_values() -> None:
    char_metric = CharMetric()
    char_metric.set_character_code(0)
    char_metric.set_name("name")
    char_metric.set_wx(10)
    char_metric.set_w0x(20)
    char_metric.set_w1x(30)
    char_metric.set_wy(40)
    char_metric.set_w0y(50)
    char_metric.set_w1y(60)

    assert char_metric.get_character_code() == 0
    assert char_metric.get_name() == "name"
    assert char_metric.get_wx() == 10.0
    assert char_metric.get_w0x() == 20.0
    assert char_metric.get_w1x() == 30.0
    assert char_metric.get_wy() == 40.0
    assert char_metric.get_w0y() == 50.0
    assert char_metric.get_w1y() == 60.0


def test_char_metric_array_values() -> None:
    char_metric = CharMetric()
    char_metric.set_w([10, 20])
    char_metric.set_w0([30, 40])
    char_metric.set_w1([50, 60])
    char_metric.set_vv([70, 80])
    w = char_metric.get_w()
    assert w is not None
    assert w[0] == 10.0
    assert w[1] == 20.0
    w0 = char_metric.get_w0()
    assert w0 is not None
    assert w0[0] == 30.0
    assert w0[1] == 40.0
    w1 = char_metric.get_w1()
    assert w1 is not None
    assert w1[0] == 50.0
    assert w1[1] == 60.0
    vv = char_metric.get_vv()
    assert vv is not None
    assert vv[0] == 70.0
    assert vv[1] == 80.0


def test_char_metric_complex_values() -> None:
    char_metric = CharMetric()
    char_metric.set_bounding_box(BoundingBox(10, 20, 30, 40))
    bbox = char_metric.get_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 10
    assert bbox.get_lower_left_y() == 20
    assert bbox.get_upper_right_x() == 30
    assert bbox.get_upper_right_y() == 40

    assert len(char_metric.get_ligatures()) == 0
    ligature = Ligature("successor", "ligature")
    char_metric.add_ligature(ligature)
    ligatures = char_metric.get_ligatures()
    assert len(ligatures) == 1
    assert ligatures[0].get_successor() == "successor"
    # Returned list is a copy — mutating it must not change CharMetric.
    ligatures.append(ligature)
    assert len(char_metric.get_ligatures()) == 1
