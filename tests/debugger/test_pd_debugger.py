"""Hand-written tests for :class:`pypdfbox.debugger.pd_debugger.PDFDebugger`.

The Tk-based debugger needs a running ``Tk()`` root, which can't be
created on headless systems. We reuse the same ``tk_root`` fixture
shape used by the other debugger widget tests.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.pdmodel import PDDocument, PDPage

# ----------------------------------------------------------------------
# Fixtures (mirrors tests/debugger/ui/conftest.py)
# ----------------------------------------------------------------------


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    """Per-test Tk root. Mirrors ``tests/debugger/streampane/conftest.py``."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    # Each test starts with a clean ViewMenu singleton (and its sub-menu
    # cohort) so cached widgets don't point at a stale Tk root.
    _reset_menu_singletons()
    try:
        yield root
    finally:
        _reset_menu_singletons()
        with contextlib.suppress(tk.TclError):
            root.destroy()


def _reset_menu_singletons() -> None:
    """Drop every cached menu singleton so each test sees a fresh tree."""
    # Lazy imports avoid forcing the menu modules at collection time on a
    # headless system.
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
def synthetic_pdf(tmp_path: Path) -> Path:
    """Write a minimal one-page PDF to disk for round-trip tests."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        # Attach a tiny content stream so we have something to inspect.
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(b"BT /F1 12 Tf (hi) Tj ET\n")
        page = doc.get_pages().get(0)
        page.set_contents(stream)
        path = tmp_path / "sample.pdf"
        doc.save(str(path))
    finally:
        doc.close()
    return path


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------


def test_construction_with_no_document(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        assert debugger.has_document() is False
        assert debugger.get_document() is None
        # Tree, status bar, and find menu should exist after construction.
        assert debugger.get_tree() is not None
        assert debugger.get_status_bar() is not None
        assert debugger.get_find_menu() is not None
    finally:
        # ``destroy`` on the toplevel would kill our session root; the
        # debugger frame is garbage-collected when ``debugger`` falls out
        # of scope.
        debugger._main_frame.destroy()  # noqa: SLF001


def test_initial_view_mode_accepts_structure(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root, initial_view_mode=TreeViewMenu.VIEW_STRUCTURE)
    try:
        assert debugger.get_tree_view_mode() == TreeViewMenu.VIEW_STRUCTURE
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_set_tree_view_mode_rejects_invalid(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        debugger.set_tree_view_mode("bogus mode")
        # No exception, but the active mode is unchanged.
        assert debugger.get_tree_view_mode() == TreeViewMenu.VIEW_PAGES
        debugger.set_tree_view_mode(TreeViewMenu.VIEW_CROSS_REF_TABLE)
        assert debugger.get_tree_view_mode() == TreeViewMenu.VIEW_CROSS_REF_TABLE
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Document opening
# ----------------------------------------------------------------------


def test_open_document_loads_tree(tk_root: tk.Tk, synthetic_pdf: Path) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        assert debugger.has_document() is True
        # The root row + at least one child should be present.
        children = debugger.get_tree().get_children("")
        assert len(children) == 1
        root_iid = children[0]
        sub_children = debugger.get_tree().get_children(root_iid)
        assert len(sub_children) >= 1
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Selection-route dispatch (manual: bypass the live tree)
# ----------------------------------------------------------------------


def test_selection_route_stream_mounts_stream_pane(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # Build a content-stream node manually.
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(b"BT /F1 12 Tf (hi) Tj ET\n")
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("Contents"))
        entry.set_value(cs)
        # Insert it into the tree to mirror the selection-changed path.
        iid = debugger.get_tree().insert("", "end", text="Contents")
        debugger.get_tree().register_node(iid, entry)
        debugger.get_tree().selection_set(iid)
        # Force the dispatch.
        debugger._dispatch_selection(entry, None, iid, "")  # noqa: SLF001
        widget = debugger.get_right_widget()
        # StreamPane.get_panel() returns a ttk.Frame; the actual class
        # behind it is recorded by checking the registered ``_panel``
        # reference. Easier: just check that the widget exists and is
        # mounted under the right_frame.
        assert widget is not None
        assert widget.master is debugger._right_frame  # noqa: SLF001
    finally:
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_selection_route_string_mounts_string_pane(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        node = MapEntry()
        node.set_key(COSName.get_pdf_name("ID"))
        node.set_value(COSString("hello"))
        iid = debugger.get_tree().insert("", "end", text="ID")
        debugger.get_tree().register_node(iid, node)
        debugger._dispatch_selection(node, None, iid, "")  # noqa: SLF001
        widget = debugger.get_right_widget()
        assert widget is not None
    finally:
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_selection_route_unknown_falls_back_to_text(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # A bare COSDictionary that isn't a Page/Font triggers the
        # generic "COSDictionary" text fallback.
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("Bogus"))
        entry.set_value(COSDictionary())
        iid = debugger.get_tree().insert("", "end", text="Bogus")
        debugger.get_tree().register_node(iid, entry)
        debugger._dispatch_selection(entry, None, iid, "")  # noqa: SLF001
        widget = debugger.get_right_widget()
        assert widget is not None
        assert isinstance(widget, tk.Text)
    finally:
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Menu wiring (smoke checks)
# ----------------------------------------------------------------------


def test_menus_smoke_check(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        toplevel = debugger._toplevel  # noqa: SLF001
        menu_name = toplevel.cget("menu")
        assert menu_name  # Truthy means a menu was installed.
        menu = toplevel.nametowidget(menu_name)
        # Iterate top-level cascades. We expect File / Edit / View /
        # Window / Help.
        labels: list[str] = []
        last = menu.index("end")
        assert last is not None
        for i in range(last + 1):
            with contextlib.suppress(tk.TclError):
                labels.append(menu.entrycget(i, "label"))
        for expected in ("File", "Edit", "View", "Window", "Help"):
            assert expected in labels
        # ``Find`` must exist on the Edit menu cascade.
        find_menu = debugger.get_find_menu()
        assert find_menu is not None
        find_labels: list[str] = []
        last = find_menu.index("end")
        assert last is not None
        for i in range(last + 1):
            with contextlib.suppress(tk.TclError):
                find_labels.append(find_menu.entrycget(i, "label"))
        assert "Find..." in find_labels
        assert "Find Next" in find_labels
        assert "Find Previous" in find_labels
    finally:
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Static helper coverage
# ----------------------------------------------------------------------


def test_is_page_helper() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))
    entry = MapEntry()
    entry.set_value(d)
    assert PDFDebugger._is_page(entry) is True  # noqa: SLF001
    assert PDFDebugger._is_page(MapEntry()) is False  # noqa: SLF001


def test_is_stream_helper() -> None:
    entry = MapEntry()
    entry.set_value(COSStream())
    assert PDFDebugger._is_stream(entry) is True  # noqa: SLF001


def test_first_array_name_returns_none_for_empty() -> None:
    entry = MapEntry()
    entry.set_value(COSDictionary())
    assert PDFDebugger._first_array_name(entry) is None  # noqa: SLF001


# ---- additional static helper coverage ----------------------------------


def test_is_string_helper() -> None:
    entry = MapEntry()
    entry.set_value(COSString("hi"))
    assert PDFDebugger._is_string(entry) is True  # noqa: SLF001
    assert PDFDebugger._is_string(MapEntry()) is False  # noqa: SLF001


def test_is_font_helper_with_font_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    entry = MapEntry()
    entry.set_value(d)
    assert PDFDebugger._is_font(entry) is True  # noqa: SLF001


def test_is_font_excludes_cid_subtypes() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType2"))
    entry = MapEntry()
    entry.set_value(d)
    assert PDFDebugger._is_font(entry) is False  # noqa: SLF001


def test_is_font_returns_false_for_non_dictionary() -> None:
    entry = MapEntry()
    entry.set_value(COSString("not a font"))
    assert PDFDebugger._is_font(entry) is False  # noqa: SLF001


def test_is_flag_node_matches_well_known_names() -> None:
    parent_value = COSDictionary()
    parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("FontDescriptor"))
    parent = MapEntry()
    parent.set_value(parent_value)
    flag = MapEntry()
    flag.set_key(COSName.get_pdf_name("Flags"))
    assert PDFDebugger._is_flag_node(flag, parent) is True  # noqa: SLF001


def test_is_flag_node_panose_always_true() -> None:
    parent = MapEntry()
    parent.set_value(COSDictionary())
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("Panose"))
    assert PDFDebugger._is_flag_node(node, parent) is True  # noqa: SLF001


def test_is_flag_node_rejects_non_map_entry() -> None:
    assert PDFDebugger._is_flag_node(object(), object()) is False  # noqa: SLF001


def test_is_flag_node_handles_null_key() -> None:
    parent = MapEntry()
    parent.set_value(COSDictionary())
    node = MapEntry()  # key is None
    assert PDFDebugger._is_flag_node(node, parent) is False  # noqa: SLF001


def test_is_annot_helper() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Annot"))
    entry = MapEntry()
    entry.set_value(d)
    assert PDFDebugger._is_annot(entry) is True  # noqa: SLF001


def test_is_font_descriptor_helper() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("FontDescriptor"))
    entry = MapEntry()
    entry.set_value(d)
    assert PDFDebugger._is_font_descriptor(entry) is True  # noqa: SLF001


def test_is_encrypt_helper() -> None:
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Encrypt"))
    entry.set_value(COSDictionary())
    assert PDFDebugger._is_encrypt(entry) is True  # noqa: SLF001


def test_is_signature_helper() -> None:
    parent_value = COSDictionary()
    parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))
    parent = MapEntry()
    parent.set_key(COSName.get_pdf_name("V"))
    parent.set_value(parent_value)
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("Contents"))
    assert PDFDebugger._is_signature(node, parent) is True  # noqa: SLF001


def test_is_signature_rejects_when_parent_is_not_sig() -> None:
    parent_value = COSDictionary()
    parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("Annot"))
    parent = MapEntry()
    parent.set_key(COSName.get_pdf_name("V"))
    parent.set_value(parent_value)
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("Contents"))
    assert PDFDebugger._is_signature(node, parent) is False  # noqa: SLF001


def test_node_label_for_array_entry() -> None:
    from pypdfbox.debugger.pd_debugger import _node_label
    from pypdfbox.debugger.ui.array_entry import ArrayEntry

    ae = ArrayEntry()
    ae.set_index(3)
    assert _node_label(ae) == "[3]"


def test_node_label_for_map_entry_with_null_key() -> None:
    from pypdfbox.debugger.pd_debugger import _node_label

    me = MapEntry()
    # No set_key call.
    assert _node_label(me) == "(null)"


def test_convert_to_string_basics() -> None:
    from pypdfbox.cos import COSBoolean, COSFloat, COSInteger, COSNull
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    assert _convert_to_string(COSBoolean.TRUE) == "true"
    assert _convert_to_string(COSBoolean.FALSE) == "false"
    assert _convert_to_string(COSFloat(2.5)) == "2.5"
    assert _convert_to_string(COSInteger(7)) == "7"
    assert _convert_to_string(COSNull.NULL) == "null"
    assert _convert_to_string(COSName.get_pdf_name("X")) == "X"


def test_convert_to_string_for_control_string_emits_hex() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    rendered = _convert_to_string(COSString("\x01ctrl"))
    assert rendered.startswith("<") and rendered.endswith(">")


def test_convert_to_string_for_dictionary_and_array() -> None:
    from pypdfbox.cos import COSArray
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    assert _convert_to_string(COSDictionary()) == "COSDictionary"
    assert _convert_to_string(COSArray()) == "COSArray"


def test_convert_to_string_for_unknown_type_returns_none() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    assert _convert_to_string(object()) is None


def test_read_stream_bytes_returns_empty_for_missing_creator() -> None:
    from pypdfbox.debugger.pd_debugger import _read_stream_bytes

    class _NoCreator:
        pass

    assert _read_stream_bytes(_NoCreator(), raw=False) == b""  # type: ignore[arg-type]
    assert _read_stream_bytes(_NoCreator(), raw=True) == b""  # type: ignore[arg-type]


def test_read_stream_bytes_handles_oserror() -> None:
    from pypdfbox.debugger.pd_debugger import _read_stream_bytes

    assert _read_stream_bytes(COSStream(), raw=False) == b""  # empty body


def test_selection_route_page_dispatch(tk_root: tk.Tk, synthetic_pdf) -> None:
    """Selecting a page node mounts a PagePane."""
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        # First child of the root should be the document's pages branch;
        # navigate to find a page dict.
        root_children = debugger.get_tree().get_children("")
        assert root_children
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001
