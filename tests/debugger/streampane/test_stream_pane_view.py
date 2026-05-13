"""Tests for :class:`StreamPaneView`."""

from __future__ import annotations

import pytest

from pypdfbox.debugger.streampane.stream_pane_view import StreamPaneView

PIL = pytest.importorskip("PIL.Image")


def test_show_stream_text_installs_text_view(tk_root) -> None:
    view = StreamPaneView(tk_root)
    child = view.show_stream_text([("BT", "operator")], [("operator", {})], None)
    assert view.current_child is child


def test_show_stream_image_installs_image_view(tk_root) -> None:
    view = StreamPaneView(tk_root)
    image = PIL.new("RGB", (16, 16), color="red")
    child = view.show_stream_image(image)
    assert view.current_child is child


def test_show_stream_replaces_previous_child(tk_root) -> None:
    view = StreamPaneView(tk_root)
    first = view.show_stream_text([("first", None)], [], None)
    second = view.show_stream_text([("second", None)], [], None)
    assert view.current_child is second
    assert second is not first


def test_get_stream_panel_returns_container(tk_root) -> None:
    view = StreamPaneView(tk_root)
    panel = view.get_stream_panel()
    assert panel is not None
