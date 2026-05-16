"""Hand-written tests for ``SearchPanel.init_ui`` (upstream parity)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import pytest

from pypdfbox.debugger.ui.textsearcher.search_panel import SearchPanel


@pytest.fixture
def _tk_root() -> tk.Tk:
    """Locally-scoped Tk root respecting ``PYPDFBOX_SKIP_TK``."""
    if os.environ.get("PYPDFBOX_SKIP_TK") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless guard
        pytest.skip(f"Tk display unavailable: {exc}")
    try:
        yield root
    finally:
        root.destroy()


class _NoopListener:
    """A duck-typed stand-in for the upstream Swing listeners."""

    def changed_update(self, _event: object) -> None:  # pragma: no cover - smoke
        pass

    def state_changed(self, _event: object) -> None:  # pragma: no cover - smoke
        pass

    def component_shown(self, _event: object) -> None:  # pragma: no cover - smoke
        pass

    def component_hidden(self, _event: object) -> None:  # pragma: no cover - smoke
        pass


def _make_panel(parent: tk.Misc) -> SearchPanel:
    return SearchPanel(
        document_listener=_NoopListener(),
        change_listener=_NoopListener(),
        component_listener=_NoopListener(),
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=parent,
    )


def test_init_ui_runs_during_construction(_tk_root: tk.Tk) -> None:
    panel = _make_panel(_tk_root)
    # The frame is exposed and populated by init_ui().
    frame = panel.get_panel()
    assert isinstance(frame, ttk.Frame)
    # Search field/buttons exist and are children of the frame.
    children = frame.winfo_children()
    assert any(isinstance(child, ttk.Entry) for child in children)
    assert any(isinstance(child, ttk.Button) for child in children)


def test_init_ui_is_public_callable(_tk_root: tk.Tk) -> None:
    """``init_ui`` is the new public name (mirrors upstream ``initUI``)."""
    panel = _make_panel(_tk_root)
    assert callable(panel.init_ui)
    # Back-compat alias preserved — both names resolve to the same function.
    assert SearchPanel._init_ui is SearchPanel.init_ui  # noqa: SLF001


def test_init_ui_wires_search_var_to_document_listener(_tk_root: tk.Tk) -> None:
    fired: list[object] = []

    class _Doc:
        def changed_update(self, event: object) -> None:
            fired.append(event)

    panel = SearchPanel(
        document_listener=_Doc(),
        change_listener=_NoopListener(),
        component_listener=_NoopListener(),
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=_tk_root,
    )
    # Mutating the search var must reach the document listener — confirms
    # ``init_ui`` installed the ``trace_add("write", ...)`` callback.
    panel._search_var.set("hello")  # noqa: SLF001 - smoke probe
    assert len(fired) == 1
