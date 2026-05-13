"""Tests for the :class:`FontEncodingView` Tkinter widget."""

from __future__ import annotations

from pypdfbox.debugger.fontencodingpane.font_encoding_view import FontEncodingView


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
