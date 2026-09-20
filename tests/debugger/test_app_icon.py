"""Icon wiring for the Tk debugger window (``pypdfbox.debugger.app_icon``)."""

from __future__ import annotations

import contextlib
import os
import struct
import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.app_icon import _PHOTO_SIZES, apply_window_icon, icon_dir


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    if os.environ.get("PYPDFBOX_SKIP_TK") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk tests opted out")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    try:
        yield root
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()


def test_icon_dir_resolves_inside_the_package() -> None:
    directory = icon_dir()
    assert directory.is_dir()
    assert directory.name == "icon"


@pytest.mark.parametrize("size", _PHOTO_SIZES)
def test_png_exists_and_is_square_at_its_declared_size(size: int) -> None:
    """Each shipped PNG really is `size` x `size`.

    Read from the IHDR chunk directly rather than via Pillow so the shipped
    asset is validated even if the image stack is unavailable.
    """
    png = icon_dir() / f"pypdfbox-{size}.png"
    header = png.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    width, height = struct.unpack(">II", header[16:24])
    assert (width, height) == (size, size)


def test_windows_ico_is_shipped_for_iconbitmap() -> None:
    ico = icon_dir() / "pypdfbox.ico"
    assert ico.is_file()
    # ICO header: reserved=0, type=1 (icon), then the image count.
    reserved, image_type, count = struct.unpack("<HHH", ico.read_bytes()[:6])
    assert (reserved, image_type) == (0, 1)
    assert count >= 6, "expected a multi-size ICO"


def test_apply_window_icon_sets_an_icon(tk_root: tk.Tk) -> None:
    assert apply_window_icon(tk_root) is True


def test_apply_window_icon_keeps_a_reference_to_the_images(
    tk_root: tk.Tk,
) -> None:
    """Tk only weakly references a PhotoImage.

    Without the module-level anchor the images are collected as soon as
    ``apply_window_icon`` returns and the icon silently blanks.
    """
    from pypdfbox.debugger import app_icon

    before = len(app_icon._ICON_REFS)
    apply_window_icon(tk_root)
    assert len(app_icon._ICON_REFS) > before


def test_apply_window_icon_never_raises_on_a_hostile_window() -> None:
    """A window whose icon calls all fail yields False, not an exception."""

    class _Hostile:
        def iconbitmap(self, *args: object, **kwargs: object) -> None:
            raise tk.TclError("no")

        def iconphoto(self, *args: object) -> None:
            raise tk.TclError("no")

    assert apply_window_icon(_Hostile()) is False


def test_photo_sizes_are_largest_first() -> None:
    """The dock takes the FIRST image as primary.

    Ascending order made 16x16 primary, so macOS upscaled a 16px bitmap to
    dock size and the icon rendered blurred. Pin the ordering so that
    regression cannot come back silently.
    """
    assert list(_PHOTO_SIZES) == sorted(_PHOTO_SIZES, reverse=True)
    assert _PHOTO_SIZES[0] == 512


def test_every_declared_photo_size_ships() -> None:
    directory = icon_dir()
    missing = [s for s in _PHOTO_SIZES if not (directory / f"pypdfbox-{s}.png").is_file()]
    assert not missing, f"declared but not shipped: {missing}"
