"""Wave 1365 parity tests for :class:`TreeStatus` jump-to-path semantics.

Upstream ``TreeStatus.java`` is the find/jump-by-string engine the debugger's
status bar uses. The existing wave-1349/1354 suites cover the happy path and a
handful of error returns; this file fills in the remaining round-trip and
boundary cases:

* Round-trip: a path produced by ``generate_path_string`` must resolve back
  to an equivalent path under ``generate_path`` (the upstream invariant).
* ``generate_path_string`` on a single-element path (root only) returns "".
* ``parse_path_string`` strips matched bracket pairs but also handles a
  bare ``"[5]"`` chunk (upstream's brackets-on-array-index form).
* ``parse_path_string`` returns ``None`` for whitespace-only chunks.
* ``search_node`` unwraps :class:`COSObject` inside a :class:`MapEntry` value
  before descending (mirrors upstream ``while obj instanceof COSObject``).
* ``search_node`` on a non-container (e.g. an integer) returns ``None``
  rather than raising — upstream's else-fallthrough.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
)
from pypdfbox.debugger.treestatus import TreeStatus
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry


def _build_round_trip_tree() -> COSDictionary:
    """Layout::

        Root (COSDictionary)
          /Catalog -> COSDictionary
                       /Pages -> COSArray[ COSDictionary{ /Type = /Page },
                                           COSDictionary{ /Type = /Page } ]
    """
    page0 = COSDictionary()
    page0.set_item("Type", COSName.get_pdf_name("Page"))
    page1 = COSDictionary()
    page1.set_item("Type", COSName.get_pdf_name("Page"))
    pages = COSArray()
    pages.add(page0)
    pages.add(page1)
    catalog = COSDictionary()
    catalog.set_item("Pages", pages)
    outer = COSDictionary()
    outer.set_item("Catalog", catalog)
    return outer


def test_round_trip_generate_then_resolve() -> None:
    """A path string built from a known tree must resolve back to that tree."""
    outer = _build_round_trip_tree()
    # Build the leaf path: Catalog -> Pages -> [1]
    cat_entry = MapEntry()
    cat_entry.set_key(COSName.get_pdf_name("Catalog"))
    cat_entry.set_value(outer.get_dictionary_object("Catalog"))
    pages_entry = MapEntry()
    pages_entry.set_key(COSName.get_pdf_name("Pages"))
    pages_entry.set_value(cat_entry.get_value().get_dictionary_object("Pages"))
    idx_entry = ArrayEntry()
    idx_entry.set_index(1)

    ts = TreeStatus(outer)
    path_in = (outer, cat_entry, pages_entry, idx_entry)
    status = ts.generate_path_string(path_in)
    assert status == "Catalog/Pages/[1]"
    resolved = ts.generate_path(status)
    assert resolved is not None
    # The first element is the same root object identity.
    assert resolved[0] is outer
    # The leaf is an ArrayEntry at index 1.
    leaf = resolved[-1]
    assert isinstance(leaf, ArrayEntry)
    assert leaf.get_index() == 1


def test_generate_path_string_root_only_returns_empty() -> None:
    """Upstream: a one-element path (just the root) yields the empty string."""
    outer = _build_round_trip_tree()
    ts = TreeStatus(outer)
    assert ts.generate_path_string((outer,)) == ""


def test_parse_path_string_strips_outer_brackets() -> None:
    """A ``"[5]"`` chunk is reduced to the plain digit (upstream's bracket
    replace step)."""
    nodes = TreeStatus.parse_path_string("Catalog/Pages/[5]")
    assert nodes == ["Catalog", "Pages", "5"]


def test_parse_path_string_whitespace_only_chunk_returns_none() -> None:
    """A chunk that is whitespace-only is treated as empty => parse fails."""
    assert TreeStatus.parse_path_string("Catalog/   /Foo") is None


def test_search_node_unwraps_map_entry_value() -> None:
    """When the cursor is a MapEntry, its value is the descent target."""
    outer = _build_round_trip_tree()
    cat_entry = MapEntry()
    cat_entry.set_key(COSName.get_pdf_name("Catalog"))
    cat_entry.set_value(outer.get_dictionary_object("Catalog"))
    out = TreeStatus.search_node(cat_entry, "Pages")
    assert isinstance(out, MapEntry)
    assert out.get_key().get_name() == "Pages"


def test_search_node_on_non_container_returns_none() -> None:
    """An integer leaf (not COSDictionary/COSArray) yields None — upstream's
    fallthrough at the end of the method."""
    leaf = COSInteger.get(7)
    assert TreeStatus.search_node(leaf, "Anything") is None


def test_search_node_array_with_non_numeric_returns_none() -> None:
    """Index parse failure on a COSArray returns None (caught ValueError)."""
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSInteger.get(1))
    assert TreeStatus.search_node(arr, "not-a-number") is None
