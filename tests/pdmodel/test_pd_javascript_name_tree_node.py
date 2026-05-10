"""Hand-written tests for ``PDJavascriptNameTreeNode``.

Covers the typed ``convert_cos_to_pd`` / ``convertCOSToPD`` factory and
the inherited generic name-tree behaviour as exercised through the
JavaScript-action subclass.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_javascript_name_tree_node import (
    PDJavascriptNameTreeNode,
)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_ACTION: COSName = COSName.get_pdf_name("Action")
_S: COSName = COSName.get_pdf_name("S")
_JS: COSName = COSName.get_pdf_name("JS")
_JAVASCRIPT: COSName = COSName.get_pdf_name("JavaScript")


def _js_action(body: str) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _ACTION)
    d.set_item(_S, _JAVASCRIPT)
    d.set_string(_JS, body)
    return d


def test_convert_cos_to_pd_returns_js_body() -> None:
    """``convert_cos_to_pd`` mirrors upstream's typed
    ``convertCOSToPD`` (Java line 51-58 in PDJavascriptNameTreeNode).
    pypdfbox exposes the raw JS body string instead of a typed
    PDActionJavaScript wrapper (CHANGES.md)."""
    tree = PDJavascriptNameTreeNode()
    action = _js_action("alert('hi')")
    assert tree.convert_cos_to_pd(action) == "alert('hi')"


def test_convert_cos_to_pd_rejects_non_dictionary() -> None:
    """Upstream throws IOException when the leaf isn't a COSDictionary;
    pypdfbox surfaces that as OSError."""
    tree = PDJavascriptNameTreeNode()
    with pytest.raises(OSError):
        tree.convert_cos_to_pd(COSInteger.get(1))


def test_set_names_round_trips() -> None:
    tree = PDJavascriptNameTreeNode()
    tree.set_names({"hello": "console.log('a')", "world": "console.log('b')"})
    names = tree.get_names()
    assert names is not None
    assert names["hello"] == "console.log('a')"
    assert names["world"] == "console.log('b')"


def test_create_child_node_returns_same_type() -> None:
    tree = PDJavascriptNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDJavascriptNameTreeNode)


def test_round_trip_via_existing_cos_dictionary() -> None:
    arr = COSArray()
    arr.add(COSString("greet"))
    arr.add(_js_action("alert('boo')"))
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Names"), arr)
    tree = PDJavascriptNameTreeNode(raw)
    assert tree.get_value("greet") == "alert('boo')"
