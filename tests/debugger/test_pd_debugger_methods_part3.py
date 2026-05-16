"""Hand-written tests for the ``PDFDebugger`` methods added in wave 1313.

Covers window / mac / action handlers, plus the public spellings of
``init_components`` / ``init_global_event_handlers`` / ``load_configuration``
/ ``text_dialog`` / ``hyperlink_update`` / ``replace_right_component`` /
``get_node_key`` / ``get_underneath_object`` / ``action_performed`` /
``open`` introduced this wave. Follows the Tk-fixture conventions used by
``tests/debugger/test_pd_debugger_methods.py`` and honours
``PYPDFBOX_SKIP_TK=1`` for headless CI shards.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.pdmodel import PDDocument, PDPage

# ----------------------------------------------------------------------
# Fixtures
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
    """Drop every cached menu singleton so each test sees a fresh tree."""
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
# 1. window_opened
# ----------------------------------------------------------------------


def test_window_opened_focuses_tree(debugger: PDFDebugger) -> None:
    # Should not raise — Tk's ``focus_set`` is benign even when the tree
    # is not yet mapped.
    debugger.window_opened()


def test_window_opened_accepts_event_argument(debugger: PDFDebugger) -> None:
    # Swing's hook signature passes a WindowEvent. Tk callers pass a
    # ``tk.Event``; either should be accepted without raising.
    debugger.window_opened(None)
    debugger.window_opened("anything")


# ----------------------------------------------------------------------
# 2. window_closing
# ----------------------------------------------------------------------


def test_window_closing_destroys_toplevel(debugger: PDFDebugger) -> None:
    # ``window_closing`` -> ``_exit_menu_item_action_performed`` ->
    # ``perform_application_exit`` -> ``self._toplevel.destroy()``.
    debugger.window_closing()
    with pytest.raises(tk.TclError):
        # Once destroyed, any Tk method should fail.
        debugger._toplevel.title()  # noqa: SLF001


def test_window_closing_accepts_event_argument(tk_root: tk.Tk) -> None:
    instance = PDFDebugger(tk_root)
    instance.window_closing(None)


# ----------------------------------------------------------------------
# 3. init_components
# ----------------------------------------------------------------------


def test_init_components_rebuilds_widget_tree(debugger: PDFDebugger) -> None:
    # Calling again is allowed — destroys + rebuilds the body.
    debugger.init_components()
    # After rebuild, the tree should still exist.
    assert debugger._tree is not None  # noqa: SLF001


def test_init_components_does_not_raise_without_document(
    debugger: PDFDebugger,
) -> None:
    debugger.init_components()  # should be a no-op-safe re-layout


# ----------------------------------------------------------------------
# 4. init_global_event_handlers
# ----------------------------------------------------------------------


def test_init_global_event_handlers_no_op_on_non_mac(
    debugger: PDFDebugger,
) -> None:
    # On Linux / Windows the method returns immediately. We just verify
    # it doesn't raise.
    debugger.init_global_event_handlers()


# ----------------------------------------------------------------------
# 5. load_configuration (public spelling)
# ----------------------------------------------------------------------


def test_load_configuration_no_file_is_silent(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    saved = dict(PDFDebugger.configuration)
    PDFDebugger.configuration.clear()
    try:
        PDFDebugger.load_configuration()
        assert PDFDebugger.configuration == {}
    finally:
        PDFDebugger.configuration.clear()
        PDFDebugger.configuration.update(saved)


def test_load_configuration_parses_value(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    (tmp_path / "config.properties").write_text("a=b\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    saved = dict(PDFDebugger.configuration)
    PDFDebugger.configuration.clear()
    try:
        PDFDebugger.load_configuration()
        assert PDFDebugger.configuration["a"] == "b"
    finally:
        PDFDebugger.configuration.clear()
        PDFDebugger.configuration.update(saved)


# ----------------------------------------------------------------------
# 6. osx_open_files / osx_quit (public spellings)
# ----------------------------------------------------------------------


def test_osx_open_files_loads_synthetic_pdf(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.osx_open_files(str(synthetic_pdf))
    assert debugger.has_document() is True


def test_osx_open_files_swallows_bad_path(debugger: PDFDebugger) -> None:
    # Should not raise even when the file does not exist; the upstream
    # method routes failures through ErrorDialog (stubbed in the fixture).
    debugger.osx_open_files("/nonexistent/path/that/should/not/exist.pdf")


def test_osx_quit_destroys_toplevel(debugger: PDFDebugger) -> None:
    debugger.osx_quit()
    with pytest.raises(tk.TclError):
        debugger._toplevel.title()  # noqa: SLF001


# ----------------------------------------------------------------------
# 7. text_dialog (public spelling)
# ----------------------------------------------------------------------


def test_text_dialog_opens_local_file(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    resource = tmp_path / "about.txt"
    resource.write_text("Hello dialog", encoding="utf-8")
    # Should not raise; creates a Toplevel that's transient on the master.
    debugger.text_dialog("About", str(resource))


def test_text_dialog_missing_file_swallows_error(debugger: PDFDebugger) -> None:
    # Missing file routes through ErrorDialog (stubbed).
    debugger.text_dialog("About", "/nonexistent/dialog/path.html")


# ----------------------------------------------------------------------
# 8. hyperlink_update (public spelling)
# ----------------------------------------------------------------------


def test_hyperlink_update_invalid_url_does_not_raise(
    debugger: PDFDebugger,
) -> None:
    # Routes ``OSError`` through ErrorDialog (stubbed); should not raise.
    debugger.hyperlink_update("http://invalid-host-that-does-not-resolve.test/")


# ----------------------------------------------------------------------
# 9. replace_right_component (public spelling)
# ----------------------------------------------------------------------


def test_replace_right_component_mounts_widget(debugger: PDFDebugger) -> None:
    label = tk.Label(debugger._right_frame, text="hi")  # noqa: SLF001
    debugger.replace_right_component(label)
    assert debugger.get_right_widget() is label


def test_replace_right_component_clears_when_none(debugger: PDFDebugger) -> None:
    label = tk.Label(debugger._right_frame, text="hi")  # noqa: SLF001
    debugger.replace_right_component(label)
    debugger.replace_right_component(None)
    assert debugger.get_right_widget() is None


# ----------------------------------------------------------------------
# 10. get_node_key (public spelling)
# ----------------------------------------------------------------------


def test_get_node_key_returns_key_for_map_entry() -> None:
    entry = MapEntry()
    entry.set_key(COSName.TYPE)
    entry.set_value(COSName.get_pdf_name("Page"))
    key = PDFDebugger.get_node_key(entry)
    assert key is COSName.TYPE


def test_get_node_key_returns_none_for_non_map_entry() -> None:
    assert PDFDebugger.get_node_key("not a map entry") is None


# ----------------------------------------------------------------------
# 11. get_underneath_object (public spelling)
# ----------------------------------------------------------------------


def test_get_underneath_object_unwraps_map_entry() -> None:
    value = COSDictionary()
    entry = MapEntry()
    entry.set_key(COSName.TYPE)
    entry.set_value(value)
    assert PDFDebugger.get_underneath_object(entry) is value


def test_get_underneath_object_unwraps_array_entry() -> None:
    value = COSName.get_pdf_name("DeviceRGB")
    entry = ArrayEntry()
    entry.set_index(0)
    entry.set_value(value)
    assert PDFDebugger.get_underneath_object(entry) is value


def test_get_underneath_object_passthrough_for_plain_objects() -> None:
    obj = COSDictionary()
    assert PDFDebugger.get_underneath_object(obj) is obj


# ----------------------------------------------------------------------
# 12. action_performed (recent-file action handler)
# ----------------------------------------------------------------------


def test_action_performed_loads_existing_file(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.action_performed(str(synthetic_pdf))
    assert debugger.has_document() is True


def test_action_performed_swallows_missing_path(debugger: PDFDebugger) -> None:
    # OSError routed through stubbed ErrorDialog; should not raise.
    debugger.action_performed("/nonexistent/recent.pdf")


# ----------------------------------------------------------------------
# 13. open (PDFDebugger-level)
# ----------------------------------------------------------------------


def test_open_returns_none_when_no_path_set(debugger: PDFDebugger) -> None:
    assert debugger.open() is None


def test_open_returns_loaded_document(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    doc = debugger.open()
    assert doc is not None
    assert debugger.has_document() is True


def test_open_returns_existing_document_without_reloading(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger.open_document(synthetic_pdf)
    first = debugger.get_document()
    second = debugger.open()
    assert second is first
