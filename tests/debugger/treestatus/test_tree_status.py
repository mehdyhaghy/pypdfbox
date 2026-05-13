"""Hand-written tests for :class:`pypdfbox.debugger.treestatus.TreeStatus`."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.debugger.treestatus import TreeStatus
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry


def _make_doc() -> COSDictionary:
    """Build a tiny dictionary tree used by every test below.

    Layout::

        Root (COSDictionary)
          /Foo  -> COSDictionary
                     /Bar -> COSArray[ COSInteger(7), COSInteger(8) ]
    """
    inner = COSArray()
    inner.add(COSInteger.get(7))
    inner.add(COSInteger.get(8))
    foo = COSDictionary()
    foo.set_item("Bar", inner)
    root = COSDictionary()
    root.set_item("Foo", foo)
    return root


def test_get_string_for_path_with_dict_and_array_entries() -> None:
    root = _make_doc()
    foo_entry = MapEntry()
    foo_entry.set_key(COSName.get_pdf_name("Foo"))
    foo_entry.set_value(root.get_dictionary_object("Foo"))
    bar_entry = MapEntry()
    bar_entry.set_key(COSName.get_pdf_name("Bar"))
    bar_entry.set_value(foo_entry.get_value().get_dictionary_object("Bar"))
    idx_entry = ArrayEntry()
    idx_entry.set_index(1)

    status = TreeStatus(root)
    assert (
        status.get_string_for_path((root, foo_entry, bar_entry, idx_entry))
        == "Foo/Bar/[1]"
    )


def test_get_string_for_path_with_only_root() -> None:
    root = _make_doc()
    status = TreeStatus(root)
    assert status.get_string_for_path((root,)) == ""


def test_get_path_for_string_resolves_round_trip() -> None:
    root = _make_doc()
    status = TreeStatus(root)
    path = status.get_path_for_string("Foo/Bar/[1]")
    assert path is not None
    # First component is the root, last is the array entry at index 1.
    assert path[0] is root
    assert isinstance(path[1], MapEntry)
    assert path[1].get_key() == COSName.get_pdf_name("Foo")
    assert isinstance(path[2], MapEntry)
    assert path[2].get_key() == COSName.get_pdf_name("Bar")
    assert isinstance(path[3], ArrayEntry)
    assert path[3].get_index() == 1


def test_round_trip_string_for_resolved_path() -> None:
    root = _make_doc()
    status = TreeStatus(root)
    path = status.get_path_for_string("Foo/Bar/[1]")
    assert status.get_string_for_path(path) == "Foo/Bar/[1]"


def test_get_path_for_invalid_string_returns_none() -> None:
    root = _make_doc()
    status = TreeStatus(root)
    # Empty node segment.
    assert status.get_path_for_string("Foo//Bar") is None
    # Unknown dictionary key.
    assert status.get_path_for_string("Missing") is None
    # Array index out of range.
    assert status.get_path_for_string("Foo/Bar/[99]") is None
    # Non-numeric array index.
    assert status.get_path_for_string("Foo/Bar/[abc]") is None


def test_parse_path_string_accepts_whitespace() -> None:
    root = _make_doc()
    status = TreeStatus(root)
    path = status.get_path_for_string(" Foo / Bar / [ 0 ] ")
    assert path is not None
    assert isinstance(path[-1], ArrayEntry)
    assert path[-1].get_index() == 0


def test_unknown_node_type_raises() -> None:
    status = TreeStatus(_make_doc())
    with pytest.raises(ValueError):
        # ``_get_object_name`` should reject random types.
        status.get_string_for_path((object(), object()))


def test_map_entry_with_null_key_renders_blank_segment() -> None:
    """A ``MapEntry`` whose key was never set should render as an empty
    string in the path. Mirrors upstream's tolerant behaviour."""
    null_entry = MapEntry()  # no set_key call → key is None
    status = TreeStatus(_make_doc())
    result = status.get_string_for_path((_make_doc(), null_entry))
    # Empty key produces an empty segment, which trims to "".
    assert result == ""


def test_page_entry_path_component() -> None:
    """A ``PageEntry`` exposes its own path string."""
    from pypdfbox.debugger.ui import DocumentEntry
    from pypdfbox.pdmodel import PDDocument, PDPage

    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        entry = DocumentEntry(doc, "x.pdf")
        page_entry = entry.get_page(0)
        status = TreeStatus(entry)
        rendered = status.get_string_for_path((entry, page_entry))
        # PageEntry's get_path returns a non-empty identifier.
        assert rendered  # truthy
    finally:
        doc.close()


def test_xref_entry_path_component() -> None:
    """An ``XrefEntry`` likewise contributes a non-empty path component."""
    from pypdfbox.cos import COSInteger, COSObject, COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry

    cos_obj = COSObject(13, 0, resolved=COSInteger(0))
    xe = XrefEntry(0, COSObjectKey(13, 0), 100, cos_obj)
    status = TreeStatus(_make_doc())
    rendered = status.get_string_for_path((_make_doc(), xe))
    assert rendered  # truthy


def test_resolution_through_xref_entry_unwraps_cos_object() -> None:
    """``_search_node`` follows an :class:`XrefEntry` → :class:`COSObject`
    chain so paths that start at a cross-reference can keep navigating."""
    from pypdfbox.cos import COSDictionary, COSInteger, COSObject

    inner_dict = COSDictionary()
    inner_dict.set_item("X", COSInteger(99))
    # COSObject wrapping the dict to exercise the unwrap branch.
    cos_obj = COSObject(20, 0, resolved=inner_dict)
    # Search inside a COSObject's resolved dict.
    out = TreeStatus._search_node(cos_obj, "X")  # noqa: SLF001
    assert out is not None
    assert out.get_value().int_value() == 99
