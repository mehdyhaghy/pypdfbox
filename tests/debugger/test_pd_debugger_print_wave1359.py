"""Wave-1359 tests for the Debugger Print menu action.

The Print menu previously surfaced a "not implemented" messagebox; it now
rasterises pages and dispatches to the host OS spooler. These tests
exercise:

* the no-document early-return branch;
* the empty-document branch;
* the success-dispatch path (mocked spooler);
* the spooler-fallback (Popen raises) path; and
* the unwrapped ``_send_document_to_printer`` helper across the three
  platform-dispatch arms (Windows ``startfile`` / POSIX ``lp`` / opener).

Tests honour ``PYPDFBOX_SKIP_TK=1`` via the local ``tk_root`` fixture.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from typing import Any

import pytest
from PIL import Image

from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.pdmodel import PDDocument, PDPage

# ----------------------------------------------------------------------
# Fixtures (mirror tests/debugger/test_pd_debugger.py)
# ----------------------------------------------------------------------


def _reset_menu_singletons() -> None:
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu
    from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    ViewMenu._reset_instance()  # noqa: SLF001
    ZoomMenu._reset_instance()  # noqa: SLF001
    RotationMenu._reset_instance()  # noqa: SLF001
    RenderDestinationMenu._reset_instance()  # noqa: SLF001
    TreeViewMenu._reset_for_testing()  # noqa: SLF001
    ImageTypeMenu._reset_for_testing()  # noqa: SLF001
    TextStripperMenu._reset_for_testing()  # noqa: SLF001


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk tests opted out")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    _reset_menu_singletons()
    try:
        yield root
    finally:
        _reset_menu_singletons()
        with contextlib.suppress(tk.TclError):
            root.destroy()


@pytest.fixture()
def debugger(tk_root: tk.Tk) -> Iterator[PDFDebugger]:
    instance = PDFDebugger(tk_root)
    try:
        yield instance
    finally:
        with contextlib.suppress(tk.TclError):
            instance._main_frame.destroy()  # noqa: SLF001


@pytest.fixture()
def stub_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``PDFRenderer.render_image_with_dpi`` with a tiny stub."""
    from pypdfbox.rendering import pdf_renderer as _pdf_renderer

    def _render(
        self: Any,  # noqa: ARG001 - matches the bound-method signature
        page_index: int,  # noqa: ARG001
        dpi: float = 72.0,  # noqa: ARG001
        image_type: Any = None,  # noqa: ARG001
        destination: Any = None,  # noqa: ARG001
    ) -> Image.Image:
        # 8x8 white RGB — small and cheap to encode to PDF.
        return Image.new("RGB", (8, 8), "white")

    monkeypatch.setattr(
        _pdf_renderer.PDFRenderer, "render_image_with_dpi", _render,
    )


# ----------------------------------------------------------------------
# Top-level ``_print_menu_item_action_performed`` branches
# ----------------------------------------------------------------------


