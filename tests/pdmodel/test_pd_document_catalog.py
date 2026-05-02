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


def test_get_actions_auto_creates_empty_aa() -> None:
    """Mirrors upstream ``getActions`` — auto-creates ``/AA`` when absent
    so callers can attach triggers without first wiring the sub-dict."""
    from pypdfbox.pdmodel.interactive.action import (
        PDDocumentCatalogAdditionalActions,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    actions = cat.get_actions()
    assert isinstance(actions, PDDocumentCatalogAdditionalActions)
    # Side effect — /AA is now stored in the catalog dict.
    assert COSName.get_pdf_name("AA") in cat
    # Identity stays stable across calls (backed by the same /AA dict).
    again = cat.get_actions()
    assert again.get_cos_object() is actions.get_cos_object()


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
    from pypdfbox.pdmodel.interactive.action import PDURIDictionary

    doc = PDDocument()
    catalog = doc.get_document_catalog()

    # Back-compat: raw COSDictionary still accepted as the value.
    uri_dict = COSDictionary()
    uri_dict.set_item(COSName.get_pdf_name("Base"), COSString("https://example.test/"))
    catalog.set_uri(uri_dict)

    resolved = catalog.get_uri()
    assert isinstance(resolved, PDURIDictionary)
    assert resolved.get_cos_object() is uri_dict
    assert resolved.get_base() == "https://example.test/"

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


# ---------- /URI typed wrapper ----------


def test_set_uri_accepts_pd_uri_dictionary() -> None:
    """``set_uri`` accepts a typed :class:`PDURIDictionary` (mirroring
    upstream's ``setURI(PDURIDictionary)``) and round-trips through
    ``get_uri()``."""
    from pypdfbox.pdmodel.interactive.action import PDURIDictionary

    doc = PDDocument()
    catalog = doc.get_document_catalog()
    typed = PDURIDictionary()
    typed.set_base("https://typed.example/")
    catalog.set_uri(typed)

    fetched = catalog.get_uri()
    assert isinstance(fetched, PDURIDictionary)
    assert fetched.get_cos_object() is typed.get_cos_object()
    assert fetched.get_base() == "https://typed.example/"


# ---------- find_named_destination_page ----------


def test_find_named_destination_page_via_names_dests_tree() -> None:
    """``findNamedDestinationPage`` resolves a :class:`PDNamedDestination`
    through the catalog's ``/Names /Dests`` name tree (PDF 1.2+ shape)."""
    from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
        PDNamedDestination,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()

    # Wire /Names → /Dests dictionary holding {"chap1": [<page><dest>]}.
    names = COSDictionary()
    dests = COSDictionary()
    arr = COSArray()
    page_dest = PDPageXYZDestination()
    page_dest.set_page_number(2)
    names_arr = COSArray()
    names_arr.add(COSString("chap1"))
    names_arr.add(page_dest.get_cos_object())
    dests.set_item(COSName.get_pdf_name("Names"), names_arr)
    arr.add(dests)
    names.set_item(COSName.get_pdf_name("Dests"), dests)
    cat.get_cos_object().set_item(COSName.get_pdf_name("Names"), names)

    named = PDNamedDestination("chap1")
    resolved = cat.find_named_destination_page(named)
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 2


def test_find_named_destination_page_via_legacy_dests() -> None:
    """Falls back to the catalog's legacy flat ``/Dests`` dictionary
    when ``/Names /Dests`` is absent (PDF 1.1 shape)."""
    from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
        PDNamedDestination,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()

    legacy = COSDictionary()
    page_dest = PDPageXYZDestination()
    page_dest.set_page_number(5)
    legacy.set_item(COSName.get_pdf_name("foo"), page_dest.get_cos_object())
    cat.get_cos_object().set_item(COSName.get_pdf_name("Dests"), legacy)

    named = PDNamedDestination("foo")
    resolved = cat.find_named_destination_page(named)
    assert resolved is not None
    assert resolved.get_page_number() == 5


def test_find_named_destination_page_returns_none_when_unknown() -> None:
    from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
        PDNamedDestination,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.find_named_destination_page(PDNamedDestination("missing")) is None


def test_find_named_destination_page_handles_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().find_named_destination_page(None) is None


# ---------- set_oc_properties version bump ----------


def test_set_oc_properties_bumps_version_to_1_5() -> None:
    """Upstream side effect: optional content groups require PDF 1.5,
    so ``setOCProperties`` raises the document version when below."""
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentProperties,
    )

    doc = PDDocument()
    # Ensure the doc starts below 1.5 (a fresh PDDocument is 1.4).
    assert doc.get_version() < 1.5

    ocp = PDOptionalContentProperties()
    cat = doc.get_document_catalog()
    cat.set_oc_properties(ocp)

    assert doc.get_version() >= 1.5


