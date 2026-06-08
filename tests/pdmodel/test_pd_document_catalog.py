from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDDocumentOutline
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)


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


def test_get_dests_wraps_legacy_destination_dictionary() -> None:
    # Upstream PDDocumentCatalog.getDests wraps the flat (PDF 1.1) /Dests
    # catalog entry in PDDocumentNameDestinationDictionary (whose keys map
    # directly to destinations), NOT the name-tree node form.
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    dests_dict = COSDictionary()
    catalog.get_cos_object().set_item(COSName.get_pdf_name("Dests"), dests_dict)

    dests = catalog.get_dests()
    assert isinstance(dests, PDDocumentNameDestinationDictionary)
    assert dests.get_cos_object() is dests_dict

    dest = PDPageXYZDestination()
    dest.set_page_number(1)
    dests.set_destination("Chapter1", dest)

    resolved = catalog.get_dests()
    assert isinstance(resolved, PDDocumentNameDestinationDictionary)
    fetched = resolved.get_destination("Chapter1")
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
    """Repeated ``get_acro_form(None)`` calls return the same wrapper
    instance after the first lookup (parity with upstream
    ``cachedAcroForm``).

    Note: this caching holds for the *same fixup* (or ``None``). Two
    consecutive **no-arg** ``get_acro_form()`` calls each mint a fresh
    ``AcroFormDefaultFixup`` which clears the cache, so they return
    *different* wrapper instances — confirmed against the live PDFBox
    3.0.7 oracle (``getAcroForm() == getAcroForm()`` is ``false``); see
    :func:`test_get_acro_form_no_arg_mints_fresh_wrapper_each_call`."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))
    a = cat.get_acro_form(None)
    b = cat.get_acro_form(None)
    assert a is b


def test_get_acro_form_no_arg_mints_fresh_wrapper_each_call() -> None:
    """Two consecutive no-arg ``get_acro_form()`` calls return distinct
    wrapper instances because each creates a fresh
    ``AcroFormDefaultFixup`` that clears the cache — mirroring upstream's
    no-arg ``getAcroForm()`` which is ``getAcroForm(new
    AcroFormDefaultFixup(document))`` (oracle-confirmed: PDFBox 3.0.7
    returns ``f1 != f2``). The backing ``/AcroForm`` dict is identical."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_acro_form(PDAcroForm(doc))
    a = cat.get_acro_form()
    b = cat.get_acro_form()
    assert a is not b
    assert a.get_cos_object() is b.get_cos_object()


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


# ---------- get_page_mode_or_default / get_page_layout_or_default ----------


def test_get_page_mode_or_default_returns_use_none_when_absent() -> None:
    """Mirrors upstream ``getPageMode()`` — implicit ``UseNone`` when
    ``/PageMode`` is absent (PDF 32000-1 §7.7.3.3 Table 28)."""
    from pypdfbox.pdmodel.page_mode import PageMode

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_page_mode_or_default() is PageMode.USE_NONE


def test_get_page_mode_or_default_returns_use_none_when_unrecognised() -> None:
    """An unrecognised ``/PageMode`` value also collapses to the spec
    default — matches upstream's ``IllegalArgumentException`` →
    ``USE_NONE`` fallback in ``getPageMode()``."""
    from pypdfbox.pdmodel.page_mode import PageMode

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PageMode"), COSName.get_pdf_name("BogusMode")
    )
    assert cat.get_page_mode_or_default() is PageMode.USE_NONE


def test_get_page_mode_or_default_returns_explicit_value() -> None:
    """When ``/PageMode`` is set to a recognised value, the helper
    returns it unchanged (no default substitution)."""
    from pypdfbox.pdmodel.page_mode import PageMode

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_page_mode(PageMode.USE_OUTLINES)
    assert cat.get_page_mode_or_default() is PageMode.USE_OUTLINES


def test_get_page_layout_or_default_returns_single_page_when_absent() -> None:
    """Mirrors upstream ``getPageLayout()`` — implicit ``SinglePage``
    when ``/PageLayout`` is absent."""
    from pypdfbox.pdmodel.page_layout import PageLayout

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_page_layout_or_default() is PageLayout.SINGLE_PAGE


