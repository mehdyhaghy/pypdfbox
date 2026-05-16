"""Hand-written tests covering the upstream-named TreeStatus helpers.

Exercises :meth:`TreeStatus.generate_path`,
:meth:`TreeStatus.generate_path_string`, :meth:`TreeStatus.get_object_name`,
:meth:`TreeStatus.parse_path_string` and :meth:`TreeStatus.search_node`
against a small COS dictionary/array tree.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.debugger.treestatus import TreeStatus
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry


def _make_tree() -> COSDictionary:
    """Build a small dictionary tree shared across tests.

    Layout::

        Root (COSDictionary)
          /Root  -> COSDictionary
                      /Foo -> COSArray[ COSInteger(0), COSInteger(1),
                                        COSInteger(2), COSInteger(3) ]
    """
    foo = COSArray()
    for value in range(4):
        foo.add(COSInteger.get(value))
    root_dict = COSDictionary()
    root_dict.set_item("Foo", foo)
    outer = COSDictionary()
    outer.set_item("Root", root_dict)
    return outer


def _make_resolved_path() -> tuple:
    """Return a (root, MapEntry, MapEntry, ArrayEntry) tuple."""
    outer = _make_tree()
    root_entry = MapEntry()
    root_entry.set_key(COSName.get_pdf_name("Root"))
    root_entry.set_value(outer.get_dictionary_object("Root"))
    foo_entry = MapEntry()
    foo_entry.set_key(COSName.get_pdf_name("Foo"))
    foo_entry.set_value(root_entry.get_value().get_dictionary_object("Foo"))
    idx_entry = ArrayEntry()
    idx_entry.set_index(2)
    return outer, root_entry, foo_entry, idx_entry


# ---- generate_path_string ----------------------------------------------------


def test_generate_path_string_canonical_form() -> None:
    """A hand-built path renders as the slash-separated canonical form."""
    outer, root_entry, foo_entry, idx_entry = _make_resolved_path()
    status = TreeStatus(outer)
    rendered = status.generate_path_string((outer, root_entry, foo_entry, idx_entry))
    assert rendered == "Root/Foo/[2]"


def test_generate_path_string_only_root_returns_empty() -> None:
    outer = _make_tree()
    status = TreeStatus(outer)
    assert status.generate_path_string((outer,)) == ""


# ---- parse_path_string -------------------------------------------------------


def test_parse_path_string_canonical_form() -> None:
    parsed = TreeStatus.parse_path_string("Root/Foo/[2]")
    assert parsed == ["Root", "Foo", "2"]


def test_parse_path_string_strips_whitespace() -> None:
    parsed = TreeStatus.parse_path_string(" Root / Foo / [ 2 ] ")
    assert parsed == ["Root", "Foo", "2"]


def test_parse_path_string_empty_segment_returns_none() -> None:
    assert TreeStatus.parse_path_string("Root//Foo") is None


# ---- generate_path -----------------------------------------------------------


def test_generate_path_round_trips_with_generate_path_string() -> None:
    outer = _make_tree()
    status = TreeStatus(outer)
    path = status.generate_path("Root/Foo/[2]")
    assert path is not None
    assert status.generate_path_string(path) == "Root/Foo/[2]"


def test_generate_path_resolves_components() -> None:
    outer = _make_tree()
    status = TreeStatus(outer)
    path = status.generate_path("Root/Foo/[2]")
    assert path is not None
    assert path[0] is outer
    assert isinstance(path[1], MapEntry)
    assert path[1].get_key() == COSName.get_pdf_name("Root")
    assert isinstance(path[2], MapEntry)
    assert path[2].get_key() == COSName.get_pdf_name("Foo")
    assert isinstance(path[3], ArrayEntry)
    assert path[3].get_index() == 2


def test_generate_path_invalid_returns_none() -> None:
    outer = _make_tree()
    status = TreeStatus(outer)
    assert status.generate_path("Root//Foo") is None
    assert status.generate_path("Missing") is None
    assert status.generate_path("Root/Foo/[99]") is None
    assert status.generate_path("Root/Foo/[abc]") is None


# ---- search_node -------------------------------------------------------------


def test_search_node_finds_dictionary_entry() -> None:
    outer = _make_tree()
    out = TreeStatus.search_node(outer, "Root")
    assert isinstance(out, MapEntry)
    assert out.get_key() == COSName.get_pdf_name("Root")


def test_search_node_finds_array_entry() -> None:
    outer = _make_tree()
    foo = outer.get_dictionary_object("Root").get_dictionary_object("Foo")
    out = TreeStatus.search_node(foo, "1")
    assert isinstance(out, ArrayEntry)
    assert out.get_index() == 1


def test_search_node_returns_none_for_unknown_key() -> None:
    outer = _make_tree()
    assert TreeStatus.search_node(outer, "Missing") is None


def test_search_node_returns_none_for_out_of_range_index() -> None:
    outer = _make_tree()
    foo = outer.get_dictionary_object("Root").get_dictionary_object("Foo")
    assert TreeStatus.search_node(foo, "99") is None


# ---- get_object_name ---------------------------------------------------------


def test_get_object_name_map_entry() -> None:
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Foo"))
    assert TreeStatus.get_object_name(entry) == "Foo"


def test_get_object_name_array_entry() -> None:
    entry = ArrayEntry()
    entry.set_index(7)
    assert TreeStatus.get_object_name(entry) == "[7]"


def test_get_object_name_page_entry() -> None:
    from pypdfbox.debugger.ui import DocumentEntry
    from pypdfbox.pdmodel import PDDocument, PDPage

    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        entry = DocumentEntry(doc, "x.pdf")
        page_entry = entry.get_page(0)
        rendered = TreeStatus.get_object_name(page_entry)
        # PageEntry.get_path returns a non-empty identifier.
        assert rendered
    finally:
        doc.close()


def test_get_object_name_xref_entry() -> None:
    from pypdfbox.cos import COSInteger, COSObject, COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry

    cos_obj = COSObject(13, 0, resolved=COSInteger(0))
    xe = XrefEntry(0, COSObjectKey(13, 0), 100, cos_obj)
    rendered = TreeStatus.get_object_name(xe)
    assert rendered  # truthy


def test_get_object_name_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        TreeStatus.get_object_name(object())


# ---- search_node convenience for status-string round trips -------------------


def test_search_node_helper_finds_correct_node_via_path_string() -> None:
    """End-to-end: build a path string, resolve to nodes, and verify the
    last component is the expected leaf."""
    outer = _make_tree()
    status = TreeStatus(outer)
    path = status.generate_path("Root/Foo/[3]")
    assert path is not None
    leaf = path[-1]
    assert isinstance(leaf, ArrayEntry)
    assert leaf.get_index() == 3


def test_search_node_helper_returns_none_for_missing_path() -> None:
    outer = _make_tree()
    status = TreeStatus(outer)
    assert status.generate_path("Root/Foo/[7]") is None
    assert status.generate_path("Root/NotThere") is None
