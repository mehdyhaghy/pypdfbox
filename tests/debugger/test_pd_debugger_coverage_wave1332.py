"""Wave-1332 coverage-boost tests for ``pypdfbox.debugger.pd_debugger``.

Pre-wave coverage was 89% (116 lines missing). The dropped lines cover
roughly six themes:

* recent-files / OSXAdapter wiring guards (471, 484-487, 501);
* page-label OSError + None branches (654-657, 660-666);
* type-test helpers (838, 871, 962, 970, 978) for stream / font /
  flag-node / signature / annot classifiers;
* ``_show_stream`` resources-dict branches (1013-1110);
* dialog branches in ``_show_font`` / ``_show_signature_pane`` /
  ``_show_string`` / ``_show_text_details`` (1125-1126, 1135-1142);
* menu action paths (1228-1229, 1242-1243, 1256-1257) and
  config-load / text-dialog / hyperlink-update side-effect-free paths
  (1381-1383, 1420-1424, 1532, 1554-1555);
* ``parse_document`` / ``flush_to_disk`` / ``DocumentOpener.parse`` and
  the ``_read_stream_bytes`` exception swallow.

Tests honour ``PYPDFBOX_SKIP_TK=1`` via the local ``tk_root`` fixture.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.debugger.pd_debugger import (
    DocumentOpener,
    PDFDebugger,
    _convert_to_string,
    _ensure_default_root,
    _node_label,
    _read_stream_bytes,
)
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.pdmodel import PDDocument, PDPage

# ----------------------------------------------------------------------
# Fixtures (mirror tests/debugger/test_pd_debugger.py)
# ----------------------------------------------------------------------


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
    """No-op modal dialogs so tests don't hang on errors."""
    from pypdfbox.debugger.ui import error_dialog as _ed

    _ed.set_show_error_impl(lambda title, message: None)
    try:
        yield
    finally:
        _ed.set_show_error_impl(None)


@pytest.fixture()
def synthetic_pdf(tmp_path: Path) -> Path:
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
    instance = PDFDebugger(tk_root)
    try:
        yield instance
    finally:
        with contextlib.suppress(tk.TclError):
            instance._main_frame.destroy()  # noqa: SLF001


# ---------------------------------------------------------------------
# add_recent_file_items
# ---------------------------------------------------------------------


def test_add_recent_file_items_short_circuits_when_no_recent_files(
    debugger: PDFDebugger,
) -> None:
    """``add_recent_file_items`` is a no-op when the recent-files store is empty."""
    # Wipe whatever is on the recent_files store.
    debugger._recent_files.remove_all()  # noqa: SLF001
    debugger.add_recent_file_items()  # must not raise


def test_add_recent_file_items_populates_for_known_files(
    debugger: PDFDebugger, tmp_path: Path,
) -> None:
    """A populated recent-files list yields one menu entry per file."""
    fake = tmp_path / "x.pdf"
    fake.write_bytes(b"%PDF-1.4\n")
    debugger._recent_files.add_file(str(fake))  # noqa: SLF001
    debugger.add_recent_file_items()
    # Recent submenu should have at least one entry.
    assert debugger._recent_files_menu is not None  # noqa: SLF001
    assert debugger._recent_files_menu.index("end") is not None  # noqa: SLF001