def test_get_page_layout_or_default_returns_single_page_when_unrecognised() -> None:
    """An unrecognised ``/PageLayout`` value collapses to ``SinglePage``
    — matches upstream's ``IllegalArgumentException`` → ``SINGLE_PAGE``
    fallback."""
    from pypdfbox.pdmodel.page_layout import PageLayout

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PageLayout"),
        COSName.get_pdf_name("BogusLayout"),
    )
    assert cat.get_page_layout_or_default() is PageLayout.SINGLE_PAGE


def test_get_page_layout_or_default_returns_explicit_value() -> None:
    """When ``/PageLayout`` is set to a recognised value, the helper
    returns it unchanged."""
    from pypdfbox.pdmodel.page_layout import PageLayout

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_page_layout(PageLayout.TWO_COLUMN_LEFT)
    assert cat.get_page_layout_or_default() is PageLayout.TWO_COLUMN_LEFT


# ---------- presence predicates ----------


def test_has_acro_form_reflects_entry_presence() -> None:
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_acro_form() is False

    cat.set_acro_form(PDAcroForm(doc))
    assert cat.has_acro_form() is True

    # Stray non-dict entry counts as "no" (defensive parity with
    # ``get_acro_form`` returning ``None`` for malformed values).
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("AcroForm"), COSString("not-a-dict")
    )
    assert cat.has_acro_form() is False

    cat.set_acro_form(None)
    assert cat.has_acro_form() is False


def test_has_struct_tree_root_reflects_entry_presence() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_struct_tree_root() is False

    cat.set_struct_tree_root(PDStructureTreeRoot())
    assert cat.has_struct_tree_root() is True

    cat.set_struct_tree_root(None)
    assert cat.has_struct_tree_root() is False


def test_has_metadata_requires_stream_not_dict() -> None:
    """``/Metadata`` must be a stream — a stray dict-typed entry should
    read as absent, mirroring :meth:`get_metadata`'s type guard."""
    from pypdfbox.cos import COSStream

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_metadata() is False

    # A plain dict is wrong shape — has_metadata stays False.
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Metadata"), COSDictionary()
    )
    assert cat.has_metadata() is False

    # A real stream flips it to True.
    cat.set_metadata(COSStream())
    assert cat.has_metadata() is True


def test_has_outline_reflects_entry_presence() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_outline() is False

    cat.set_document_outline(PDDocumentOutline())
    assert cat.has_outline() is True

    cat.set_document_outline(None)
    assert cat.has_outline() is False


def test_has_page_labels_reflects_entry_presence() -> None:
    from pypdfbox.pdmodel.pd_page_labels import PDPageLabels

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_page_labels() is False

    cat.set_page_labels(PDPageLabels(doc))
    assert cat.has_page_labels() is True

    cat.set_page_labels(None)
    assert cat.has_page_labels() is False


def test_has_open_action_accepts_dict_or_array() -> None:
    """``/OpenAction`` is legitimately either an action dictionary or a
    destination array — both shapes flip the predicate to ``True``."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_open_action() is False

    # Action dictionary form.
    action = COSDictionary()
    action.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("URI"))
    cat.set_open_action(action)
    assert cat.has_open_action() is True

    # Destination array form.
    cat.set_open_action(COSArray())
    assert cat.has_open_action() is True

    cat.set_open_action(None)
    assert cat.has_open_action() is False


def test_has_open_action_false_for_unrecognised_value() -> None:
    """A non-dict, non-array stray value (e.g. an integer) reads as
    absent — matches :meth:`get_open_action`'s ``None`` fallback."""
    from pypdfbox.cos import COSInteger

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("OpenAction"), COSInteger.get(1)
    )
    assert cat.has_open_action() is False


def test_has_names_reflects_entry_presence() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_names() is False

    cat.get_cos_object().set_item(COSName.get_pdf_name("Names"), COSDictionary())
    assert cat.has_names() is True

    cat.set_names(None)
    assert cat.has_names() is False


def test_has_oc_properties_reflects_entry_presence() -> None:
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentProperties,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_oc_properties() is False

    cat.set_oc_properties(PDOptionalContentProperties())
    assert cat.has_oc_properties() is True

    cat.set_oc_properties(None)
    assert cat.has_oc_properties() is False


# ---------- is_tagged ----------


