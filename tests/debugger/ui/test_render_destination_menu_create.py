"""Hand-written tests for ``RenderDestinationMenu.create_menu``."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    RenderDestinationMenu._reset_instance()
    yield
    RenderDestinationMenu._reset_instance()


def test_create_menu_returns_tk_menu_with_three_entries(tk_root: tk.Tk) -> None:
    menu = RenderDestinationMenu.get_instance(master=tk_root)
    rebuilt = menu.create_menu()
    assert isinstance(rebuilt, tk.Menu)
    assert rebuilt.index("end") == 2  # three entries, last index = 2


def test_create_menu_entries_match_labels(tk_root: tk.Tk) -> None:
    menu = RenderDestinationMenu.get_instance(master=tk_root)
    rebuilt = menu.create_menu()
    labels = [rebuilt.entrycget(i, "label") for i in range(3)]
    assert labels == [
        RenderDestinationMenu.RENDER_DESTINATION_EXPORT,
        RenderDestinationMenu.RENDER_DESTINATION_PRINT,
        RenderDestinationMenu.RENDER_DESTINATION_VIEW,
    ]


def test_create_menu_private_alias_still_works(tk_root: tk.Tk) -> None:
    """The previously-private ``_create_menu`` remains callable for back-compat."""
    menu = RenderDestinationMenu.get_instance(master=tk_root)
    rebuilt = menu._create_menu()  # noqa: SLF001 - back-compat alias
    assert isinstance(rebuilt, tk.Menu)
