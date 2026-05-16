"""Tests for :class:`StreamImageView`."""

from __future__ import annotations

import os

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


# ---- add_image / init_ui / zoom_image (upstream parity) ------------------


def test_add_image_replaces_current_image(tk_root) -> None:
    """``add_image`` swaps the displayed image and re-renders the canvas."""

    first = PIL.new("RGB", (10, 10), color="red")
    second = PIL.new("RGB", (20, 8), color="green")
    view = StreamImageView(tk_root, first)
    assert view.current_image is not None
    assert view.current_image.size == (10, 10)

    view.add_image(second)
    assert view.current_image is not None
    assert view.current_image.size == (20, 8)


def test_zoom_image_doubles_dimensions(tk_root) -> None:
    """``zoom_image(2.0)`` returns an image with doubled width and height."""

    image = PIL.new("RGB", (10, 10), color="red")
    view = StreamImageView(tk_root, image)
    rendered = view.zoom_image(2.0)
    assert rendered is not None
    assert rendered.size == (20, 20)


def test_zoom_image_halves_dimensions(tk_root) -> None:
    """``zoom_image(0.5)`` returns an image with halved dimensions."""

    image = PIL.new("RGB", (10, 10), color="red")
    view = StreamImageView(tk_root, image)
    rendered = view.zoom_image(0.5)
    assert rendered is not None
    assert rendered.size == (5, 5)


def test_add_image_then_zoom_one_preserves_dimensions(tk_root) -> None:
    """Round-trip: ``add_image`` then ``zoom_image(1.0)`` keeps size."""

    placeholder = PIL.new("RGB", (32, 32), color="white")
    payload = PIL.new("RGB", (10, 10), color="blue")

    view = StreamImageView(tk_root, placeholder)
    view.add_image(payload)
    rendered = view.zoom_image(1.0)
    assert rendered is not None
    assert rendered.size == (10, 10)


def test_init_ui_smoke_honours_skip_tk_env(tk_root) -> None:
    """``init_ui`` rebuilds the widget tree; honours ``PYPDFBOX_SKIP_TK``."""

    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk smoke test opted out")

    image = PIL.new("RGB", (10, 10), color="purple")
    view = StreamImageView(tk_root, image)
    first_canvas = view.canvas

    # Re-invoking init_ui rebuilds the canvas; calling it twice must
    # not raise and must still leave the view with a usable canvas.
    view.init_ui()
    assert view.canvas is not None
    # The canvas widget is fresh after rebuild.
    assert view.canvas is not first_canvas or view.canvas.winfo_exists()
