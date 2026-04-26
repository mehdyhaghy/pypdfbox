from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString
from pypdfbox.pdmodel.pd_alternate_presentations_name_tree_node import (
    PDAlternatePresentationsNameTreeNode,
)
from pypdfbox.pdmodel.pd_ids_name_tree_node import PDIDSNameTreeNode
from pypdfbox.pdmodel.pd_pages_name_tree_node import PDPagesNameTreeNode
from pypdfbox.pdmodel.pd_renditions_name_tree_node import PDRenditionsNameTreeNode
from pypdfbox.pdmodel.pd_templates_name_tree_node import PDTemplatesNameTreeNode
from pypdfbox.pdmodel.pd_urls_name_tree_node import PDURLSNameTreeNode

# ---------- /Pages ----------


def test_pages_name_tree_round_trip() -> None:
    tree = PDPagesNameTreeNode()
    page = COSDictionary()
    tree.set_names({"cover": page})

    fetched = tree.get_value("cover")
    assert isinstance(fetched, COSDictionary)
    assert fetched is page


def test_pages_create_child_node_returns_same_type() -> None:
    tree = PDPagesNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDPagesNameTreeNode)


# ---------- /Templates ----------


def test_templates_name_tree_round_trip() -> None:
    tree = PDTemplatesNameTreeNode()
    tpl = COSDictionary()
    tree.set_names({"tpl1": tpl})

    fetched = tree.get_value("tpl1")
    assert isinstance(fetched, COSDictionary)
    assert fetched is tpl


def test_templates_create_child_node_returns_same_type() -> None:
    tree = PDTemplatesNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDTemplatesNameTreeNode)


# ---------- /IDS ----------


def test_ids_name_tree_round_trip_bytes() -> None:
    tree = PDIDSNameTreeNode()
    payload = b"\x00\x01\x02digital-id\xff"
    tree.set_names({"doc1": payload})

    fetched = tree.get_value("doc1")
    assert isinstance(fetched, bytes)
    assert fetched == payload


def test_ids_value_to_cos_packs_as_cos_string() -> None:
    tree = PDIDSNameTreeNode()
    cos = tree.convert_value_to_cos(b"abc")
    assert isinstance(cos, COSString)
    assert cos.get_bytes() == b"abc"


def test_ids_create_child_node_returns_same_type() -> None:
    tree = PDIDSNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDIDSNameTreeNode)


# ---------- /URLS ----------


def test_urls_name_tree_round_trip() -> None:
    tree = PDURLSNameTreeNode()
    alias = COSDictionary()
    tree.set_names({"home-url": alias})

    fetched = tree.get_value("home-url")
    assert isinstance(fetched, COSDictionary)
    assert fetched is alias


def test_urls_create_child_node_returns_same_type() -> None:
    tree = PDURLSNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDURLSNameTreeNode)


# ---------- /AlternatePresentations ----------


def test_alternate_presentations_name_tree_round_trip() -> None:
    tree = PDAlternatePresentationsNameTreeNode()
    show = COSDictionary()
    tree.set_names({"slideshow1": show})

    fetched = tree.get_value("slideshow1")
    assert isinstance(fetched, COSDictionary)
    assert fetched is show


def test_alternate_presentations_create_child_node_returns_same_type() -> None:
    tree = PDAlternatePresentationsNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDAlternatePresentationsNameTreeNode)


# ---------- /Renditions ----------


def test_renditions_name_tree_round_trip() -> None:
    tree = PDRenditionsNameTreeNode()
    rend = COSDictionary()
    tree.set_names({"video1": rend})

    fetched = tree.get_value("video1")
    assert isinstance(fetched, COSDictionary)
    assert fetched is rend


def test_renditions_create_child_node_returns_same_type() -> None:
    tree = PDRenditionsNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDRenditionsNameTreeNode)


# ---------- shared sanity: /Names array layout matches base class ----------


def test_pages_set_names_writes_cos_array_pairs() -> None:
    tree = PDPagesNameTreeNode()
    a = COSDictionary()
    b = COSDictionary()
    tree.set_names({"a": a, "b": b})
    arr = tree.get_cos_object().get_dictionary_object("Names")
    assert isinstance(arr, COSArray)
    assert arr.size() == 4
