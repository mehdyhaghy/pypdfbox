"""Predicate-focused tests for :class:`pypdfbox.debugger.ui.ViewMenu`.

Covers the methods promoted/added in wave 1308 to round out parity with
upstream ``ViewMenu``:

* ``create_view_menu`` — smoke test that the upstream-named builder
  returns a populated ``tk.Menu``.
* ``is_show_font_b_box`` / ``is_repair_acroform_selected`` — read-only
  predicates that mirror the underlying checkbox state.
* ``is_extract_text_event`` / ``is_repair_acroform_event`` — predicates
  on the *action command* carried by a dispatched event (Tk label or
  Swing-shaped object that exposes ``action_command``/``label``).
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
from pypdfbox.debugger.ui.rotation_menu import RotationMenu
from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

# Mirror the indices from ``test_view_menu.py`` so reads here also serve
# as documentation of the upstream menu order.
IDX_SHOW_APPROXIMATE_TEXT_BOUNDS = 8
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
# create_view_menu — upstream-named builder
# ----------------------------------------------------------------------


def test_create_view_menu_returns_populated_menu(tk_root: tk.Tk) -> None:
    view = ViewMenu(master=tk_root)
    # Constructor already wired ``set_menu(create_view_menu())`` — the
    # returned menu should match the one ``get_menu`` exposes and carry
    # the full 17-entry upstream layout (indices 0..16).
    menu = view.get_menu()
    assert menu is not None
    assert isinstance(menu, tk.Menu)
    assert menu.index("end") == IDX_REPAIR_ACROFORM
    # Last entry is the Repair AcroForm checkbutton.
    assert menu.type(IDX_REPAIR_ACROFORM) == "checkbutton"
    assert menu.entrycget(IDX_REPAIR_ACROFORM, "label") == ViewMenu.REPAIR_ACROFORM


def test_create_view_menu_callable_directly(tk_root: tk.Tk) -> None:
    # Calling ``create_view_menu`` a second time should yield a fresh
    # ``tk.Menu`` instance (mirrors upstream behavior — the builder
    # constructs a new ``JMenu`` on every call).
    view = ViewMenu(master=tk_root)
    rebuilt = view.create_view_menu()
    assert rebuilt is not view.get_menu()
    assert rebuilt.index("end") == IDX_REPAIR_ACROFORM


# ----------------------------------------------------------------------
# is_show_font_b_box — alias of is_show_approximate_text_bounds
# ----------------------------------------------------------------------


def test_is_show_font_b_box_default_false(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_show_font_b_box() is False


def test_is_show_font_b_box_reflects_checkbox(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    menu = view.get_menu()
    menu.entryconfigure(IDX_SHOW_APPROXIMATE_TEXT_BOUNDS, state="normal")
    menu.invoke(IDX_SHOW_APPROXIMATE_TEXT_BOUNDS)
    assert ViewMenu.is_show_font_b_box() is True
    # Toggling off via the same entry must clear the predicate too.
    menu.invoke(IDX_SHOW_APPROXIMATE_TEXT_BOUNDS)
    assert ViewMenu.is_show_font_b_box() is False


def test_is_show_font_b_box_without_instance() -> None:
    ViewMenu._reset_instance()
    assert ViewMenu.is_show_font_b_box() is False


# ----------------------------------------------------------------------
# is_repair_acroform_selected — alias of is_repair_acro_form
# ----------------------------------------------------------------------


def test_is_repair_acroform_selected_default_false(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_repair_acroform_selected() is False


def test_is_repair_acroform_selected_reflects_checkbox(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    menu = view.get_menu()
    menu.entryconfigure(IDX_REPAIR_ACROFORM, state="normal")
    menu.invoke(IDX_REPAIR_ACROFORM)
    assert ViewMenu.is_repair_acroform_selected() is True
    menu.invoke(IDX_REPAIR_ACROFORM)
    assert ViewMenu.is_repair_acroform_selected() is False


def test_is_repair_acroform_selected_without_instance() -> None:
    ViewMenu._reset_instance()
    assert ViewMenu.is_repair_acroform_selected() is False


# ----------------------------------------------------------------------
# Event predicates — accept Tk label strings and Swing-shaped objects.
# ----------------------------------------------------------------------


@dataclass
class _FakeActionEvent:
    """Stand-in for ``java.awt.event.ActionEvent`` — exposes only the
    attribute the predicates inspect."""

    action_command: str


def test_is_extract_text_event_label_string() -> None:
    assert ViewMenu.is_extract_text_event(ViewMenu.EXTRACT_TEXT) is True
    assert ViewMenu.is_extract_text_event(ViewMenu.REPAIR_ACROFORM) is False
    assert ViewMenu.is_extract_text_event("Zoom") is False


def test_is_extract_text_event_event_object() -> None:
    assert (
        ViewMenu.is_extract_text_event(_FakeActionEvent(ViewMenu.EXTRACT_TEXT))
        is True
    )
    assert (
        ViewMenu.is_extract_text_event(_FakeActionEvent(ViewMenu.REPAIR_ACROFORM))
        is False
    )


def test_is_extract_text_event_unknown_payload_returns_false() -> None:
    # Neither a string, nor an attribute-bearing object → no match.
    assert ViewMenu.is_extract_text_event(object()) is False
    assert ViewMenu.is_extract_text_event(None) is False


def test_is_repair_acroform_event_label_string() -> None:
    assert ViewMenu.is_repair_acroform_event(ViewMenu.REPAIR_ACROFORM) is True
    assert ViewMenu.is_repair_acroform_event(ViewMenu.EXTRACT_TEXT) is False
    assert ViewMenu.is_repair_acroform_event("nonsense") is False


def test_is_repair_acroform_event_event_object() -> None:
    assert (
        ViewMenu.is_repair_acroform_event(_FakeActionEvent(ViewMenu.REPAIR_ACROFORM))
        is True
    )
    assert (
        ViewMenu.is_repair_acroform_event(_FakeActionEvent(ViewMenu.EXTRACT_TEXT))
        is False
    )


def test_event_predicates_use_label_attribute_fallback() -> None:
    """Some Tk-side adapters expose ``label`` rather than ``action_command``;
    the predicate must fall back to that attribute."""

    class _LabelBearing:
        def __init__(self, label: str) -> None:
            self.label = label

    assert (
        ViewMenu.is_extract_text_event(_LabelBearing(ViewMenu.EXTRACT_TEXT)) is True
    )
    assert (
        ViewMenu.is_repair_acroform_event(_LabelBearing(ViewMenu.REPAIR_ACROFORM))
        is True
    )
