"""Hand-written tests for the 15 ``PDFDebugger`` methods added in wave 1313.

Covers state accessors, file-handling lifecycle wrappers, tree-event
dispatchers, window-state updaters, and drag-drop stubs. Honours
``PYPDFBOX_SKIP_TK=1`` for headless CI shards.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.pdmodel import PDDocument, PDPage

# ----------------------------------------------------------------------
# Fixtures (mirror tests/debugger/test_pd_debugger_methods.py)
# ----------------------------------------------------------------------


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    """Per-test Tk root."""
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


@pytest.fixture(autouse=True)
def _stub_error_dialog() -> Iterator[None]:
    """Replace ``ErrorDialog``'s underlying ``showerror`` with a no-op."""
    from pypdfbox.debugger.ui import error_dialog as _ed

    _ed.set_show_error_impl(lambda title, message: None)
    try:
        yield
    finally:
        _ed.set_show_error_impl(None)


@pytest.fixture()
def synthetic_pdf(tmp_path: Path) -> Path:
    """Write a minimal one-page PDF to disk for round-trip tests."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        path = tmp_path / "sample.pdf"
        doc.save(str(path))
    finally:
        doc.close()
    return path


@pytest.fixture()
def debugger(tk_root: tk.Tk) -> Iterator[PDFDebugger]:
    """A freshly-built debugger with no document loaded."""
    instance = PDFDebugger(tk_root)
    try:
        yield instance
    finally:
        with contextlib.suppress(tk.TclError):
            instance._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# 1. get_current_file_path
# ----------------------------------------------------------------------


def test_get_current_file_path_none_initially(debugger: PDFDebugger) -> None:
    assert debugger.get_current_file_path() is None


def test_get_current_file_path_set_after_load(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    assert debugger.get_current_file_path() == str(synthetic_pdf)


# ----------------------------------------------------------------------
# 2. get_pdf_file
# ----------------------------------------------------------------------


def test_get_pdf_file_none_initially(debugger: PDFDebugger) -> None:
    assert debugger.get_pdf_file() is None


def test_get_pdf_file_returns_path(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    p = debugger.get_pdf_file()
    assert isinstance(p, Path)
    assert p == Path(str(synthetic_pdf))


def test_get_pdf_file_none_for_url(debugger: PDFDebugger) -> None:
    debugger._current_file_path = "https://example.com/foo.pdf"  # noqa: SLF001
    assert debugger.get_pdf_file() is None


# ----------------------------------------------------------------------
# 3. read_pdf_file
# ----------------------------------------------------------------------


def test_read_pdf_file_loads_document(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    assert debugger.has_document() is True


def test_read_pdf_file_accepts_string(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(str(synthetic_pdf))
    assert debugger.get_current_file_path() == str(synthetic_pdf)


# ----------------------------------------------------------------------
# 4. read_pdf_url
# ----------------------------------------------------------------------


def test_read_pdf_url_rejects_bare_path(debugger: PDFDebugger) -> None:
    with pytest.raises(ValueError, match="invalid URL"):
        debugger.read_pdf_url("not-a-url")


def test_read_pdf_url_delegates_to_private(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[str, str | bytes]] = []

    def _fake(url: str, password: str | bytes = "") -> None:
        captured.append((url, password))

    monkeypatch.setattr(debugger, "_read_pdf_url", _fake)
    debugger.read_pdf_url("https://example.com/x.pdf", "")
    assert captured == [("https://example.com/x.pdf", "")]


# ----------------------------------------------------------------------
# 5. parse_document
# ----------------------------------------------------------------------


def test_parse_document_loads_from_path(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    doc = debugger.parse_document(synthetic_pdf)
    try:
        assert isinstance(doc, PDDocument)
        # parse_document must not mutate the debugger's own state.
        assert debugger.has_document() is False
    finally:
        doc.close()


def test_parse_document_loads_from_bytes(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    data = synthetic_pdf.read_bytes()
    doc = debugger.parse_document(data)
    try:
        assert isinstance(doc, PDDocument)
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 6. flush_to_disk
# ----------------------------------------------------------------------


def test_flush_to_disk_writes_pdf(
    debugger: PDFDebugger, synthetic_pdf: Path, tmp_path: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    target = tmp_path / "out.pdf"
    debugger.flush_to_disk(target)
    assert target.exists()
    assert target.stat().st_size > 0
    # File begins with PDF magic.
    assert target.read_bytes().startswith(b"%PDF-")


def test_flush_to_disk_noop_without_document(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    target = tmp_path / "nope.pdf"
    debugger.flush_to_disk(target)
    assert not target.exists()


# ----------------------------------------------------------------------
# 7. value_changed
# ----------------------------------------------------------------------


def test_value_changed_with_empty_selection_is_silent(
    debugger: PDFDebugger,
) -> None:
    # No document loaded => no selection => no exception.
    debugger.value_changed(None)


def test_value_changed_after_load_dispatches(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    # init_tree auto-selects the first child; value_changed should
    # cleanly re-dispatch without raising.
    debugger.value_changed(None)


# ----------------------------------------------------------------------
# 8. process_tree_selection
# ----------------------------------------------------------------------


def test_process_tree_selection_unknown_iid_is_silent(
    debugger: PDFDebugger,
) -> None:
    debugger.process_tree_selection("does-not-exist")  # should not raise


def test_process_tree_selection_with_real_iid(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    # Root is the first child of "".
    children = debugger.get_tree().get_children("")
    assert children
    debugger.process_tree_selection(children[0])
    # After dispatch, the tree must report something selected.
    assert debugger.get_tree().selection()


# ----------------------------------------------------------------------
# 9. update_title
# ----------------------------------------------------------------------


def test_update_title_default_no_document(debugger: PDFDebugger) -> None:
    debugger.update_title()
    assert debugger._toplevel.title() == PDFDebugger.TITLE  # noqa: SLF001


def test_update_title_explicit_string(debugger: PDFDebugger) -> None:
    debugger.update_title("Custom")
    assert debugger._toplevel.title() == "Custom"  # noqa: SLF001


# ----------------------------------------------------------------------
# 10. update_status
# ----------------------------------------------------------------------


def test_update_status_writes_label(debugger: PDFDebugger) -> None:
    debugger.update_status("hello")
    label = debugger.get_status_bar().get_status_label()
    assert label is not None
    assert label.cget("text") == "hello"


def test_update_status_default_clears(debugger: PDFDebugger) -> None:
    debugger.update_status("first")
    debugger.update_status()
    label = debugger.get_status_bar().get_status_label()
    assert label is not None
    assert label.cget("text") == ""


# ----------------------------------------------------------------------
# 11. update_tree_pane
# ----------------------------------------------------------------------


def test_update_tree_pane_noop_without_document(debugger: PDFDebugger) -> None:
    debugger.update_tree_pane()  # should not raise
    assert debugger.get_tree().get_children("") == ()


def test_update_tree_pane_repopulates(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    children_before = debugger.get_tree().get_children("")
    debugger.update_tree_pane()
    children_after = debugger.get_tree().get_children("")
    # Both runs produce exactly one root row.
    assert len(children_before) == 1
    assert len(children_after) == 1


# ----------------------------------------------------------------------
# 12. can_import
# ----------------------------------------------------------------------


def test_can_import_returns_false(debugger: PDFDebugger) -> None:
    assert debugger.can_import() is False


def test_can_import_ignores_payload(debugger: PDFDebugger) -> None:
    # Even with a "transfer support"-shaped argument, we return False.
    assert debugger.can_import(object()) is False


# ----------------------------------------------------------------------
# 13. import_data
# ----------------------------------------------------------------------


def test_import_data_returns_false(debugger: PDFDebugger) -> None:
    assert debugger.import_data() is False


def test_import_data_ignores_payload(debugger: PDFDebugger) -> None:
    assert debugger.import_data(["/tmp/whatever.pdf"]) is False


# ----------------------------------------------------------------------
# 14. parse_document with password (failure path)
# ----------------------------------------------------------------------


def test_parse_document_invalid_url_raises(debugger: PDFDebugger) -> None:
    # file:// scheme over a non-existent path triggers OSError on open.
    with pytest.raises(OSError):
        debugger.parse_document("file:///does/not/exist.pdf")


# ----------------------------------------------------------------------
# 15. read_pdf_file + update_title interaction
# ----------------------------------------------------------------------


def test_read_pdf_file_updates_title(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    title = debugger._toplevel.title()  # noqa: SLF001
    # On macOS upstream sets bare filename; on other platforms full prefix.
    assert "sample.pdf" in title or str(synthetic_pdf) in title
