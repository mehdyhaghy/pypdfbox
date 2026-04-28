from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDDocumentOutline


def test_catalog_attached_to_fresh_document() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert isinstance(cat, PDDocumentCatalog)
    assert cat.get_cos_object().get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]


def test_get_pages_returns_tree_rooted_at_pages() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    tree = cat.get_pages()
    pages_dict = cat.get_cos_object().get_dictionary_object(COSName.PAGES)  # type: ignore[attr-defined]
    assert tree.get_cos_object() is pages_dict


def test_language_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_language("en-US")
    assert cat.get_language() == "en-US"
    cat.set_language(None)
    assert cat.get_language() is None


def test_page_layout_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_page_layout("OneColumn")
    assert cat.get_page_layout() == "OneColumn"
    cat.set_page_layout(None)
    assert cat.get_page_layout() is None


def test_page_mode_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_page_mode("UseOutlines")
    assert cat.get_page_mode() == "UseOutlines"


def test_version_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_version("1.7")
    assert cat.get_version() == "1.7"


def test_get_metadata_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_metadata() is None


def test_get_actions_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_actions() is None


def test_get_output_intents_absent_returns_empty_list() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_output_intents() == []


def test_get_acro_form_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_acro_form() is None


def test_get_names_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_names() is None


def test_get_struct_tree_root_mark_info_oc_properties_absent_return_none() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_struct_tree_root() is None
    assert cat.get_mark_info() is None
    assert cat.get_oc_properties() is None


def test_get_viewer_preferences_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_viewer_preferences() is None


def test_get_page_labels_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_page_labels() is None


def test_document_outline_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    outline = PDDocumentOutline()

    catalog.set_document_outline(outline)
    resolved = catalog.get_document_outline()

    assert isinstance(resolved, PDDocumentOutline)
    assert resolved.get_cos_object() is outline.get_cos_object()


def test_open_action_accepts_action_or_destination() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    action = PDActionURI()
    action.set_uri("https://example.test")

    catalog.set_open_action(action)
    resolved_action = catalog.get_open_action()
    assert isinstance(resolved_action, PDActionURI)
    assert resolved_action.get_uri() == "https://example.test"

    dest = PDPageXYZDestination()
    dest.set_page_number(0)
    catalog.set_open_action(dest)
    resolved_dest = catalog.get_open_action()
    assert isinstance(resolved_dest, PDPageXYZDestination)
    assert resolved_dest.get_page_number() == 0


def test_get_dests_wraps_destination_name_tree() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    dests_dict = COSDictionary()
    catalog.get_cos_object().set_item(COSName.get_pdf_name("Dests"), dests_dict)

    dests = catalog.get_dests()
    assert isinstance(dests, PDDestinationNameTreeNode)
    assert dests.get_cos_object() is dests_dict

    dest = PDPageXYZDestination()
    dest.set_page_number(1)
    dests.set_value("Chapter1", dest)

    resolved = catalog.get_dests()
    assert isinstance(resolved, PDDestinationNameTreeNode)
    fetched = resolved.get_value("Chapter1")
    assert isinstance(fetched, PDPageXYZDestination)
    assert fetched.get_page_number() == 1


# ---------- /URI dictionary ----------


def test_get_uri_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_uri() is None


def test_uri_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    uri_dict = COSDictionary()
    uri_dict.set_item(COSName.get_pdf_name("Base"), COSString("https://example.test/"))
    catalog.set_uri(uri_dict)

    resolved = catalog.get_uri()
    assert isinstance(resolved, COSDictionary)
    assert resolved is uri_dict
    assert resolved.get_string(COSName.get_pdf_name("Base")) == "https://example.test/"

    catalog.set_uri(None)
    assert catalog.get_uri() is None


def test_get_uri_returns_none_when_entry_is_not_a_dictionary() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    catalog.get_cos_object().set_item(
        COSName.get_pdf_name("URI"), COSString("not-a-dict")
    )
    assert catalog.get_uri() is None


# ---------- /Requirements ----------


def test_get_requirements_absent_returns_empty_list() -> None:
    doc = PDDocument()
    reqs = doc.get_document_catalog().get_requirements()
    assert reqs == []
    assert isinstance(reqs, list)


def test_add_requirement_creates_array_on_demand() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    req = COSDictionary()
    req.set_item(COSName.TYPE, COSName.get_pdf_name("Requirement"))  # type: ignore[attr-defined]
    req.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("EnableJavaScripts"))

    catalog.add_requirement(req)

    arr = catalog.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Requirements")
    )
    assert isinstance(arr, COSArray)
    assert arr.size() == 1

    fetched = catalog.get_requirements()
    assert len(fetched) == 1
    assert fetched[0] is req


def test_set_requirements_replaces_array() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    req1 = COSDictionary()
    req1.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("R1"))
    req2 = COSDictionary()
    req2.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("R2"))

    catalog.set_requirements([req1, req2])
    fetched = catalog.get_requirements()
    assert len(fetched) == 2
    assert fetched[0] is req1
    assert fetched[1] is req2

    # Replace with new list.
    req3 = COSDictionary()
    req3.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("R3"))
    catalog.set_requirements([req3])
    fetched = catalog.get_requirements()
    assert len(fetched) == 1
    assert fetched[0] is req3


def test_set_requirements_none_or_empty_removes_entry() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    req = COSDictionary()
    catalog.add_requirement(req)
    assert COSName.get_pdf_name("Requirements") in catalog

    catalog.set_requirements(None)
    assert COSName.get_pdf_name("Requirements") not in catalog

    catalog.add_requirement(req)
    catalog.set_requirements([])
    assert COSName.get_pdf_name("Requirements") not in catalog


