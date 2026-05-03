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


# ---------- Wave 211: presence predicates on PDDocumentNameDictionary ----------


def _xyz_array() -> COSArray:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(1.0))
    return arr


def test_has_predicates_all_false_on_empty_names() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.has_dests() is False
    assert nd.has_ap() is False
    assert nd.has_embedded_files() is False
    assert nd.has_javascript() is False
    assert nd.has_pages() is False
    assert nd.has_templates() is False
    assert nd.has_ids() is False
    assert nd.has_urls() is False
    assert nd.has_alternate_presentations() is False
    assert nd.has_renditions() is False


def test_has_dests_true_for_names_entry() -> None:
    nd = PDDocumentNameDictionary()
    nd.get_cos_object().set_item(
        COSName.get_pdf_name("Dests"), COSDictionary()
    )
    assert nd.has_dests() is True


def test_has_dests_true_for_catalog_legacy_fallback() -> None:
    cat = _FakeCatalog()
    legacy = COSDictionary()
    cat.get_cos_object().set_item(COSName.get_pdf_name("Dests"), legacy)
    nd = PDDocumentNameDictionary(catalog=cat)
    # /Names doesn't carry /Dests, but the catalog does → still present.
    assert nd.has_dests() is True


def test_has_dests_false_when_value_is_not_a_dict() -> None:
    """Stray non-dict /Dests value → predicate reports False (defensive)."""
    nd = PDDocumentNameDictionary()
    nd.get_cos_object().set_item(
        COSName.get_pdf_name("Dests"), COSName.get_pdf_name("oops")
    )
    assert nd.has_dests() is False


def test_has_ap_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    assert nd.has_ap() is False
    nd.set_ap(COSDictionary())
    assert nd.has_ap() is True
    nd.set_ap(None)
    assert nd.has_ap() is False


def test_has_embedded_files_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_embedded_files(PDEmbeddedFilesNameTreeNode())
    assert nd.has_embedded_files() is True
    nd.set_embedded_files(None)
    assert nd.has_embedded_files() is False


def test_has_javascript_round_trip() -> None:
    nd = PDDocumentNameDictionary()
    nd.set_javascript(PDJavascriptNameTreeNode())
    assert nd.has_javascript() is True
    nd.set_javascript(None)
    assert nd.has_javascript() is False


def test_has_pages_templates_ids_urls_alternate_renditions_round_trip() -> None:
    """Cover the predicate set that maps to the typed-wrapper categories."""
    from pypdfbox.pdmodel.pd_alternate_presentations_name_tree_node import (
        PDAlternatePresentationsNameTreeNode,
    )
    from pypdfbox.pdmodel.pd_ids_name_tree_node import PDIDSNameTreeNode
    from pypdfbox.pdmodel.pd_pages_name_tree_node import PDPagesNameTreeNode
    from pypdfbox.pdmodel.pd_renditions_name_tree_node import (
        PDRenditionsNameTreeNode,
    )
    from pypdfbox.pdmodel.pd_templates_name_tree_node import (
        PDTemplatesNameTreeNode,
    )
    from pypdfbox.pdmodel.pd_urls_name_tree_node import PDURLSNameTreeNode

    nd = PDDocumentNameDictionary()

    nd.set_pages(PDPagesNameTreeNode())
    nd.set_templates(PDTemplatesNameTreeNode())
    nd.set_ids(PDIDSNameTreeNode())
    nd.set_urls(PDURLSNameTreeNode())
    nd.set_alternate_presentations(PDAlternatePresentationsNameTreeNode())
    nd.set_renditions(PDRenditionsNameTreeNode())

    assert nd.has_pages() is True
    assert nd.has_templates() is True
    assert nd.has_ids() is True
    assert nd.has_urls() is True
    assert nd.has_alternate_presentations() is True
    assert nd.has_renditions() is True

    nd.set_pages(None)
    nd.set_templates(None)
    nd.set_ids(None)
    nd.set_urls(None)
    nd.set_alternate_presentations(None)
    nd.set_renditions(None)

    assert nd.has_pages() is False
    assert nd.has_templates() is False
    assert nd.has_ids() is False
    assert nd.has_urls() is False
    assert nd.has_alternate_presentations() is False
    assert nd.has_renditions() is False


# ---------- Wave 211: KEY_* class constants and NAME_KEYS tuple ----------