def test_set_oc_properties_none_removes_entry() -> None:
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentProperties,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_oc_properties(PDOptionalContentProperties())
    assert COSName.get_pdf_name("OCProperties") in cat

    cat.set_oc_properties(None)
    assert COSName.get_pdf_name("OCProperties") not in cat


# ---------- AcroForm caching ----------


def test_get_acro_form_returns_cached_wrapper_after_set() -> None:
    """Repeated ``get_acro_form`` calls return the same wrapper instance
    after the first lookup (parity with upstream ``cachedAcroForm``)."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))
    a = cat.get_acro_form()
    b = cat.get_acro_form()
    assert a is b


def test_set_acro_form_clears_cached_wrapper() -> None:
    """A subsequent ``set_acro_form`` invalidates the cache so the next
    ``get_acro_form`` materialises the freshly-installed value (mirrors
    upstream's ``cachedAcroForm = null`` reset — the supplied PDAcroForm
    is not preserved by reference; only the backing /AcroForm dict is)."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    first = PDAcroForm(doc)
    cat.set_acro_form(first)
    cached_first = cat.get_acro_form()
    assert cached_first is not None
    assert cached_first.get_cos_object() is first.get_cos_object()

    second = PDAcroForm(doc)
    cat.set_acro_form(second)
    out = cat.get_acro_form()
    # Cache was cleared — different wrapper than the previously-cached one.
    assert out is not cached_first
    # The swap took effect — backing dicts match the new wrapper.
    assert out is not None
    assert out.get_cos_object() is second.get_cos_object()


def test_set_acro_form_none_clears_cache_and_returns_none() -> None:
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))
    assert cat.get_acro_form() is not None
    cat.set_acro_form(None)
    assert cat.get_acro_form() is None


# ---------- get_acro_form(fixup) overload ----------


def test_get_acro_form_with_fixup_invokes_apply_once() -> None:
    """``get_acro_form(fixup)`` mirrors upstream's
    ``getAcroForm(PDDocumentFixup)`` overload — the fixup's ``apply()`` is
    called once, and a second call with the same instance is a no-op."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))

    calls: list[int] = []

    class _Fixup:
        def apply(self) -> None:
            calls.append(1)

    fixup = _Fixup()
    cat.get_acro_form(fixup)
    cat.get_acro_form(fixup)
    assert calls == [1]


def test_get_acro_form_with_new_fixup_clears_cache() -> None:
    """A fresh fixup invalidates the cached wrapper so the post-apply
    ``/AcroForm`` dictionary is re-read."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))
    cached_first = cat.get_acro_form()
    assert cached_first is not None

    class _Fixup:
        def apply(self) -> None:
            return None

    new_form = cat.get_acro_form(_Fixup())
    # New fixup → cache cleared → fresh wrapper minted from the same dict.
    assert new_form is not cached_first
    assert new_form.get_cos_object() is cached_first.get_cos_object()


def test_get_acro_form_no_fixup_returns_unfixed() -> None:
    """``get_acro_form(None)`` (or no-arg) returns the AcroForm without
    re-applying any previously-applied fixup."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))

    calls: list[int] = []

    class _Fixup:
        def apply(self) -> None:
            calls.append(1)

    fixup = _Fixup()
    cat.get_acro_form(fixup)
    cat.get_acro_form()  # no-arg: no re-apply
    cat.get_acro_form(None)  # explicit None: no re-apply
    assert calls == [1]


# ---------- get_threads auto-create parity ----------


def test_get_threads_auto_creates_threads_array() -> None:
    """Mirrors upstream ``getThreads`` — auto-creates ``/Threads`` when
    absent so callers can mutate the catalog-backed array."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    threads = cat.get_threads()
    assert threads == []
    # Side effect: /Threads is now stored in the catalog.
    arr = cat.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Threads"))
    assert isinstance(arr, COSArray)
    assert arr.size() == 0


# ---------- defensive parsing ----------


def test_get_threads_skips_non_dict_array_entries() -> None:
    """``/Threads`` array entries that aren't ``COSDictionary`` are
    skipped (defensive parsing for malformed PDFs)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    arr = COSArray()
    arr.add(COSString("not a thread"))
    valid = COSDictionary()
    arr.add(valid)
    cat.get_cos_object().set_item(COSName.get_pdf_name("Threads"), arr)
    threads = cat.get_threads()
    assert len(threads) == 1
    assert threads[0].get_cos_object() is valid


def test_get_threads_replaces_non_array_with_fresh_array() -> None:
    """If ``/Threads`` exists but isn't an array (malformed), the auto-
    create path overwrites it with a fresh empty array — matches upstream
    ``getCOSArray`` returning null for non-array values."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Threads"), COSString("not an array")
    )
    threads = cat.get_threads()
    assert threads == []
    arr = cat.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Threads"))
    assert isinstance(arr, COSArray)
    assert arr.size() == 0