def test_set_requirements_rejects_non_cos_dict() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    with pytest.raises(TypeError):
        catalog.set_requirements(["not-a-dict"])  # type: ignore[list-item]


def test_add_requirement_rejects_non_cos_dict() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    with pytest.raises(TypeError):
        catalog.add_requirement("not-a-dict")  # type: ignore[arg-type]


def test_get_requirements_skips_non_dict_entries() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    arr = COSArray()
    arr.add(COSString("not-a-dict"))
    good = COSDictionary()
    arr.add(good)
    catalog.get_cos_object().set_item(COSName.get_pdf_name("Requirements"), arr)

    fetched = catalog.get_requirements()
    assert len(fetched) == 1
    assert fetched[0] is good


# ---------- set_pages ----------


def test_set_pages_swaps_page_tree() -> None:
    from pypdfbox.pdmodel import PDPageTree

    doc = PDDocument()
    catalog = doc.get_document_catalog()
    original = catalog.get_pages()

    replacement = PDPageTree(document=doc)
    catalog.set_pages(replacement)

    fetched = catalog.get_cos_object().get_dictionary_object(COSName.PAGES)  # type: ignore[attr-defined]
    assert fetched is replacement.get_cos_object()
    assert fetched is not original.get_cos_object()


def test_set_pages_none_removes_entry() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    # Force /Pages population.
    catalog.get_pages()
    assert COSName.PAGES in catalog  # type: ignore[attr-defined]

    catalog.set_pages(None)
    assert COSName.PAGES not in catalog  # type: ignore[attr-defined]


# ---------- MarkInfo convenience accessors ----------


def test_mark_info_convenience_defaults_when_absent() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.is_document_marked() is False
    assert cat.has_user_properties() is False
    assert cat.has_suspects() is False


def test_mark_info_convenience_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_document_marked(True)
    cat.set_user_properties(True)
    cat.set_suspects(True)
    assert cat.is_document_marked() is True
    assert cat.has_user_properties() is True
    assert cat.has_suspects() is True
    # Sub-dict is materialised under /MarkInfo.
    mark = cat.get_mark_info()
    assert mark is not None
    assert mark.is_marked() is True
    assert mark.is_user_properties() is True
    assert mark.is_suspects() is True


# ---------- StructureTreeRoot upstream-name aliases ----------


def test_structure_tree_root_alias_returns_same() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_structure_tree_root() is None
    # set_structure_tree_root mirrors set_struct_tree_root.
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )

    root = PDStructureTreeRoot()
    cat.set_structure_tree_root(root)
    assert cat.get_structure_tree_root() is not None
    assert (
        cat.get_structure_tree_root().get_cos_object()
        is root.get_cos_object()
    )


# ---------- /OutputIntents set_output_intents ----------


def test_set_output_intents_replaces_array() -> None:
    from pypdfbox.pdmodel.graphics.color import PDOutputIntent

    doc = PDDocument()
    cat = doc.get_document_catalog()

    a = PDOutputIntent()
    b = PDOutputIntent()
    cat.set_output_intents([a, b])
    assert len(cat.get_output_intents()) == 2

    c = PDOutputIntent()
    cat.set_output_intents([c])
    fetched = cat.get_output_intents()
    assert len(fetched) == 1
    assert fetched[0].get_cos_object() is c.get_cos_object()


def test_set_output_intents_none_or_empty_removes_entry() -> None:
    from pypdfbox.pdmodel.graphics.color import PDOutputIntent

    doc = PDDocument()
    cat = doc.get_document_catalog()

    cat.add_output_intent(PDOutputIntent())
    cat.set_output_intents(None)
    assert COSName.get_pdf_name("OutputIntents") not in cat

    cat.add_output_intent(PDOutputIntent())
    cat.set_output_intents([])
    assert COSName.get_pdf_name("OutputIntents") not in cat


# ---------- /AF AssociatedFiles ----------


def test_get_associated_files_absent_returns_empty_list() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_associated_files() == []


def test_associated_files_round_trip() -> None:
    from pypdfbox.pdmodel.common.filespecification import (
        PDComplexFileSpecification,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()

    fs = PDComplexFileSpecification()
    fs.set_file("attached.txt")
    cat.set_associated_files([fs])

    fetched = cat.get_associated_files()
    assert len(fetched) == 1
    assert fetched[0].get_file() == "attached.txt"

    cat.set_associated_files(None)
    assert cat.get_associated_files() == []


def test_associated_files_set_empty_removes_entry() -> None:
    from pypdfbox.pdmodel.common.filespecification import (
        PDComplexFileSpecification,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()

    fs = PDComplexFileSpecification()
    cat.set_associated_files([fs])
    assert COSName.get_pdf_name("AF") in cat

    cat.set_associated_files([])
    assert COSName.get_pdf_name("AF") not in cat


# ---------- /PieceInfo ----------


def test_piece_info_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_piece_info() is None


def test_piece_info_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()

    piece = COSDictionary()
    piece.set_item(COSName.get_pdf_name("ADBE"), COSDictionary())
    cat.set_piece_info(piece)

    fetched = cat.get_piece_info()
    assert fetched is piece

    cat.set_piece_info(None)
    assert cat.get_piece_info() is None


def test_piece_info_returns_none_when_entry_is_not_dict() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PieceInfo"), COSString("nope")
    )
    assert cat.get_piece_info() is None
