"""Tests for ``Vertex`` public-method additions (Wave 1281)."""

from pypdfbox.pdmodel.graphics.shading.vertex import Vertex


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