def test_is_tagged_false_when_mark_info_absent() -> None:
    """``is_tagged`` follows the strict spec: needs ``/MarkInfo /Marked``
    set to ``True``. A document with no ``/MarkInfo`` reads as untagged
    even when ``/StructTreeRoot`` is present."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.is_tagged() is False

    # Adding only a struct tree root is not enough — spec requires the
    # producer commitment carried by ``/MarkInfo /Marked``.
    cat.set_struct_tree_root(PDStructureTreeRoot())
    assert cat.is_tagged() is False


def test_is_tagged_true_when_mark_info_marked() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_document_marked(True)
    assert cat.is_tagged() is True


def test_is_tagged_false_when_mark_info_explicitly_unmarked() -> None:
    """``/MarkInfo`` present but ``/Marked = false`` is explicitly
    untagged."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_document_marked(False)
    assert cat.is_tagged() is False


# ---------- Wave 219: more presence predicates + validation + AcroForm helper ----------


def test_has_viewer_preferences_reflects_entry_presence() -> None:
    from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_viewer_preferences() is False

    cat.set_viewer_preferences(PDViewerPreferences(COSDictionary()))
    assert cat.has_viewer_preferences() is True

    cat.set_viewer_preferences(None)
    assert cat.has_viewer_preferences() is False


def test_has_viewer_preferences_false_for_stray_value() -> None:
    """A non-dictionary stray value reads as absent."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("ViewerPreferences"), COSString("nope")
    )
    assert cat.has_viewer_preferences() is False


def test_has_mark_info_independent_of_marked_flag() -> None:
    """``has_mark_info`` only checks the dictionary's presence, not the
    ``/Marked`` boolean inside — explicitly ``/Marked=false`` still has
    a MarkInfo dict."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_mark_info() is False

    cat.set_document_marked(False)
    assert cat.has_mark_info() is True
    assert cat.is_tagged() is False  # /Marked is False, but dict exists.

    cat.set_document_marked(True)
    assert cat.has_mark_info() is True


def test_has_threads_false_for_empty_array() -> None:
    """Empty ``/Threads`` arrays read as absent — matches "no article
    threads to navigate" semantics."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_threads() is False

    # ``get_threads`` auto-creates an empty array; predicate still says no.
    cat.get_threads()
    assert cat.has_threads() is False


def test_has_threads_true_when_populated() -> None:
    from pypdfbox.pdmodel.interactive.pagenavigation import PDThread

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_threads([PDThread()])
    assert cat.has_threads() is True

    cat.set_threads(None)
    assert cat.has_threads() is False


def test_has_dests_reflects_legacy_entry_presence() -> None:
    """``has_dests`` checks the catalog-level legacy ``/Dests`` dictionary,
    distinct from the modern ``/Names /Dests`` name tree."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_dests() is False

    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Dests"), COSDictionary()
    )
    assert cat.has_dests() is True

    cat.set_dests(None)
    assert cat.has_dests() is False


def test_has_uri_reflects_entry_presence() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_uri() is False

    cat.set_base_uri("https://example.com/")
    assert cat.has_uri() is True

    cat.set_uri(None)
    assert cat.has_uri() is False


def test_has_associated_files_false_for_empty_array() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_associated_files() is False

    # An explicit empty array is treated as absent.
    cat.get_cos_object().set_item(COSName.get_pdf_name("AF"), COSArray())
    assert cat.has_associated_files() is False


def test_has_associated_files_true_when_populated() -> None:
    from pypdfbox.pdmodel.common.filespecification import (
        PDComplexFileSpecification,
    )

    doc = PDDocument()
    cat = doc.get_document_catalog()
    fs = PDComplexFileSpecification()
    fs.set_file("attached.txt")
    cat.set_associated_files([fs])
    assert cat.has_associated_files() is True

    cat.set_associated_files(None)
    assert cat.has_associated_files() is False


def test_has_requirements_false_for_empty_array() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_requirements() is False

    cat.get_cos_object().set_item(COSName.get_pdf_name("Requirements"), COSArray())
    assert cat.has_requirements() is False


def test_has_requirements_true_when_populated() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    req = COSDictionary()
    req.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("EnableJavaScripts"))
    cat.add_requirement(req)
    assert cat.has_requirements() is True

    cat.set_requirements(None)
    assert cat.has_requirements() is False


def test_has_developer_extensions_false_for_empty_dict() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_developer_extensions() is False

    # An empty /Extensions dict counts as absent for the predicate.
    cat.get_cos_object().set_item(COSName.get_pdf_name("Extensions"), COSDictionary())
    assert cat.has_developer_extensions() is False


