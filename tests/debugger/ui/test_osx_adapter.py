"""Hand-written tests for ``pypdfbox.debugger.ui.OSXAdapter``."""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Any

import pytest

from pypdfbox.debugger.ui import OSXAdapter


class FakeRoot:
    """Stand-in for ``tk.Misc`` -- records every ``createcommand`` call."""

    def __init__(self) -> None:
        self.commands: dict[str, Any] = {}

    def createcommand(self, name: str, callback: Any) -> None:
        self.commands[name] = callback


def test_methods_noop_on_non_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    fake = FakeRoot()
    adapter = OSXAdapter(fake)
    assert adapter.set_quit_handler(lambda: None) is False
    assert adapter.set_about_handler(lambda: None) is False
    assert adapter.set_preferences_handler(lambda: None) is False
    assert adapter.set_file_handler(lambda path: None) is False
    assert fake.commands == {}


def test_methods_register_on_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = FakeRoot()
    adapter = OSXAdapter(fake)
    assert adapter.set_quit_handler(lambda: None) is True
    assert adapter.set_about_handler(lambda: None) is True
    assert adapter.set_preferences_handler(lambda: None) is True
    assert adapter.set_file_handler(lambda path: None) is True
    assert "::tk::mac::Quit" in fake.commands
    assert "tk::mac::standardAboutPanel" in fake.commands
    assert "::tk::mac::ShowPreferences" in fake.commands
    assert "::tk::mac::OpenDocument" in fake.commands


def test_methods_skip_none_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = FakeRoot()
    adapter = OSXAdapter(fake)
    assert adapter.set_quit_handler(None) is False
    assert adapter.set_file_handler(None) is False
    assert fake.commands == {}


def test_register_returns_none_on_non_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    fake = FakeRoot()
    result = OSXAdapter.register(fake, {"quit": lambda: None})
    assert result is None
    assert fake.commands == {}


def test_register_installs_all_callbacks_on_darwin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = FakeRoot()
    quit_calls: list[int] = []
    about_calls: list[int] = []
    prefs_calls: list[int] = []
    file_calls: list[str] = []
    result = OSXAdapter.register(
        fake,
        {
            "quit": lambda: quit_calls.append(1),
            "about": lambda: about_calls.append(1),
            "preferences": lambda: prefs_calls.append(1),
            "file": lambda path: file_calls.append(path),
        },
    )
    assert result is not None
    fake.commands["::tk::mac::Quit"]()
    fake.commands["tk::mac::standardAboutPanel"]()
    fake.commands["::tk::mac::ShowPreferences"]()
    fake.commands["::tk::mac::OpenDocument"]("/tmp/x.pdf")
    assert quit_calls == [1]
    assert about_calls == [1]
    assert prefs_calls == [1]
    assert file_calls == ["/tmp/x.pdf"]


def test_register_with_no_callbacks_still_returns_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = FakeRoot()
    adapter = OSXAdapter.register(fake, None)
    assert adapter is not None
    assert fake.commands == {}


def test_register_handles_unknown_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = FakeRoot()
    adapter = OSXAdapter.register(
        fake, {"unknown": lambda: None, "quit": lambda: None}
    )
    assert adapter is not None
    # ``quit`` was installed; ``unknown`` was ignored.
    assert "::tk::mac::Quit" in fake.commands


def test_file_handler_ignores_empty_path_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = FakeRoot()
    adapter = OSXAdapter(fake)
    seen: list[str] = []
    adapter.set_file_handler(lambda path: seen.append(path))
    # Tk would normally pass at least one arg; with zero we should no-op.
    fake.commands["::tk::mac::OpenDocument"]()
    assert seen == []
    fake.commands["::tk::mac::OpenDocument"]("/tmp/a", "/tmp/b")
    assert seen == ["/tmp/a"]


def test_real_tk_root_accepts_create_command(tk_root: tk.Tk) -> None:
    # Plain smoke test: a real Tk root supports createcommand even on Linux,
    # since createcommand is a generic Tcl primitive.
    tk_root.createcommand("test::noop", lambda: None)
