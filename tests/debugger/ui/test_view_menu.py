"""Hand-written tests for :class:`pypdfbox.debugger.ui.ViewMenu`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
from pypdfbox.debugger.ui.rotation_menu import RotationMenu
from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

# Menu indices for the wiring built in ViewMenu.__init__. Kept here so each
# test reads as documentation of the upstream-mirrored layout.
IDX_TREE_VIEW = 0
IDX_ZOOM = 1
IDX_ROTATION = 2
IDX_IMAGE_TYPE = 3
IDX_RENDER_DESTINATION = 4
IDX_SEP_1 = 5
IDX_SHOW_TEXT_POSITIONS = 6
IDX_SHOW_TEXT_STRIP_BEADS = 7
IDX_SHOW_APPROXIMATE_TEXT_BOUNDS = 8
IDX_SHOW_GLYPH_BOUNDS = 9
IDX_SEP_2 = 10
IDX_ALLOW_SUBSAMPLING = 11
IDX_SEP_3 = 12
IDX_EXTRACT_TEXT = 13
IDX_TEXT_STRIPPER = 14
IDX_SEP_4 = 15
IDX_REPAIR_ACROFORM = 16


@pytest.fixture(autouse=True)
def _reset_singletons() -> Iterator[None]:
    ViewMenu._reset_instance()
    ZoomMenu._reset_instance()
    RotationMenu._reset_instance()
    RenderDestinationMenu._reset_instance()
    TreeViewMenu._reset_for_testing()
    ImageTypeMenu._reset_for_testing()
    TextStripperMenu._reset_for_testing()
    yield
    ViewMenu._reset_instance()
    ZoomMenu._reset_instance()
    RotationMenu._reset_instance()
    RenderDestinationMenu._reset_instance()
    TreeViewMenu._reset_for_testing()
    ImageTypeMenu._reset_for_testing()
    TextStripperMenu._reset_for_testing()


# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------


def test_construction_wires_full_upstream_layout(tk_root: tk.Tk) -> None:
    view = ViewMenu(master=tk_root)
    tk_menu = view.get_menu()
    # 5 cascades + 1 sep + 4 checkbuttons + 1 sep + 1 checkbutton + 1 sep
    # + 1 command + 1 cascade + 1 sep + 1 checkbutton => indices 0..16.
    assert tk_menu.index("end") == IDX_REPAIR_ACROFORM
    assert tk_menu.type(IDX_TREE_VIEW) == "cascade"
    assert tk_menu.type(IDX_ZOOM) == "cascade"
    assert tk_menu.type(IDX_ROTATION) == "cascade"
    assert tk_menu.type(IDX_IMAGE_TYPE) == "cascade"
    assert tk_menu.type(IDX_RENDER_DESTINATION) == "cascade"
    assert tk_menu.type(IDX_SEP_1) == "separator"
    assert tk_menu.type(IDX_SHOW_TEXT_POSITIONS) == "checkbutton"
    assert tk_menu.type(IDX_SHOW_TEXT_STRIP_BEADS) == "checkbutton"
    assert tk_menu.type(IDX_SHOW_APPROXIMATE_TEXT_BOUNDS) == "checkbutton"
    assert tk_menu.type(IDX_SHOW_GLYPH_BOUNDS) == "checkbutton"
    assert tk_menu.type(IDX_SEP_2) == "separator"
    assert tk_menu.type(IDX_ALLOW_SUBSAMPLING) == "checkbutton"
    assert tk_menu.type(IDX_SEP_3) == "separator"
    assert tk_menu.type(IDX_EXTRACT_TEXT) == "command"
    assert tk_menu.type(IDX_TEXT_STRIPPER) == "cascade"
    assert tk_menu.type(IDX_SEP_4) == "separator"
    assert tk_menu.type(IDX_REPAIR_ACROFORM) == "checkbutton"


def test_singleton(tk_root: tk.Tk) -> None:
    a = ViewMenu.get_instance(master=tk_root)
    b = ViewMenu.get_instance(master=tk_root)
    assert a is b


def test_view_menu_starts_with_submenus_disabled(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    # Construction sets each sub-menu's entries to disabled.
    assert ZoomMenu.get_instance().get_menu().entrycget(0, "state") == "disabled"
    assert RotationMenu.get_instance().get_menu().entrycget(0, "state") == "disabled"
    assert (
        RenderDestinationMenu.get_instance().get_menu().entrycget(0, "state")
        == "disabled"
    )
    assert ImageTypeMenu.get_instance().get_menu().entrycget(0, "state") == "disabled"
    assert (
        TextStripperMenu.get_instance().get_menu().entrycget(0, "state") == "disabled"
    )


# ----------------------------------------------------------------------
# Allow subsampling (always enabled, regression-guarded from wave 1294)
# ----------------------------------------------------------------------


def test_allow_subsampling_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_allow_subsampling() is False


def test_allow_subsampling_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    view.get_menu().invoke(IDX_ALLOW_SUBSAMPLING)
    assert ViewMenu.is_allow_subsampling() is True
    view.get_menu().invoke(IDX_ALLOW_SUBSAMPLING)
    assert ViewMenu.is_allow_subsampling() is False


# ----------------------------------------------------------------------
# Per-render-pass overlay toggles
# ----------------------------------------------------------------------


def _enable_and_invoke(menu: tk.Menu, index: int) -> None:
    """Helper — render-overlay entries start disabled by upstream design;
    re-enable for the test then invoke."""
    menu.entryconfigure(index, state="normal")
    menu.invoke(index)


def test_show_text_positions_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_show_text_positions() is False


def test_show_text_positions_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    _enable_and_invoke(view.get_menu(), IDX_SHOW_TEXT_POSITIONS)
    assert ViewMenu.is_show_text_positions() is True
    view.get_menu().invoke(IDX_SHOW_TEXT_POSITIONS)
    assert ViewMenu.is_show_text_positions() is False


def test_show_text_strip_beads_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_show_text_strip_beads() is False


def test_show_text_strip_beads_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    _enable_and_invoke(view.get_menu(), IDX_SHOW_TEXT_STRIP_BEADS)
    assert ViewMenu.is_show_text_strip_beads() is True
    view.get_menu().invoke(IDX_SHOW_TEXT_STRIP_BEADS)
    assert ViewMenu.is_show_text_strip_beads() is False


def test_show_approximate_text_bounds_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_show_approximate_text_bounds() is False


def test_show_approximate_text_bounds_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    _enable_and_invoke(view.get_menu(), IDX_SHOW_APPROXIMATE_TEXT_BOUNDS)
    assert ViewMenu.is_show_approximate_text_bounds() is True
    view.get_menu().invoke(IDX_SHOW_APPROXIMATE_TEXT_BOUNDS)
    assert ViewMenu.is_show_approximate_text_bounds() is False


def test_show_glyph_bounds_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_show_glyph_bounds() is False


def test_show_glyph_bounds_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    _enable_and_invoke(view.get_menu(), IDX_SHOW_GLYPH_BOUNDS)
    assert ViewMenu.is_show_glyph_bounds() is True
    view.get_menu().invoke(IDX_SHOW_GLYPH_BOUNDS)
    assert ViewMenu.is_show_glyph_bounds() is False


# ----------------------------------------------------------------------
# Repair AcroForm
# ----------------------------------------------------------------------


def test_repair_acro_form_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_repair_acro_form() is False


def test_repair_acro_form_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    _enable_and_invoke(view.get_menu(), IDX_REPAIR_ACROFORM)
    assert ViewMenu.is_repair_acro_form() is True
    view.get_menu().invoke(IDX_REPAIR_ACROFORM)
    assert ViewMenu.is_repair_acro_form() is False


# ----------------------------------------------------------------------
# Extract Text callback
# ----------------------------------------------------------------------


def test_extract_text_invokes_registered_callback(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    fired = []

    def _on_extract() -> None:
        fired.append(True)

    view.set_extract_text_callback(_on_extract)
    # Upstream disables the entry by default; enable it for this test.
    view.get_menu().entryconfigure(IDX_EXTRACT_TEXT, state="normal")
    view.get_menu().invoke(IDX_EXTRACT_TEXT)
    assert fired == [True]


def test_extract_text_no_callback_is_safe(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    view.get_menu().entryconfigure(IDX_EXTRACT_TEXT, state="normal")
    # No callback registered — invocation should be a no-op, not raise.
    view.get_menu().invoke(IDX_EXTRACT_TEXT)


def test_extract_text_callback_can_be_cleared(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    fired = []
    view.set_extract_text_callback(lambda: fired.append(True))
    view.set_extract_text_callback(None)
    view.get_menu().entryconfigure(IDX_EXTRACT_TEXT, state="normal")
    view.get_menu().invoke(IDX_EXTRACT_TEXT)
    assert fired == []


# ----------------------------------------------------------------------
# Static helpers
# ----------------------------------------------------------------------


def test_is_rendering_option_recognises_upstream_labels() -> None:
    assert ViewMenu.is_rendering_option(ViewMenu.SHOW_TEXT_STRIPPER) is True
    assert ViewMenu.is_rendering_option(ViewMenu.SHOW_TEXT_STRIPPER_BEADS) is True
    assert ViewMenu.is_rendering_option(ViewMenu.SHOW_FONT_BBOX) is True
    assert ViewMenu.is_rendering_option(ViewMenu.SHOW_GLYPH_BOUNDS) is True
    assert ViewMenu.is_rendering_option(ViewMenu.ALLOW_SUBSAMPLING) is True
    assert ViewMenu.is_rendering_option(ViewMenu.EXTRACT_TEXT) is False
    assert ViewMenu.is_rendering_option(ViewMenu.REPAIR_ACROFORM) is False
    assert ViewMenu.is_rendering_option("nonsense") is False


def test_accessors_without_instance_default_to_false() -> None:
    # No singleton constructed — every read-only accessor returns False
    # rather than crashing (mirrors the *Allow subsampling* contract).
    ViewMenu._reset_instance()
    assert ViewMenu.is_allow_subsampling() is False
    assert ViewMenu.is_show_text_positions() is False
    assert ViewMenu.is_show_text_strip_beads() is False
    assert ViewMenu.is_show_approximate_text_bounds() is False
    assert ViewMenu.is_show_glyph_bounds() is False
    assert ViewMenu.is_repair_acro_form() is False