def test_has_developer_extensions_true_when_populated() -> None:
    from pypdfbox.pdmodel.pd_developer_extension import PDDeveloperExtension

    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)
    assert cat.has_developer_extensions() is True

    cat.remove_developer_extension("ADBE")
    # The /Extensions dict was removed when last entry left.
    assert cat.has_developer_extensions() is False


# ---------- get_acro_form_or_create ----------


def test_get_acro_form_or_create_materialises_when_absent() -> None:
    """Returns a fresh, non-``None`` :class:`PDAcroForm` and persists it
    on the catalog."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_acro_form() is None
    assert cat.has_acro_form() is False

    form = cat.get_acro_form_or_create()
    assert isinstance(form, PDAcroForm)
    assert cat.has_acro_form() is True
    # Persisted on the catalog dictionary.
    assert isinstance(
        cat.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AcroForm")),
        COSDictionary,
    )


def test_get_acro_form_or_create_returns_existing_when_present() -> None:
    """Pre-existing AcroForm is returned unchanged — no rewrite of the
    underlying ``/AcroForm`` dictionary."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    original = PDAcroForm(doc)
    cat.set_acro_form(original)
    original_dict = original.get_cos_object()

    fetched = cat.get_acro_form_or_create()
    assert fetched.get_cos_object() is original_dict


# ---------- type validation in set_output_intents / set_associated_files ----------


def test_set_output_intents_rejects_non_pd_output_intent() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    with pytest.raises(TypeError, match="PDOutputIntent"):
        cat.set_output_intents([COSDictionary()])


def test_set_associated_files_rejects_non_filespec() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    with pytest.raises(TypeError, match="PDFileSpecification"):
        cat.set_associated_files(["not-a-spec"])


# ---------- Wave 259: typed name-as-string accessors tolerate COSString ----------


def test_get_version_accepts_cos_string() -> None:
    """Mirrors upstream ``getNameAsString`` — defensively accepts the
    rare malformed-producer case of ``/Version`` written as a string."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Version"), COSString("1.7")
    )
    assert cat.get_version() == "1.7"


def test_get_version_returns_none_when_entry_is_unrecognised_type() -> None:
    """Non-name / non-string entries (integers, arrays, etc.) read as
    absent — type-tolerant but type-correct."""
    from pypdfbox.cos import COSInteger

    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Version"), COSInteger.get(2)
    )
    assert cat.get_version() is None


def test_get_page_layout_accepts_cos_string() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PageLayout"), COSString("TwoColumnLeft")
    )
    assert cat.get_page_layout() == "TwoColumnLeft"


def test_get_page_mode_accepts_cos_string() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PageMode"), COSString("UseOutlines")
    )
    assert cat.get_page_mode() == "UseOutlines"


def test_get_page_layout_empty_string_returns_none() -> None:
    """Upstream ``getPageLayout`` treats empty strings as absent; pypdfbox
    matches that posture — empty COSString reads as ``None`` rather than
    raising on the unrecognised name."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PageLayout"), COSString("")
    )
    assert cat.get_page_layout() is None
    # ...and the default-applying read still falls back to SinglePage.
    from pypdfbox.pdmodel.page_layout import PageLayout

    assert cat.get_page_layout_or_default() == PageLayout.SINGLE_PAGE


def test_get_page_mode_empty_string_returns_none() -> None:
    """Empty COSString for ``/PageMode`` reads as absent (parity with
    upstream's ``getNameAsString`` returning empty, which falls into the
    ``IllegalArgumentException`` branch and yields ``USE_NONE``)."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("PageMode"), COSString("")
    )
    assert cat.get_page_mode() is None


# ---------- Wave 259: presence predicates round-out ----------


def test_has_collection_and_is_collection_round_trip() -> None:
    """``/Collection`` flips a regular PDF into a Portfolio (PDF 1.7
    §7.11.5). ``has_collection()`` and ``is_collection()`` are synonyms."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_collection() is False
    assert cat.is_collection() is False

    coll = COSDictionary()
    cat.set_collection(coll)
    assert cat.has_collection() is True
    assert cat.is_collection() is True

    cat.set_collection(None)
    assert cat.has_collection() is False
    assert cat.is_collection() is False