def test_get_metadata_returns_none_when_entry_is_not_a_stream() -> None:
    """``/Metadata`` must be a stream — a stray dictionary should not
    materialise a wrapper. Mirrors upstream's ``getCOSStream`` returning
    null for non-stream values."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Metadata"), COSDictionary()
    )
    assert cat.get_metadata() is None


def test_get_oc_properties_returns_none_when_entry_is_not_a_dict() -> None:
    """``/OCProperties`` must be a dictionary — non-dict values map to
    ``None`` (mirrors upstream's typed ``getCOSDictionary`` accessor)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("OCProperties"), COSString("bogus")
    )
    assert cat.get_oc_properties() is None


def test_get_open_action_returns_none_when_entry_is_unrecognised() -> None:
    """Truly unrecognised ``/OpenAction`` value types (not a dictionary,
    array, name, or string) resolve to ``None`` via
    :class:`PDDestinationOrAction.create`. Defensive parsing parity with
    upstream."""
    from pypdfbox.cos import COSInteger

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("OpenAction"), COSInteger.get(42)
    )
    assert cat.get_open_action() is None


# ---------- raw COS setters back-compat ----------


def test_set_metadata_accepts_raw_cos_stream() -> None:
    """Raw :class:`COSStream` values are stored directly without going
    through a :class:`PDMetadata` wrapper — useful for low-level
    re-wiring flows that already have the stream in hand."""
    from pypdfbox.cos import COSStream

    doc = PDDocument()
    cat = doc.get_document_catalog()
    stream = COSStream()
    cat.set_metadata(stream)
    stored = cat.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Metadata"))
    assert stored is stream
    # And the typed getter still wraps it.
    assert cat.get_metadata() is not None


def test_set_actions_accepts_raw_cos_dictionary() -> None:
    """Raw :class:`COSDictionary` values are stored directly under ``/AA``
    without requiring a :class:`PDDocumentCatalogAdditionalActions`
    wrapper. Mirrors upstream's polymorphic ``setItem`` resolving
    ``COSObjectable`` and ``COSBase`` alike."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    aa_dict = COSDictionary()
    aa_dict.set_item(
        COSName.get_pdf_name("WP"),
        COSDictionary(),
    )
    cat.set_actions(aa_dict)
    stored = cat.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AA"))
    assert stored is aa_dict


def test_set_open_action_accepts_raw_cos_dictionary_and_array() -> None:
    """Raw :class:`COSDictionary` (action) and :class:`COSArray`
    (destination) values are stored directly without requiring a
    :class:`PDDestinationOrAction` wrapper."""
    doc = PDDocument()
    cat = doc.get_document_catalog()

    raw_action = COSDictionary()
    raw_action.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("URI"))
    raw_action.set_item(COSName.get_pdf_name("URI"), COSString("https://x.test"))
    cat.set_open_action(raw_action)
    assert cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OpenAction")
    ) is raw_action

    raw_dest = COSArray()
    cat.set_open_action(raw_dest)
    assert cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OpenAction")
    ) is raw_dest


def test_set_oc_properties_accepts_raw_cos_dictionary() -> None:
    """Raw :class:`COSDictionary` values are stored directly under
    ``/OCProperties`` without going through
    :class:`PDOptionalContentProperties`. Version bump still fires since
    optional content groups require PDF 1.5."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    doc.set_version(1.4)

    raw_oc = COSDictionary()
    cat.set_oc_properties(raw_oc)
    stored = cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OCProperties")
    )
    assert stored is raw_oc
    assert doc.get_version() == 1.5


# ---------- /NeedsRendering ----------


def test_needs_rendering_defaults_to_false_when_absent() -> None:
    """``/NeedsRendering`` is optional (PDF 32000-1 §7.7.3.4 Table 28); when
    omitted the implicit default is ``False``."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.is_needs_rendering() is False
    assert COSName.get_pdf_name("NeedsRendering") not in cat


def test_needs_rendering_round_trip() -> None:
    """``set_needs_rendering(True)`` writes the boolean entry; reading
    it back returns ``True``. Setting it to ``False`` keeps the entry
    explicitly written so producers can distinguish "explicitly off"
    from "absent"."""
    doc = PDDocument()
    cat = doc.get_document_catalog()

    cat.set_needs_rendering(True)
    assert cat.is_needs_rendering() is True
    assert (
        cat.get_cos_object().get_boolean(
            COSName.get_pdf_name("NeedsRendering"), False
        )
        is True
    )

    cat.set_needs_rendering(False)
    assert cat.is_needs_rendering() is False
    assert COSName.get_pdf_name("NeedsRendering") in cat


def test_needs_rendering_set_none_removes_entry() -> None:
    """Passing ``None`` removes the entry entirely (back to implicit
    default)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_needs_rendering(True)
    assert COSName.get_pdf_name("NeedsRendering") in cat

    cat.set_needs_rendering(None)
    assert COSName.get_pdf_name("NeedsRendering") not in cat
    assert cat.is_needs_rendering() is False


