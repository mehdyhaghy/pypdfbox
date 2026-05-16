"""Hand-written tests for ``RotationMenu.create_rotation_menu``."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.rotation_menu import RotationMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    RotationMenu._reset_instance()
    yield
    RotationMenu._reset_instance()


def test_create_rotation_menu_returns_tk_menu_with_four_entries(tk_root: tk.Tk) -> None:
    menu = RotationMenu.get_instance(master=tk_root)
    rebuilt = menu.create_rotation_menu()
    assert isinstance(rebuilt, tk.Menu)
    assert rebuilt.index("end") == 3  # four entries, last index = 3


def test_create_rotation_menu_entries_match_labels(tk_root: tk.Tk) -> None:
    menu = RotationMenu.get_instance(master=tk_root)
    rebuilt = menu.create_rotation_menu()
    labels = [rebuilt.entrycget(i, "label") for i in range(4)]
    assert labels == [
        RotationMenu.ROTATE_0_DEGREES,
        RotationMenu.ROTATE_90_DEGREES,
        RotationMenu.ROTATE_180_DEGREES,
        RotationMenu.ROTATE_270_DEGREES,
    ]


def test_create_rotation_menu_private_alias_still_works(tk_root: tk.Tk) -> None:
    menu = RotationMenu.get_instance(master=tk_root)
    rebuilt = menu._create_rotation_menu()  # noqa: SLF001 - back-compat alias
    assert isinstance(rebuilt, tk.Menu)
