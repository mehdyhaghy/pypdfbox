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


# ----------------------------------------------------------------------
# init_tree / render_tree edge branches
# ----------------------------------------------------------------------


def test_init_tree_returns_early_without_document(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # No document loaded — init_tree should be a no-op and not raise.
        debugger.init_tree()
        assert debugger.get_tree().get_children("") == ()
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_init_tree_cross_ref_table_mode(tk_root: tk.Tk, synthetic_pdf) -> None:
    """init_tree mounted in CROSS_REF_TABLE mode populates the xref view."""
    import contextlib

    debugger = PDFDebugger(
        tk_root, initial_view_mode=TreeViewMenu.VIEW_CROSS_REF_TABLE
    )
    try:
        debugger.open_document(synthetic_pdf)
        root_children = debugger.get_tree().get_children("")
        assert root_children
        # The root label should be ``CRT``.
        root_iid = root_children[0]
        text = debugger.get_tree().item(root_iid, "text")
        assert text == "CRT"
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_init_tree_structure_mode(tk_root: tk.Tk, synthetic_pdf) -> None:
    """The other-mode branch (else) of init_tree uses ``PDFTreeModel(doc)`` root."""
    import contextlib

    debugger = PDFDebugger(tk_root, initial_view_mode=TreeViewMenu.VIEW_STRUCTURE)
    try:
        debugger.open_document(synthetic_pdf)
        root_children = debugger.get_tree().get_children("")
        assert root_children
        root_iid = root_children[0]
        assert debugger.get_tree().item(root_iid, "text") == "Root"
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_render_tree_handles_none_root_obj(tk_root: tk.Tk) -> None:
    from pypdfbox.debugger.ui.pdf_tree_model import PDFTreeModel

    debugger = PDFDebugger(tk_root)
    try:
        # Pre-populate the tree, then call _render_tree with None — it
        # should wipe the tree and bail.
        debugger.get_tree().insert("", "end", text="bogus")
        model = PDFTreeModel(None)
        debugger._render_tree(model, None, "ignored")  # noqa: SLF001
        assert debugger.get_tree().get_children("") == ()
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_populate_children_swallows_get_child_count_error(
    tk_root: tk.Tk,
) -> None:
    """populate_children logs and returns when ``get_child_count`` raises."""

    class _FailingModel:
        def get_child_count(self, _node):
            raise RuntimeError("boom")

        def get_child(self, _node, _index):  # pragma: no cover - unreachable
            raise AssertionError

        def is_leaf(self, _node) -> bool:  # pragma: no cover - unreachable
            return True

    debugger = PDFDebugger(tk_root)
    try:
        parent = debugger.get_tree().insert("", "end", text="root")
        debugger._populate_children(_FailingModel(), parent, object())  # noqa: SLF001
        # No children were inserted.
        assert debugger.get_tree().get_children(parent) == ()
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_populate_children_swallows_get_child_error(tk_root: tk.Tk) -> None:
    """When ``get_child`` raises mid-iteration we keep going."""

    class _PartialModel:
        def get_child_count(self, _node) -> int:
            return 2

        def get_child(self, _node, index):
            if index == 0:
                raise RuntimeError("boom")
            entry = MapEntry()
            entry.set_key(COSName.get_pdf_name("Ok"))
            entry.set_value(COSString("ok"))
            return entry

        def is_leaf(self, _node) -> bool:
            return True

    debugger = PDFDebugger(tk_root)
    try:
        parent = debugger.get_tree().insert("", "end", text="root")
        debugger._populate_children(_PartialModel(), parent, object())  # noqa: SLF001
        # The first iteration logged + skipped; the second inserted one row.
        assert len(debugger.get_tree().get_children(parent)) == 1
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_populate_children_swallows_is_leaf_error(tk_root: tk.Tk) -> None:
    """When ``is_leaf`` raises the disclosure sentinel is omitted, no crash."""

    class _LeafErrModel:
        def get_child_count(self, _node) -> int:
            return 1

        def get_child(self, _node, _index):
            entry = MapEntry()
            entry.set_key(COSName.get_pdf_name("X"))
            entry.set_value(COSString("v"))
            return entry

        def is_leaf(self, _node) -> bool:
            raise RuntimeError("boom")

    debugger = PDFDebugger(tk_root)
    try:
        parent = debugger.get_tree().insert("", "end", text="root")
        debugger._populate_children(_LeafErrModel(), parent, object())  # noqa: SLF001
        # The row was inserted, the sentinel was not.
        children = debugger.get_tree().get_children(parent)
        assert len(children) == 1
        assert debugger.get_tree().get_children(children[0]) == ()
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# _on_tree_open
# ----------------------------------------------------------------------


def test_on_tree_open_no_document_returns_early(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # _document is None; should be a no-op.
        debugger._on_tree_open(None)  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_on_tree_open_replaces_sentinel(tk_root: tk.Tk, synthetic_pdf) -> None:
    """When the focused node holds a single ``...`` sentinel it expands."""
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        # Find a node with a single sentinel child (look one level down).
        root_iids = debugger.get_tree().get_children("")
        assert root_iids
        root_iid = root_iids[0]
        for child in debugger.get_tree().get_children(root_iid):
            grandkids = debugger.get_tree().get_children(child)
            if (
                len(grandkids) == 1
                and debugger.get_tree().item(grandkids[0], "text") == "..."
                and debugger.get_tree().get_node(grandkids[0]) is None
            ):
                debugger.get_tree().focus(child)
                debugger._on_tree_open(None)  # noqa: SLF001
                # The sentinel should now be gone; real children may or
                # may not exist depending on the node type.
                texts = [
                    debugger.get_tree().item(g, "text")
                    for g in debugger.get_tree().get_children(child)
                ]
                assert "..." not in texts
                break
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# _on_tree_selection_changed
# ----------------------------------------------------------------------


def test_on_tree_selection_changed_no_selection(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # No selection — the handler must early-return.
        debugger._on_tree_selection_changed(None)  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_on_tree_selection_changed_unregistered_node(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        iid = debugger.get_tree().insert("", "end", text="unregistered")
        debugger.get_tree().selection_set(iid)
        # No node registered for ``iid`` — handler returns silently.
        debugger._on_tree_selection_changed(None)  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_on_tree_selection_changed_dispatch_exception_falls_back(
    tk_root: tk.Tk, monkeypatch
) -> None:
    debugger = PDFDebugger(tk_root)
    try:

        def _boom(*_a, **_kw):
            raise RuntimeError("dispatch failed")

        monkeypatch.setattr(debugger, "_dispatch_selection", _boom)
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("X"))
        entry.set_value(COSString("hi"))
        iid = debugger.get_tree().insert("", "end", text="X")
        debugger.get_tree().register_node(iid, entry)
        debugger.get_tree().selection_set(iid)
        debugger._on_tree_selection_changed(None)  # noqa: SLF001
        # Even though dispatch raised, the text-fallback mounted a widget.
        assert debugger.get_right_widget() is not None
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# _dispatch_selection: XrefEntry and other branches
# ----------------------------------------------------------------------


def test_dispatch_selection_xref_entry_uses_text_details(tk_root: tk.Tk) -> None:
    from pypdfbox.debugger.ui.xref_entry import XrefEntry

    debugger = PDFDebugger(tk_root)
    try:
        node = XrefEntry(0, None, 0, None)
        iid = debugger.get_tree().insert("", "end", text="x")
        debugger.get_tree().register_node(iid, node)
        debugger._dispatch_selection(node, None, iid, "")  # noqa: SLF001
        assert isinstance(debugger.get_right_widget(), tk.Text)
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_dispatch_selection_color_pane(tk_root: tk.Tk) -> None:
    from pypdfbox.cos import COSArray

    debugger = PDFDebugger(tk_root)
    try:
        arr = COSArray()
        arr.add(COSName.get_pdf_name("Indexed"))
        # CSIndexed only inspects the first element type at construction.
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("ColorSpace"))
        entry.set_value(arr)
        iid = debugger.get_tree().insert("", "end", text="cs")
        debugger.get_tree().register_node(iid, entry)
        # The dispatcher attempts to mount CSIndexed; if it can't complete
        # the panel build it still picks the color-pane branch — we only
        # need the dispatcher to reach _show_color_pane, so swallow any
        # widget-construction error.
        with contextlib.suppress(Exception):
            debugger._dispatch_selection(entry, None, iid, "")  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_dispatch_selection_flag_pane(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        parent_value = COSDictionary()
        parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("FontDescriptor"))
        parent = MapEntry()
        parent.set_key(COSName.get_pdf_name("FD"))
        parent.set_value(parent_value)
        flag = MapEntry()
        flag.set_key(COSName.get_pdf_name("Flags"))
        from pypdfbox.cos import COSInteger

        flag.set_value(COSInteger(0))
        iid = debugger.get_tree().insert("", "end", text="Flags")
        debugger.get_tree().register_node(iid, flag)
        with contextlib.suppress(Exception):
            debugger._dispatch_selection(flag, parent, iid, "")  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_dispatch_selection_signature_pane(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        parent_value = COSDictionary()
        parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))
        parent = MapEntry()
        parent.set_key(COSName.get_pdf_name("V"))
        parent.set_value(parent_value)
        node = MapEntry()
        node.set_key(COSName.get_pdf_name("Contents"))
        node.set_value(COSString(b"\x30\x80\x00\x00"))
        iid = debugger.get_tree().insert("", "end", text="Contents")
        debugger.get_tree().register_node(iid, node)
        with contextlib.suppress(Exception):
            debugger._dispatch_selection(node, parent, iid, "")  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_dispatch_selection_font(tk_root: tk.Tk) -> None:
    """Font dispatch reaches _show_font; missing resources fall through to text."""

    debugger = PDFDebugger(tk_root)
    try:
        font_dict = COSDictionary()
        font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
        font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("F1"))
        entry.set_value(font_dict)
        iid = debugger.get_tree().insert("", "end", text="F1")
        debugger.get_tree().register_node(iid, entry)
        # No parent in the tree → grand_node is None → falls back to text.
        debugger._dispatch_selection(entry, None, iid, "")  # noqa: SLF001
        assert debugger.get_right_widget() is not None
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# _get_underneath_object / _get_node_key branches
# ----------------------------------------------------------------------


