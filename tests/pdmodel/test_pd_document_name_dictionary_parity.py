from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_alternate_presentations_name_tree_node import (
    PDAlternatePresentationsNameTreeNode,
)
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.pd_ids_name_tree_node import PDIDSNameTreeNode
from pypdfbox.pdmodel.pd_javascript_name_tree_node import PDJavascriptNameTreeNode
from pypdfbox.pdmodel.pd_pages_name_tree_node import PDPagesNameTreeNode
from pypdfbox.pdmodel.pd_renditions_name_tree_node import PDRenditionsNameTreeNode
from pypdfbox.pdmodel.pd_templates_name_tree_node import PDTemplatesNameTreeNode
from pypdfbox.pdmodel.pd_urls_name_tree_node import PDURLSNameTreeNode

_NAMES = COSName.get_pdf_name("Names")
_DESTS = COSName.get_pdf_name("Dests")
_AP = COSName.get_pdf_name("AP")
_EMBEDDED_FILES = COSName.get_pdf_name("EmbeddedFiles")
_JAVA_SCRIPT = COSName.get_pdf_name("JavaScript")
_PAGES = COSName.get_pdf_name("Pages")
_TEMPLATES = COSName.get_pdf_name("Templates")
_IDS = COSName.get_pdf_name("IDS")
_URLS = COSName.get_pdf_name("URLS")
_ALTERNATE_PRESENTATIONS = COSName.get_pdf_name("AlternatePresentations")
_RENDITIONS = COSName.get_pdf_name("Renditions")


# ---------- Fake catalog stand-in (avoids importing PDDocumentCatalog) ----------


class _FakeCatalog:
    def __init__(self) -> None:
        self._dict = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


# ---------- get_dests / set_dests ----------


def test_get_dests_round_trip_returns_destination_dictionary() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_DESTS, inner)

    out = nd.get_dests()
    assert out is not None
    assert isinstance(out, PDDestinationNameTreeNode)
    assert out.get_cos_object() is inner


def test_set_dests_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    dests = PDDestinationNameTreeNode()
    nd.set_dests(dests)
    out = nd.get_dests()
    assert out is not None
    assert out.get_cos_object() is dests.get_cos_object()


def test_set_dests_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_dests(PDDestinationNameTreeNode())
    assert nd.get_cos_object().get_dictionary_object(_DESTS) is not None
    nd.set_dests(None)
    assert nd.get_dests() is None
    assert nd.get_cos_object().get_dictionary_object(_DESTS) is None


def test_get_dests_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_dests() is None


def test_set_dests_preserves_destination_name_tree_leaf() -> None:
    nd = PDDocumentNameDictionary()
    dests = PDDestinationNameTreeNode()
    destination = PDPageXYZDestination()
    destination.set_page_number(2)
    dests.set_value("chapter", destination)

    nd.set_dests(dests)

    out = nd.get_dests()
    assert isinstance(out, PDDestinationNameTreeNode)
    fetched = out.get_value("chapter")
    assert isinstance(fetched, PDPageXYZDestination)
    assert fetched.get_page_number() == 2


# ---------- get_embedded_files / set_embedded_files ----------


def test_get_embedded_files_wraps_existing_subdict() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_EMBEDDED_FILES, inner)

    out = nd.get_embedded_files()
    assert isinstance(out, PDEmbeddedFilesNameTreeNode)
    assert out.get_cos_object() is inner


def test_set_embedded_files_round_trip_preserves_leaf() -> None:
    nd = PDDocumentNameDictionary()
    efs = PDEmbeddedFilesNameTreeNode()
    spec = PDComplexFileSpecification()
    spec.set_file("a.bin")
    efs.set_names({"a.bin": spec})

    nd.set_embedded_files(efs)
    out = nd.get_embedded_files()
    assert out is not None
    assert out.get_cos_object() is efs.get_cos_object()
    fetched = out.get_value("a.bin")
    assert isinstance(fetched, PDComplexFileSpecification)
    assert fetched.get_file() == "a.bin"


def test_get_embedded_files_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_embedded_files() is None


# ---------- get_javascript / set_javascript ----------


def test_get_javascript_wraps_existing_subdict() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_JAVA_SCRIPT, inner)
    out = nd.get_javascript()
    assert isinstance(out, PDJavascriptNameTreeNode)
    assert out.get_cos_object() is inner


