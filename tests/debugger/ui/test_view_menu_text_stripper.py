"""Tests for the upstream-named :class:`ViewMenu` text-stripper accessors.

Covers :py:meth:`ViewMenu.is_show_text_stripper` and
:py:meth:`ViewMenu.is_show_text_stripper_beads`, which mirror upstream
``isShowTextStripper()`` / ``isShowTextStripperBeads()``.
"""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.ui.view_menu import ViewMenu


def test_is_show_text_stripper_defaults_false() -> None:
    """When no singleton has been created, the accessor returns False."""
    ViewMenu._reset_instance()  # noqa: SLF001
    assert ViewMenu.is_show_text_stripper() is False
    assert ViewMenu.is_show_text_stripper_beads() is False


def test_is_show_text_stripper_mirrors_underlying_variable(tk_root: tk.Tk) -> None:
    ViewMenu._reset_instance()  # noqa: SLF001
    try:
        instance = ViewMenu.get_instance(master=tk_root)
        # Both upstream-named accessors must agree with their
        # snake_cased counterparts that already existed.
        instance._show_text_positions_var.set(True)  # noqa: SLF001
        assert ViewMenu.is_show_text_stripper() is True
        assert ViewMenu.is_show_text_positions() is True
        instance._show_text_strip_beads_var.set(True)  # noqa: SLF001
        assert ViewMenu.is_show_text_stripper_beads() is True
        assert ViewMenu.is_show_text_strip_beads() is True
    finally:
        ViewMenu._reset_instance()  # noqa: SLF001


def test_is_show_text_stripper_toggles_independently(tk_root: tk.Tk) -> None:
    ViewMenu._reset_instance()  # noqa: SLF001
    try:
        instance = ViewMenu.get_instance(master=tk_root)
        instance._show_text_positions_var.set(True)  # noqa: SLF001
        instance._show_text_strip_beads_var.set(False)  # noqa: SLF001
        assert ViewMenu.is_show_text_stripper() is True
        assert ViewMenu.is_show_text_stripper_beads() is False
    finally:
        ViewMenu._reset_instance()  # noqa: SLF001
