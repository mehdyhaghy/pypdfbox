from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
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
