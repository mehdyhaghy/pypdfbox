"""Tests for ``OSXAdapter.set_handler`` (port of upstream ``setHandler``)."""

from __future__ import annotations

from typing import Any

from pypdfbox.debugger.ui import OSXAdapter


class _FakeRoot:
    """Records every ``createcommand`` call."""

    def __init__(self) -> None:
        self.commands: dict[str, Any] = {}

    def createcommand(self, name: str, callback: Any) -> None:
        self.commands[name] = callback


class _Adapter:
    """Minimal adapter exposing the handle_* surface ``set_handler`` looks for."""

    def __init__(self, root: Any) -> None:
        self._root = root
        self.reopens: list[int] = []
        self.quits: list[int] = []
        self.abouts: list[int] = []

    def handle_reopen_application(self) -> None:
        self.reopens.append(1)

    def handle_quit(self) -> None:
        self.quits.append(1)

    def handle_about(self) -> None:
        self.abouts.append(1)


def test_set_handler_registers_all_handle_methods() -> None:
    root = _FakeRoot()
    adapter = _Adapter(root)
    assert OSXAdapter.set_handler(adapter) is True
    assert "::tk::mac::ReopenApplication" in root.commands
    assert "::tk::mac::Quit" in root.commands
    assert "tk::mac::standardAboutPanel" in root.commands
    # Verify the bound methods are actually wired up.
    root.commands["::tk::mac::ReopenApplication"]()
    root.commands["::tk::mac::Quit"]()
    root.commands["tk::mac::standardAboutPanel"]()
    assert adapter.reopens == [1]
    assert adapter.quits == [1]
    assert adapter.abouts == [1]


def test_set_handler_returns_false_when_root_lacks_createcommand() -> None:
    class _Bare:
        _root = object()  # no createcommand

    assert OSXAdapter.set_handler(_Bare()) is False


def test_set_handler_skips_missing_handle_methods() -> None:
    root = _FakeRoot()

    class _Partial:
        def __init__(self, r: Any) -> None:
            self._root = r

        def handle_quit(self) -> None:
            pass

    assert OSXAdapter.set_handler(_Partial(root)) is True
    # Only Quit was registered; the other Tk mac commands were not.
    assert list(root.commands) == ["::tk::mac::Quit"]
