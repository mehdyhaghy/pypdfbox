"""Wave 1402 — branch-coverage round-out for the debugger ``Tree``.

Targets the residual partial branches in
``pypdfbox/debugger/ui/tree.py``:

* 54->exit — ``init(row_height=None)`` ⇒ the row-height branch is False.
* 108->117 — single-filter stream ⇒ skip the partial-decode items.
* 165->164 — ``_get_filters_for_stream`` array entry is NOT a COSName
  ⇒ continue past without appending.
* 312->314 — ``_compute_tree_path`` walks past an iid with no
  registered node.
* 369->371 — ``_read_stream_partial`` finds a stream whose
  ``get_filters`` returns neither a COSName nor a COSArray.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from pypdfbox.cos import COSArray, COSName, COSStream, COSString
from pypdfbox.debugger.ui import Tree
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.tree import _read_stream_partial


def test_init_with_none_row_height_is_noop(tk_root: tk.Tk) -> None:
    """54->exit — ``init(None)`` skips the row-height branch."""
    tree = Tree(tk_root)
    before = tree._row_height  # noqa: SLF001
    tree.init(row_height=None)
    assert tree._row_height == before  # noqa: SLF001


def test_build_menu_items_skips_partial_decode_for_single_filter(
    tk_root: tk.Tk,
) -> None:
    """Single filter ⇒ no partial-decode items but the Save Raw Stream
    line is still emitted (covers the inner ``len(filters) >= 2`` arm)."""
    stream = COSStream()
    stream.set_item("Filter", COSName.FLATE_DECODE)
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("S"))
    entry.set_value(stream)
    items = tree.build_menu_items(entry, (entry,))
    labels = [label for label, _ in items]
    # The Save Raw Stream entry is present...
    assert any("Save Raw Stream" in label for label in labels)
    # ...but no "Partial Decode" / "Partially Decode" entry was added.
    assert not any("artial" in label for label in labels)


def test_build_menu_items_when_stream_has_no_filters(tk_root: tk.Tk) -> None:
    """108->117 — empty filter list ⇒ ``if filters:`` is False, skip
    both partial-decode and Save Raw Stream entries."""
    stream = COSStream()  # no /Filter set
    tree = Tree(tk_root)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("S"))
    entry.set_value(stream)
    items = tree.build_menu_items(entry, (entry,))
    labels = [label for label, _ in items]
    # No raw-stream entry and no partial-decode entries — the whole
    # ``if filters:`` block is skipped.
    assert not any("Save Raw Stream" in label for label in labels)
    assert not any("artial" in label for label in labels)


def test_get_filters_for_stream_array_with_non_name_entry() -> None:
    """165->164 — array entry that isn't a COSName is skipped."""
    stream = COSStream()
    chain = COSArray()
    chain.add(COSName.get_pdf_name("ASCIIHexDecode"))
    chain.add(COSString("not-a-name"))  # ⇒ skip
    chain.add(COSName.get_pdf_name("FlateDecode"))
    stream.set_item("Filter", chain)
    assert Tree._get_filters_for_stream(stream) == [  # noqa: SLF001
        "ASCIIHexDecode",
        "FlateDecode",
    ]


def test_compute_tree_path_skips_unregistered_nodes(tk_root: tk.Tk) -> None:
    """312->314 — walking parents past an iid with no registered node
    just continues; only registered nodes land in the chain."""
    tree = Tree(tk_root)
    outer_iid = tree.insert("", "end", text="outer")  # no register_node
    inner_iid = tree.insert(outer_iid, "end", text="inner")
    me = MapEntry()
    tree.register_node(inner_iid, me)
    path = tree._compute_tree_path(inner_iid)  # noqa: SLF001
    # Only the registered node lands in the chain.
    assert path == (me,)


def test_read_stream_partial_when_filters_neither_name_nor_array() -> None:
    """369->371 — stream's ``get_filters`` returns ``None`` (e.g. no
    /Filter at all) ⇒ neither branch fires, ``filters`` stays empty,
    and ``stop_filters`` ends up empty."""

    class _Stream:
        # Bare stream-like object.
        def get_filters(self) -> Any:
            return None

        def create_input_stream(self, _stop: list[str] | None = None) -> Any:
            return b"raw-bytes"

    # Cast to COSStream-shaped duck.
    result = _read_stream_partial(_Stream(), stop_index=0)  # type: ignore[arg-type]
    assert result == b"raw-bytes"
