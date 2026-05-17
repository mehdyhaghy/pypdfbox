"""Coverage round-out for :class:`PDFDebugger` — wave 1339.

Targets the few remaining uncovered branches in
``pypdfbox/debugger/pd_debugger.py``:

* Non-mac-only ``Exit`` entry on the ``File`` menu.
* ``_populate_recent_files_menu`` early return when the cascade has not
  been built yet.
* Find / Find Next / Find Previous getters returning ``None`` before
  menus are built.
* ``_on_tree_open`` empty-selection short circuit and ``node is None``
  sentinel-collapse case.
* ``_show_page`` / ``_show_color_pane`` (``CSArrayBased`` branch) /
  ``_show_flag_pane`` (key-missing + view-None paths) early returns.
* ``_show_stream`` content / image / thumb / pattern branches.
* ``_show_font`` notdef-fallthrough branches.
* Save-as / decoded / raw stream ``OSError`` recovery via stubbed
  document.
* ``_text_dialog`` ``urlopen`` branch via a fake ``urllib.request``.
* ``set_title`` non-mac default-string formatting.
* ``_read_stream_bytes`` non-``read`` data path (returns ``bytes(data)``).

Honours ``PYPDFBOX_SKIP_TK=1`` like the rest of the debugger suite.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.debugger import pd_debugger as _pd_debugger
from pypdfbox.debugger.pd_debugger import PDFDebugger, _read_stream_bytes
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu

# ----------------------------------------------------------------------
# Fixtures
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
    from pypdfbox.debugger.ui import error_dialog as _ed

    _ed.set_show_error_impl(lambda title, message: None)
    try:
        yield
    finally:
        _ed.set_show_error_impl(None)


@pytest.fixture()
def debugger(tk_root: tk.Tk) -> Iterator[PDFDebugger]:
    instance = PDFDebugger(tk_root)
    try:
        yield instance
    finally:
        with contextlib.suppress(tk.TclError):
            instance._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Non-mac file-menu Exit entry (lines 356-357)
# ----------------------------------------------------------------------


def test_create_file_menu_appends_exit_on_non_mac(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force ``_is_mac_os`` False so we exercise the ``Exit`` branch."""
    monkeypatch.setattr(_pd_debugger, "_is_mac_os", lambda: False)
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_file_menu(parent)
    # ``end`` index is now larger than the print index — the Exit row sits
    # after a separator that follows Print.
    last = menu.index("end")
    assert last is not None
    # Walk the entries — the last command-typed entry should be "Exit".
    found_exit = False
    for i in range(last + 1):
        try:
            entry_type = menu.type(i)
        except tk.TclError:
            continue
        if entry_type == "command":
            with contextlib.suppress(tk.TclError):
                if menu.entrycget(i, "label") == "Exit":
                    found_exit = True
    assert found_exit


# ----------------------------------------------------------------------
# _populate_recent_files_menu early-return (line 471)
# ----------------------------------------------------------------------


def test_populate_recent_files_menu_returns_when_menu_unbuilt(
    debugger: PDFDebugger,
) -> None:
    debugger._recent_files_menu = None  # noqa: SLF001
    # No raise — the method returns immediately because the cascade has
    # not been built.
    debugger._populate_recent_files_menu()  # noqa: SLF001


def test_populate_recent_files_menu_returns_when_file_menu_unbuilt(
    debugger: PDFDebugger,
) -> None:
    debugger._file_menu = None  # noqa: SLF001
    debugger._populate_recent_files_menu()  # noqa: SLF001


def test_add_recent_file_items_early_return_when_menu_unbuilt(
    debugger: PDFDebugger,
) -> None:
    """``add_recent_file_items`` mirrors upstream's public spelling — it
    must short-circuit when the cascade hasn't been built yet."""
    debugger._recent_files_menu = None  # noqa: SLF001
    debugger.add_recent_file_items()


def test_add_recent_file_items_early_return_when_file_menu_unbuilt(
    debugger: PDFDebugger,
) -> None:
    debugger._file_menu = None  # noqa: SLF001
    debugger.add_recent_file_items()


def test_add_recent_file_items_returns_when_no_files(debugger: PDFDebugger) -> None:
    """No recorded entries — ``is_empty()`` triggers the second early
    return after the menu-built guard."""
    debugger._recent_files.remove_all()  # noqa: SLF001
    debugger.add_recent_file_items()


