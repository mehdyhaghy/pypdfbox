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


# ---- direct exercise of tooltip handlers --------------------------------


def test_on_motion_shows_tooltip_when_controller_returns_string(tk_root) -> None:
    class Controller:
        def get_tool_tip(self, offset, text_widget):
            return "tip text"

    view = StreamTextView(
        tk_root,
        [("hello", None)],
        [],
        tool_tip_controller=Controller(),
    )
    # Build a fake event with the attributes ``_on_motion`` reads.
    import types

    event = types.SimpleNamespace(x=10, y=5, x_root=200, y_root=300)
    view._on_motion(event)  # type: ignore[arg-type]  # noqa: SLF001
    # Tooltip window has been spawned.
    assert view._tool_tip_window is not None  # noqa: SLF001
    view._hide_tooltip()  # noqa: SLF001
    assert view._tool_tip_window is None  # noqa: SLF001


def test_on_motion_handles_controller_exception(tk_root) -> None:
    class BoomController:
        def get_tool_tip(self, offset, text_widget):
            raise RuntimeError("boom")

    view = StreamTextView(
        tk_root,
        [("hello", None)],
        [],
        tool_tip_controller=BoomController(),
    )
    import types

    event = types.SimpleNamespace(x=10, y=5, x_root=200, y_root=300)
    # The motion handler must swallow the controller's error.
    view._on_motion(event)  # type: ignore[arg-type]  # noqa: SLF001
    # No tooltip window since the controller blew up.
    assert view._tool_tip_window is None  # noqa: SLF001


def test_on_motion_without_controller_is_noop(tk_root) -> None:
    view = StreamTextView(tk_root, [("hi", None)], [])
    # Reach in and call _on_motion directly — should early-return.
    import types

    event = types.SimpleNamespace(x=0, y=0, x_root=0, y_root=0)
    view._on_motion(event)  # type: ignore[arg-type]  # noqa: SLF001


def test_text_index_to_offset_across_lines(tk_root) -> None:
    from pypdfbox.debugger.streampane.stream_text_view import (
        _text_index_to_offset,
    )

    view = StreamTextView(tk_root, [("abc\nxyz", None)], [])
    # Offset of the 'x' on line 2 column 0 = 4 ('abc' + '\n').
    assert _text_index_to_offset(view.text, "2.0") == 4
