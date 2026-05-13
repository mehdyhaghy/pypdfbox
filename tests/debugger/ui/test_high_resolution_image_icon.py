"""Hand-written tests for ``pypdfbox.debugger.ui.HighResolutionImageIcon``."""

import os
import sys

import pytest

from pypdfbox.debugger.ui import HighResolutionImageIcon

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402  (after importorskip)


def _make_image(w: int = 64, h: int = 64) -> Image.Image:
    return Image.new("RGB", (w, h), (10, 20, 30))


def test_base_dimensions() -> None:
    icon = HighResolutionImageIcon(_make_image(128, 96), 64, 48)
    assert icon.get_icon_width() == 64
    assert icon.get_icon_height() == 48


def test_get_image_returns_original() -> None:
    img = _make_image(40, 30)
    icon = HighResolutionImageIcon(img, 20, 15)
    assert icon.get_image() is img


def _can_open_display() -> bool:
    if sys.platform == "darwin":
        # On macOS Tk needs an active WindowServer; CI may run headless.
        return os.environ.get("DISPLAY") is not None or os.environ.get("CI") != "true"
    if sys.platform == "win32":
        return True
    return os.environ.get("DISPLAY") is not None


@pytest.mark.skipif(
    not _can_open_display(), reason="No display available for Tk"
)
def test_get_photo_image_resizes() -> None:
    try:
        import tkinter as tk
    except ImportError:
        pytest.skip("tkinter not available")

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Cannot create Tk root in this environment")
    try:
        icon = HighResolutionImageIcon(_make_image(128, 96), 64, 48)
        photo = icon.get_photo_image()
        # Calling twice returns the cached PhotoImage.
        assert icon.get_photo_image() is photo
        assert photo.width() == 64
        assert photo.height() == 48
    finally:
        root.destroy()


@pytest.mark.skipif(
    not _can_open_display(), reason="No display available for Tk"
)
def test_paint_icon_uses_canvas() -> None:
    try:
        import tkinter as tk
    except ImportError:
        pytest.skip("tkinter not available")

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Cannot create Tk root in this environment")
    try:
        canvas = tk.Canvas(root, width=100, height=100)
        icon = HighResolutionImageIcon(_make_image(40, 40), 20, 20)
        item_id = icon.paint_icon(canvas, 5, 7)
        assert canvas.coords(item_id) == [5.0, 7.0]
    finally:
        root.destroy()