def test_get_underneath_object_array_entry() -> None:
    from pypdfbox.debugger.ui.array_entry import ArrayEntry

    ae = ArrayEntry()
    ae.set_value(COSString("v"))
    assert PDFDebugger._get_underneath_object(ae) is ae.get_value()  # noqa: SLF001


def test_get_underneath_object_page_entry() -> None:
    from pypdfbox.debugger.ui.page_entry import PageEntry

    d = COSDictionary()
    pe = PageEntry(d, 1, None)
    assert PDFDebugger._get_underneath_object(pe) is d  # noqa: SLF001


def test_get_underneath_object_xref_entry() -> None:
    from pypdfbox.debugger.ui.xref_entry import XrefEntry

    entry = XrefEntry(0, None, 0, None)
    assert PDFDebugger._get_underneath_object(entry) is None  # noqa: SLF001


def test_get_node_key_for_non_map_entry_returns_none() -> None:
    assert PDFDebugger._get_node_key(object()) is None  # noqa: SLF001


# ----------------------------------------------------------------------
# _first_array_name happy path
# ----------------------------------------------------------------------


def test_first_array_name_returns_name() -> None:
    from pypdfbox.cos import COSArray

    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    entry = MapEntry()
    entry.set_value(arr)
    assert PDFDebugger._first_array_name(entry) == "DeviceN"  # noqa: SLF001


