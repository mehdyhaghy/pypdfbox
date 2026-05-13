"""Hand-written tests for ``pypdfbox.debugger.ui.FileOpenSaveDialog``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.debugger.ui import FileOpenSaveDialog
from pypdfbox.debugger.ui import file_open_save_dialog as module


@pytest.fixture(autouse=True)
def _reset_impls() -> Iterator[None]:
    module.set_open_impl(None)
    module.set_save_impl(None)
    yield
    module.set_open_impl(None)
    module.set_save_impl(None)


def test_open_file_returns_chosen_path(tmp_path: Path) -> None:
    target = tmp_path / "foo.pdf"
    target.write_bytes(b"data")
    captured: dict[str, Any] = {}

    def fake_open(**kwargs: Any) -> str:
        captured.update(kwargs)
        return str(target)

    module.set_open_impl(fake_open)
    dialog = FileOpenSaveDialog(None, [("PDF", "*.pdf")])
    result = dialog.open_file()
    assert result == str(target)
    assert captured["filetypes"] == [("PDF", "*.pdf")]


def test_open_file_returns_none_on_cancel() -> None:
    module.set_open_impl(lambda **kwargs: "")
    dialog = FileOpenSaveDialog(None)
    assert dialog.open_file() is None


def test_save_file_writes_bytes(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    module.set_save_impl(lambda **kwargs: str(target))
    dialog = FileOpenSaveDialog(None)
    ok = dialog.save_file(b"hello", None)
    assert ok is True
    assert target.read_bytes() == b"hello"


def test_save_file_appends_extension(tmp_path: Path) -> None:
    target = tmp_path / "out"
    module.set_save_impl(lambda **kwargs: str(target))
    dialog = FileOpenSaveDialog(None)
    ok = dialog.save_file(b"x", "bin")
    assert ok is True
    assert (tmp_path / "out.bin").exists()


def test_save_file_returns_false_on_cancel() -> None:
    module.set_save_impl(lambda **kwargs: "")
    dialog = FileOpenSaveDialog(None)
    assert dialog.save_file(b"", "pdf") is False


def test_save_document_uses_extension_and_security_removal(tmp_path: Path) -> None:
    target = tmp_path / "doc"
    module.set_save_impl(lambda **kwargs: str(target))
    calls: list[tuple[str, Any]] = []

    class DummyDoc:
        def set_all_security_to_be_removed(self, flag: bool) -> None:
            calls.append(("security", flag))

        def save(self, path: str) -> None:
            calls.append(("save", path))

    dialog = FileOpenSaveDialog(None)
    ok = dialog.save_document(DummyDoc(), "pdf")
    assert ok is True
    assert calls == [
        ("security", True),
        ("save", str(target) + ".pdf"),
    ]


def test_save_document_returns_false_on_cancel() -> None:
    module.set_save_impl(lambda **kwargs: "")

    class DummyDoc:
        def set_all_security_to_be_removed(self, flag: bool) -> None:
            raise AssertionError("not called")

        def save(self, path: str) -> None:
            raise AssertionError("not called")

    dialog = FileOpenSaveDialog(None)
    assert dialog.save_document(DummyDoc(), "pdf") is False


def test_open_file_passes_parent_when_provided() -> None:
    captured: dict[str, Any] = {}
    module.set_open_impl(lambda **kw: (captured.update(kw), "")[-1])
    sentinel = object()
    dialog = FileOpenSaveDialog(sentinel)
    dialog.open_file()
    assert captured.get("parent") is sentinel


def test_save_path_passes_parent_and_filter(tmp_path: Path) -> None:
    """When parent + file_filter are provided, both flow into the save impl."""
    target = tmp_path / "out.pdf"
    captured: dict[str, Any] = {}

    def fake_save(**kw: Any) -> str:
        captured.update(kw)
        return str(target)

    module.set_save_impl(fake_save)
    sentinel = object()
    dialog = FileOpenSaveDialog(sentinel, [("PDF", "*.pdf")])
    ok = dialog.save_file(b"x", "pdf")
    assert ok is True
    assert captured.get("parent") is sentinel
    assert captured.get("filetypes") == [("PDF", "*.pdf")]


def test_default_open_routes_through_filedialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_default_open`` lazily imports ``tkinter.filedialog`` and forwards
    to ``askopenfilename``.

    We patch the ``filedialog`` attribute on the ``tkinter`` module directly
    (not just ``sys.modules``), because once ``tkinter.filedialog`` has been
    imported transitively (e.g. via ``pypdfbox.debugger.pd_debugger``), the
    attribute on ``tkinter`` shadows any ``sys.modules`` entry and the real
    ``askopenfilename`` would open a blocking native file dialog.
    """
    import tkinter
    import types

    captured: list[dict[str, Any]] = []
    fake = types.ModuleType("tkinter.filedialog")

    def fake_askopenfilename(**kwargs: Any) -> str:
        captured.append(dict(kwargs))
        return "/tmp/opened.pdf"

    fake.askopenfilename = fake_askopenfilename  # type: ignore[attr-defined]
    monkeypatch.setattr(tkinter, "filedialog", fake, raising=False)

    assert module._default_open(initialdir="/tmp") == "/tmp/opened.pdf"
    assert captured == [{"initialdir": "/tmp"}]


def test_default_save_routes_through_filedialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_default_save`` lazily imports ``tkinter.filedialog`` and forwards
    to ``asksaveasfilename``. See ``test_default_open_routes_through_filedialog``
    for why we patch the attribute on ``tkinter`` rather than ``sys.modules``.
    """
    import tkinter
    import types

    captured: list[dict[str, Any]] = []
    fake = types.ModuleType("tkinter.filedialog")

    def fake_asksaveasfilename(**kwargs: Any) -> str:
        captured.append(dict(kwargs))
        return "/tmp/saved.pdf"

    fake.asksaveasfilename = fake_asksaveasfilename  # type: ignore[attr-defined]
    monkeypatch.setattr(tkinter, "filedialog", fake, raising=False)

    assert module._default_save(initialdir="/tmp") == "/tmp/saved.pdf"
    assert captured == [{"initialdir": "/tmp"}]