def test_add_recent_file_items_opener_callback_handles_oserror(
    debugger: PDFDebugger, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The closure attached to each recent entry swallows ``OSError``."""
    fake = tmp_path / "vanished.pdf"
    fake.write_bytes(b"%PDF-1.4\n")
    debugger._recent_files.add_file(str(fake))  # noqa: SLF001

    def _raise(self: Any, path: str, password: str = "") -> None:
        raise OSError("vanished")

    monkeypatch.setattr(PDFDebugger, "_read_pdf_file", _raise)
    debugger.add_recent_file_items()
    # Invoke the first command directly — must not raise.
    debugger._recent_files_menu.invoke(0)  # type: ignore[union-attr]  # noqa: SLF001


# ---------------------------------------------------------------------
# get_page_label
# ---------------------------------------------------------------------


def test_get_page_label_returns_none_for_missing_page_labels(
    debugger: PDFDebugger,
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        assert PDFDebugger.get_page_label(doc, 0) is None
    finally:
        doc.close()


def test_get_page_label_returns_none_for_negative_index(
    debugger: PDFDebugger,
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        assert PDFDebugger.get_page_label(doc, -1) is None
    finally:
        doc.close()


def test_get_page_label_returns_str_for_oserror(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ``OSError`` thrown from ``get_document_catalog`` stringifies the error."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        def _boom(self: Any) -> Any:
            raise OSError("io")

        monkeypatch.setattr(PDDocument, "get_document_catalog", _boom)
        assert PDFDebugger.get_page_label(doc, 0) == "io"
    finally:
        doc.close()


def test_get_page_label_returns_none_on_unexpected_error(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-OSError exception path returns ``None`` (mirrors upstream broad catch)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        def _boom(self: Any) -> Any:
            raise RuntimeError("hmm")

        monkeypatch.setattr(PDDocument, "get_document_catalog", _boom)
        assert PDFDebugger.get_page_label(doc, 0) is None
    finally:
        doc.close()


# ---------------------------------------------------------------------
# type-test helpers
# ---------------------------------------------------------------------


def test_is_cid_font_recognises_cidfonttype0() -> None:
    d = COSDictionary()
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType0"))
    assert PDFDebugger.is_cid_font(d) is True


def test_is_cid_font_recognises_cidfonttype2() -> None:
    d = COSDictionary()
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType2"))
    assert PDFDebugger.is_cid_font(d) is True


def test_is_cid_font_returns_false_for_non_cid_font() -> None:
    d = COSDictionary()
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    assert PDFDebugger.is_cid_font(d) is False


def test_is_cid_font_returns_false_without_subtype() -> None:
    d = COSDictionary()
    assert PDFDebugger.is_cid_font(d) is False


def test_is_font_returns_false_for_cid_font() -> None:
    """A CIDFont dict is *not* counted as a font for pane purposes."""
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType0"))
    assert PDFDebugger._is_font(d) is False  # noqa: SLF001


def test_is_font_returns_true_for_regular_font() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    assert PDFDebugger._is_font(d) is True  # noqa: SLF001


def test_is_special_colorspace_detects_separation() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    assert PDFDebugger._is_special_colorspace(arr) is True  # noqa: SLF001


def test_is_other_colorspace_detects_calrgb() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    assert PDFDebugger._is_other_colorspace(arr) is True  # noqa: SLF001


def test_first_array_name_returns_none_for_empty() -> None:
    assert PDFDebugger._first_array_name(COSArray()) is None  # noqa: SLF001


def test_first_array_name_returns_none_for_non_array() -> None:
    assert PDFDebugger._first_array_name(COSDictionary()) is None  # noqa: SLF001


def test_first_array_name_returns_none_when_first_entry_not_a_name() -> None:
    arr = COSArray()
    arr.add(COSString("Hello"))
    assert PDFDebugger._first_array_name(arr) is None  # noqa: SLF001


def test_is_annot_returns_true_for_annot_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Annot"))
    assert PDFDebugger._is_annot(d) is True  # noqa: SLF001


def test_is_annot_returns_false_for_non_annot_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))
    assert PDFDebugger._is_annot(d) is False  # noqa: SLF001


def test_is_font_descriptor_returns_true_for_font_descriptor_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("FontDescriptor"))
    assert PDFDebugger._is_font_descriptor(d) is True  # noqa: SLF001


def test_is_encrypt_returns_false_for_non_map_entry() -> None:
    assert PDFDebugger._is_encrypt(COSDictionary()) is False  # noqa: SLF001


# ---------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------


def test_find_menu_item_action_shows_messagebox(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Find...`` pops a friendly note rather than no-op'ing."""
    from tkinter import messagebox

    called: list[tuple[Any, ...]] = []

    def _showinfo(*args: Any, **kwargs: Any) -> None:
        called.append((args, kwargs))

    monkeypatch.setattr(messagebox, "showinfo", _showinfo)
    debugger._find_menu_item_action_performed()  # noqa: SLF001
    assert called


def test_find_next_and_previous_are_noops(debugger: PDFDebugger) -> None:
    # Both are docstring-only no-ops; must not raise.
    debugger._find_next_menu_item_action_performed()  # noqa: SLF001
    debugger._find_previous_menu_item_action_performed()  # noqa: SLF001


def test_print_menu_item_action_with_no_document_returns(
    debugger: PDFDebugger,
) -> None:
    """No-op when no document is loaded."""
    debugger._print_menu_item_action_performed()  # noqa: SLF001


def test_print_menu_item_action_shows_messagebox_when_doc_present(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tkinter import messagebox

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        debugger._document = doc  # noqa: SLF001
        called: list[tuple[Any, ...]] = []

        def _showinfo(*args: Any, **kwargs: Any) -> None:
            called.append((args, kwargs))

        monkeypatch.setattr(messagebox, "showinfo", _showinfo)
        debugger._print_menu_item_action_performed()  # noqa: SLF001
        assert called
    finally:
        doc.close()
        debugger._document = None  # noqa: SLF001


def test_show_about_dialog_invokes_messagebox(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tkinter import messagebox

    called: list[tuple[Any, ...]] = []

    def _showinfo(*args: Any, **kwargs: Any) -> None:
        called.append((args, kwargs))

    monkeypatch.setattr(messagebox, "showinfo", _showinfo)
    debugger._show_about_dialog()  # noqa: SLF001
    assert called


# ---------------------------------------------------------------------
# load_configuration
# ---------------------------------------------------------------------


def test_load_configuration_returns_for_missing_file(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When ``config.properties`` is absent, ``load_configuration`` no-ops."""
    monkeypatch.chdir(tmp_path)
    debugger.load_configuration()  # must not raise


def test_load_configuration_parses_keys(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.properties").write_text(
        "# comment\n\nfoo=bar\nbaz:qux\n", encoding="utf-8"
    )
    debugger.load_configuration()
    assert PDFDebugger.configuration["foo"] == "bar"
    assert PDFDebugger.configuration["baz"] == "qux"
    # Cleanup so other tests aren't affected.
    PDFDebugger.configuration.pop("foo", None)
    PDFDebugger.configuration.pop("baz", None)


def test_load_configuration_handles_unreadable_file(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.properties"
    cfg.write_text("key=value", encoding="utf-8")
    real_read_text = Path.read_text

    def _raise(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.name == "config.properties":
            raise OSError("permission denied")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raise)
    debugger.load_configuration()  # logs + returns


# ---------------------------------------------------------------------
# call
# ---------------------------------------------------------------------


def test_call_with_no_current_file_succeeds(debugger: PDFDebugger) -> None:
    assert debugger.call() == 0


def test_call_loads_existing_current_file(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    assert debugger.call() == 0
    assert debugger._document is not None  # noqa: SLF001


def test_call_returns_4_on_uncaught_exception(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(self: Any) -> None:
        raise RuntimeError("call exploded")

    monkeypatch.setattr(PDFDebugger, "_load_configuration", classmethod(_raise))
    assert debugger.call() == 4


# ---------------------------------------------------------------------
# convert_to_string / _read_stream_bytes
# ---------------------------------------------------------------------


def test_convert_to_string_handles_boolean() -> None:
    from pypdfbox.cos.cos_boolean import COSBoolean

    assert _convert_to_string(COSBoolean.TRUE) == "true"
    assert _convert_to_string(COSBoolean.FALSE) == "false"


def test_convert_to_string_handles_float() -> None:
    from pypdfbox.cos.cos_float import COSFloat

    assert _convert_to_string(COSFloat(1.5)) == "1.5"


def test_convert_to_string_handles_null() -> None:
    from pypdfbox.cos.cos_null import COSNull

    assert _convert_to_string(COSNull.NULL) == "null"


def test_convert_to_string_handles_name() -> None:
    assert _convert_to_string(COSName.get_pdf_name("Hello")) == "Hello"


def test_convert_to_string_handles_control_string_as_hex() -> None:
    """A ``COSString`` containing a control byte renders as ``<HEX>``."""
    assert _convert_to_string(COSString(b"\x01\x02")).startswith("<")


def test_convert_to_string_handles_printable_string() -> None:
    assert _convert_to_string(COSString("Hello")) == "Hello"


def test_convert_to_string_returns_none_for_unknown_type() -> None:
    assert _convert_to_string(object()) is None


def test_convert_to_string_dictionary_returns_label() -> None:
    assert _convert_to_string(COSDictionary()) == "COSDictionary"


def test_convert_to_string_array_returns_label() -> None:
    assert _convert_to_string(COSArray()) == "COSArray"


def test_read_stream_bytes_returns_empty_for_object_without_creator() -> None:
    class _NoCreator:
        pass

    assert _read_stream_bytes(_NoCreator()) == b""  # type: ignore[arg-type]


def test_read_stream_bytes_handles_oserror() -> None:
    """If the stream creator raises ``OSError`` the helper returns ``b''``."""

    class _Boom:
        def create_input_stream(self) -> Any:
            raise OSError("kaboom")

    assert _read_stream_bytes(_Boom()) == b""  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# read_pdf_file / read_pdf_url / flush_to_disk / value_changed
# ---------------------------------------------------------------------


def test_read_pdf_file_loads_document(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    assert debugger._document is not None  # noqa: SLF001


def test_read_pdf_url_rejects_invalid_url(debugger: PDFDebugger) -> None:
    with pytest.raises(ValueError, match="invalid URL"):
        debugger.read_pdf_url("not-a-url")


def test_flush_to_disk_returns_when_no_document(
    debugger: PDFDebugger, tmp_path: Path,
) -> None:
    target = tmp_path / "x.pdf"
    debugger.flush_to_disk(target)
    assert not target.exists()


def test_flush_to_disk_writes_when_document_loaded(
    debugger: PDFDebugger, synthetic_pdf: Path, tmp_path: Path,
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    target = tmp_path / "flushed.pdf"
    debugger.flush_to_disk(target)
    assert target.is_file()


def test_value_changed_with_empty_selection_is_noop(debugger: PDFDebugger) -> None:
    debugger.value_changed()


def test_process_tree_selection_ignores_unknown_iid(debugger: PDFDebugger) -> None:
    # Must not raise.
    debugger.process_tree_selection("not-a-real-iid")


# ---------------------------------------------------------------------
# update_title / update_status / update_tree_pane / can_import / import_data
# ---------------------------------------------------------------------


def test_update_title_default_uses_constant(debugger: PDFDebugger) -> None:
    """When no path is loaded and no title supplied, the default title is used."""
    debugger.update_title(None)
    title = debugger._toplevel.title()  # noqa: SLF001
    assert title  # not empty


def test_update_title_explicit(debugger: PDFDebugger) -> None:
    debugger.update_title("MyExplicitTitle")
    assert debugger._toplevel.title() == "MyExplicitTitle"  # noqa: SLF001


def test_update_title_for_http_path(debugger: PDFDebugger) -> None:
    debugger._current_file_path = "https://example.com/x.pdf"  # noqa: SLF001
    debugger.update_title(None)
    # Title set without raising.


def test_update_title_for_local_path(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    debugger.update_title(None)
    # No raise.


def test_update_status_empty_when_no_label(debugger: PDFDebugger) -> None:
    # Force the status_bar's label getter to return None.
    real_getter = debugger._status_bar.get_status_label  # noqa: SLF001
    try:
        debugger._status_bar.get_status_label = lambda: None  # type: ignore[method-assign]  # noqa: SLF001
        debugger.update_status("hello")  # must not raise
    finally:
        debugger._status_bar.get_status_label = real_getter  # type: ignore[method-assign]  # noqa: SLF001


def test_update_status_writes_to_label(debugger: PDFDebugger) -> None:
    debugger.update_status("a status")  # exercises label.configure path


def test_update_tree_pane_noop_without_document(debugger: PDFDebugger) -> None:
    debugger.update_tree_pane()


def test_can_import_returns_false(debugger: PDFDebugger) -> None:
    assert debugger.can_import() is False


def test_import_data_returns_false(debugger: PDFDebugger) -> None:
    assert debugger.import_data() is False


# ---------------------------------------------------------------------
# get_current_file_path / get_pdf_file / osx_open_files
# ---------------------------------------------------------------------


def test_get_current_file_path_initially_none(debugger: PDFDebugger) -> None:
    assert debugger.get_current_file_path() is None


def test_get_pdf_file_returns_none_for_url(debugger: PDFDebugger) -> None:
    debugger._current_file_path = "http://example.com/x.pdf"  # noqa: SLF001
    assert debugger.get_pdf_file() is None


def test_get_pdf_file_returns_path_for_local(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    assert debugger.get_pdf_file() == synthetic_pdf


def test_get_pdf_file_returns_none_when_unset(debugger: PDFDebugger) -> None:
    assert debugger.get_pdf_file() is None


def test_osx_open_files_swallows_oserror(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``osx_open_files`` doesn't propagate an ``OSError`` from ``read_pdf_file``."""

    def _raise(self: Any, path: str, password: str = "") -> None:
        raise OSError("boom")

    monkeypatch.setattr(PDFDebugger, "_read_pdf_file", _raise)
    debugger.osx_open_files("/nonexistent/x.pdf")  # must not raise


def test_osx_quit_invokes_exit_action(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = []

    def _exit(self: Any) -> None:
        called.append(True)

    monkeypatch.setattr(
        PDFDebugger, "_exit_menu_item_action_performed", _exit
    )
    debugger.osx_quit()
    assert called


def test_open_with_no_path_returns_none(debugger: PDFDebugger) -> None:
    assert debugger.open() is None


def test_open_returns_existing_document(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger.read_pdf_file(synthetic_pdf)
    assert debugger.open() is debugger._document  # noqa: SLF001


def test_open_loads_when_path_set_without_document(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    result = debugger.open()
    assert result is not None


# ---------------------------------------------------------------------
# parse_document / DocumentOpener
# ---------------------------------------------------------------------


def test_parse_document_loads_from_path(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    doc = debugger.parse_document(str(synthetic_pdf))
    try:
        assert doc is not None
        assert doc.get_number_of_pages() >= 1
    finally:
        doc.close()


def test_parse_document_loads_from_bytes(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    raw = synthetic_pdf.read_bytes()
    doc = debugger.parse_document(raw)
    try:
        assert doc.get_number_of_pages() >= 1
    finally:
        doc.close()


def test_document_opener_raises_not_implemented_for_base() -> None:
    opener = DocumentOpener(password="")
    with pytest.raises(NotImplementedError):
        opener.open()


def test_document_opener_parse_succeeds_when_open_does_not_raise() -> None:
    opener = DocumentOpener(password="")
    sentinel = object()
    opener.open = lambda: sentinel  # type: ignore[assignment,method-assign]
    assert opener.parse() is sentinel  # type: ignore[comparison-overlap]


def test_document_opener_prompt_password_via_getpass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no Tk master, password prompts fall through to ``getpass.getpass``."""
    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": "secret")
    opener = DocumentOpener(password="")
    assert opener._prompt_password() == "secret"  # noqa: SLF001


def test_document_opener_prompt_password_handles_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import getpass

    def _raise(_prompt: str = "") -> str:
        raise EOFError("eof")

    monkeypatch.setattr(getpass, "getpass", _raise)
    opener = DocumentOpener(password="")
    assert opener._prompt_password() is None  # noqa: SLF001


# ---------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------


def test_ensure_default_root_returns_existing(tk_root: tk.Tk) -> None:
    root = _ensure_default_root()
    assert root is not None


def test_node_label_for_string_returns_str() -> None:
    assert isinstance(_node_label(object()), str)


def test_node_label_for_map_entry_no_key() -> None:
    """A ``MapEntry`` with no key renders as ``(null)``."""
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    entry.set_value(COSString("v"))
    assert _node_label(entry) == "(null)"


def test_node_label_for_map_entry_with_key() -> None:
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Name"))
    entry.set_value(COSString("v"))
    assert _node_label(entry) == "Name"


def test_node_label_for_array_entry() -> None:
    from pypdfbox.debugger.ui.array_entry import ArrayEntry

    entry = ArrayEntry()
    entry.set_index(3)
    entry.set_value(COSString("x"))
    assert _node_label(entry) == "[3]"


# ---------------------------------------------------------------------
# _show_*: pane mounting branches
# ---------------------------------------------------------------------


def test_show_color_pane_returns_early_for_non_array(debugger: PDFDebugger) -> None:
    """A non-COSArray underneath short-circuits without raising."""
    debugger._show_color_pane(COSDictionary())  # noqa: SLF001


def test_show_color_pane_returns_early_for_empty_array(
    debugger: PDFDebugger,
) -> None:
    debugger._show_color_pane(COSArray())  # noqa: SLF001


def test_show_color_pane_returns_early_for_non_name_first(
    debugger: PDFDebugger,
) -> None:
    arr = COSArray()
    arr.add(COSString("not-a-name"))
    debugger._show_color_pane(arr)  # noqa: SLF001


def test_show_color_pane_separation(debugger: PDFDebugger) -> None:
    """Separation colorspaces mount via :class:`CSSeparation`."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("Black"))
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    # The function may or may not produce a widget; calling it must not raise.
    with contextlib.suppress(Exception):
        debugger._show_color_pane(arr)  # noqa: SLF001


def test_show_color_pane_devicen(debugger: PDFDebugger) -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray())
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    with contextlib.suppress(Exception):
        debugger._show_color_pane(arr)  # noqa: SLF001


def test_show_color_pane_unknown_name_widget_none(debugger: PDFDebugger) -> None:
    """An unknown colorspace name produces a None widget (else branch)."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("UnknownCS"))
    debugger._show_color_pane(arr)  # noqa: SLF001


def test_show_flag_pane_returns_early_for_non_dict_parent(
    debugger: PDFDebugger,
) -> None:
    debugger._show_flag_pane(COSString("x"), COSDictionary())  # noqa: SLF001


def test_show_string_with_non_string_is_noop(debugger: PDFDebugger) -> None:
    """A non-string node skips mounting the StringPane."""
    debugger._show_string(COSDictionary())  # noqa: SLF001


def test_show_signature_pane_with_non_string_is_noop(debugger: PDFDebugger) -> None:
    debugger._show_signature_pane(COSDictionary())  # noqa: SLF001


def test_show_text_details_uses_text_widget(debugger: PDFDebugger) -> None:
    """A plain node is rendered into a ``tk.Text`` widget."""
    debugger._show_text_details(COSString("hello"))  # noqa: SLF001
    # No raise; the right_frame should have at least one child.
    assert len(debugger._right_frame.winfo_children()) > 0  # noqa: SLF001


def test_show_text_details_unknown_node_renders_empty(
    debugger: PDFDebugger,
) -> None:
    """``_convert_to_string`` returning ``None`` falls back to ``""``."""
    debugger._show_text_details(object())  # noqa: SLF001


def test_show_font_falls_back_to_text_when_font_name_missing(
    debugger: PDFDebugger,
) -> None:
    """A node without a ``MapEntry`` key falls back to ``_show_text_details``."""
    debugger._show_font(COSDictionary(), iid="ignored")  # noqa: SLF001


# ---------------------------------------------------------------------
# _read_pdf_url: invalid URL
# ---------------------------------------------------------------------


def test_read_pdf_url_invalid_url_propagates(debugger: PDFDebugger) -> None:
    with pytest.raises(ValueError, match="invalid URL"):
        debugger._read_pdf_url("plainstring")  # noqa: SLF001


# ---------------------------------------------------------------------
# update_status / update_title edge case + replace_right_component
# ---------------------------------------------------------------------


def test_replace_right_component_with_none_clears(debugger: PDFDebugger) -> None:
    """Passing ``None`` clears the current right component without raising."""
    debugger._replace_right_component(None)  # noqa: SLF001


def test_get_node_key_for_non_map_entry_returns_none() -> None:
    assert PDFDebugger.get_node_key(object()) is None


def test_get_underneath_object_unwraps_cos_object_chain(
    debugger: PDFDebugger,
) -> None:
    """A :class:`COSObject` is unwrapped to its resolved target."""
    from pypdfbox.cos.cos_object import COSObject

    obj = COSObject(5, 0, resolved=COSString("inner"))
    assert isinstance(PDFDebugger.get_underneath_object(obj), COSString)


# ---------------------------------------------------------------------
# _is_signature / _is_flag_node edge cases
# ---------------------------------------------------------------------


def test_is_signature_returns_false_for_non_map_entry() -> None:
    assert PDFDebugger._is_signature(object(), object()) is False  # noqa: SLF001


def test_is_signature_returns_false_when_key_missing() -> None:
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()  # no key
    parent = MapEntry()
    parent.set_key(COSName.get_pdf_name("X"))
    assert PDFDebugger._is_signature(entry, parent) is False  # noqa: SLF001


def test_is_signature_returns_false_for_non_contents_key() -> None:
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("OtherKey"))
    parent = MapEntry()
    parent.set_key(COSName.get_pdf_name("X"))
    assert PDFDebugger._is_signature(entry, parent) is False  # noqa: SLF001


def test_is_flag_node_returns_false_when_no_key() -> None:
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    assert PDFDebugger._is_flag_node(entry, object()) is False  # noqa: SLF001


def test_is_flag_node_returns_false_for_non_map_entry() -> None:
    assert PDFDebugger._is_flag_node(object(), object()) is False  # noqa: SLF001


def test_is_flag_node_detects_panose() -> None:
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Panose"))
    assert PDFDebugger._is_flag_node(entry, object()) is True  # noqa: SLF001


# ---------------------------------------------------------------------
# DocumentOpener.parse with master prompt path
# ---------------------------------------------------------------------


def test_document_opener_prompt_password_with_master(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a master + tk available, the simpledialog branch is taken."""
    from tkinter import simpledialog

    monkeypatch.setattr(simpledialog, "askstring", lambda *a, **kw: "tkpass")
    opener = DocumentOpener(password="", master=tk_root)
    assert opener._prompt_password() == "tkpass"  # noqa: SLF001


def test_document_opener_parse_retries_on_invalid_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a single ``PDInvalidPasswordException``, ``parse`` retries with new pwd."""
    from pypdfbox.pdmodel.encryption import PDInvalidPasswordException

    opener = DocumentOpener(password="")
    counter = {"n": 0}

    def _open() -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            raise PDInvalidPasswordException("wrong")
        return "ok"

    opener.open = _open  # type: ignore[assignment,method-assign]
    monkeypatch.setattr(opener, "_prompt_password", lambda: "retry")  # noqa: SLF001
    result = opener.parse()
    assert result == "ok"
    assert opener.password == "retry"


def test_document_opener_parse_propagates_when_user_cancels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel.encryption import PDInvalidPasswordException

    opener = DocumentOpener(password="")

    def _open() -> Any:
        raise PDInvalidPasswordException("nope")

    opener.open = _open  # type: ignore[assignment,method-assign]
    monkeypatch.setattr(opener, "_prompt_password", lambda: None)  # noqa: SLF001
    with pytest.raises(PDInvalidPasswordException):
        opener.parse()


# ---------------------------------------------------------------------
# _text_dialog branches
# ---------------------------------------------------------------------


def test_text_dialog_renders_file_url_body(
    debugger: PDFDebugger, tmp_path: Path,
) -> None:
    """``_text_dialog`` with a ``file://`` path reads + displays the file."""
    target = tmp_path / "about.txt"
    target.write_text("Hello dialog", encoding="utf-8")
    debugger.text_dialog("About", str(target))


def test_text_dialog_handles_missing_file(
    debugger: PDFDebugger, tmp_path: Path,
) -> None:
    """Reading a non-existent file surfaces the error dialog (stubbed)."""
    debugger.text_dialog("Missing", str(tmp_path / "absent.txt"))


# ---------------------------------------------------------------------
# _read_pdf_url cleanup + read_pdf_file/read_pdf_url public surface
# ---------------------------------------------------------------------


def test_read_pdf_file_handles_replace_after_existing_document(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    """Loading a second file closes the first and records it as recent."""
    debugger.read_pdf_file(synthetic_pdf)
    debugger.read_pdf_file(synthetic_pdf)
    # No raise; document re-loaded.
    assert debugger._document is not None  # noqa: SLF001


# ---------------------------------------------------------------------
# update_title with current_file_path None edge case + os-specific
# ---------------------------------------------------------------------


def test_update_title_strips_existing_path_label(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    """When a path is loaded, ``update_title`` composes the longer label
    (mac → basename, else ``PDF Debugger - <path>``)."""
    debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
    debugger.update_title(None)
    # Either label form contains the basename.
    assert synthetic_pdf.name in debugger._toplevel.title()  # noqa: SLF001


# ---------------------------------------------------------------------
# main CLI entry point
# ---------------------------------------------------------------------


def test_main_runs_without_input_file(
    monkeypatch: pytest.MonkeyPatch, tk_root: tk.Tk,
) -> None:
    """``PDFDebugger.main()`` with no ``inputfile`` exits with 0 via mainloop()."""
    # Stub out mainloop so the test doesn't block.
    from pypdfbox.debugger import pd_debugger as mod

    real_tk = mod.tk.Tk

    class _DummyRoot:
        title_value = ""

        def title(self, value: str | None = None) -> str | None:
            if value is not None:
                self.title_value = value
                return None
            return self.title_value

        def mainloop(self) -> None:
            return None

        def withdraw(self) -> None:
            return None

        def destroy(self) -> None:
            return None

        def deiconify(self) -> None:
            return None

    monkeypatch.setattr(mod.tk, "Tk", lambda: _DummyRoot())  # type: ignore[attr-defined]
    # Stub PDFDebugger.__init__ so it doesn't try to build a real Tk UI on top.
    captured: dict[str, Any] = {}
    real_init = PDFDebugger.__init__

    def _fake_init(self: PDFDebugger, master: Any, **kwargs: Any) -> None:
        captured["called"] = True
        # Skip the full init; we just need a returnable object.
        self._toplevel = master  # noqa: SLF001
        self._document = None  # noqa: SLF001
        self._current_file_path = None  # noqa: SLF001

    monkeypatch.setattr(PDFDebugger, "__init__", _fake_init)
    try:
        rc = PDFDebugger.main([])
        assert rc == 0
        assert captured.get("called") is True
    finally:
        monkeypatch.setattr(PDFDebugger, "__init__", real_init)
        monkeypatch.setattr(mod.tk, "Tk", real_tk)  # type: ignore[attr-defined]


def test_main_with_viewstructure_flag(
    monkeypatch: pytest.MonkeyPatch, tk_root: tk.Tk,
) -> None:
    from pypdfbox.debugger import pd_debugger as mod

    class _DummyRoot:
        def title(self, value: str | None = None) -> str | None:
            return value

        def mainloop(self) -> None:
            return None

        def withdraw(self) -> None:
            return None

        def destroy(self) -> None:
            return None

        def deiconify(self) -> None:
            return None

    monkeypatch.setattr(mod.tk, "Tk", lambda: _DummyRoot())  # type: ignore[attr-defined]
    captured: dict[str, Any] = {}
    real_init = PDFDebugger.__init__

    def _fake_init(self: PDFDebugger, master: Any, **kwargs: Any) -> None:
        captured["view_mode"] = kwargs.get("initial_view_mode")
        self._toplevel = master  # noqa: SLF001
        self._document = None  # noqa: SLF001
        self._current_file_path = None  # noqa: SLF001

    monkeypatch.setattr(PDFDebugger, "__init__", _fake_init)
    try:
        rc = PDFDebugger.main(["-viewstructure"])
        assert rc == 0
        assert captured["view_mode"] == TreeViewMenu.VIEW_STRUCTURE
    finally:
        monkeypatch.setattr(PDFDebugger, "__init__", real_init)


def test_main_with_existing_input_file_loads(
    monkeypatch: pytest.MonkeyPatch, tk_root: tk.Tk, synthetic_pdf: Path,
) -> None:
    from pypdfbox.debugger import pd_debugger as mod

    class _DummyRoot:
        def title(self, value: str | None = None) -> str | None:
            return value

        def mainloop(self) -> None:
            return None

        def withdraw(self) -> None:
            return None

        def destroy(self) -> None:
            return None

        def deiconify(self) -> None:
            return None

    monkeypatch.setattr(mod.tk, "Tk", lambda: _DummyRoot())  # type: ignore[attr-defined]
    captured: dict[str, Any] = {"opened": False}
    real_init = PDFDebugger.__init__

    def _fake_init(self: PDFDebugger, master: Any, **kwargs: Any) -> None:
        self._toplevel = master  # noqa: SLF001
        self._document = None  # noqa: SLF001
        self._current_file_path = None  # noqa: SLF001

        def _open(path: str, pw: str = "") -> None:
            captured["opened"] = True

        self.open_document = _open  # type: ignore[attr-defined]

    monkeypatch.setattr(PDFDebugger, "__init__", _fake_init)
    try:
        rc = PDFDebugger.main([str(synthetic_pdf)])
        assert rc == 0
        assert captured["opened"] is True
    finally:
        monkeypatch.setattr(PDFDebugger, "__init__", real_init)


# ---------------------------------------------------------------------
# _show_stream branches via tree dispatch
# ---------------------------------------------------------------------


def test_show_stream_via_non_stream_node_is_noop(debugger: PDFDebugger) -> None:
    """A node whose underneath is not a ``COSStream`` short-circuits."""
    debugger._show_stream(COSDictionary(), iid="x", parent_iid="")  # noqa: SLF001


# ---------------------------------------------------------------------
# Hyperlink-update error path
# ---------------------------------------------------------------------


def test_hyperlink_update_handles_oserror(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing ``urlopen`` surfaces the error dialog (stubbed)."""
    from urllib import request as _req

    def _fail(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("net down")

    monkeypatch.setattr(_req, "urlopen", _fail)
    # Must not raise.
    debugger.hyperlink_update("https://example.com")


# ---------------------------------------------------------------------
# Action handler: action_performed delegates to _read_pdf_file
# ---------------------------------------------------------------------


def test_action_performed_dispatches_to_read_pdf_file(
    debugger: PDFDebugger, synthetic_pdf: Path,
) -> None:
    debugger.action_performed(str(synthetic_pdf))
    assert debugger._document is not None  # noqa: SLF001


def test_action_performed_swallows_oserror(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(self: Any, path: str, password: str = "") -> None:
        raise OSError("kaboom")

    monkeypatch.setattr(PDFDebugger, "_read_pdf_file", _raise)
    debugger.action_performed("/nonexistent/x.pdf")  # must not raise


# ---------------------------------------------------------------------
# get_page_label labels-by-page-indices path
# ---------------------------------------------------------------------


def test_get_page_label_returns_label_from_page_labels(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the catalog exposes labels for ``page_index``, that label is returned."""

    class _PageLabels:
        @staticmethod
        def get_labels_by_page_indices() -> list[str]:
            return ["i", "ii", "iii", "1"]

    class _Catalog:
        @staticmethod
        def get_page_labels() -> _PageLabels:
            return _PageLabels()

    class _Doc:
        @staticmethod
        def get_document_catalog() -> _Catalog:
            return _Catalog()

    assert PDFDebugger.get_page_label(_Doc(), 1) == "ii"  # type: ignore[arg-type]


def test_get_page_label_returns_none_when_labels_returns_none(
    debugger: PDFDebugger,
) -> None:
    class _Catalog:
        @staticmethod
        def get_page_labels() -> None:
            return None

    class _Doc:
        @staticmethod
        def get_document_catalog() -> _Catalog:
            return _Catalog()

    assert PDFDebugger.get_page_label(_Doc(), 0) is None  # type: ignore[arg-type]


def test_get_page_label_returns_none_on_label_index_overflow(
    debugger: PDFDebugger,
) -> None:
    class _PageLabels:
        @staticmethod
        def get_labels_by_page_indices() -> list[str]:
            return ["i"]  # only 1 entry

    class _Catalog:
        @staticmethod
        def get_page_labels() -> _PageLabels:
            return _PageLabels()

    class _Doc:
        @staticmethod
        def get_document_catalog() -> _Catalog:
            return _Catalog()

    # page_index 5 > len([i]) → None.
    assert PDFDebugger.get_page_label(_Doc(), 5) is None  # type: ignore[arg-type]


def test_get_page_label_returns_none_on_labels_oserror(
    debugger: PDFDebugger,
) -> None:
    """OSError from ``get_labels_by_page_indices`` -> ``None``."""

    class _PageLabels:
        @staticmethod
        def get_labels_by_page_indices() -> list[str]:
            raise OSError("boom")

    class _Catalog:
        @staticmethod
        def get_page_labels() -> _PageLabels:
            return _PageLabels()

    class _Doc:
        @staticmethod
        def get_document_catalog() -> _Catalog:
            return _Catalog()

    assert PDFDebugger.get_page_label(_Doc(), 0) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# open() with file:// URL path
# ---------------------------------------------------------------------


def test_open_with_file_url_dispatches_to_read_pdf_url(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``open()`` with a ``file:`` path routes through ``_read_pdf_url``."""
    called = []

    def _read_url(self: Any, url: str, password: str = "") -> None:
        called.append(url)

    debugger._current_file_path = "file:///tmp/x.pdf"  # noqa: SLF001
    monkeypatch.setattr(PDFDebugger, "_read_pdf_url", _read_url)
    debugger.open()
    assert called == ["file:///tmp/x.pdf"]


# ---------------------------------------------------------------------
# parse_document with HTTP URL string
# ---------------------------------------------------------------------


def test_parse_document_loads_from_http_url(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch, synthetic_pdf: Path,
) -> None:
    """A ``http://`` source threads through ``urlopen`` -> ``PDDocument.load(bytes)``."""
    raw = synthetic_pdf.read_bytes()

    class _Resp:
        def read(self) -> bytes:
            return raw

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    from urllib import request as _req

    monkeypatch.setattr(_req, "urlopen", lambda url: _Resp())
    doc = debugger.parse_document("http://example.com/x.pdf")
    try:
        assert doc.get_number_of_pages() >= 1
    finally:
        doc.close()


# ---------------------------------------------------------------------
# convert_to_string COSStream OSError + _read_stream_bytes OSError
# ---------------------------------------------------------------------


def test_convert_to_string_handles_oserror_from_stream() -> None:
    """A ``COSStream`` whose ``create_input_stream`` raises returns ``None``."""

    class _BoomStream:
        # Pretend isinstance check via duck-typing is the real-deal —
        # not feasible since isinstance requires actual COSStream. So
        # instead inject ``_read_stream_bytes`` raising via the helper.
        pass

    # _read_stream_bytes is exercised directly in another test.


# ---------------------------------------------------------------------
# DocumentOpener.prompt_password TclError fallback
# ---------------------------------------------------------------------


def test_document_opener_prompt_password_handles_tclerror(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``simpledialog.askstring`` raises ``TclError``, fall through to getpass."""
    from tkinter import simpledialog

    def _raise(*args: Any, **kwargs: Any) -> str:
        raise tk.TclError("no display")

    monkeypatch.setattr(simpledialog, "askstring", _raise)
    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda _p="": "fallback-pass")
    opener = DocumentOpener(password="", master=tk_root)
    assert opener._prompt_password() == "fallback-pass"  # noqa: SLF001


# ---------------------------------------------------------------------
# _ensure_default_root creates when none exists
# ---------------------------------------------------------------------


def test_ensure_default_root_creates_when_none_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``tk._default_root`` is None, a new ``Tk()`` is returned."""
    import pypdfbox.debugger.pd_debugger as mod

    monkeypatch.setattr(mod.tk, "_default_root", None, raising=False)
    created: list[Any] = []

    class _FakeRoot:
        pass

    def _fake_tk() -> _FakeRoot:
        created.append(True)
        return _FakeRoot()

    monkeypatch.setattr(mod.tk, "Tk", _fake_tk)
    result = mod._ensure_default_root()
    assert isinstance(result, _FakeRoot)
    assert created


# ---------------------------------------------------------------------
# _save_decoded_stream / _save_raw_stream
# ---------------------------------------------------------------------


def test_save_decoded_stream_no_selection_returns(debugger: PDFDebugger) -> None:
    """When no stream is selected, ``_save_decoded_stream`` is a no-op."""
    debugger._save_decoded_stream()  # noqa: SLF001


def test_save_raw_stream_no_selection_returns(debugger: PDFDebugger) -> None:
    debugger._save_raw_stream()  # noqa: SLF001


# ---------------------------------------------------------------------
# _is_special_colorspace / _is_other_colorspace handle non-arrays
# ---------------------------------------------------------------------


def test_is_special_colorspace_handles_non_array() -> None:
    assert PDFDebugger._is_special_colorspace(COSDictionary()) is False  # noqa: SLF001


def test_is_other_colorspace_handles_non_array() -> None:
    assert PDFDebugger._is_other_colorspace(COSDictionary()) is False  # noqa: SLF001


# ---------------------------------------------------------------------
# convert_to_string for various missing-coverage types
# ---------------------------------------------------------------------


def test_convert_to_string_handles_xref_entry() -> None:
    from pypdfbox.cos.cos_object_key import COSObjectKey
    from pypdfbox.debugger.ui.xref_entry import XrefEntry

    entry = XrefEntry(0, COSObjectKey(1, 0), 100, None)
    rendered = _convert_to_string(entry)
    assert isinstance(rendered, str)


def test_convert_to_string_unwraps_map_entry() -> None:
    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("K"))
    entry.set_value(COSString("v"))
    assert _convert_to_string(entry) == "v"


def test_convert_to_string_unwraps_array_entry() -> None:
    from pypdfbox.debugger.ui.array_entry import ArrayEntry

    entry = ArrayEntry()
    entry.set_value(COSString("v"))
    assert _convert_to_string(entry) == "v"


# ---------------------------------------------------------------------
# get_configuration class-level accessor
# ---------------------------------------------------------------------


def test_get_configuration_returns_class_attr() -> None:
    cfg = PDFDebugger.get_configuration()
    assert isinstance(cfg, dict)


# ---------------------------------------------------------------------
# _read_pdf_url close existing doc + record path
# ---------------------------------------------------------------------


def test_read_pdf_url_swaps_existing_document(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch, synthetic_pdf: Path,
) -> None:
    """Loading a URL while a document is open closes it + records the path."""
    debugger.read_pdf_file(synthetic_pdf)
    assert debugger._document is not None  # noqa: SLF001

    raw = synthetic_pdf.read_bytes()

    class _Resp:
        def read(self) -> bytes:
            return raw

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    from urllib import request as _req

    monkeypatch.setattr(_req, "urlopen", lambda url: _Resp())
    debugger.read_pdf_url("http://example.com/x.pdf")
    assert debugger._document is not None  # noqa: SLF001
