"""Wave 1402 — branch-coverage round-out for ``PDFDebugger``.

Targets the residual partial branches reported by ``--cov-branch`` on
``pypdfbox/debugger/pd_debugger.py``:

* 503->exit, 1825->exit — ``add_recent_file_items`` /
  ``_populate_recent_files_menu`` skip the cascade-state update when
  ``_reopen_menu_index`` is ``None``.
* 797->exit — ``_on_tree_open`` falls through when the only child is
  NOT the sentinel placeholder.
* 838->841 — ``_select_node`` keeps going when the status-bar label
  is absent.
* 971->973 — ``_is_encrypt`` False when the key is non-Encrypt.
* 999->1003 — ``_is_signature`` False when the parent value is not a
  ``COSDictionary``.
* 1097->1099, 1114->1123, 1118->1123, 1120->1123 — ``_show_stream``
  three negative branches around the Image-subtype path.
* 1407->1409 — ``_copy_tree_path`` ignores ``None`` nodes during the
  parent walk.
* 1486->1481 — ``load_configuration`` swallows a separator-free line.
* 1719->1725, 1762->1768, 1798->exit, 1958->1961 — ``_read_pdf_file``,
  ``_read_pdf_url``, ``_enable_document_actions`` and
  ``save_document_to_path`` skip optional steps when their guards fail.

The fixture pattern matches ``test_pd_debugger_wave1339.py``.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.map_entry import MapEntry


def _reset_menu_singletons() -> None:
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu
    from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
    from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
    from pypdfbox.debugger.ui.view_menu import ViewMenu
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
# add_recent_file_items / _populate_recent_files_menu — reopen-index None
# ----------------------------------------------------------------------


def test_add_recent_file_items_skips_cascade_state_when_no_reopen_index(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    """503->exit — when ``_reopen_menu_index`` is ``None`` the cascade
    state update is skipped (cascade itself isn't owned by the file menu)."""
    debugger._reopen_menu_index = None  # noqa: SLF001
    debugger._recent_files.remove_all()  # noqa: SLF001
    path = tmp_path / "alpha.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    debugger._recent_files.add_file(str(path))  # noqa: SLF001
    # Should not raise even with reopen_menu_index None.
    debugger.add_recent_file_items()


def test_populate_recent_files_menu_skips_state_when_no_reopen_index(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    """1825->exit — same skip on the lower-level repopulate helper."""
    debugger._reopen_menu_index = None  # noqa: SLF001
    path = tmp_path / "beta.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    debugger._recent_files.remove_all()  # noqa: SLF001
    debugger._recent_files.add_file(str(path))  # noqa: SLF001
    debugger._populate_recent_files_menu()  # noqa: SLF001


# ----------------------------------------------------------------------
# _on_tree_open — only-child IS NOT a sentinel placeholder
# ----------------------------------------------------------------------


def test_on_tree_open_skips_when_single_child_is_not_sentinel(
    debugger: PDFDebugger,
) -> None:
    """797->exit — when the only child has a real label / node, the
    sentinel-replacement guard is False and we just return."""
    debugger._document = MagicMock()  # noqa: SLF001 - guard at line 790
    tree = debugger._tree  # noqa: SLF001
    parent_iid = tree.insert("", "end", text="parent")
    # Single child with non-"..." text and a registered node, so the
    # if-condition collapses to False on the get_node-is-None clause.
    child_iid = tree.insert(parent_iid, "end", text="real-child")
    tree.register_node(child_iid, MapEntry())
    tree.focus(parent_iid)
    # Should be a no-op (the child must remain).
    debugger._on_tree_open(None)  # type: ignore[arg-type]  # noqa: SLF001
    assert tree.exists(child_iid)


# ----------------------------------------------------------------------
# _select_node — status label absent (line 838 → 841)
# ----------------------------------------------------------------------


def test_select_node_when_status_label_is_none(debugger: PDFDebugger) -> None:
    """838->841 — ``_select_node`` continues past the status-clear step
    when ``get_status_label()`` returns ``None``."""
    sb = debugger._status_bar  # noqa: SLF001

    def _no_label() -> None:
        return None

    # Monkeypatch in-place — we want the real ``_select_node`` body.
    sb.get_status_label = _no_label  # type: ignore[method-assign]
    # XrefEntry triggers the early-return branch in _dispatch_selection
    # and exercises the path past the status-label guard.
    from pypdfbox.debugger.ui.xref_entry import XrefEntry

    node = XrefEntry(0, None, 0, None)
    debugger._dispatch_selection(node, None, "fake_iid", "fake_parent")  # noqa: SLF001


# ----------------------------------------------------------------------
# _is_encrypt — key None / non-Encrypt key (line 971 → 973)
# ----------------------------------------------------------------------


def test_is_encrypt_false_when_key_is_not_encrypt() -> None:
    """971->973 — wrong key → the inner type-check is skipped."""
    me = MapEntry()
    me.set_key(COSName.get_pdf_name("Other"))
    me.set_value(COSDictionary())
    assert PDFDebugger._is_encrypt(me) is False  # noqa: SLF001


def test_is_encrypt_false_when_key_is_none() -> None:
    me = MapEntry()
    me.set_key(None)
    me.set_value(COSDictionary())
    assert PDFDebugger._is_encrypt(me) is False  # noqa: SLF001


# ----------------------------------------------------------------------
# _is_signature — parent value not a COSDictionary (line 999 → 1003)
# ----------------------------------------------------------------------


def test_is_signature_false_when_parent_value_not_dict() -> None:
    """999->1003 — ``parent_value`` is a non-dict ⇒ fall through to
    the trailing ``return False``."""
    node = MapEntry()
    node.set_key(COSName.get_pdf_name("Contents"))
    parent = MapEntry()
    parent.set_value(COSArray())  # not a COSDictionary
    assert PDFDebugger._is_signature(node, parent) is False  # noqa: SLF001


# ----------------------------------------------------------------------
# _show_stream — Image-subtype branch — three negative arrows
#   1097->1099 — page_dict is NOT a COSDictionary
#   1114->1123 — Image subtype but grand_iid is empty (parent is root)
#   1118->1123 — grand_iid resolves to None grand_node
#   1120->1123 — grand_node's underneath isn't a COSDictionary
# ----------------------------------------------------------------------


def _build_show_stream_world(
    debugger: PDFDebugger,
    stream: COSStream,
    *,
    parent_key_name: str | None = None,
    grand_node: Any | None = None,
) -> tuple[MapEntry, MapEntry, str, str]:
    """Insert ``stream`` into the tree under a parent we can shape."""
    tree = debugger._tree  # noqa: SLF001
    # Always-empty grand parent (root) so the topmost iid is "".
    if grand_node is None:
        parent_iid = tree.insert("", "end", text="parent")
    else:
        grand_iid = tree.insert("", "end", text="grand")
        tree.register_node(grand_iid, grand_node)
        parent_iid = tree.insert(grand_iid, "end", text="parent")
    parent_node = MapEntry()
    if parent_key_name is not None:
        parent_node.set_key(COSName.get_pdf_name(parent_key_name))
    parent_node.set_value(COSDictionary())
    tree.register_node(parent_iid, parent_node)
    iid = tree.insert(parent_iid, "end", text="stream")
    node = MapEntry()
    node.set_value(stream)
    tree.register_node(iid, node)
    return node, parent_node, iid, parent_iid


def test_show_stream_contents_key_with_non_dict_grandparent(
    debugger: PDFDebugger,
) -> None:
    """1097->1099 — parent_key is Contents but grand_node's underneath
    isn't a dict, so ``resources_dict`` stays ``None``."""
    stream = COSStream()
    # grand_node is a MapEntry whose value is a non-dict — _get_underneath
    # returns the COSArray, isinstance(COSDictionary) is False.
    grand = MapEntry()
    grand.set_value(COSArray())
    # parent_key=Contents drives the elif branch at line 1090.
    node, _parent_node, iid, parent_iid = _build_show_stream_world(
        debugger, stream, parent_key_name="Contents", grand_node=grand
    )
    debugger._show_stream(node, iid, parent_iid)  # noqa: SLF001


def test_show_stream_neither_form_nor_pattern_nor_thumb_nor_image(
    debugger: PDFDebugger,
) -> None:
    """1114->1123 — stream subtype is unknown (not Form/Pattern/Thumb
    /Image) ⇒ the elif chain collapses to the fall-through."""
    stream = COSStream()
    # No subtype, no type, no PatternType → all guards false.
    node, _parent_node, iid, parent_iid = _build_show_stream_world(
        debugger, stream
    )
    debugger._show_stream(node, iid, parent_iid)  # noqa: SLF001


def test_show_stream_image_subtype_grand_node_none(debugger: PDFDebugger) -> None:
    """1118->1123 — grand_iid exists but no node registered, so
    grand_node resolves to ``None``."""
    stream = COSStream()
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    tree = debugger._tree  # noqa: SLF001
    grand_iid = tree.insert("", "end", text="grand")
    # Intentionally no register_node ⇒ get_node returns None.
    parent_iid = tree.insert(grand_iid, "end", text="parent")
    parent_node = MapEntry()
    parent_node.set_value(COSDictionary())
    tree.register_node(parent_iid, parent_node)
    iid = tree.insert(parent_iid, "end", text="stream")
    node = MapEntry()
    node.set_value(stream)
    tree.register_node(iid, node)
    debugger._show_stream(node, iid, parent_iid)  # noqa: SLF001


def test_show_stream_image_subtype_underneath_not_dict(
    debugger: PDFDebugger,
) -> None:
    """1120->1123 — grand_node exists but its underneath is not a
    ``COSDictionary`` ⇒ resources_dict stays ``None``."""
    stream = COSStream()
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    grand = MapEntry()
    grand.set_value(COSArray())  # non-dict underneath
    node, _parent_node, iid, parent_iid = _build_show_stream_world(
        debugger, stream, grand_node=grand
    )
    debugger._show_stream(node, iid, parent_iid)  # noqa: SLF001


# ----------------------------------------------------------------------
# _copy_tree_path — node walk skips None nodes (line 1407 → 1409)
# ----------------------------------------------------------------------


def test_copy_tree_path_skips_unregistered_nodes(debugger: PDFDebugger) -> None:
    """1407->1409 — ``get_node(parent)`` is ``None`` for an
    intermediate iid; that iteration of the while-loop just continues."""
    tree = debugger._tree  # noqa: SLF001
    # 3-level chain: root → outer (no node) → middle (node) → leaf (node)
    outer_iid = tree.insert("", "end", text="outer")  # no register_node
    middle_iid = tree.insert(outer_iid, "end", text="middle")
    tree.register_node(middle_iid, MapEntry())
    leaf_iid = tree.insert(middle_iid, "end", text="leaf")
    tree.register_node(leaf_iid, MapEntry())
    tree.selection_set(leaf_iid)
    # _document is None ⇒ the early return after the walk fires, but we
    # have already exercised the get_node-None branch by then.
    debugger._copy_tree_path()  # noqa: SLF001


# ----------------------------------------------------------------------
# load_configuration — separator-free line (1486 → 1481)
# ----------------------------------------------------------------------


def test_load_configuration_skips_separator_free_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """1486->1481 — neither ``=`` nor ``:`` ⇒ inner loop exhausts; the
    outer loop carries on to the next line."""
    cfg = tmp_path / "config.properties"
    cfg.write_text("malformed_line_no_separator\nkey=value\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # Reset configuration so the assertion is meaningful.
    PDFDebugger.configuration.clear()
    PDFDebugger.load_configuration()
    # Only the well-formed line should land in configuration.
    assert PDFDebugger.configuration.get("key") == "value"
    assert "malformed_line_no_separator" not in PDFDebugger.configuration


# ----------------------------------------------------------------------
# _read_pdf_file — current_file_path None / starts with http
#   (line 1719 → 1725)
# ----------------------------------------------------------------------


def test_read_pdf_file_skips_recent_files_when_prior_path_is_http(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """1719->1725 — previous _current_file_path startswith('http')
    short-circuits the add-to-recent step."""
    # Simulate a previously loaded http URL with a fake document.
    prior_doc = MagicMock()
    prior_doc.close.return_value = None
    debugger._document = prior_doc  # noqa: SLF001
    debugger._current_file_path = "http://example.com/foo.pdf"  # noqa: SLF001
    target = tmp_path / "x.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    # Patch PDDocument.load so the actual parser isn't exercised.
    fake_doc = MagicMock()
    fake_doc.get_document.return_value = MagicMock(get_trailer=lambda: COSDictionary())
    import pypdfbox.pdmodel as _pm

    monkeypatch.setattr(_pm.PDDocument, "load", lambda *a, **kw: fake_doc)
    add_spy = MagicMock()
    debugger._recent_files.add_file = add_spy  # type: ignore[method-assign]  # noqa: SLF001
    # set_visible suppresses any UI exception path.
    with contextlib.suppress(Exception):
        debugger._read_pdf_file(str(target), "")  # noqa: SLF001
    # Since the previous path was http, no add_file call.
    assert add_spy.call_count == 0


def test_read_pdf_file_when_prior_path_is_none(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """1719->1725 — _current_file_path is None — same outcome."""
    prior_doc = MagicMock()
    prior_doc.close.return_value = None
    debugger._document = prior_doc  # noqa: SLF001
    debugger._current_file_path = None  # noqa: SLF001
    target = tmp_path / "y.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    fake_doc = MagicMock()
    fake_doc.get_document.return_value = MagicMock(get_trailer=lambda: COSDictionary())
    import pypdfbox.pdmodel as _pm

    monkeypatch.setattr(_pm.PDDocument, "load", lambda *a, **kw: fake_doc)
    add_spy = MagicMock()
    debugger._recent_files.add_file = add_spy  # type: ignore[method-assign]  # noqa: SLF001
    with contextlib.suppress(Exception):
        debugger._read_pdf_file(str(target), "")  # noqa: SLF001
    assert add_spy.call_count == 0


# ----------------------------------------------------------------------
# _read_pdf_url — current_file_path startswith 'http' (1762 → 1768)
# ----------------------------------------------------------------------


def test_read_pdf_url_skips_recent_files_when_prior_was_http(
    debugger: PDFDebugger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1762->1768 — same skip as the file-load path for URL loads."""
    prior_doc = MagicMock()
    prior_doc.close.return_value = None
    debugger._document = prior_doc  # noqa: SLF001
    debugger._current_file_path = "http://earlier.example/a.pdf"  # noqa: SLF001
    add_spy = MagicMock()
    debugger._recent_files.add_file = add_spy  # type: ignore[method-assign]  # noqa: SLF001
    # Fake urlopen returning bytes.
    from io import BytesIO

    class _FakeResp:
        def __init__(self, data: bytes) -> None:
            self._b = BytesIO(data)

        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def read(self) -> bytes:
            return self._b.read()

    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda url, **kw: _FakeResp(b"%PDF-1.7\n")
    )
    # Stub PDDocument.load so we never actually parse.
    fake_doc = MagicMock()
    fake_doc.get_document.return_value = MagicMock(get_trailer=lambda: COSDictionary())
    import pypdfbox.pdmodel as _pm

    monkeypatch.setattr(_pm.PDDocument, "load", lambda *a, **kw: fake_doc)
    with contextlib.suppress(Exception):
        debugger._read_pdf_url("http://example.com/x.pdf", "")  # noqa: SLF001
    assert add_spy.call_count == 0


# ----------------------------------------------------------------------
# _enable_document_actions — save_as index is None (line 1798 → exit)
# ----------------------------------------------------------------------


def test_enable_document_actions_skips_save_stream_when_save_as_unset(
    debugger: PDFDebugger,
) -> None:
    """1798->exit — when ``_save_as_menu_index`` is ``None`` the
    Save-decoded/raw block is skipped entirely."""
    debugger._save_as_menu_index = None  # noqa: SLF001
    # Must not raise even though the file menu IS built.
    debugger._enable_document_actions()  # noqa: SLF001


# ----------------------------------------------------------------------
# save_document_to_path — remove_security False branch (1958 → 1961)
# ----------------------------------------------------------------------


def test_save_document_to_path_without_remove_security(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    """1958->1961 — ``remove_security=False`` ⇒ the security-clear
    block is skipped; the save call still runs."""
    fake_doc = MagicMock()
    debugger._document = fake_doc  # noqa: SLF001
    target = tmp_path / "saved.pdf"
    debugger.flush_to_disk(str(target), remove_security=False)
    # Only ``save`` should have been called; security setter should not.
    fake_doc.save.assert_called_once_with(str(target))
    fake_doc.set_all_security_to_be_removed.assert_not_called()
