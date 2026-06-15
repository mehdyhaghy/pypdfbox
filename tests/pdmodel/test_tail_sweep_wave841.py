from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPageTree
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_uri_dictionary import PDURIDictionary
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination

_BASE = COSName.get_pdf_name("Base")
_K = COSName.get_pdf_name("K")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


def test_wave841_structure_node_remove_kid_matches_plain_integer_array_entry() -> None:
    node = PDStructureNode()
    kids = COSArray()
    kids.add(COSInteger.get(2))
    kids.add(9)  # type: ignore[arg-type]
    node.get_cos_object().set_item(_K, kids)

    assert node.remove_kid(COSInteger.get(9)) is True

    assert node.get_kids() == [2]
    assert node.get_cos_object().get_dictionary_object(_K) == COSInteger.get(2)


def test_wave841_page_tree_getitem_rejects_non_int_index() -> None:
    tree = PDPageTree()

    with pytest.raises(TypeError, match="indices must be int"):
        tree[1.0]  # type: ignore[index]


def test_wave841_embedded_goto_non_page_non_named_destination_resolves_absent() -> None:
    class OtherDestination(PDDestination):
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    action = PDActionEmbeddedGoTo()
    action.get_d = lambda: OtherDestination()  # type: ignore[method-assign]

    assert action._resolve_final_destination(PDDocument()) is None


def test_wave841_hide_single_raw_annotation_dictionary_and_uri_name_base() -> None:
    annotation = COSDictionary()
    annotation.set_name(_SUBTYPE, "Text")
    action = PDActionHide()

    action.set_annotations([annotation])

    assert action.get_target() is annotation
    assert action.get_annotations()[0].get_cos_object() is annotation  # type: ignore[index]

    # Wave 1530: upstream getBase (plain getString) only decodes a COSString;
    # a COSName /Base returns None. Use a COSString to exercise the decode path.
    uri = PDURIDictionary()
    uri.get_cos_object().set_item(_BASE, COSString("https://example.test/"))
    assert uri.get_base() == "https://example.test/"

    uri_name = PDURIDictionary()
    uri_name.get_cos_object().set_item(_BASE, COSName.get_pdf_name("nope"))
    assert uri_name.get_base() is None
