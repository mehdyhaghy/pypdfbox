"""Hand-written tests for ``pypdfbox.debugger.ui.HighResolutionImageIcon``."""

import tkinter as tk

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


def test_get_photo_image_resizes(tk_root: tk.Tk) -> None:
    """Uses the session-scoped ``tk_root`` from ``conftest.py`` so we
    don't spin up a second ``Tk()`` (which is what was crashing in
    parallel pytest invocations on macOS).
    """
    icon = HighResolutionImageIcon(_make_image(128, 96), 64, 48)
    photo = icon.get_photo_image()
    # Calling twice returns the cached PhotoImage.
    assert icon.get_photo_image() is photo
    assert photo.width() == 64
    assert photo.height() == 48


def test_paint_icon_uses_canvas(tk_root: tk.Tk) -> None:
    """Uses the session-scoped ``tk_root`` from ``conftest.py``."""
    canvas = tk.Canvas(tk_root, width=100, height=100)
    try:
        icon = HighResolutionImageIcon(_make_image(40, 40), 20, 20)
        item_id = icon.paint_icon(canvas, 5, 7)
        assert canvas.coords(item_id) == [5.0, 7.0]
    finally:
        canvas.destroy()