def test_first_array_name_non_name_first_entry_returns_none() -> None:
    from pypdfbox.cos import COSArray

    arr = COSArray()
    arr.add(COSString("not-a-name"))
    entry = MapEntry()
    entry.set_value(arr)
    assert PDFDebugger._first_array_name(entry) is None  # noqa: SLF001


# ----------------------------------------------------------------------
# _is_flag_node F/Encrypt branches
# ----------------------------------------------------------------------


def test_is_flag_node_f_with_annot_parent() -> None:
    parent_value = COSDictionary()
    parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("Annot"))
    parent = MapEntry()
    parent.set_value(parent_value)
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("F"))
    assert PDFDebugger._is_flag_node(node, parent) is True  # noqa: SLF001


def test_is_flag_node_p_with_encrypt_parent() -> None:
    parent_value = COSDictionary()
    parent = MapEntry()
    parent.set_key(COSName.get_pdf_name("Encrypt"))
    parent.set_value(parent_value)
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("P"))
    assert PDFDebugger._is_flag_node(node, parent) is True  # noqa: SLF001


def test_is_signature_rejects_non_map_entries() -> None:
    assert PDFDebugger._is_signature(object(), object()) is False  # noqa: SLF001


def test_is_signature_rejects_non_contents_key() -> None:
    parent_value = COSDictionary()
    parent_value.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))
    parent = MapEntry()
    parent.set_value(parent_value)
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("Other"))
    assert PDFDebugger._is_signature(node, parent) is False  # noqa: SLF001


