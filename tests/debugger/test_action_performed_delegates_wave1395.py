"""Wave 1395 — close residual ``action_performed`` / ``mouse_moved`` /
``ancestor_added`` delegate branches across the debugger UI modules.

These public methods exist solely for upstream-API parity (each maps to a
Java ``ActionListener.actionPerformed`` / ``MouseMotionListener.mouseMoved``
/ ``AncestorListener.ancestorAdded`` callback) and forward to the
already-tested private ``_on_*`` callbacks. The branches themselves are a
single call to the private handler; the tests below assert the delegate
fires without raising and routes through the expected callable.

Targets:

* ``debugger/ui/textsearcher/searcher.py`` line 107 —
  ``Searcher.action_performed`` delegates to ``_next_action``.
* ``debugger/ui/textsearcher/search_panel.py`` line 265 —
  ``SearchPanel.action_performed`` delegates to ``_find_action``.
* ``debugger/streampane/stream_pane.py`` line 195 —
  ``StreamPane.action_performed`` delegates to ``_on_filter_changed``.
* ``debugger/streampane/stream_image_view.py`` line 166 —
  ``StreamImageView.action_performed`` delegates to ``_render``.
* ``debugger/streampane/stream_text_view.py`` lines 124-126 —
  ``StreamTextView.mouse_moved`` (event=None early-return + non-None
  forward to ``_on_motion``).
* ``debugger/colorpane/cs_separation.py`` line 221 —
  ``CSSeparation.action_performed`` delegates to ``_on_tint_entry``.
* ``debugger/hexviewer/hex_editor.py`` line 229 —
  ``HexEditor.action_performed`` delegates to ``_show_jump_dialog``.
* ``debugger/treestatus/tree_status_pane.py`` lines 128-131 —
  ``TreeStatusPane.action_performed`` delegates to ``_on_text_input``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

# ---------- Searcher.action_performed ----------


def test_searcher_action_performed_delegates_to_next_action() -> None:
    from pypdfbox.debugger.ui.textsearcher.searcher import Searcher

    class _StubText:
        def get(self, _s: str, _e: str) -> str:
            return ""

        def tag_add(self, *_a: Any, **_kw: Any) -> None:
            return None

        def tag_remove(self, *_a: Any, **_kw: Any) -> None:
            return None

        def see(self, *_a: Any) -> None:
            return None

    searcher = Searcher(_StubText())
    with patch.object(searcher, "_next_action") as next_call:
        searcher.action_performed()
        next_call.assert_called_once()


# ---------- SearchPanel.action_performed ----------


def test_search_panel_action_performed_delegates_to_find_action() -> None:
    from pypdfbox.debugger.ui.textsearcher.search_panel import SearchPanel

    panel = SearchPanel.__new__(SearchPanel)  # bypass Tk init
    with patch.object(panel, "_find_action", create=True) as find_call:
        panel.action_performed()
        find_call.assert_called_once()


# ---------- StreamPane.action_performed ----------


def test_stream_pane_action_performed_delegates_to_filter_changed() -> None:
    from pypdfbox.debugger.streampane.stream_pane import StreamPane

    pane = StreamPane.__new__(StreamPane)  # bypass Tk init
    with patch.object(pane, "_on_filter_changed", create=True) as on_call:
        pane.action_performed(None)
        on_call.assert_called_once_with(None)


# ---------- StreamImageView.action_performed ----------


def test_stream_image_view_action_performed_triggers_render() -> None:
    from pypdfbox.debugger.streampane.stream_image_view import StreamImageView

    view = StreamImageView.__new__(StreamImageView)  # bypass Tk init
    with patch.object(view, "_render", create=True) as render_call:
        view.action_performed()
        render_call.assert_called_once()


# ---------- StreamTextView.mouse_moved (event=None + non-None) ----------


def test_stream_text_view_mouse_moved_none_event_is_noop() -> None:
    from pypdfbox.debugger.streampane.stream_text_view import StreamTextView

    view = StreamTextView.__new__(StreamTextView)  # bypass Tk init
    with patch.object(view, "_on_motion", create=True) as motion_call:
        view.mouse_moved(None)
        motion_call.assert_not_called()


def test_stream_text_view_mouse_moved_forwards_real_event() -> None:
    from pypdfbox.debugger.streampane.stream_text_view import StreamTextView

    view = StreamTextView.__new__(StreamTextView)  # bypass Tk init
    with patch.object(view, "_on_motion", create=True) as motion_call:
        sentinel = object()
        view.mouse_moved(sentinel)  # type: ignore[arg-type]
        motion_call.assert_called_once_with(sentinel)


# ---------- CSSeparation.action_performed ----------


def test_cs_separation_action_performed_delegates_to_on_tint_entry() -> None:
    from pypdfbox.debugger.colorpane.cs_separation import CSSeparation

    pane = CSSeparation.__new__(CSSeparation)  # bypass Tk init
    with patch.object(pane, "_on_tint_entry", create=True) as call:
        pane.action_performed(None)
        call.assert_called_once_with(None)


# ---------- HexEditor.action_performed ----------


def test_hex_editor_action_performed_opens_jump_dialog() -> None:
    from pypdfbox.debugger.hexviewer.hex_editor import HexEditor

    editor = HexEditor.__new__(HexEditor)  # bypass Tk init
    with patch.object(editor, "_show_jump_dialog", create=True) as show_call:
        editor.action_performed()
        show_call.assert_called_once()


# ---------- TreeStatusPane.action_performed ----------


def test_tree_status_pane_action_performed_returns_on_text_input_value() -> None:
    from pypdfbox.debugger.treestatus.tree_status_pane import TreeStatusPane

    pane = TreeStatusPane.__new__(TreeStatusPane)  # bypass Tk init
    with patch.object(
        pane,
        "_on_text_input",
        create=True,
        return_value="break",
    ) as call:
        result = pane.action_performed()
        assert result == "break"
        call.assert_called_once_with(None)
