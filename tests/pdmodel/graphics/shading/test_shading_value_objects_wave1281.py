"""Tests for ``IntPoint`` / ``Vertex`` public-method additions (Wave 1281)."""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.shading.int_point import IntPoint
from pypdfbox.pdmodel.graphics.shading.vertex import Vertex


def test_int_point_hash_code_matches_upstream_formula():
    p = IntPoint(3, 4)
    assert p.hash_code() == 89 * (623 + 3) + 4


def test_int_point_equals_compares_components():
    a = IntPoint(3, 4)
    b = IntPoint(3, 4)
    c = IntPoint(5, 6)
    assert a.equals(b) is True
    assert a.equals(c) is False
    assert a.equals(None) is False
    assert a == b
    assert a != c


def test_vertex_to_string_format():
    v = Vertex((1.0, 2.0), [0.5, 0.75])
    text = v.to_string()
    assert text.startswith("Vertex{")
    assert "0.50" in text and "0.75" in text


def test_vertex_color_is_defensively_copied():
    src = [0.1, 0.2, 0.3]
    v = Vertex((0.0, 0.0), src)
    src[0] = 99.0
    assert v.color[0] == 0.1