# ---------- /OCProperties long-form alias ----------


def test_get_optional_content_properties_alias_matches_get_oc_properties() -> None:
    """``get_optional_content_properties`` is a long-form alias —
    delegates to :meth:`get_oc_properties` and returns a wrapper around
    the same backing :class:`COSDictionary`."""
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentProperties,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_optional_content_properties() is None

    raw = COSDictionary()
    cat.get_cos_object().set_item(COSName.get_pdf_name("OCProperties"), raw)
    fetched = cat.get_optional_content_properties()
    assert isinstance(fetched, PDOptionalContentProperties)
    assert fetched.get_cos_object() is raw
    via_short = cat.get_oc_properties()
    assert via_short.get_cos_object() is fetched.get_cos_object()


def test_set_optional_content_properties_alias_bumps_version() -> None:
    """``set_optional_content_properties`` shares the version-bump side
    effect — optional content groups require PDF 1.5 (matches upstream
    ``setOCProperties``)."""
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentProperties,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    doc.set_version(1.4)

    props = PDOptionalContentProperties()
    cat.set_optional_content_properties(props)
    assert doc.get_version() == 1.5
    assert cat.get_optional_content_properties() is not None

    cat.set_optional_content_properties(None)
    assert cat.get_optional_content_properties() is None


# ---------- /URI /Base catalog-level shortcut ----------


def test_get_base_uri_absent_returns_none() -> None:
    """``/URI`` absent → ``None``; ``/URI`` present without ``/Base`` →
    ``None``."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_base_uri() is None

    # /URI present but empty.
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("URI"), COSDictionary()
    )
    assert cat.get_base_uri() is None


def test_set_base_uri_creates_uri_dict_on_demand() -> None:
    """Writing ``/URI /Base`` materialises the ``/URI`` sub-dictionary
    on the catalog when absent — mirrors the
    :meth:`set_document_marked` style auto-create behaviour."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert COSName.get_pdf_name("URI") not in cat

    cat.set_base_uri("https://example.com/")
    assert cat.get_base_uri() == "https://example.com/"
    uri_dict = cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("URI")
    )
    assert isinstance(uri_dict, COSDictionary)
    assert uri_dict.get_string("Base") == "https://example.com/"


def test_set_base_uri_round_trip_with_existing_uri_dict() -> None:
    """Writing ``/URI /Base`` reuses the existing ``/URI`` sub-dictionary
    rather than replacing it — preserves any sibling entries some
    producers attach (PDF 32000-1 §12.6.4.7 only defines ``/Base`` but
    leaves the dictionary extensible)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    existing = COSDictionary()
    existing.set_string("Custom", "keep-me")
    cat.get_cos_object().set_item(COSName.get_pdf_name("URI"), existing)

    cat.set_base_uri("https://pdf.example/")
    fetched = cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("URI")
    )
    assert fetched is existing  # not replaced
    assert fetched.get_string("Base") == "https://pdf.example/"
    assert fetched.get_string("Custom") == "keep-me"


def test_set_base_uri_none_clears_base_and_removes_empty_uri_dict() -> None:
    """Setting ``/Base`` to ``None`` clears just that entry; if the
    ``/URI`` dictionary becomes empty as a result it is removed from the
    catalog so the catalog stays minimal."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_base_uri("https://example.com/")
    assert COSName.get_pdf_name("URI") in cat

    cat.set_base_uri(None)
    assert cat.get_base_uri() is None
    assert COSName.get_pdf_name("URI") not in cat


def test_set_base_uri_none_preserves_non_empty_uri_dict() -> None:
    """If sibling entries remain after clearing ``/Base``, the ``/URI``
    dictionary is left in place (only the ``/Base`` key is removed)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_base_uri("https://example.com/")
    uri_dict = cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("URI")
    )
    assert isinstance(uri_dict, COSDictionary)
    uri_dict.set_string("Custom", "stay")

    cat.set_base_uri(None)
    assert cat.get_base_uri() is None
    fetched = cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("URI")
    )
    assert isinstance(fetched, COSDictionary)
    assert fetched.get_string("Custom") == "stay"


def test_set_base_uri_none_when_uri_absent_is_a_noop() -> None:
    """Clearing ``/Base`` when ``/URI`` is absent is a no-op (no fresh
    dictionary materialised)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert COSName.get_pdf_name("URI") not in cat
    cat.set_base_uri(None)
    assert COSName.get_pdf_name("URI") not in cat
