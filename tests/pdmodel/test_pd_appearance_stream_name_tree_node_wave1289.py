"""``/Names /AP`` typed name-tree wrapper (Wave 1289).

Covers :class:`PDAppearanceStreamNameTreeNode` and the
:py:meth:`PDDocumentNameDictionary.get_ap` typed accessor that replaces
the previous raw-COSDictionary placeholder.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream_name_tree_node import (
    PDAppearanceStreamNameTreeNode,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary


def _make_appearance_stream() -> COSStream:
    """Build a minimal appearance-stream backing COSStream."""
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    return stream


def _leaf_node(name: str, stream: COSStream) -> COSDictionary:
    """Wrap ``name -> stream`` as a name-tree leaf dictionary."""
    leaf = COSDictionary()
    names = COSArray()
    names.add(COSString(name.encode("ascii")))
    names.add(stream)
    leaf.set_item(COSName.get_pdf_name("Names"), names)
    return leaf


def test_convert_cos_to_value_wraps_appearance_stream() -> None:
    stream = _make_appearance_stream()
    node = PDAppearanceStreamNameTreeNode()
    wrapped = node.convert_cos_to_value(stream)
    assert isinstance(wrapped, PDAppearanceStream)
    assert wrapped.get_cos_object() is stream


def test_convert_cos_to_value_rejects_non_stream() -> None:
    node = PDAppearanceStreamNameTreeNode()
    with pytest.raises(OSError):
        node.convert_cos_to_value(COSDictionary())


def test_convert_value_to_cos_returns_backing_stream() -> None:
    stream = _make_appearance_stream()
    node = PDAppearanceStreamNameTreeNode()
    val = PDAppearanceStream(stream)
    assert node.convert_value_to_cos(val) is stream


def test_create_child_node_returns_same_type() -> None:
    parent = PDAppearanceStreamNameTreeNode()
    child = parent.create_child_node(COSDictionary())
    assert isinstance(child, PDAppearanceStreamNameTreeNode)


def test_document_name_dictionary_get_ap_returns_typed_wrapper() -> None:
    names = COSDictionary()
    stream = _make_appearance_stream()
    ap_dict = _leaf_node("Sig1", stream)
    names.set_item(COSName.get_pdf_name("AP"), ap_dict)

    nd = PDDocumentNameDictionary(names=names)
    ap = nd.get_ap()
    assert isinstance(ap, PDAppearanceStreamNameTreeNode)
    # The wrapper points at the same backing dictionary.
    assert ap.get_cos_object() is ap_dict


def test_document_name_dictionary_get_ap_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary(names=COSDictionary())
    assert nd.get_ap() is None


def test_document_name_dictionary_set_ap_round_trip() -> None:
    nd = PDDocumentNameDictionary(names=COSDictionary())
    stream = _make_appearance_stream()
    ap_dict = _leaf_node("Sig1", stream)
    wrapper = PDAppearanceStreamNameTreeNode(ap_dict)
    nd.set_ap(wrapper)

    fetched = nd.get_ap()
    assert isinstance(fetched, PDAppearanceStreamNameTreeNode)
    assert fetched.get_cos_object() is ap_dict


def test_document_name_dictionary_set_ap_accepts_raw_cosdictionary() -> None:
    nd = PDDocumentNameDictionary(names=COSDictionary())
    ap_dict = _leaf_node("Sig2", _make_appearance_stream())
    nd.set_ap(ap_dict)
    fetched = nd.get_ap()
    assert isinstance(fetched, PDAppearanceStreamNameTreeNode)
    assert fetched.get_cos_object() is ap_dict


def test_document_name_dictionary_set_ap_none_removes_entry() -> None:
    names = COSDictionary()
    names.set_item(
        COSName.get_pdf_name("AP"),
        _leaf_node("X", _make_appearance_stream()),
    )
    nd = PDDocumentNameDictionary(names=names)
    nd.set_ap(None)
    assert nd.get_ap() is None
    assert nd.has_ap() is False


def test_get_ap_raw_escape_hatch() -> None:
    names = COSDictionary()
    ap_dict = _leaf_node("Sig", _make_appearance_stream())
    names.set_item(COSName.get_pdf_name("AP"), ap_dict)
    nd = PDDocumentNameDictionary(names=names)
    raw = nd.get_ap_raw()
    assert raw is ap_dict