def test_print_no_document_is_silent(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Print menu must early-return when ``_document is None``."""
    called: list[Any] = []
    monkeypatch.setattr(
        debugger, "_send_document_to_printer",
        lambda n: called.append(n),
    )
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.messagebox.showinfo",
        lambda *a, **kw: called.append(("info", a, kw)),
    )
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.messagebox.showerror",
        lambda *a, **kw: called.append(("error", a, kw)),
    )
    assert debugger._document is None  # noqa: SLF001 - precondition
    debugger._print_menu_item_action_performed()  # noqa: SLF001
    assert called == []


def test_print_empty_document_shows_info_and_skips_spooler(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero-page document must not call the spooler hand-off helper."""
    doc = PDDocument()
    try:
        debugger._document = doc  # noqa: SLF001
        send_calls: list[int] = []
        info_calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(
            debugger, "_send_document_to_printer",
            lambda n: send_calls.append(n),
        )
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.messagebox.showinfo",
            lambda *a, **kw: info_calls.append((a, kw)),
        )
        debugger._print_menu_item_action_performed()  # noqa: SLF001
        assert send_calls == []
        assert info_calls and "no pages" in info_calls[0][0][1].lower()
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_print_with_pages_dispatches_to_send_helper(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated document feeds the page-count into the spooler helper."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        send_calls: list[int] = []
        monkeypatch.setattr(
            debugger, "_send_document_to_printer",
            lambda n: send_calls.append(n),
        )
        debugger._print_menu_item_action_performed()  # noqa: SLF001
        assert send_calls == [3]
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_print_propagates_helper_failure_to_messagebox(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``_send_document_to_printer`` raises, surface via ``showerror``."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        error_calls: list[tuple[Any, ...]] = []

        def _boom(n: int) -> None:
            raise RuntimeError(f"boom on {n}")

        monkeypatch.setattr(debugger, "_send_document_to_printer", _boom)
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.messagebox.showerror",
            lambda *a, **kw: error_calls.append((a, kw)),
        )
        debugger._print_menu_item_action_performed()  # noqa: SLF001
        assert error_calls
        assert "boom on 1" in error_calls[0][0][1]
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_print_handles_get_number_of_pages_failure(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken document surfaces an error rather than crashing the UI."""

    class _Boom:
        def get_number_of_pages(self) -> int:
            raise RuntimeError("xref corrupt")

    debugger._document = _Boom()  # type: ignore[assignment]  # noqa: SLF001
    error_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.messagebox.showerror",
        lambda *a, **kw: error_calls.append((a, kw)),
    )
    try:
        debugger._print_menu_item_action_performed()  # noqa: SLF001
        assert error_calls
        assert "xref corrupt" in error_calls[0][0][1]
    finally:
        debugger._document = None  # noqa: SLF001


# ----------------------------------------------------------------------
# ``_send_document_to_printer`` platform-dispatch arms
# ----------------------------------------------------------------------


def test_send_document_writes_temp_pdf_with_all_pages(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    stub_render: None,
) -> None:
    """Rasterised pages land in a temporary multi-page PDF."""
    import subprocess

    doc = PDDocument()
    captured_path: list[str] = []

    class _FakePopen:
        def __init__(self, argv: list[str]) -> None:
            captured_path.append(argv[-1])

    try:
        for _ in range(3):
            doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        # Force the POSIX ``lp`` branch.
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.sys.platform", "linux",
        )

        def _which(cmd: str) -> str | None:
            return "/usr/bin/lp" if cmd == "lp" else None

        monkeypatch.setattr("shutil.which", _which)
        monkeypatch.setattr(subprocess, "Popen", _FakePopen)
        debugger._send_document_to_printer(3)  # noqa: SLF001
        assert captured_path, "spooler was not invoked"
        path = captured_path[0]
        assert path.endswith(".pdf")
        # Confirm the temp PDF is structurally valid + has 3 pages.
        roundtrip = PDDocument.load(path)
        try:
            assert roundtrip.get_number_of_pages() == 3
        finally:
            roundtrip.close()
        # Best-effort cleanup of the temp PDF.
        with contextlib.suppress(OSError):
            os.unlink(path)
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_send_document_windows_uses_startfile(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    stub_render: None,
) -> None:
    """Windows path goes through ``os.startfile(path, 'print')``."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.sys.platform", "win32",
        )
        startfile_calls: list[tuple[str, str]] = []

        def _startfile(path: str, op: str) -> None:
            startfile_calls.append((path, op))

        # ``os.startfile`` is POSIX-absent; install a stub for the test.
        monkeypatch.setattr(os, "startfile", _startfile, raising=False)
        debugger._send_document_to_printer(1)  # noqa: SLF001
        assert startfile_calls
        path, op = startfile_calls[0]
        assert op == "print"
        assert path.endswith(".pdf")
        with contextlib.suppress(OSError):
            os.unlink(path)
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_send_document_fallback_to_opener_when_no_spooler(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    stub_render: None,
) -> None:
    """No ``lp``/``lpr`` on PATH → fall back to ``open`` / ``xdg-open``."""
    import subprocess

    doc = PDDocument()
    popen_calls: list[list[str]] = []

    class _FakePopen:
        def __init__(self, argv: list[str]) -> None:
            popen_calls.append(list(argv))

    try:
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.sys.platform", "darwin",
        )

        def _which(cmd: str) -> str | None:
            # No spoolers; only the GUI opener.
            return "/usr/bin/open" if cmd == "open" else None

        monkeypatch.setattr("shutil.which", _which)
        monkeypatch.setattr(subprocess, "Popen", _FakePopen)
        debugger._send_document_to_printer(1)  # noqa: SLF001
        assert popen_calls and popen_calls[0][0] == "open"
        with contextlib.suppress(OSError):
            os.unlink(popen_calls[0][1])
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_send_document_lp_oserror_falls_through_to_opener(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    stub_render: None,
) -> None:
    """If ``lp`` is on PATH but ``Popen`` raises, fall back to the opener."""
    import subprocess

    doc = PDDocument()
    popen_calls: list[list[str]] = []

    class _FakePopen:
        def __init__(self, argv: list[str]) -> None:
            if argv[0] == "lp":
                raise OSError("spooler down")
            popen_calls.append(list(argv))

    try:
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.sys.platform", "linux",
        )

        def _which(cmd: str) -> str | None:
            return f"/usr/bin/{cmd}" if cmd in {"lp", "xdg-open"} else None

        monkeypatch.setattr("shutil.which", _which)
        monkeypatch.setattr(subprocess, "Popen", _FakePopen)
        debugger._send_document_to_printer(1)  # noqa: SLF001
        assert popen_calls and popen_calls[0][0] == "xdg-open"
        with contextlib.suppress(OSError):
            os.unlink(popen_calls[0][1])
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_send_document_no_spooler_no_opener_surfaces_path(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    stub_render: None,
) -> None:
    """No print command and no opener → info dialog points at the file."""
    doc = PDDocument()
    info_calls: list[tuple[Any, ...]] = []
    try:
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.sys.platform", "linux",
        )
        monkeypatch.setattr("shutil.which", lambda _cmd: None)
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.messagebox.showinfo",
            lambda *a, **kw: info_calls.append((a, kw)),
        )
        debugger._send_document_to_printer(1)  # noqa: SLF001
        assert info_calls
        body = info_calls[0][0][1]
        assert ".pdf" in body
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001
