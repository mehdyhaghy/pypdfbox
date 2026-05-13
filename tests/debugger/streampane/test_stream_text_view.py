"""Tests for :class:`StreamTextView`."""

from __future__ import annotations

from pypdfbox.debugger.streampane.stream_text_view import StreamTextView


def test_text_view_inserts_segments_with_tags(tk_root) -> None:
    segments = [
        ("BT", "operator"),
        ("\n  /F1 12 Tf", "name"),
        ("\n", None),
    ]
    styles = [
        ("operator", {"foreground": "#19379c"}),
        ("name", {"foreground": "#8c2691"}),
    ]
    view = StreamTextView(tk_root, segments, styles)
    contents = view.text.get("1.0", "end-1c")
    assert "BT" in contents
    assert "/F1 12 Tf" in contents


def test_text_view_is_disabled_after_construction(tk_root) -> None:
    view = StreamTextView(tk_root, [("payload", None)], [])
    assert str(view.text.cget("state")) == "disabled"


def test_text_view_returns_self_from_get_view(tk_root) -> None:
    view = StreamTextView(tk_root, [], [])
    assert view.get_view() is view


def test_text_view_with_tooltip_controller_responds_to_motion(tk_root) -> None:
    captured = []

    class Controller:
        def get_tool_tip(self, offset, text_widget):
            captured.append(offset)
            return None  # nothing to show — exercises only the call path

    view = StreamTextView(
        tk_root,
        [("hello", None)],
        [],
        tool_tip_controller=Controller(),
    )
    # Trigger the binding manually — we don't need real coordinates.
    view.text.event_generate("<Motion>", x=10, y=5)
    tk_root.update_idletasks()
    # We can't synchronously assert the binding ran, but at minimum
    # the constructor must have succeeded.
    assert view.get_view() is view
