"""Tests for :class:`StreamImageView`."""

from __future__ import annotations

import pytest

from pypdfbox.debugger.streampane.stream_image_view import StreamImageView

PIL = pytest.importorskip("PIL.Image")


def test_image_view_constructs_without_error(tk_root) -> None:
    image = PIL.new("RGB", (32, 16), color="blue")
    view = StreamImageView(tk_root, image)
    assert view.get_view() is view


def test_image_view_zoom_updates_canvas(tk_root) -> None:
    image = PIL.new("RGB", (32, 16), color="blue")
    view = StreamImageView(tk_root, image, zoom_scale=1.0)
    initial = view.canvas.cget("scrollregion")
    view.set_zoom(2.0)
    updated = view.canvas.cget("scrollregion")
    # Both must be non-empty; the second should reflect the larger canvas.
    assert str(initial)
    assert str(updated) != str(initial)


def test_image_view_rotation_updates_canvas(tk_root) -> None:
    image = PIL.new("RGB", (32, 16), color="blue")
    view = StreamImageView(tk_root, image, rotation_degrees=0)
    initial = view.canvas.cget("scrollregion")
    view.set_rotation(90)
    rotated = view.canvas.cget("scrollregion")
    assert str(rotated) != str(initial)
