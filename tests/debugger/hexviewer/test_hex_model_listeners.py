"""Tests for the promoted ``HexModel.fire_model_changed`` and ``is_ascii_printable``.

Both helpers existed as private (``_fire_model_changed`` /
``_is_ascii_printable``) before; the upstream ``HexModel`` keeps them in
its public/private interface but the parity tracker counts them by
upstream name, so we promote ``fire_model_changed`` to public dispatch and
``is_ascii_printable`` to a public static helper.
"""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[HexModelChangedEvent] = []

    def hex_model_changed(self, event: HexModelChangedEvent) -> None:
        self.events.append(event)


def test_fire_model_changed_notifies_registered_listeners() -> None:
    model = HexModel(b"abcdef")
    rec = _Recorder()
    model.add_hex_model_change_listener(rec)
    model.fire_model_changed(2)
    assert len(rec.events) == 1
    assert rec.events[0].get_start_index() == 2
    assert rec.events[0].get_change_type() == HexModelChangedEvent.SINGLE_CHANGE


def test_fire_model_changed_with_no_listeners_is_safe() -> None:
    model = HexModel(b"abc")
    # No listeners registered; the call must not raise.
    model.fire_model_changed(0)


def test_is_ascii_printable_boundaries() -> None:
    assert HexModel.is_ascii_printable(" ")  # 32 — first printable
    assert HexModel.is_ascii_printable("~")  # 126 — last printable
    assert not HexModel.is_ascii_printable("\x1f")  # 31 — below range
    assert not HexModel.is_ascii_printable("\x7f")  # 127 — DEL, excluded
    assert not HexModel.is_ascii_printable("")  # empty string handled


def test_is_ascii_printable_replaces_non_printable_in_get_line_chars() -> None:
    # Verifies the new public helper is wired into the existing rendering path.
    model = HexModel(b"\x00ABC\x7f")
    chars = model.get_line_chars(1)
    # Bytes 0 (NUL) and 0x7f (DEL) are non-printable -> '.'.
    assert chars[0] == "."
    assert chars[-1] == "."
    assert chars[1:4] == ["A", "B", "C"]


def test_legacy_private_aliases_still_work() -> None:
    """The ``_fire_model_changed`` / ``_is_ascii_printable`` aliases survive."""
    model = HexModel(b"x")
    rec = _Recorder()
    model.add_hex_model_change_listener(rec)
    model._fire_model_changed(0)  # noqa: SLF001
    assert len(rec.events) == 1
    assert HexModel._is_ascii_printable("A")  # noqa: SLF001
