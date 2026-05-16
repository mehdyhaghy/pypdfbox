"""Hand-written tests for ``ImageTypeMenu.create_menu`` (upstream parity)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    ImageTypeMenu._reset_for_testing()
    yield
    ImageTypeMenu._reset_for_testing()


def test_create_menu_returns_tk_menu_with_four_entries(tk_root: tk.Tk) -> None:
    menu = ImageTypeMenu.get_instance(master=tk_root)
    rebuilt = menu.create_menu()
    assert isinstance(rebuilt, tk.Menu)
    assert rebuilt.index("end") == 3  # four entries, last index = 3


def test_create_menu_entries_match_labels(tk_root: tk.Tk) -> None:
    menu = ImageTypeMenu.get_instance(master=tk_root)
    rebuilt = menu.create_menu()
    labels = [rebuilt.entrycget(i, "label") for i in range(4)]
    assert labels == [
        ImageTypeMenu.IMAGETYPE_RGB,
        ImageTypeMenu.IMAGETYPE_ARGB,
        ImageTypeMenu.IMAGETYPE_GRAY,
        ImageTypeMenu.IMAGETYPE_BITONAL,
    ]


def test_create_menu_private_alias_still_works(tk_root: tk.Tk) -> None:
    """The previously-private ``_create_menu`` remains callable for back-compat."""
    menu = ImageTypeMenu.get_instance(master=tk_root)
    rebuilt = menu._create_menu()  # noqa: SLF001 - back-compat alias
    assert isinstance(rebuilt, tk.Menu)