def test_set_javascript_round_trip_preserves_leaf() -> None:
    nd = PDDocumentNameDictionary()
    js = PDJavascriptNameTreeNode()
    js.set_names({"hi": "app.alert('hi')"})

    nd.set_javascript(js)
    out = nd.get_javascript()
    assert out is not None
    assert out.get_cos_object() is js.get_cos_object()
    assert out.get_value("hi") == "app.alert('hi')"


def test_get_javascript_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_javascript() is None


# ---------- typed wrappers when entries present ----------


def test_get_pages_returns_typed_wrapper_when_present() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_PAGES, inner)
    out = nd.get_pages()
    assert isinstance(out, PDPagesNameTreeNode)
    assert out.get_cos_object() is inner


def test_get_pages_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_pages() is None


def test_get_templates_returns_typed_wrapper_when_present() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_TEMPLATES, inner)
    out = nd.get_templates()
    assert isinstance(out, PDTemplatesNameTreeNode)
    assert out.get_cos_object() is inner


def test_get_templates_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_templates() is None


def test_get_ids_returns_typed_wrapper_when_present() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_IDS, inner)
    out = nd.get_ids()
    assert isinstance(out, PDIDSNameTreeNode)
    assert out.get_cos_object() is inner


def test_get_ids_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_ids() is None


def test_get_urls_returns_typed_wrapper_when_present() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_URLS, inner)
    out = nd.get_urls()
    assert isinstance(out, PDURLSNameTreeNode)
    assert out.get_cos_object() is inner


def test_get_urls_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_urls() is None


def test_get_alternate_presentations_returns_typed_wrapper_when_present() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_ALTERNATE_PRESENTATIONS, inner)
    out = nd.get_alternate_presentations()
    assert isinstance(out, PDAlternatePresentationsNameTreeNode)
    assert out.get_cos_object() is inner


def test_get_renditions_returns_typed_wrapper_when_present() -> None:
    nd = PDDocumentNameDictionary()
    inner = COSDictionary()
    nd.get_cos_object().set_item(_RENDITIONS, inner)
    out = nd.get_renditions()
    assert isinstance(out, PDRenditionsNameTreeNode)
    assert out.get_cos_object() is inner


# ---------- /AP placeholder ----------


def test_get_ap_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_ap() is None


def test_set_and_get_ap_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    ap = COSDictionary()
    nd.set_ap(ap)
    out = nd.get_ap()
    assert out is ap
    assert nd.get_cos_object().get_dictionary_object(_AP) is ap


def test_set_ap_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_ap(COSDictionary())
    assert nd.get_cos_object().get_dictionary_object(_AP) is not None
    nd.set_ap(None)
    assert nd.get_ap() is None
    assert nd.get_cos_object().get_dictionary_object(_AP) is None


# ---------- setters that clear via None ----------


def test_set_pages_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_pages(PDPagesNameTreeNode())
    nd.set_pages(None)
    assert nd.get_pages() is None
    assert nd.get_cos_object().get_dictionary_object(_PAGES) is None


def test_set_templates_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_templates(PDTemplatesNameTreeNode())
    nd.set_templates(None)
    assert nd.get_templates() is None


def test_set_ids_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_ids(PDIDSNameTreeNode())
    nd.set_ids(None)
    assert nd.get_ids() is None


def test_set_urls_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_urls(PDURLSNameTreeNode())
    nd.set_urls(None)
    assert nd.get_urls() is None


def test_set_alternate_presentations_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_alternate_presentations(PDAlternatePresentationsNameTreeNode())
    nd.set_alternate_presentations(None)
    assert nd.get_alternate_presentations() is None


def test_set_renditions_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_renditions(PDRenditionsNameTreeNode())
    nd.set_renditions(None)
    assert nd.get_renditions() is None


# ---------- pdmodel package-level exports ----------


def test_pd_document_name_dictionary_exported_from_pdmodel() -> None:
    """Mirrors upstream ``org.apache.pdfbox.pdmodel.PDDocumentNameDictionary``
    package placement — importable from the ``pypdfbox.pdmodel`` namespace."""
    import pypdfbox.pdmodel as pdmodel

    assert pdmodel.PDDocumentNameDictionary is PDDocumentNameDictionary
    assert "PDDocumentNameDictionary" in pdmodel.__all__