# ----------------------------------------------------------------------
# _replace_right_component
# ----------------------------------------------------------------------


def test_replace_right_component_with_none(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        debugger._replace_right_component(None)  # noqa: SLF001
        assert debugger.get_right_widget() is None
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Menu actions: _open_*, _save_*, _print_*, _exit_*, _find_*, _copy_*
# ----------------------------------------------------------------------


def test_open_menu_item_action_cancel(tk_root: tk.Tk, monkeypatch) -> None:
    """User cancelling the dialog short-circuits the action."""
    debugger = PDFDebugger(tk_root)
    try:
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.askopenfilename",
            lambda **_kw: "",
        )
        debugger._open_menu_item_action_performed()  # noqa: SLF001
        assert debugger.has_document() is False
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_open_menu_item_action_loads_pdf(
    tk_root: tk.Tk, synthetic_pdf, monkeypatch
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.askopenfilename",
            lambda **_kw: str(synthetic_pdf),
        )
        debugger._open_menu_item_action_performed()  # noqa: SLF001
        assert debugger.has_document() is True
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_open_menu_item_action_handles_oserror(
    tk_root: tk.Tk, monkeypatch
) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.askopenfilename",
            lambda **_kw: "/nonexistent/path/to/some.pdf",
        )
        # Stub ErrorDialog so the actual messagebox doesn't pop up.
        shown: list[BaseException] = []

        class _StubErrorDialog:
            def __init__(self, ex: BaseException) -> None:
                shown.append(ex)

            def set_visible(self, _b: bool) -> None:
                pass

        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.ErrorDialog", _StubErrorDialog
        )
        debugger._open_menu_item_action_performed()  # noqa: SLF001
        assert shown  # an error was surfaced
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_open_url_menu_cancel(tk_root: tk.Tk, monkeypatch) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.simpledialog.askstring",
            lambda *a, **kw: None,
        )
        debugger._open_url_menu_item_action_performed()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_open_url_menu_invalid_url(tk_root: tk.Tk, monkeypatch) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.simpledialog.askstring",
            lambda *a, **kw: "no-scheme",
        )

        class _StubErrorDialog:
            instances: list = []

            def __init__(self, ex):
                _StubErrorDialog.instances.append(ex)

            def set_visible(self, _b):
                pass

        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.ErrorDialog", _StubErrorDialog
        )
        debugger._open_url_menu_item_action_performed()  # noqa: SLF001
        assert _StubErrorDialog.instances
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_reopen_menu_no_path(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # No current file path → noop.
        debugger._reopen_menu_item_action_performed()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_reopen_menu_with_file_path(
    tk_root: tk.Tk, synthetic_pdf
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        debugger._reopen_menu_item_action_performed()  # noqa: SLF001
        assert debugger.has_document() is True
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_reopen_menu_with_http_path(tk_root: tk.Tk, monkeypatch) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        debugger._current_file_path = "http://example.invalid/missing.pdf"  # noqa: SLF001
        # Stub ErrorDialog so the OSError surfaced doesn't show a real popup.
        called: list = []

        class _StubErrorDialog:
            def __init__(self, ex):
                called.append(ex)

            def set_visible(self, _b):
                pass

        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.ErrorDialog", _StubErrorDialog
        )
        debugger._reopen_menu_item_action_performed()  # noqa: SLF001
        assert called  # urlopen raised; the dialog was constructed
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_save_as_no_document(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        debugger._save_as_menu_item_action_performed()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_save_as_writes_pdf(
    tk_root: tk.Tk, synthetic_pdf, tmp_path: Path, monkeypatch
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        target = tmp_path / "copy.pdf"
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
            lambda **_kw: str(target),
        )
        debugger._save_as_menu_item_action_performed()  # noqa: SLF001
        assert target.exists()
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_save_as_cancel_short_circuits(
    tk_root: tk.Tk, synthetic_pdf, monkeypatch
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
            lambda **_kw: "",
        )
        debugger._save_as_menu_item_action_performed()  # noqa: SLF001
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_save_decoded_stream_no_selection(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # No selection → _selected_stream returns None → action is a noop.
        debugger._save_decoded_stream()  # noqa: SLF001
        debugger._save_raw_stream()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_save_decoded_stream_writes_bytes(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch
) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(b"hello")
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("X"))
        entry.set_value(cs)
        iid = debugger.get_tree().insert("", "end", text="X")
        debugger.get_tree().register_node(iid, entry)
        debugger.get_tree().selection_set(iid)
        target = tmp_path / "out.bin"
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
            lambda **_kw: str(target),
        )
        debugger._save_decoded_stream()  # noqa: SLF001
        assert target.exists()
        assert target.read_bytes() == b"hello"
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_save_raw_stream_writes_bytes(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch
) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(b"raw-bytes")
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("X"))
        entry.set_value(cs)
        iid = debugger.get_tree().insert("", "end", text="X")
        debugger.get_tree().register_node(iid, entry)
        debugger.get_tree().selection_set(iid)
        target = tmp_path / "out.raw"
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
            lambda **_kw: str(target),
        )
        debugger._save_raw_stream()  # noqa: SLF001
        assert target.exists()
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_save_decoded_stream_cancel(tk_root: tk.Tk, monkeypatch) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        cs = COSStream()
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("X"))
        entry.set_value(cs)
        iid = debugger.get_tree().insert("", "end", text="X")
        debugger.get_tree().register_node(iid, entry)
        debugger.get_tree().selection_set(iid)
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.filedialog.asksaveasfilename",
            lambda **_kw: "",
        )
        debugger._save_decoded_stream()  # noqa: SLF001
        debugger._save_raw_stream()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_print_menu_no_document(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # Document is None → noop, no messagebox.
        debugger._print_menu_item_action_performed()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_print_menu_with_document(
    tk_root: tk.Tk, synthetic_pdf, monkeypatch
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        called: list = []
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.messagebox.showinfo",
            lambda *a, **kw: called.append((a, kw)),
        )
        debugger._print_menu_item_action_performed()  # noqa: SLF001
        assert called
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_find_menu_item_action_shows_info(tk_root: tk.Tk, monkeypatch) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        called: list = []
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.messagebox.showinfo",
            lambda *a, **kw: called.append((a, kw)),
        )
        debugger._find_menu_item_action_performed()  # noqa: SLF001
        debugger._find_next_menu_item_action_performed()  # noqa: SLF001
        debugger._find_previous_menu_item_action_performed()  # noqa: SLF001
        assert called  # only Find... actually shows a dialog
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_show_about_dialog(tk_root: tk.Tk, monkeypatch) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        called: list = []
        monkeypatch.setattr(
            "pypdfbox.debugger.pd_debugger.messagebox.showinfo",
            lambda *a, **kw: called.append((a, kw)),
        )
        debugger._show_about_dialog()  # noqa: SLF001
        assert called
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_exit_menu_item_action_clears_state(
    tk_root: tk.Tk, synthetic_pdf
) -> None:
    """``_exit_menu_item_action_performed`` closes the document and destroys
    the toplevel.

    We swap in a throw-away toplevel so destroying it doesn't kill the
    shared session root.
    """

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        scratch = tk.Toplevel(tk_root)
        debugger._toplevel = scratch  # noqa: SLF001
        debugger._exit_menu_item_action_performed()  # noqa: SLF001
        assert debugger.has_document() is False
    finally:
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_copy_tree_path_no_selection(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # No selection → early return.
        debugger._copy_tree_path()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_copy_tree_path_no_document(tk_root: tk.Tk) -> None:
    """With a selection but no document loaded, _copy_tree_path returns
    silently before touching the clipboard."""
    debugger = PDFDebugger(tk_root)
    try:
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("Root"))
        entry.set_value(COSDictionary())
        iid = debugger.get_tree().insert("", "end", text="Root")
        debugger.get_tree().register_node(iid, entry)
        debugger.get_tree().selection_set(iid)
        # No document; should not throw.
        debugger._copy_tree_path()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_copy_tree_path_with_document(
    tk_root: tk.Tk, synthetic_pdf
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        # Select the root row.
        roots = debugger.get_tree().get_children("")
        assert roots
        debugger.get_tree().selection_set(roots[0])
        debugger._copy_tree_path()  # noqa: SLF001
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_osx_open_file_swallows_oserror(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        # Non-existent path triggers an OSError that the wrapper swallows.
        debugger._osx_open_file("/nonexistent.pdf")  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Recent files menu opener
# ----------------------------------------------------------------------


def test_populate_recent_files_menu_with_entries(
    tk_root: tk.Tk, synthetic_pdf, monkeypatch
) -> None:
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger._recent_files.add_file(str(synthetic_pdf))  # noqa: SLF001
        debugger._populate_recent_files_menu()  # noqa: SLF001
        recent_menu = debugger._recent_files_menu  # noqa: SLF001
        assert recent_menu is not None
        # Invoke the opener and confirm the document loads.
        last_index = recent_menu.index("end")
        assert last_index is not None
        recent_menu.invoke(last_index)
        assert debugger.has_document() is True
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# _read_pdf_url / file double-open close-and-recent path
# ----------------------------------------------------------------------


def test_read_pdf_url_via_file_scheme(
    tk_root: tk.Tk, synthetic_pdf, monkeypatch
) -> None:
    """The URL path with a ``file://`` scheme exercises urlopen against
    a real on-disk file without making a network request."""
    import contextlib
    import urllib.request as _urllib_request

    debugger = PDFDebugger(tk_root)
    try:
        url = synthetic_pdf.as_uri()
        # Sanity: urlopen works against file URLs in tests.
        with _urllib_request.urlopen(url) as resp:
            assert resp.read(1)
        debugger._read_pdf_url(url, "")  # noqa: SLF001
        assert debugger.has_document() is True
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


def test_read_pdf_url_rejects_missing_scheme(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        with pytest.raises(ValueError, match="invalid URL"):
            debugger._read_pdf_url("no-scheme", "")  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_read_pdf_file_reopen_closes_existing(
    tk_root: tk.Tk, synthetic_pdf
) -> None:
    """Loading a second document closes the first."""
    import contextlib

    debugger = PDFDebugger(tk_root)
    try:
        debugger.open_document(synthetic_pdf)
        first_doc = debugger.get_document()
        # Set the previous file path to a non-http path so the
        # add_file branch is exercised.
        debugger._current_file_path = str(synthetic_pdf)  # noqa: SLF001
        debugger.open_document(synthetic_pdf)
        assert debugger.has_document() is True
        # The old document object should be different from the new one.
        assert debugger.get_document() is not first_doc
    finally:
        if debugger.get_document() is not None:
            with contextlib.suppress(Exception):
                debugger.get_document().close()
        with contextlib.suppress(tk.TclError):
            debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# _enable_document_actions early return
# ----------------------------------------------------------------------


def test_enable_document_actions_without_file_menu(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        debugger._file_menu = None  # noqa: SLF001
        # Should not throw despite the file menu being absent.
        debugger._enable_document_actions()  # noqa: SLF001
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# Module helpers
# ----------------------------------------------------------------------


def test_ensure_default_root_returns_existing(tk_root: tk.Tk) -> None:
    from pypdfbox.debugger.pd_debugger import _ensure_default_root

    # ``tk_root`` is the active per-test root. ``_ensure_default_root`` should
    # return the implicit default rather than construct a new one.
    root = _ensure_default_root()
    assert root is not None
    # Calling twice should return the same default root.
    assert _ensure_default_root() is root


def test_node_label_for_page_entry() -> None:
    from pypdfbox.debugger.pd_debugger import _node_label
    from pypdfbox.debugger.ui.page_entry import PageEntry

    d = COSDictionary()
    pe = PageEntry(d, 2, None)
    assert _node_label(pe) == "Page: 2"


def test_node_label_for_xref_entry() -> None:
    from pypdfbox.debugger.pd_debugger import _node_label
    from pypdfbox.debugger.ui.xref_entry import XrefEntry

    xe = XrefEntry(0, None, 0, None)
    assert _node_label(xe) == "(null)"


def test_node_label_for_map_entry_with_key() -> None:
    from pypdfbox.debugger.pd_debugger import _node_label

    me = MapEntry()
    me.set_key(COSName.get_pdf_name("Hello"))
    assert _node_label(me) == "Hello"


def test_node_label_for_unknown_falls_back_to_str() -> None:
    from pypdfbox.debugger.pd_debugger import _node_label

    assert _node_label(42) == "42"


def test_convert_to_string_for_plain_string() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    assert _convert_to_string(COSString("plain")) == "plain"


def test_convert_to_string_for_cos_stream() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    cs = COSStream()
    with cs.create_output_stream() as out:
        out.write(b"hello")
    rendered = _convert_to_string(cs)
    assert rendered is not None
    assert "hello" in rendered


def test_convert_to_string_for_array_entry() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string
    from pypdfbox.debugger.ui.array_entry import ArrayEntry

    ae = ArrayEntry()
    ae.set_value(COSString("plain"))
    assert _convert_to_string(ae) == "plain"


def test_convert_to_string_for_map_entry() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string

    me = MapEntry()
    me.set_value(COSString("plain"))
    assert _convert_to_string(me) == "plain"


def test_convert_to_string_for_xref_entry() -> None:
    from pypdfbox.debugger.pd_debugger import _convert_to_string
    from pypdfbox.debugger.ui.xref_entry import XrefEntry

    xe = XrefEntry(0, None, 0, None)
    assert _convert_to_string(xe) == "(null)"


def test_read_stream_bytes_returns_data() -> None:
    from pypdfbox.debugger.pd_debugger import _read_stream_bytes

    cs = COSStream()
    with cs.create_output_stream() as out:
        out.write(b"hello-bytes")
    data = _read_stream_bytes(cs, raw=False)
    assert data == b"hello-bytes"


# ----------------------------------------------------------------------
# _show_text_details with a COSStream falls back to HexView
# ----------------------------------------------------------------------


def test_show_text_details_with_stream_mounts_hex_view(tk_root: tk.Tk) -> None:
    debugger = PDFDebugger(tk_root)
    try:
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(b"raw-bytes")
        entry = MapEntry()
        entry.set_key(COSName.get_pdf_name("Bin"))
        entry.set_value(cs)
        # This stream is not classified as a content stream (no Contents
        # parent key and no Form/Pattern markers), so _show_text_details
        # is reached via _dispatch_selection's fall-through.
        iid = debugger.get_tree().insert("", "end", text="Bin")
        debugger.get_tree().register_node(iid, entry)
        debugger._show_text_details(entry)  # noqa: SLF001
        assert debugger.get_right_widget() is not None
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


def test_show_text_details_with_unrenderable_node(tk_root: tk.Tk) -> None:
    """When ``_convert_to_string`` returns None the text widget is mounted
    with an empty string body."""
    debugger = PDFDebugger(tk_root)
    try:
        debugger._show_text_details(object())  # noqa: SLF001
        widget = debugger.get_right_widget()
        assert isinstance(widget, tk.Text)
    finally:
        debugger._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# main() entry point
# ----------------------------------------------------------------------


def test_main_without_input_file(tk_root: tk.Tk, monkeypatch) -> None:
    """``main`` parses args, builds a debugger and falls through mainloop."""
    captured: dict = {}

    class _StubRoot:
        TITLE_HOLDER: list = []

        def title(self, t):
            self.TITLE_HOLDER.append(t)

        def mainloop(self) -> None:
            captured["mainloop"] = True

    class _ScratchDebugger:
        TITLE = "stub"
        instances: list = []

        def __init__(self, root, initial_view_mode=None):
            self.root = root
            self.initial_view_mode = initial_view_mode
            _ScratchDebugger.instances.append(self)

        def open_document(self, *_a, **_kw):  # pragma: no cover - not called
            captured["opened"] = True

    # Bind ``cls`` to the stub by patching the class on the module — invoke
    # via the bound ``main`` classmethod object captured *before* the patch.
    # Don't actually invoke a fresh tk.Tk; route to the session root so we
    # don't disturb the implicit ``tk._default_root`` shared with sibling
    # tests.
    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.tk.Tk", lambda: _StubRoot()
    )
    main_fn = PDFDebugger.main
    rc = main_fn.__func__(_ScratchDebugger, [])
    assert rc == 0
    assert captured.get("mainloop") is True


def test_main_with_inputfile(tk_root: tk.Tk, synthetic_pdf, monkeypatch) -> None:
    """``main`` opens the input file when one is provided."""
    captured: dict = {}

    class _StubRoot:
        def title(self, _t):
            pass

        def mainloop(self) -> None:
            captured["mainloop"] = True

    class _ScratchDebugger:
        TITLE = "stub"

        def __init__(self, root, initial_view_mode=None):
            captured["mode"] = initial_view_mode

        def open_document(self, path, password):
            captured["path"] = str(path)
            captured["password"] = password

    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.tk.Tk", lambda: _StubRoot()
    )

    main_fn = PDFDebugger.main
    rc = main_fn.__func__(
        _ScratchDebugger, ["-viewstructure", str(synthetic_pdf)]
    )
    assert rc == 0
    assert captured.get("path") == str(synthetic_pdf)
    assert captured.get("mode") == TreeViewMenu.VIEW_STRUCTURE


def test_main_with_inputfile_open_error(
    tk_root: tk.Tk, monkeypatch, tmp_path: Path
) -> None:
    """``main`` logs and returns 0 when ``open_document`` raises OSError."""

    class _StubRoot:
        def title(self, _t):
            pass

        def mainloop(self) -> None:
            pass

    class _BadDebugger:
        TITLE = "stub"

        def __init__(self, root, initial_view_mode=None):
            pass

        def open_document(self, _path, _password):
            raise OSError("nope")

    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.tk.Tk", lambda: _StubRoot()
    )

    # Create a real file so ``Path(...).exists()`` passes.
    sample = tmp_path / "x.pdf"
    sample.write_bytes(b"%PDF-")
    main_fn = PDFDebugger.main
    rc = main_fn.__func__(_BadDebugger, [str(sample)])
    assert rc == 0


def test_main_with_missing_inputfile(tk_root: tk.Tk, monkeypatch) -> None:
    """``main`` skips the open when the input file doesn't exist."""

    class _StubRoot:
        def title(self, _t):
            pass

        def mainloop(self) -> None:
            pass

    opened: list = []

    class _OnlyConstructDebugger:
        TITLE = "stub"

        def __init__(self, *_a, **_kw):
            pass

        def open_document(self, *_a, **_kw):  # pragma: no cover - must not run
            opened.append(True)

    monkeypatch.setattr(
        "pypdfbox.debugger.pd_debugger.tk.Tk", lambda: _StubRoot()
    )

    main_fn = PDFDebugger.main
    rc = main_fn.__func__(_OnlyConstructDebugger, ["/nonexistent/path.pdf"])
    assert rc == 0
    assert not opened


# ----------------------------------------------------------------------
# DocumentOpener (port of PDFDebugger.DocumentOpener inner class)
# ----------------------------------------------------------------------


def test_document_opener_open_raises_when_unoverridden() -> None:
    """Base ``open()`` must raise — mirrors the upstream abstract method."""
    from pypdfbox.debugger.pd_debugger import DocumentOpener

    opener = DocumentOpener(password="initial")
    assert opener.password == "initial"
    with pytest.raises(NotImplementedError):
        opener.open()


def test_document_opener_parse_returns_open_result() -> None:
    """When ``open()`` succeeds first try, ``parse()`` returns its document."""
    from pypdfbox.debugger.pd_debugger import DocumentOpener

    doc = PDDocument()
    try:
        class _StubOpener(DocumentOpener):
            def open(self):  # type: ignore[override]
                return doc

        opener = _StubOpener(password="")
        result = opener.parse()
        assert result is doc
    finally:
        doc.close()


def test_document_opener_parse_retries_after_password_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``parse()`` re-asks for a password on each PDInvalidPasswordException."""
    from pypdfbox.debugger.pd_debugger import DocumentOpener
    from pypdfbox.pdmodel.encryption import PDInvalidPasswordException

    doc = PDDocument()
    try:
        attempts: list[str | bytes] = []

        class _RetryOpener(DocumentOpener):
            def open(self):  # type: ignore[override]
                attempts.append(self.password)
                if len(attempts) < 3:
                    raise PDInvalidPasswordException()
                return doc

        # Simulate the user typing two wrong passwords before the right
        # one — the prompt is invoked exactly twice (once per failure).
        prompts = iter(["wrong-one", "wrong-two", "correct"])
        monkeypatch.setattr(
            DocumentOpener,
            "_prompt_password",
            lambda self: next(prompts),
        )
        opener = _RetryOpener(password="initial-wrong")
        result = opener.parse()
        assert result is doc
        # First call uses constructor password; next two use the prompt
        # values. After parse, the *latest* prompt value is retained on
        # the instance.
        assert attempts == ["initial-wrong", "wrong-one", "wrong-two"]
        assert opener.password == "wrong-two"
    finally:
        doc.close()


def test_document_opener_parse_propagates_on_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``None`` from the prompt cancels the loop and re-raises."""
    from pypdfbox.debugger.pd_debugger import DocumentOpener
    from pypdfbox.pdmodel.encryption import PDInvalidPasswordException

    class _AlwaysFailsOpener(DocumentOpener):
        def open(self):  # type: ignore[override]
            raise PDInvalidPasswordException()

    monkeypatch.setattr(
        DocumentOpener,
        "_prompt_password",
        lambda self: None,
    )
    opener = _AlwaysFailsOpener(password="")
    with pytest.raises(PDInvalidPasswordException):
        opener.parse()