def test_has_collection_rejects_non_dict_entry() -> None:
    """A stray non-dict ``/Collection`` value reads as absent — mirrors
    the ``isinstance`` guard used elsewhere in the predicate family."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Collection"), COSArray()
    )
    assert cat.has_collection() is False


def test_dictionary_only_catalog_setters_reject_non_dict_values() -> None:
    """Dictionary-typed catalog setters reject stray COS values at the API
    boundary instead of persisting malformed entries."""
    with PDDocument() as doc:
        cat = doc.get_document_catalog()

        with pytest.raises(TypeError, match="set_perms expected COSDictionary"):
            cat.set_perms(COSArray())  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="set_legal expected COSDictionary"):
            cat.set_legal(COSArray())  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="set_collection expected COSDictionary"):
            cat.set_collection(COSArray())  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="set_piece_info expected COSDictionary"):
            cat.set_piece_info(COSArray())  # type: ignore[arg-type]


def test_has_perms_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_perms() is False
    cat.set_perms(COSDictionary())
    assert cat.has_perms() is True
    cat.set_perms(None)
    assert cat.has_perms() is False


def test_has_legal_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_legal() is False
    cat.set_legal(COSDictionary())
    assert cat.has_legal() is True
    cat.set_legal(None)
    assert cat.has_legal() is False


def test_has_piece_info_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_piece_info() is False
    cat.set_piece_info(COSDictionary())
    assert cat.has_piece_info() is True
    cat.set_piece_info(None)
    assert cat.has_piece_info() is False


def test_has_language_only_true_for_cos_string() -> None:
    """``/Lang`` is spec-defined as a text string. A ``COSName`` value
    (occasionally seen in malformed producers) does NOT count for the
    predicate — only the spec-correct ``COSString`` shape does. Read
    accessors stay tolerant; the predicate stays strict."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.has_language() is False

    cat.set_language("en-US")
    assert cat.has_language() is True

    cat.set_language(None)
    assert cat.has_language() is False

    # COSName /Lang — invalid shape, predicate stays False.
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Lang"), COSName.get_pdf_name("en-US")
    )
    assert cat.has_language() is False


def test_has_version_round_trip_and_accepts_cos_string() -> None:
    """``has_version`` flips when ``/Version`` is explicitly cleared and
    flips back regardless of whether the value is a ``COSName`` or a
    (defensively-tolerated) ``COSString``."""
    doc = PDDocument()
    cat = doc.get_document_catalog()

    # PDDocument's constructor pre-populates ``/Version`` (PDFBox keeps
    # the catalog version in sync with the header). Clear it first so
    # the predicate has somewhere to flip from.
    cat.set_version(None)
    assert cat.has_version() is False

    cat.set_version("1.7")
    assert cat.has_version() is True

    cat.set_version(None)
    assert cat.has_version() is False

    # Defensive: COSString /Version still counts as "present".
    cat.get_cos_object().set_item(
        COSName.get_pdf_name("Version"), COSString("1.7")
    )
    assert cat.has_version() is True


def test_has_dests_name_tree_distinguishes_modern_from_legacy() -> None:
    """``/Names /Dests`` (modern, PDF 1.2+) and ``/Dests`` (legacy,
    PDF 1.1) live on the catalog independently. The two predicates
    address them separately so callers can tell which scheme is wired."""
    doc = PDDocument()
    cat = doc.get_document_catalog()

    assert cat.has_dests_name_tree() is False
    assert cat.has_dests() is False

    # Wire only the legacy /Dests dict — modern predicate stays False.
    legacy = COSDictionary()
    cat.get_cos_object().set_item(COSName.get_pdf_name("Dests"), legacy)
    assert cat.has_dests() is True
    assert cat.has_dests_name_tree() is False

    # Now also wire /Names /Dests — modern predicate flips True.
    names = COSDictionary()
    dests_tree = COSDictionary()
    names.set_item(COSName.get_pdf_name("Dests"), dests_tree)
    cat.get_cos_object().set_item(COSName.get_pdf_name("Names"), names)
    assert cat.has_dests_name_tree() is True


def test_has_dests_name_tree_false_when_names_is_present_but_dests_absent() -> None:
    """``/Names`` without a ``/Dests`` sub-entry reads as no name tree."""
    doc = PDDocument()
    cat = doc.get_document_catalog()
    names = COSDictionary()
    # JavaScript name tree only — no /Dests.
    names.set_item(COSName.get_pdf_name("JavaScript"), COSDictionary())
    cat.get_cos_object().set_item(COSName.get_pdf_name("Names"), names)
    assert cat.has_names() is True
    assert cat.has_dests_name_tree() is False
