"""Wave 1354 tail-sweep for the treestatus search-node helper.

Covers the XrefEntry unwrap branch (line 133 in ``tree_status.py``) by
calling ``_search_node`` directly with an :class:`XrefEntry` whose
wrapped :class:`COSObject` resolves to a :class:`COSDictionary`.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSObject, COSObjectKey
from pypdfbox.debugger.treestatus import TreeStatus
from pypdfbox.debugger.ui.xref_entry import XrefEntry


def test_search_node_unwraps_xref_entry() -> None:
    inner = COSDictionary()
    inner.set_item("X", COSInteger.get(99))
    cos_obj = COSObject(20, 0, resolved=inner)
    xe = XrefEntry(0, COSObjectKey(20, 0), 100, cos_obj)
    out = TreeStatus._search_node(xe, "X")  # noqa: SLF001
    assert out is not None
    assert out.get_value().int_value() == 99