def test_add_recent_file_items_rebuilds_with_entries(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    """Populate the recent-files cache so we walk the full body."""
    debugger._recent_files.remove_all()  # noqa: SLF001
    path = tmp_path / "alpha.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    debugger._recent_files.add_file(str(path))  # noqa: SLF001
    debugger.add_recent_file_items()
    # The cascade should now host the one entry.
    assert debugger._recent_files_menu is not None  # noqa: SLF001
    assert debugger._recent_files_menu.index("end") == 0  # noqa: SLF001


# ----------------------------------------------------------------------
# get_find_*_menu_item return None before menu built (lines 616/622/628)
# ----------------------------------------------------------------------


def test_get_find_menu_item_returns_none_before_build(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    # Even after construction, ``_find_menu_index`` may be set; force it
    # back to None so we hit the ``return None`` branch.
    debugger._find_menu_index = None  # noqa: SLF001
    assert debugger.get_find_menu_item() is None


def test_get_find_next_menu_item_returns_none_before_build(
    tk_root: tk.Tk,
) -> None:
    debugger = PDFDebugger(tk_root)
    debugger._find_next_menu_index = None  # noqa: SLF001
    assert debugger.get_find_next_menu_item() is None


def test_get_find_previous_menu_item_returns_none_before_build(
    tk_root: tk.Tk,
) -> None:
    debugger = PDFDebugger(tk_root)
    debugger._find_previous_menu_index = None  # noqa: SLF001
    assert debugger.get_find_previous_menu_item() is None


# ----------------------------------------------------------------------
# _on_tree_open empty-selection and node-None paths (lines 783, 794)
# ----------------------------------------------------------------------


class _StubDoc:
    def get_document_catalog(self) -> Any:
        return None

    def close(self) -> None:
        return None


def test_on_tree_open_returns_when_no_selection(debugger: PDFDebugger) -> None:
    debugger._document = _StubDoc()  # noqa: SLF001
    # ``self._tree.focus()`` returns "" when nothing focused — the method
    # should return immediately.
    debugger._on_tree_open(None)  # type: ignore[arg-type]  # noqa: SLF001


def test_on_tree_open_returns_when_get_node_is_none(debugger: PDFDebugger) -> None:
    debugger._document = _StubDoc()  # noqa: SLF001
    # Insert a sentinel-only row whose ``get_node`` returns None.
    iid = debugger._tree.insert("", "end", text="x")  # noqa: SLF001
    debugger._tree.insert(iid, "end", text="...")  # noqa: SLF001
    debugger._tree.focus(iid)  # noqa: SLF001
    debugger._on_tree_open(None)  # type: ignore[arg-type]  # noqa: SLF001


# ----------------------------------------------------------------------
# _show_page early return (line 1013)
# ----------------------------------------------------------------------


def test_show_page_returns_when_underneath_not_cos_dict(
    debugger: PDFDebugger,
) -> None:
    # ``_get_underneath_object`` of a plain string returns the string
    # itself, which is not a COSDictionary -> early return.
    debugger._show_page("not-a-dict")  # noqa: SLF001


# ----------------------------------------------------------------------
# _show_color_pane CSArrayBased branch (line 1038-1039)
# ----------------------------------------------------------------------


def test_show_color_pane_handles_other_colorspace_name(
    debugger: PDFDebugger,
) -> None:
    arr = COSArray()
    # ``CalGray`` lives in _OTHER_COLORSPACES, so we hit the CSArrayBased
    # branch — but the array also needs at least one accompanying dict so
    # CSArrayBased's constructor doesn't crash; an empty dict is enough.
    arr.add(COSName.get_pdf_name("CalGray"))
    arr.add(COSDictionary())
    debugger._show_color_pane(arr)  # noqa: SLF001


def test_dispatch_selection_routes_colorspace_to_pane(
    debugger: PDFDebugger,
) -> None:
    """Round-trip via ``_dispatch_selection`` so the colorspace return
    after ``_show_color_pane`` is exercised (line 838)."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    arr.add(COSDictionary())
    node = _make_map_entry("CS", arr)
    iid = _insert(debugger._tree, "", "CS", node)  # noqa: SLF001
    debugger._dispatch_selection(node, None, iid, "")  # noqa: SLF001


def test_show_color_pane_returns_when_array_empty(debugger: PDFDebugger) -> None:
    debugger._show_color_pane(COSArray())  # noqa: SLF001


def test_show_color_pane_returns_when_first_not_cos_name(
    debugger: PDFDebugger,
) -> None:
    arr = COSArray()
    arr.add(COSString("hi"))
    debugger._show_color_pane(arr)  # noqa: SLF001


# ----------------------------------------------------------------------
# _show_flag_pane edges (lines 1050, 1056, 1060)
# ----------------------------------------------------------------------


def test_show_flag_pane_returns_when_underneath_not_cos_dict(
    debugger: PDFDebugger,
) -> None:
    # Parent's underneath is not a COSDictionary -> early return at 1046.
    debugger._show_flag_pane("parent", "node")  # noqa: SLF001


def test_show_flag_pane_returns_when_key_is_none(debugger: PDFDebugger) -> None:
    # Build a parent whose underneath IS a COSDictionary, but a child
    # that's not a MapEntry/ArrayEntry/PageEntry/XrefEntry — so
    # _get_node_key returns None.
    parent = COSDictionary()
    # Plain string node → _get_node_key returns None → line 1050.
    debugger._show_flag_pane(parent, "node-without-key")  # noqa: SLF001


class _NullViewPane:
    """Stand-in :class:`FlagBitsPane` whose ``get_pane`` returns None."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def get_pane(self) -> None:
        return None


class _PanelOnlyView:
    """A non-widget view that exposes ``get_panel`` only (line 1060)."""

    def __init__(self, widget: tk.Widget) -> None:
        self._w = widget

    def get_panel(self) -> tk.Widget:
        return self._w


class _PanelOnlyPane:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        master = kwargs.get("master") or (_args[3] if len(_args) >= 4 else None)
        self._view = _PanelOnlyView(tk.Frame(master))

    def get_pane(self) -> _PanelOnlyView:
        return self._view


def test_show_flag_pane_returns_when_view_is_none(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_pd_debugger, "FlagBitsPane", _NullViewPane)
    parent = COSDictionary()
    node = _make_map_entry("Ff", COSDictionary())
    debugger._show_flag_pane(parent, node)  # noqa: SLF001


def test_show_flag_pane_uses_get_panel_when_view_not_widget(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``view`` is not a ``tk.Widget`` and has no ``frame`` attr — fall
    through to ``view.get_panel()`` (covers line 1060)."""
    monkeypatch.setattr(_pd_debugger, "FlagBitsPane", _PanelOnlyPane)
    parent = COSDictionary()
    node = _make_map_entry("Ff", COSDictionary())
    debugger._show_flag_pane(parent, node)  # noqa: SLF001


# ----------------------------------------------------------------------
# _show_stream various branches (lines 1077-1110)
# ----------------------------------------------------------------------


def _stream_with(
    *,
    subtype: str | None = None,
    type_name: str | None = None,
    pattern_type: int | None = None,
    resources: COSDictionary | None = None,
) -> COSStream:
    s = COSStream()
    if subtype is not None:
        s.set_name(COSName.SUBTYPE, subtype)
    if type_name is not None:
        s.set_name(COSName.TYPE, type_name)
    if pattern_type is not None:
        s.set_int("PatternType", int(pattern_type))
    if resources is not None:
        s.set_item(COSName.RESOURCES, resources)
    return s


def _make_map_entry(key_name: str, value: Any) -> MapEntry:
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name(key_name))
    entry.set_value(value)
    return entry


def _insert(tree: Any, parent_iid: str, text: str, node: Any) -> str:
    iid = tree.insert(parent_iid, "end", text=text)
    tree.register_node(iid, node)
    return iid


def test_show_stream_contents_with_page_resources(debugger: PDFDebugger) -> None:
    """Node key == ``/Contents`` and parent is a /Page dict with /Resources."""
    page = COSDictionary()
    resources = COSDictionary()
    page.set_item(COSName.RESOURCES, resources)
    node = _make_map_entry("Contents", _stream_with())
    parent_iid = _insert(
        debugger._tree, "", "page", _make_map_entry("Page", page)  # noqa: SLF001
    )
    iid = _insert(debugger._tree, parent_iid, "Contents", node)  # noqa: SLF001
    debugger._show_stream(node, iid, parent_iid)  # noqa: SLF001


def test_show_stream_grandparent_charprocs(debugger: PDFDebugger) -> None:
    """Parent key == ``/CharProcs`` — resources resolved via grandparent."""
    page = COSDictionary()
    resources = COSDictionary()
    page.set_item(COSName.RESOURCES, resources)
    charprocs = COSDictionary()
    grand_iid = _insert(
        debugger._tree, "", "page", _make_map_entry("Page", page)  # noqa: SLF001
    )
    parent_iid = _insert(
        debugger._tree,  # noqa: SLF001
        grand_iid,
        "CharProcs",
        _make_map_entry("CharProcs", charprocs),
    )
    stream_node = _make_map_entry("cp1", _stream_with())
    iid = _insert(debugger._tree, parent_iid, "cp1", stream_node)  # noqa: SLF001
    debugger._show_stream(stream_node, iid, parent_iid)  # noqa: SLF001


def test_show_stream_form_with_resources(debugger: PDFDebugger) -> None:
    """``/Subtype /Form`` stream with ``/Resources`` → resources branch."""
    resources = COSDictionary()
    node = _make_map_entry("F1", _stream_with(subtype="Form", resources=resources))
    iid = _insert(debugger._tree, "", "form", node)  # noqa: SLF001
    debugger._show_stream(node, iid, "")  # noqa: SLF001


def test_show_stream_pattern_type_one(debugger: PDFDebugger) -> None:
    """``/PatternType 1`` triggers content-stream classification."""
    node = _make_map_entry("Pat", _stream_with(pattern_type=1))
    iid = _insert(debugger._tree, "", "pat", node)  # noqa: SLF001
    debugger._show_stream(node, iid, "")  # noqa: SLF001


def test_show_stream_thumb_branch(debugger: PDFDebugger) -> None:
    """Node key == ``/Thumb`` → ``is_thumb`` branch."""
    node = _make_map_entry("Thumb", _stream_with())
    iid = _insert(debugger._tree, "", "thumb", node)  # noqa: SLF001
    debugger._show_stream(node, iid, "")  # noqa: SLF001


def test_show_stream_image_with_grandparent_resources(
    debugger: PDFDebugger,
) -> None:
    """``/Subtype /Image`` resolves resources from grandparent dict."""
    resources = COSDictionary()
    s = _stream_with(subtype="Image")
    node = _make_map_entry("Im1", s)
    grand_iid = _insert(
        debugger._tree,  # noqa: SLF001
        "",
        "res",
        _make_map_entry("Resources", resources),
    )
    parent_iid = _insert(
        debugger._tree,  # noqa: SLF001
        grand_iid,
        "xobj",
        _make_map_entry("XObject", COSDictionary()),
    )
    iid = _insert(debugger._tree, parent_iid, "Im1", node)  # noqa: SLF001
    debugger._show_stream(node, iid, parent_iid)  # noqa: SLF001


def test_show_stream_returns_when_underneath_not_cos_stream(
    debugger: PDFDebugger,
) -> None:
    # Not a stream -> early return.
    debugger._show_stream("nope", "", "")  # noqa: SLF001


# ----------------------------------------------------------------------
# _show_font notdef fallback branches (lines 1125-1126, 1133, 1140-1142)
# ----------------------------------------------------------------------


def test_show_font_falls_back_when_no_key(debugger: PDFDebugger) -> None:
    # A plain (non-MapEntry) node has no key — falls through to
    # ``_show_text_details``.
    iid = _insert(debugger._tree, "", "x", "x")  # noqa: SLF001
    debugger._show_font("x", iid)  # noqa: SLF001


def test_show_font_falls_back_when_no_resources_dict(debugger: PDFDebugger) -> None:
    """Grandparent's underneath is not a COSDictionary -> notdef fallback."""
    font_dict = COSDictionary()
    node = _make_map_entry("F1", font_dict)
    iid = _insert(debugger._tree, "", "F1", node)  # noqa: SLF001
    debugger._show_font(node, iid)  # noqa: SLF001


class _NullPaneController:
    """A :class:`FontEncodingPaneController` stand-in whose pane is None."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def get_pane(self) -> None:
        return None


def test_show_font_resolves_to_text_details_when_pane_none(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``get_pane`` returns ``None`` -> falls back to text details
    (covers lines 1135-1142, including the early return at 1140-1141)."""
    monkeypatch.setattr(
        _pd_debugger, "FontEncodingPaneController", _NullPaneController
    )
    font_dict = COSDictionary()
    resources_dict = COSDictionary()
    font_container = COSDictionary()
    font_container.set_item(COSName.get_pdf_name("F1"), font_dict)
    resources_dict.set_item(COSName.get_pdf_name("Font"), font_container)

    grand_iid = _insert(
        debugger._tree,  # noqa: SLF001
        "",
        "Resources",
        _make_map_entry("Resources", resources_dict),
    )
    parent_iid = _insert(
        debugger._tree,  # noqa: SLF001
        grand_iid,
        "Font",
        _make_map_entry("Font", font_container),
    )
    font_node = _make_map_entry("F1", font_dict)
    iid = _insert(debugger._tree, parent_iid, "F1", font_node)  # noqa: SLF001
    debugger._show_font(font_node, iid)  # noqa: SLF001


# ----------------------------------------------------------------------
# Save-stream OSError recovery (lines 1228-1229, 1242-1243, 1256-1257)
# ----------------------------------------------------------------------


class _SaveRaisingDoc:
    def __init__(self) -> None:
        self.security_removed: bool | None = None

    def set_all_security_to_be_removed(self, value: bool) -> None:
        self.security_removed = value

    def save(self, *_args: Any, **_kwargs: Any) -> None:
        raise OSError("permission denied")

    def close(self) -> None:
        return None


def test_save_as_recovers_from_oserror(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    debugger._document = _SaveRaisingDoc()  # type: ignore[assignment]  # noqa: SLF001
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
        lambda **_: "/tmp/out.pdf",
    )
    # No raise — the OSError is swallowed and surfaced via ErrorDialog.
    debugger._save_as_menu_item_action_performed()  # noqa: SLF001


class _SelectedStreamRaising:
    def create_input_stream(self) -> Any:
        raise OSError("boom")

    def create_raw_input_stream(self) -> Any:
        raise OSError("boom")


def test_save_decoded_stream_recovers_from_oserror(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = COSStream()  # baseline; will be substituted via monkeypatch below.
    monkeypatch.setattr(
        PDFDebugger, "_selected_stream", lambda _self: s, raising=False
    )
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
        lambda **_: "/tmp/out.bin",
    )

    # Force ``_read_stream_bytes`` to raise OSError so the except branch
    # is exercised (the helper normally swallows internally, so we patch
    # the module reference at call site).
    def _raise(*_a: Any, **_kw: Any) -> bytes:
        raise OSError("io err")

    monkeypatch.setattr("pypdfbox.debugger.pd_debugger._read_stream_bytes", _raise)
    debugger._save_decoded_stream()  # noqa: SLF001
    debugger._save_raw_stream()  # noqa: SLF001


def test_save_decoded_stream_returns_when_no_stream(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        PDFDebugger, "_selected_stream", lambda _self: None, raising=False
    )
    debugger._save_decoded_stream()  # noqa: SLF001
    debugger._save_raw_stream()  # noqa: SLF001


def test_save_decoded_stream_returns_when_user_cancels_dialog(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        PDFDebugger, "_selected_stream", lambda _self: COSStream(), raising=False
    )
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
        lambda **_: "",
    )
    debugger._save_decoded_stream()  # noqa: SLF001
    debugger._save_raw_stream()  # noqa: SLF001


# ----------------------------------------------------------------------
# _text_dialog urlopen branch (lines 1554-1555)
# ----------------------------------------------------------------------


def test_text_dialog_uses_urlopen_for_http_resource(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.request

    class _Resp:
        def read(self) -> bytes:
            return b"<html>license</html>"

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_kw: _Resp())
    debugger._text_dialog("title", "http://example.invalid/license")  # noqa: SLF001


def test_text_dialog_recovers_when_urlopen_fails(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.request

    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    debugger._text_dialog("title", "http://example.invalid/license")  # noqa: SLF001


# ----------------------------------------------------------------------
# set_title non-mac fallback (line 1913)
# ----------------------------------------------------------------------


def test_update_title_uses_prefix_on_non_mac(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_pd_debugger, "_is_mac_os", lambda: False)
    debugger._current_file_path = "/tmp/foo.pdf"  # noqa: SLF001
    debugger.update_title()
    assert "PDF Debugger - " in debugger._toplevel.title()  # noqa: SLF001


# ----------------------------------------------------------------------
# _read_stream_bytes non-read data path (line 2095)
# ----------------------------------------------------------------------


class _CtxBytes:
    """Context manager yielding a bytes-like object without a ``.read``."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> bytes:
        return self._data

    def __exit__(self, *_args: Any) -> None:
        return None


class _StreamYieldingBytes:
    def create_input_stream(self) -> _CtxBytes:
        return _CtxBytes(b"abc")

    def create_raw_input_stream(self) -> _CtxBytes:
        return _CtxBytes(b"xyz")


def test_read_stream_bytes_returns_bytes_when_data_has_no_read() -> None:
    s = _StreamYieldingBytes()
    assert _read_stream_bytes(s, raw=False) == b"abc"  # type: ignore[arg-type]
    assert _read_stream_bytes(s, raw=True) == b"xyz"  # type: ignore[arg-type]


def test_convert_to_string_for_cos_stream_returns_none_on_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_convert_to_string`` for a COSStream — patch the inner reader to
    raise OSError so we exercise the ``except`` branch (lines 2070-2071).
    """
    from pypdfbox.debugger import pd_debugger as _mod

    def _raise(*_a: Any, **_kw: Any) -> bytes:
        raise OSError("io")

    monkeypatch.setattr(_mod, "_read_stream_bytes", _raise)
    cs = COSStream()
    with cs.create_output_stream() as out:
        out.write(b"hi")
    assert _mod._convert_to_string(cs) is None


# ----------------------------------------------------------------------
# _is_font_descriptor / _is_annot false-paths (lines 970, 978)
# ----------------------------------------------------------------------


def test_is_font_descriptor_false_when_no_type_key() -> None:
    node = COSDictionary()  # plain dict; no /Type key
    assert PDFDebugger._is_font_descriptor(node) is False  # noqa: SLF001


def test_is_font_descriptor_false_when_type_mismatches() -> None:
    """Dict with ``/Type /Pages`` (not FontDescriptor) -> False."""
    node = COSDictionary()
    node.set_name(COSName.TYPE, "Pages")
    assert PDFDebugger._is_font_descriptor(node) is False  # noqa: SLF001


def test_is_font_descriptor_false_when_underneath_not_dict() -> None:
    """``_get_underneath_object`` returns a non-COSDictionary (a
    COSArray) -> hit the trailing ``return False`` (line 970)."""
    assert PDFDebugger._is_font_descriptor(COSArray()) is False  # noqa: SLF001


def test_is_annot_false_when_no_type_key() -> None:
    node = COSDictionary()
    assert PDFDebugger._is_annot(node) is False  # noqa: SLF001


def test_is_annot_false_when_type_mismatches() -> None:
    """Dict with ``/Type /Page`` (not Annot) -> False."""
    node = COSDictionary()
    node.set_name(COSName.TYPE, "Page")
    assert PDFDebugger._is_annot(node) is False  # noqa: SLF001


def test_is_annot_false_when_underneath_not_dict() -> None:
    """COSArray instead of a COSDictionary -> trailing False (line 978)."""
    assert PDFDebugger._is_annot(COSArray()) is False  # noqa: SLF001


# ----------------------------------------------------------------------
# Sanity: ensure module-level platform helper still resolves on Darwin
# ----------------------------------------------------------------------


def test_is_mac_os_matches_sys_platform() -> None:
    assert _pd_debugger._is_mac_os() == (sys.platform == "darwin")


def test_init_global_event_handlers_returns_when_not_mac(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force the ``not _is_mac_os()`` branch (line 501)."""
    monkeypatch.setattr(_pd_debugger, "_is_mac_os", lambda: False)
    # No raise — the method returns immediately on non-mac.
    debugger._init_global_event_handlers()  # noqa: SLF001