def test_key_constants_are_cos_names_with_expected_spelling() -> None:
    assert COSName.get_pdf_name("Dests") == PDDocumentNameDictionary.KEY_DESTS
    assert COSName.get_pdf_name("AP") == PDDocumentNameDictionary.KEY_AP
    assert (
        COSName.get_pdf_name("EmbeddedFiles")
        == PDDocumentNameDictionary.KEY_EMBEDDED_FILES
    )
    assert (
        COSName.get_pdf_name("JavaScript")
        == PDDocumentNameDictionary.KEY_JAVA_SCRIPT
    )
    assert COSName.get_pdf_name("Pages") == PDDocumentNameDictionary.KEY_PAGES
    assert (
        COSName.get_pdf_name("Templates")
        == PDDocumentNameDictionary.KEY_TEMPLATES
    )
    assert COSName.get_pdf_name("IDS") == PDDocumentNameDictionary.KEY_IDS
    assert COSName.get_pdf_name("URLS") == PDDocumentNameDictionary.KEY_URLS
    assert (
        COSName.get_pdf_name("AlternatePresentations")
        == PDDocumentNameDictionary.KEY_ALTERNATE_PRESENTATIONS
    )
    assert (
        COSName.get_pdf_name("Renditions")
        == PDDocumentNameDictionary.KEY_RENDITIONS
    )


def test_name_keys_tuple_covers_table_31_in_order() -> None:
    """``NAME_KEYS`` enumerates the 10 spec name-tree subkeys exactly once."""
    keys = PDDocumentNameDictionary.NAME_KEYS
    assert isinstance(keys, tuple)
    assert len(keys) == 10
    # Spec order: Dests, AP, EmbeddedFiles, JavaScript, Pages, Templates,
    # IDS, URLS, AlternatePresentations, Renditions (PDF 32000-1 Table 31).
    assert keys == (
        PDDocumentNameDictionary.KEY_DESTS,
        PDDocumentNameDictionary.KEY_AP,
        PDDocumentNameDictionary.KEY_EMBEDDED_FILES,
        PDDocumentNameDictionary.KEY_JAVA_SCRIPT,
        PDDocumentNameDictionary.KEY_PAGES,
        PDDocumentNameDictionary.KEY_TEMPLATES,
        PDDocumentNameDictionary.KEY_IDS,
        PDDocumentNameDictionary.KEY_URLS,
        PDDocumentNameDictionary.KEY_ALTERNATE_PRESENTATIONS,
        PDDocumentNameDictionary.KEY_RENDITIONS,
    )
    # And no duplicates.
    assert len(set(keys)) == 10


# ---------- Wave 211: __iter__ / items() on PDDocumentNameDestinationDictionary


def test_dest_dict_iter_yields_name_destination_pairs() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _xyz_array())
    dests_cos.set_item("intro", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)

    pairs = list(iter(dd))
    assert len(pairs) == 2
    names = [name for name, _ in pairs]
    assert sorted(names) == ["home", "intro"]
    for name, dest in pairs:
        assert isinstance(name, str)
        assert isinstance(dest, PDPageXYZDestination)


def test_dest_dict_items_iterator_matches_iter() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)

    via_iter = list(iter(dd))
    via_items = list(dd.items())
    # Same names + same destination wrapper class.
    assert [n for n, _ in via_iter] == [n for n, _ in via_items]
    assert all(
        type(d_iter) is type(d_items)
        for (_, d_iter), (_, d_items) in zip(via_iter, via_items, strict=True)
    )


def test_dest_dict_items_yields_none_for_unparseable_value() -> None:
    """Empty inner dict (no /D, no array) → destination resolves to None,
    matching :meth:`get_destination` semantics."""
    dests_cos = COSDictionary()
    dests_cos.set_item("borked", COSDictionary())  # no /D
    dests_cos.set_item("home", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)

    by_name = dict(dd.items())
    assert by_name["borked"] is None
    assert isinstance(by_name["home"], PDPageXYZDestination)


def test_dest_dict_items_empty_for_empty_dict() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert list(dd.items()) == []
    assert list(iter(dd)) == []


def test_dest_dict_iter_supports_for_loop_unpacking() -> None:
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)

    seen: list[str] = []
    for name, _dest in dd:
        seen.append(name)
    assert seen == ["home"]


def test_dest_dict_items_returns_fresh_iterator_each_call() -> None:
    """Each ``items()`` call yields a fresh iterator, so callers can iterate
    multiple times. (``__iter__`` returning the iterator from ``items()``
    means we get the same guarantee.)"""
    dests_cos = COSDictionary()
    dests_cos.set_item("home", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(dests_cos)

    first = list(dd.items())
    second = list(dd.items())
    assert first[0][0] == "home"
    assert second[0][0] == "home"
    # Independent iterators — exhausting one mustn't drain the other.
    it1 = dd.items()
    it2 = dd.items()
    next(it1)
    # it2 should still have the first entry available.
    name, _ = next(it2)
    assert name == "home"
