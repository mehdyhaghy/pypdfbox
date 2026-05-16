"""Hand-written tests for the 15 ``PDFDebugger`` methods added in wave 1312.

These cover smoke + correctness for each newly-ported method on the
``pypdfbox.debugger.pd_debugger.PDFDebugger`` class. They follow the
same Tk-fixture conventions as ``tests/debugger/test_pd_debugger.py``
and honour ``PYPDFBOX_SKIP_TK=1`` for headless CI shards.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.pdmodel import PDDocument, PDPage

# ----------------------------------------------------------------------
# Fixtures (mirrors tests/debugger/test_pd_debugger.py)
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
    """Replace ``ErrorDialog``'s underlying ``showerror`` with a no-op.

    Without this autouse fixture, ``_text_dialog`` and ``_hyperlink_update``
    error branches would spawn a modal ``messagebox.showerror`` that blocks
    the test runner.
    """
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
# 1. get_find_menu_item
# ----------------------------------------------------------------------


def test_get_find_menu_item_returns_menu_and_index(debugger: PDFDebugger) -> None:
    result = debugger.get_find_menu_item()
    assert result is not None
    menu, index = result
    assert isinstance(menu, tk.Menu)
    assert isinstance(index, int)
    assert menu.entrycget(index, "label") == "Find..."


def test_get_find_menu_item_label_matches(debugger: PDFDebugger) -> None:
    menu, index = debugger.get_find_menu_item()  # type: ignore[misc]
    assert "Find" in menu.entrycget(index, "label")


# ----------------------------------------------------------------------
# 2. get_find_next_menu_item
# ----------------------------------------------------------------------


def test_get_find_next_menu_item_returns_menu_and_index(
    debugger: PDFDebugger,
) -> None:
    result = debugger.get_find_next_menu_item()
    assert result is not None
    menu, index = result
    assert menu.entrycget(index, "label") == "Find Next"


def test_get_find_next_menu_item_index_distinct_from_find(
    debugger: PDFDebugger,
) -> None:
    find = debugger.get_find_menu_item()
    next_item = debugger.get_find_next_menu_item()
    assert find is not None and next_item is not None
    assert find[1] != next_item[1]


# ----------------------------------------------------------------------
# 3. get_find_previous_menu_item
# ----------------------------------------------------------------------


def test_get_find_previous_menu_item_returns_menu_and_index(
    debugger: PDFDebugger,
) -> None:
    result = debugger.get_find_previous_menu_item()
    assert result is not None
    menu, index = result
    assert menu.entrycget(index, "label") == "Find Previous"


def test_get_find_previous_menu_item_distinct_from_next(
    debugger: PDFDebugger,
) -> None:
    next_item = debugger.get_find_next_menu_item()
    prev_item = debugger.get_find_previous_menu_item()
    assert next_item is not None and prev_item is not None
    assert next_item[1] != prev_item[1]


# ----------------------------------------------------------------------
# 4. create_find_menu
# ----------------------------------------------------------------------


def test_create_find_menu_builds_three_entries(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    find = debugger.create_find_menu(parent)
    assert isinstance(find, tk.Menu)
    # Three entries: Find / Find Next / Find Previous.
    assert find.index("end") == 2


def test_create_find_menu_resets_internal_state(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    debugger.create_find_menu(parent)
    assert debugger._find_menu is not None  # noqa: SLF001
    assert debugger._find_menu_index is not None  # noqa: SLF001
    assert debugger._find_previous_menu_index is not None  # noqa: SLF001


# ----------------------------------------------------------------------
# 5. is_cid_font
# ----------------------------------------------------------------------


def test_is_cid_font_true_for_cid_type0() -> None:
    dic = COSDictionary()
    dic.set_item(COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType0"))
    assert PDFDebugger.is_cid_font(dic) is True


def test_is_cid_font_false_for_regular_font() -> None:
    dic = COSDictionary()
    dic.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    assert PDFDebugger.is_cid_font(dic) is False
    # And no subtype at all -> False.
    assert PDFDebugger.is_cid_font(COSDictionary()) is False


# ----------------------------------------------------------------------
# 6. get_configuration
# ----------------------------------------------------------------------


def test_get_configuration_returns_class_level_mapping() -> None:
    cfg = PDFDebugger.get_configuration()
    assert isinstance(cfg, dict)
    # Same object on every call (class-level state).
    assert PDFDebugger.get_configuration() is cfg


def test_get_configuration_mutation_visible_across_calls() -> None:
    cfg = PDFDebugger.get_configuration()
    cfg["test.key"] = "test.value"
    try:
        assert PDFDebugger.get_configuration()["test.key"] == "test.value"
    finally:
        cfg.pop("test.key", None)


# ----------------------------------------------------------------------
# 7. _load_configuration
# ----------------------------------------------------------------------


def test_load_configuration_no_file_is_silent(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    # Snapshot + clear so we don't pollute other tests.
    saved = dict(PDFDebugger.configuration)
    PDFDebugger.configuration.clear()
    try:
        PDFDebugger._load_configuration()  # noqa: SLF001
        assert PDFDebugger.configuration == {}
    finally:
        PDFDebugger.configuration.clear()
        PDFDebugger.configuration.update(saved)


def test_load_configuration_parses_key_value_lines(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    (tmp_path / "config.properties").write_text(
        "# comment\nkey=value\nother: thing\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    saved = dict(PDFDebugger.configuration)
    PDFDebugger.configuration.clear()
    try:
        PDFDebugger._load_configuration()  # noqa: SLF001
        assert PDFDebugger.configuration["key"] == "value"
        assert PDFDebugger.configuration["other"] == "thing"
    finally:
        PDFDebugger.configuration.clear()
        PDFDebugger.configuration.update(saved)


# ----------------------------------------------------------------------
# 8. get_page_label
# ----------------------------------------------------------------------


def test_get_page_label_returns_none_when_no_labels(synthetic_pdf: Path) -> None:
    doc = PDDocument.load(str(synthetic_pdf))
    try:
        # Our synthetic PDF has no /PageLabels — should return None.
        assert PDFDebugger.get_page_label(doc, 0) is None
    finally:
        doc.close()


def test_get_page_label_returns_none_for_negative_index(
    synthetic_pdf: Path,
) -> None:
    doc = PDDocument.load(str(synthetic_pdf))
    try:
        assert PDFDebugger.get_page_label(doc, -1) is None
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 9. call
# ----------------------------------------------------------------------


def test_call_returns_zero_with_no_input_file(debugger: PDFDebugger) -> None:
    rc = debugger.call()
    assert rc == 0


def test_call_loads_existing_file(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    rc = debugger.call()
    assert rc == 0
    assert debugger.has_document() is True


# ----------------------------------------------------------------------
# 10. _osx_quit
# ----------------------------------------------------------------------


def test_osx_quit_invokes_exit_handler(
    debugger: PDFDebugger, monkeypatch
) -> None:  # noqa: ANN001
    called: list[bool] = []
    monkeypatch.setattr(
        debugger,
        "_exit_menu_item_action_performed",
        lambda: called.append(True),
    )
    debugger._osx_quit()  # noqa: SLF001
    assert called == [True]


def test_osx_quit_does_not_raise(debugger: PDFDebugger, monkeypatch) -> None:  # noqa: ANN001
    # Suppress the destroy() inside the exit handler so the fixture
    # cleanup doesn't trip over a destroyed widget.
    monkeypatch.setattr(debugger, "perform_application_exit", lambda: None)
    debugger._osx_quit()  # noqa: SLF001  # should not raise


# ----------------------------------------------------------------------
# 11. perform_application_exit
# ----------------------------------------------------------------------


def test_perform_application_exit_destroys_toplevel(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    # Hijack the toplevel destroyer so we can observe + avoid killing
    # the shared session root.
    destroyed: list[bool] = []
    debugger._toplevel = type(  # noqa: SLF001
        "Dummy", (), {"destroy": lambda self: destroyed.append(True)}
    )()
    debugger.perform_application_exit()
    assert destroyed == [True]


def test_perform_application_exit_swallows_errors(debugger: PDFDebugger) -> None:
    class BadTopLevel:
        def destroy(self) -> None:
            raise RuntimeError("boom")

    debugger._toplevel = BadTopLevel()  # type: ignore[assignment]  # noqa: SLF001
    debugger.perform_application_exit()  # should not raise


# ----------------------------------------------------------------------
# 12. _read_pdf_file_from_path
# ----------------------------------------------------------------------


def test_read_pdf_file_from_path_accepts_path(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger._read_pdf_file_from_path(synthetic_pdf)  # noqa: SLF001
    assert debugger.has_document() is True
    assert debugger._current_file_path == str(synthetic_pdf)  # noqa: SLF001


def test_read_pdf_file_from_path_accepts_string(
    debugger: PDFDebugger, synthetic_pdf: Path
) -> None:
    debugger._read_pdf_file_from_path(str(synthetic_pdf))  # noqa: SLF001
    assert debugger.has_document() is True


# ----------------------------------------------------------------------
# 13. _text_dialog
# ----------------------------------------------------------------------


def test_text_dialog_opens_for_local_file(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    resource = tmp_path / "about.html"
    resource.write_text("<html><body>About</body></html>", encoding="utf-8")
    debugger._text_dialog("About", str(resource))  # noqa: SLF001
    # The dialog is a Toplevel of our master — at least one extra
    # Toplevel should now exist.
    toplevels = [
        w for w in debugger._toplevel.winfo_children()  # noqa: SLF001
        if isinstance(w, tk.Toplevel)
    ]
    assert len(toplevels) >= 1
    for top in toplevels:
        with contextlib.suppress(tk.TclError):
            top.destroy()


def test_text_dialog_handles_missing_resource(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    missing = tmp_path / "nope.html"
    # Should not raise — internally swallows OSError via ErrorDialog.
    # ErrorDialog itself spawns a Toplevel which we'll tear down.
    debugger._text_dialog("Missing", str(missing))  # noqa: SLF001
    for w in list(debugger._toplevel.winfo_children()):  # noqa: SLF001
        if isinstance(w, tk.Toplevel):
            with contextlib.suppress(tk.TclError):
                w.destroy()


# ----------------------------------------------------------------------
# 14. _hyperlink_update
# ----------------------------------------------------------------------


def test_hyperlink_update_handles_unreachable_url(
    debugger: PDFDebugger,
) -> None:
    # Pointing at a nonexistent local file URL exercises the OSError
    # branch without requiring network access.
    debugger._hyperlink_update("file:///nonexistent-pypdfbox-test")  # noqa: SLF001
    for w in list(debugger._toplevel.winfo_children()):  # noqa: SLF001
        if isinstance(w, tk.Toplevel):
            with contextlib.suppress(tk.TclError):
                w.destroy()


def test_hyperlink_update_renders_local_file(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    payload = tmp_path / "page.txt"
    payload.write_text("hello world", encoding="utf-8")
    debugger._hyperlink_update(payload.as_uri())  # noqa: SLF001
    # Should now have at least one Toplevel containing a Text widget.
    toplevels = [
        w for w in debugger._toplevel.winfo_children()  # noqa: SLF001
        if isinstance(w, tk.Toplevel)
    ]
    assert len(toplevels) >= 1
    for top in toplevels:
        with contextlib.suppress(tk.TclError):
            top.destroy()


# ----------------------------------------------------------------------
# 15. convert_to_string
# ----------------------------------------------------------------------


def test_convert_to_string_handles_cosname() -> None:
    assert PDFDebugger.convert_to_string(COSName.get_pdf_name("Foo")) == "Foo"


def test_convert_to_string_handles_array_and_dict() -> None:
    assert PDFDebugger.convert_to_string(COSArray()) == "COSArray"
    assert PDFDebugger.convert_to_string(COSDictionary()) == "COSDictionary"
    # ``None`` input falls through to the bottom of the type ladder.
    assert PDFDebugger.convert_to_string(object()) is None