def test_pd_document_name_destination_dictionary_exported_from_pdmodel() -> None:
    """Mirrors upstream
    ``org.apache.pdfbox.pdmodel.PDDocumentNameDestinationDictionary``
    package placement — importable from the ``pypdfbox.pdmodel`` namespace."""
    import pypdfbox.pdmodel as pdmodel
    from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
        PDDocumentNameDestinationDictionary,
    )

    assert pdmodel.PDDocumentNameDestinationDictionary is (
        PDDocumentNameDestinationDictionary
    )
    assert "PDDocumentNameDestinationDictionary" in pdmodel.__all__


# ---------- is_empty / __bool__ on PDDocumentNameDictionary ----------


def test_name_dictionary_is_empty_true_when_no_subdicts() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.is_empty() is True
    assert not nd


def test_name_dictionary_is_empty_false_when_any_subdict_present() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_javascript(PDJavascriptNameTreeNode())
    assert nd.is_empty() is False
    assert bool(nd) is True


# ---------- get_java_script alias on PDDocumentNameDictionary ----------


def test_get_java_script_strict_snake_case_alias_returns_same_value() -> None:
    """``get_java_script`` is the strict mechanical translation of upstream
    ``getJavaScript()`` and must round-trip with ``get_javascript``."""
    nd = PDDocumentNameDictionary()
    js = PDJavascriptNameTreeNode()
    js.set_names({"hi": "app.alert('hi')"})
    nd.set_javascript(js)

    via_alias = nd.get_java_script()
    assert via_alias is not None
    assert isinstance(via_alias, PDJavascriptNameTreeNode)
    assert via_alias.get_cos_object() is js.get_cos_object()
    via_legacy = nd.get_javascript()
    assert via_legacy is not None
    assert via_alias.get_cos_object() is via_legacy.get_cos_object()


def test_get_java_script_returns_none_when_absent() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.get_java_script() is None


# ---------- PDDocumentNameDestinationDictionary enumeration / membership ----------


def _make_xyz_dest_array() -> COSArray:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(1.0))
    return arr


def test_dest_dict_is_empty_true_for_empty_dict() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert dd.is_empty() is True


def test_dest_dict_is_empty_false_when_destinations_present() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _make_xyz_dest_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)
    assert dd.is_empty() is False


def test_dest_dict_get_names_returns_string_keys_in_order() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _make_xyz_dest_array())
    dests_cos.set_item("intro", _make_xyz_dest_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)

    names = dd.get_names()
    assert isinstance(names, list)
    assert all(isinstance(name, str) for name in names)
    assert sorted(names) == ["home", "intro"]


def test_dest_dict_get_names_empty_for_empty_dict() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert dd.get_names() == []


def test_dest_dict_contains_for_present_string_key() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _make_xyz_dest_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)
    assert "home" in dd
    assert "missing" not in dd


def test_dest_dict_contains_accepts_cos_name() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _make_xyz_dest_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)
    assert COSName.get_pdf_name("home") in dd


def test_dest_dict_contains_rejects_non_string_keys() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _make_xyz_dest_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)
    assert (123 in dd) is False
    assert (None in dd) is False


def test_dest_dict_contains_distinguishes_missing_from_unparseable() -> None:
    """``__contains__`` returns True even when the value cannot be coerced
    into a destination, but ``get_destination`` still returns None — letting
    callers tell ``key missing`` apart from ``key present, value malformed``."""
    dests_cos = COSDictionary()
    # Put a value that is neither a COSArray nor a COSDictionary with /D.
    dests_cos.set_item("borked", COSDictionary())  # empty dict, no /D
    dd = PDDocumentNameDestinationDictionary(dests_cos)
    assert "borked" in dd
    assert dd.get_destination("borked") is None


def test_dest_dict_len_reports_entry_count() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("a", _make_xyz_dest_array())
    dests_cos.set_item("b", _make_xyz_dest_array())
    dests_cos.set_item("c", _make_xyz_dest_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)
    assert len(dd) == 3


def test_dest_dict_len_zero_for_empty() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert len(dd) == 0
