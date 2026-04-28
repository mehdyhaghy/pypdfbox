from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDDestinationNameTreeNode,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.pd_javascript_name_tree_node import PDJavascriptNameTreeNode

_NAMES = COSName.get_pdf_name("Names")
_DESTS = COSName.get_pdf_name("Dests")
_EMBEDDED_FILES = COSName.get_pdf_name("EmbeddedFiles")
_JAVA_SCRIPT = COSName.get_pdf_name("JavaScript")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_S = COSName.get_pdf_name("S")
_JS = COSName.get_pdf_name("JS")


# ---------- Fake catalog stand-in (avoids importing PDDocumentCatalog) ----------


class _FakeCatalog:
    def __init__(self) -> None:
        self._dict = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


# ---------- PDDocumentNameDictionary ----------


def test_dict_init_with_catalog_creates_names_subdict() -> None:
    cat = _FakeCatalog()
    nd = PDDocumentNameDictionary(catalog=cat)
    # Catalog now carries a /Names dict pointing at the same COSDictionary.
    assert cat.get_cos_object().get_dictionary_object(_NAMES) is nd.get_cos_object()


def test_dict_init_with_existing_names_reuses_it() -> None:
    cat = _FakeCatalog()
    existing = COSDictionary()
    cat.get_cos_object().set_item(_NAMES, existing)
    nd = PDDocumentNameDictionary(catalog=cat)
    assert nd.get_cos_object() is existing


def test_set_and_get_embedded_files_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    efs = PDEmbeddedFilesNameTreeNode()
    spec = PDComplexFileSpecification()
    spec.set_file("hello.txt")
    efs.set_names({"hello.txt": spec})

    nd.set_embedded_files(efs)
    out = nd.get_embedded_files()
    assert out is not None
    assert out.get_cos_object() is efs.get_cos_object()
    # Round-trip a leaf value.
    fetched = out.get_value("hello.txt")
    assert isinstance(fetched, PDComplexFileSpecification)
    assert fetched.get_file() == "hello.txt"


def test_set_embedded_files_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_embedded_files(PDEmbeddedFilesNameTreeNode())
    nd.set_embedded_files(None)
    assert nd.get_embedded_files() is None
    assert nd.get_cos_object().get_dictionary_object(_EMBEDDED_FILES) is None


def test_set_and_get_javascript_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    js = PDJavascriptNameTreeNode()
    js.set_names({"action1": "app.alert('hi')"})

    nd.set_javascript(js)
    out = nd.get_javascript()
    assert out is not None
    assert out.get_cos_object() is js.get_cos_object()
    assert out.get_value("action1") == "app.alert('hi')"


def test_set_javascript_none_clears_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_javascript(PDJavascriptNameTreeNode())
    nd.set_javascript(None)
    assert nd.get_javascript() is None
    assert nd.get_cos_object().get_dictionary_object(_JAVA_SCRIPT) is None


def test_set_dests_and_clears_catalog_legacy_entry() -> None:
    cat = _FakeCatalog()
    # Legacy: catalog carries /Dests directly (PDF 1.1 form).
    legacy = COSDictionary()
    cat.get_cos_object().set_item(_DESTS, legacy)

    nd = PDDocumentNameDictionary(catalog=cat)
    new_dests = PDDestinationNameTreeNode()
    nd.set_dests(new_dests)

    assert nd.get_cos_object().get_dictionary_object(_DESTS) is new_dests.get_cos_object()
    # Catalog's legacy /Dests removed.
    assert cat.get_cos_object().get_dictionary_object(_DESTS) is None


def test_get_dests_falls_back_to_catalog_legacy() -> None:
    cat = _FakeCatalog()
    legacy = COSDictionary()
    cat.get_cos_object().set_item(_DESTS, legacy)
    nd = PDDocumentNameDictionary(catalog=cat)
    out = nd.get_dests()
    assert out is not None
    assert out.get_cos_object() is legacy


def test_get_dests_returns_destination_name_tree_for_names_entry() -> None:
    nd = PDDocumentNameDictionary()
    dests = PDDestinationNameTreeNode()
    destination = PDPageXYZDestination()
    destination.set_page_number(0)
    dests.set_value("home", destination)

    nd.set_dests(dests)

    out = nd.get_dests()
    assert isinstance(out, PDDestinationNameTreeNode)
    assert out.get_cos_object() is dests.get_cos_object()
    fetched = out.get_value("home")
    assert isinstance(fetched, PDPageXYZDestination)
    assert fetched.get_page_number() == 0


# ---------- PDEmbeddedFilesNameTreeNode ----------


def test_embedded_files_name_tree_round_trip() -> None:
    tree = PDEmbeddedFilesNameTreeNode()
    spec = PDComplexFileSpecification()
    spec.set_file("file1.txt")
    spec.set_file_description("First")
    tree.set_names({"file1.txt": spec})

    fetched = tree.get_value("file1.txt")
    assert isinstance(fetched, PDComplexFileSpecification)
    assert fetched.get_file() == "file1.txt"
    assert fetched.get_file_description() == "First"


def test_embedded_files_create_child_node_returns_same_type() -> None:
    tree = PDEmbeddedFilesNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDEmbeddedFilesNameTreeNode)


# ---------- PDJavascriptNameTreeNode ----------


def test_javascript_name_tree_round_trip() -> None:
    tree = PDJavascriptNameTreeNode()
    tree.set_names({"a": "console.log('a')", "b": "console.log('b')"})
    assert tree.get_value("a") == "console.log('a')"
    assert tree.get_value("b") == "console.log('b')"


def test_javascript_value_to_cos_builds_action_dict() -> None:
    tree = PDJavascriptNameTreeNode()
    cos = tree.convert_value_to_cos("foo()")
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(_TYPE) == "Action"
    assert cos.get_name(_S) == "JavaScript"
    assert cos.get_string(_JS) == "foo()"


def test_javascript_create_child_node_returns_same_type() -> None:
    tree = PDJavascriptNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDJavascriptNameTreeNode)


# ---------- PDDocumentNameDestinationDictionary ----------


def test_dest_dict_get_destination_for_array() -> None:
    """An item that's a direct destination array yields PDDestination."""
    dests_cos = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(0))  # placeholder page ref slot
    arr.add(COSName.get_pdf_name("XYZ"))
    arr.add(COSFloat(10.0))
    arr.add(COSFloat(20.0))
    arr.add(COSFloat(1.0))
    dests_cos.set_item("home", arr)

    dd = PDDocumentNameDestinationDictionary(dests_cos)
    dest = dd.get_destination("home")
    assert isinstance(dest, PDDestination)
    assert isinstance(dest, PDPageXYZDestination)


def test_dest_dict_get_destination_for_dict_with_d() -> None:
    """An item that's a {/D <array>} dict unwraps via /D."""
    inner = COSArray()
    inner.add(COSInteger.get(0))
    inner.add(COSName.get_pdf_name("XYZ"))
    inner.add(COSFloat(0.0))
    inner.add(COSFloat(0.0))
    inner.add(COSFloat(1.0))
    wrapper = COSDictionary()
    wrapper.set_item("D", inner)

    dests_cos = COSDictionary()
    dests_cos.set_item("intro", wrapper)

    dd = PDDocumentNameDestinationDictionary(dests_cos)
    dest = dd.get_destination("intro")
    assert isinstance(dest, PDPageXYZDestination)


def test_dest_dict_missing_returns_none() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert dd.get_destination("nope") is None
