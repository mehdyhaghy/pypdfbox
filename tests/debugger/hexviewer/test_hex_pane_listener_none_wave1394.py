"""Wave 1394 — ``HexPane`` listener-shaped public method early-exits.

Covers lines 318-320 (``mouse_clicked(None)``) and 355-357
(``key_pressed(None)``) — both public spellings accept ``None`` for
parity-tool invocation and return immediately.
"""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane


def test_mouse_clicked_none_event_returns_none(tk_root: tk.Tk) -> None:
    """``mouse_clicked(None)`` short-circuits without dispatching (lines 318-319)."""
    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    assert pane.mouse_clicked(None) is None


def test_mouse_clicked_with_event_delegates_to_on_click(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mouse_clicked(event)`` threads through to ``_on_click`` (line 320)."""
    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    spy = MagicMock(return_value="break")
    monkeypatch.setattr(pane, "_on_click", spy)
    event = tk.Event()
    assert pane.mouse_clicked(event) == "break"
    spy.assert_called_once_with(event)


def test_key_pressed_none_event_returns_none(tk_root: tk.Tk) -> None:
    """``key_pressed(None)`` short-circuits without dispatching (lines 355-356)."""
    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    assert pane.key_pressed(None) is None


def test_key_pressed_with_event_delegates_to_on_key(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``key_pressed(event)`` threads through to ``_on_key`` (line 357)."""
    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    spy = MagicMock(return_value="break")
    monkeypatch.setattr(pane, "_on_key", spy)
    event = tk.Event()
    assert pane.key_pressed(event) == "break"
    spy.assert_called_once_with(event)
