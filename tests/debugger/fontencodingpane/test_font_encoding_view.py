"""Tests for the :class:`FontEncodingView` Tkinter widget."""

from __future__ import annotations

import pytest

from pypdfbox.debugger.fontencodingpane.font_encoding_view import (
    FontEncodingView,
    GlyphCellRenderer,
    _rasterise_path,
)


def test_empty_table_still_builds_view(tk_root):
    view = FontEncodingView(
        tk_root,
        [],
        {"Font": "Helvetica"},
        ["Code", "Glyph Name", "Unicode", "Glyph"],
        None,
    )
    assert view.tree is not None
    assert view.tree.get_children() == ()
    assert view.get_panel() is view


def test_table_populates_with_string_glyphs(tk_root):
    rows = [
        [65, "A", "A", "No glyph"],
        [66, "B", "B", "No glyph"],
    ]
    view = FontEncodingView(
        tk_root,
        rows,
        {"Font": "Helvetica", "Encoding": "WinAnsi"},
        ["Code", "Glyph Name", "Unicode", "Glyph"],
        None,
    )
    children = view.tree.get_children()
    assert len(children) == 2
    first = view.tree.item(children[0])
    assert first["text"] == "65"
    values = [str(v) for v in first["values"]]
    assert values == ["A", "A", "No glyph"]


def test_table_handles_path_glyph_and_caches_photo(tk_root):
    pillow = _maybe_pillow()
    if pillow is None:
        return
    path = [("moveTo", 0.0, 0.0), ("lineTo", 10.0, 10.0), ("lineTo", 10.0, 0.0)]
    rows = [[1, "A", "A", path]]
    view = FontEncodingView(
        tk_root,
        rows,
        None,
        ["Code", "Glyph Name", "Unicode", "Glyph"],
        (0.0, 10.0),
    )
    assert len(view._photo_refs) == 1


def test_header_omitted_when_attributes_empty(tk_root):
    view = FontEncodingView(
        tk_root,
        [],
        None,
        ["Code", "Glyph"],
        None,
    )
    assert view._header_frame is None


def _maybe_pillow():
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:  # pragma: no cover
        return None


# ---- _insert_row edge cases ------------------------------------------------


def test_insert_row_with_empty_row(tk_root):
    """Empty row in ``table_data`` is silently skipped."""
    view = FontEncodingView(
        tk_root,
        [[]],
        None,
        ["Code", "Glyph"],
        None,
    )
    # Row was empty, so no children produced.
    assert view.tree.get_children() == ()


def test_insert_row_with_single_value(tk_root):
    """Row with only the head (no tail) inserts text-only."""
    view = FontEncodingView(
        tk_root,
        [[42]],
        None,
        ["Code"],
        None,
    )
    children = view.tree.get_children()
    assert len(children) == 1
    item = view.tree.item(children[0])
    assert item["text"] == "42"


# ---- GlyphCellRenderer -----------------------------------------------------


def test_glyph_cell_renderer_returns_none_for_sentinels():
    renderer = GlyphCellRenderer((0.0, 10.0))
    assert renderer.render_glyph(None) is None
    assert renderer.render_glyph("No glyph") is None
    assert renderer.render_glyph(".notdef") is None
    assert renderer.render_glyph("None") is None


def test_glyph_cell_renderer_get_y_bounds():
    renderer = GlyphCellRenderer((1.0, 2.0))
    assert renderer.get_y_bounds() == (1.0, 2.0)
    none_renderer = GlyphCellRenderer(None)
    assert none_renderer.get_y_bounds() is None


def test_glyph_cell_renderer_renders_vector_path():
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    renderer = GlyphCellRenderer((0.0, 10.0))
    path = [("moveTo", 0.0, 0.0), ("lineTo", 10.0, 10.0), ("lineTo", 10.0, 0.0)]
    img = renderer.render_glyph(path)
    assert img is not None
    assert img.size == (40, 40)


def test_glyph_cell_renderer_handles_prebaked_image():
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    from PIL import Image

    big = Image.new("RGB", (80, 80), "white")
    renderer = GlyphCellRenderer(None)
    img = renderer.render_glyph(big)
    assert img is not None
    assert img.size == (40, 40)


def test_glyph_cell_renderer_resize_failure_returns_none():
    """When ``resize`` raises, ``render_glyph`` falls back to ``None``."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")

    class _Boom:
        size = (10, 10)

        def resize(self, *_a, **_kw):
            raise RuntimeError("boom")

    renderer = GlyphCellRenderer(None)
    assert renderer.render_glyph(_Boom()) is None


def test_glyph_cell_renderer_get_table_cell_renderer_component():
    """Upstream-parity entry point delegates to ``render_glyph``."""
    renderer = GlyphCellRenderer((0.0, 10.0))
    # ``None`` value → ``None`` result.
    assert (
        renderer.get_table_cell_renderer_component(
            table="dummy", value=None
        )
        is None
    )


# ---- _rasterise_path edge cases --------------------------------------------


def test_rasterise_path_with_non_iterable_returns_none():
    """An ``int`` isn't iterable → ``_rasterise_path`` returns ``None``."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    assert _rasterise_path(42, None) is None


def test_rasterise_path_with_no_y_bounds_walks_points():
    """When ``y_bounds`` is ``None``, scan points for min/max y."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    path = [("moveTo", 0.0, 0.0), ("lineTo", 10.0, 20.0), ("lineTo", 5.0, 10.0)]
    img = _rasterise_path(path, None)
    assert img is not None
    assert img.size == (40, 40)


def test_rasterise_path_with_single_point_draws_dot():
    """A single-point path falls to the rectangle-dot branch."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    path = [("moveTo", 1.0, 2.0)]
    img = _rasterise_path(path, (0.0, 10.0))
    assert img is not None
    assert img.size == (40, 40)


def test_rasterise_path_with_two_points_draws_line():
    """A two-point path falls to the line branch."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    path = [("moveTo", 0.0, 0.0), ("lineTo", 10.0, 5.0)]
    img = _rasterise_path(path, (0.0, 10.0))
    assert img is not None
    assert img.size == (40, 40)


def test_rasterise_path_polygon_fallback_to_line(monkeypatch):
    """When ``draw.polygon`` raises, fall back to drawing polyline."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")
    from PIL import ImageDraw

    real_polygon = ImageDraw.ImageDraw.polygon

    def _broken_polygon(self, *_a, **_kw):
        raise ValueError("forced failure")

    monkeypatch.setattr(ImageDraw.ImageDraw, "polygon", _broken_polygon)
    try:
        path = [
            ("moveTo", 0.0, 0.0),
            ("lineTo", 10.0, 10.0),
            ("lineTo", 5.0, 5.0),
        ]
        img = _rasterise_path(path, (0.0, 10.0))
        assert img is not None
    finally:
        monkeypatch.setattr(ImageDraw.ImageDraw, "polygon", real_polygon)


def test_view_render_glyph_resize_failure_returns_none(tk_root):
    """View's ``_render_glyph`` returns ``None`` when ``resize`` raises."""
    pillow = _maybe_pillow()
    if pillow is None:
        pytest.skip("Pillow not available")

    class _Boom:
        size = (10, 10)

        def resize(self, *_a, **_kw):
            raise RuntimeError("boom")

    view = FontEncodingView(
        tk_root,
        [],
        None,
        ["Code", "Glyph"],
        None,
    )
    assert view._render_glyph(_Boom()) is None
