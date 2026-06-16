"""Wave 1575 — PDFMergerUtility fuzz / parity sweep (agent B).

Hammers ``PDFMergerUtility`` against the behaviours upstream
``org.apache.pdfbox.multipdf.PDFMergerUtility`` guarantees:

- page-count sums and ``/Pages /Count`` / ``/Kids`` correctness after a
  two-document merge (and N-document merges),
- object renumbering produces no collisions / no shared dictionaries
  between the two source page graphs,
- merging a source with an ``/AcroForm`` into a destination without one
  (whole-form clone) and into one with one (field-name dedup via
  ``dummyFieldName<N>``),
- the **regression pinned by this wave**: a destination form that exists
  but carries *no* ``/Fields`` key must still rename duplicate-named
  source fields (previously two ``F`` fields landed verbatim),
- named destinations (``/Names /Dests`` and legacy ``/Dests``) remap so a
  destination pointing at a cloned page resolves to the *new* page,
- an empty source document (zero pages) contributes nothing,
- merging a document into itself doubles its pages,
- ``/OpenAction`` is first-source-wins and its page reference is remapped,
- the AcroForm merge-mode setting (LEGACY vs JOIN delegate),
- page content (``/Contents``) survives the clone.

All comparisons are to PDFBox 3.0.x behaviour. ``PDDocument`` instances
are closed before any temp-file unlink (Windows file-lock safety) — these
tests use in-memory ``BytesIO`` destinations where possible.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")
_PAGES = COSName.get_pdf_name("Pages")
_COUNT = COSName.get_pdf_name("Count")
_KIDS = COSName.get_pdf_name("Kids")
_PARENT = COSName.get_pdf_name("Parent")
_OPEN_ACTION = COSName.get_pdf_name("OpenAction")
_NAMES = COSName.get_pdf_name("Names")
_DESTS = COSName.get_pdf_name("Dests")
_ACRO_FORM = COSName.get_pdf_name("AcroForm")
_CONTENTS = COSName.get_pdf_name("Contents")
_FIT = COSName.get_pdf_name("Fit")


# ---------- builders ----------


def _page(marker: bytes = b"% page\n") -> PDPage:
    p = PDPage()
    s = COSStream()
    s.set_raw_data(marker)
    p.set_contents(s)
    return p


def _doc(n: int, marker_prefix: bytes = b"% page ") -> PDDocument:
    doc = PDDocument()
    for i in range(n):
        doc.add_page(_page(marker_prefix + str(i).encode("ascii") + b"\n"))
    return doc


def _doc_with_fields(
    field_names: list[str], with_fields_key: bool = True
) -> PDDocument:
    doc = PDDocument()
    doc.add_page(_page())
    form = PDAcroForm(doc)
    if with_fields_key:
        fields = COSArray()
        for name in field_names:
            f = COSDictionary()
            f.set_item(_FT, COSName.get_pdf_name("Tx"))
            f.set_string(_T, name)
            fields.add(f)
        form.get_cos_object().set_item(_FIELDS, fields)
    else:
        form.get_cos_object().remove_item(_FIELDS)
    doc.get_document_catalog().set_acro_form(form)
    return doc


def _merge_to_bytes(sources: list[PDDocument], **kw) -> bytes:
    out = io.BytesIO()
    util = PDFMergerUtility()
    for src in sources:
        util.add_source(src)
    util.set_destination_stream(out)
    mode = kw.get("acro_mode")
    if mode is not None:
        util.set_acro_form_merge_mode(mode)
    doc_mode = kw.get("doc_mode")
    if doc_mode is not None:
        util.set_document_merge_mode(doc_mode)
    util.merge_documents()
    return out.getvalue()


def _partial_names(doc: PDDocument) -> list[str]:
    form = doc.get_document_catalog().get_acro_form()
    if form is None:
        return []
    return [f.get_partial_name() or "" for f in form.get_fields()]


def _pages_node(doc: PDDocument) -> COSDictionary:
    cat = doc.get_document_catalog().get_cos_object()
    node = cat.get_dictionary_object(_PAGES)
    assert isinstance(node, COSDictionary)
    return node


# ---------- page-count + /Count + /Kids ----------


@pytest.mark.parametrize(
    ("na", "nb"),
    [(1, 1), (2, 3), (3, 2), (5, 0), (0, 4), (1, 7), (10, 1)],
)
def test_page_count_sums(na: int, nb: int) -> None:
    a = _doc(na)
    b = _doc(nb)
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        assert m.get_number_of_pages() == na + nb
        node = _pages_node(m)
        count = node.get_dictionary_object(_COUNT)
        kids = node.get_dictionary_object(_KIDS)
        assert count.int_value() == na + nb
        assert isinstance(kids, COSArray)
        assert kids.size() == na + nb


def test_three_document_merge_count() -> None:
    a, b, c = _doc(2), _doc(3), _doc(1)
    data = _merge_to_bytes([a, b, c])
    for d in (a, b, c):
        d.close()
    with PDDocument.load(data) as m:
        assert m.get_number_of_pages() == 6
        assert _pages_node(m).get_dictionary_object(_COUNT).int_value() == 6


def test_n_document_merge_many_sources() -> None:
    docs = [_doc(1) for _ in range(12)]
    data = _merge_to_bytes(docs)
    for d in docs:
        d.close()
    with PDDocument.load(data) as m:
        assert m.get_number_of_pages() == 12


# ---------- object renumbering: no shared dicts / parents wired ----------


def test_merged_pages_are_distinct_objects() -> None:
    a, b = _doc(2), _doc(2)
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        pages = list(m.get_pages())
        cos_ids = [id(p.get_cos_object()) for p in pages]
        assert len(set(cos_ids)) == len(cos_ids)


def test_every_merged_page_parent_points_at_pages_node() -> None:
    a, b = _doc(2), _doc(3)
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        node = _pages_node(m)
        for p in m.get_pages():
            parent = p.get_cos_object().get_dictionary_object(_PARENT)
            assert parent is node


def test_page_content_preserved() -> None:
    a = PDDocument()
    a.add_page(_page(b"% AAA unique marker\n"))
    b = PDDocument()
    b.add_page(_page(b"% BBB unique marker\n"))
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        pages = list(m.get_pages())
        bodies = []
        for p in pages:
            stream = p.get_cos_object().get_dictionary_object(_CONTENTS)
            assert isinstance(stream, COSStream)
            with stream.create_input_stream() as inp:
                bodies.append(inp.read())
        joined = b"".join(bodies)
        assert b"AAA unique marker" in joined
        assert b"BBB unique marker" in joined


# ---------- AcroForm: clone-whole vs dedup ----------


def test_form_cloned_whole_when_dest_has_none() -> None:
    dest = _doc(1)  # no form
    src = _doc_with_fields(["one", "two"])
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        assert sorted(_partial_names(m)) == ["one", "two"]


def test_form_field_dedup_on_collision() -> None:
    a = _doc_with_fields(["dup"])
    b = _doc_with_fields(["dup"])
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        names = _partial_names(m)
        assert names.count("dup") == 1
        assert any(n.startswith("dummyFieldName") for n in names)


def test_no_dedup_when_names_distinct() -> None:
    a = _doc_with_fields(["x", "y"])
    b = _doc_with_fields(["p", "q"])
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        assert sorted(_partial_names(m)) == ["p", "q", "x", "y"]


def test_intra_source_dup_renamed_into_empty_array_dest() -> None:
    # dest form has an EMPTY /Fields array; source has three "F".
    dest = _doc_with_fields([], with_fields_key=True)
    src = _doc_with_fields(["F", "F", "F"])
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        names = _partial_names(m)
        # dest /Fields is empty, so the first "F" has no collision and is
        # kept; the second and third collide and are renamed.
        assert names.count("F") == 1
        dummies = [n for n in names if n.startswith("dummyFieldName")]
        assert len(dummies) == 2
        assert len(set(names)) == 3


def test_intra_source_dup_renamed_when_dest_form_has_no_fields_key() -> None:
    """Regression (wave 1575): a destination form that exists but carries
    no ``/Fields`` key must still rename duplicate-named source fields.

    Before the fix the freshly-created ``/Fields`` array was attached to
    the dest dict only *after* the field loop, so the live-view collision
    check (``dest_form.get_field(fqn)``) could not see in-progress
    additions and two ``F`` fields landed verbatim. Now the array is
    installed before the loop, matching upstream PDFBox which stamps the
    fresh COSArray immediately."""
    dest = _doc_with_fields([], with_fields_key=False)
    src = _doc_with_fields(["F", "F"])
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        names = _partial_names(m)
        # First "F" kept, the second renamed — never two bare "F".
        assert names.count("F") == 1
        assert len(set(names)) == 2
        assert any(n.startswith("dummyFieldName") for n in names)


def test_empty_source_form_leaves_dest_fields_untouched() -> None:
    dest = _doc_with_fields(["keep"])
    src = _doc_with_fields([])  # empty fields array, nothing to merge
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        assert _partial_names(m) == ["keep"]


def test_join_mode_matches_legacy_for_collisions() -> None:
    a = _doc_with_fields(["A"])
    b = _doc_with_fields(["A"])
    c = _doc_with_fields(["A"])
    legacy = _merge_to_bytes(
        [_doc_with_fields(["A"]), _doc_with_fields(["A"]), _doc_with_fields(["A"])],
        acro_mode=AcroFormMergeMode.PDFBOX_LEGACY_MODE,
    )
    join = _merge_to_bytes(
        [a, b, c], acro_mode=AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    )
    a.close()
    b.close()
    c.close()
    with PDDocument.load(legacy) as ml, PDDocument.load(join) as mj:
        assert sorted(_partial_names(ml)) == sorted(_partial_names(mj))
        assert sorted(_partial_names(mj)) == [
            "A",
            "dummyFieldName1",
            "dummyFieldName2",
        ]


def test_dummy_field_counter_survives_consecutive_appends() -> None:
    a = _doc_with_fields(["Z"])
    b = _doc_with_fields(["Z"])
    c = _doc_with_fields(["Z"])
    data = _merge_to_bytes([a, b, c])
    a.close()
    b.close()
    c.close()
    with PDDocument.load(data) as m:
        names = _partial_names(m)
        assert names.count("Z") == 1
        dummies = sorted(n for n in names if n.startswith("dummyFieldName"))
        assert dummies == ["dummyFieldName1", "dummyFieldName2"]


# ---------- empty source / self merge ----------


def test_empty_source_contributes_no_pages() -> None:
    empty = _doc(0)
    src = _doc(3)
    data = _merge_to_bytes([empty, src])
    empty.close()
    src.close()
    with PDDocument.load(data) as m:
        assert m.get_number_of_pages() == 3


def test_merge_document_into_itself_doubles_pages() -> None:
    doc = _doc(2)
    out = io.BytesIO()
    util = PDFMergerUtility()
    util.add_source(doc)
    util.add_source(doc)
    util.set_destination_stream(out)
    util.merge_documents()
    doc.close()
    with PDDocument.load(out.getvalue()) as m:
        assert m.get_number_of_pages() == 4


def test_only_empty_sources_yield_empty_pages_node() -> None:
    a, b = _doc(0), _doc(0)
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        assert m.get_number_of_pages() == 0


# ---------- /OpenAction ----------


def _doc_with_open_action_to_last_page(n: int) -> PDDocument:
    doc = _doc(n)
    last = list(doc.get_pages())[-1]
    oa = COSArray()
    oa.add(last.get_cos_object())
    oa.add(_FIT)
    doc.get_document_catalog().get_cos_object().set_item(_OPEN_ACTION, oa)
    return doc


def test_open_action_remapped_to_cloned_page() -> None:
    dest = _doc(1)  # no OpenAction
    src = _doc_with_open_action_to_last_page(3)
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        cat = m.get_document_catalog().get_cos_object()
        oa = cat.get_dictionary_object(_OPEN_ACTION)
        assert isinstance(oa, COSArray)
        target = oa.get_object(0)
        pages = list(m.get_pages())
        # src last page is merged index = 1 (dest) + 2 (src page idx) = 3.
        assert pages[3].get_cos_object() is target


def test_open_action_first_source_wins() -> None:
    a = _doc_with_open_action_to_last_page(2)  # OA -> a's page index 1
    b = _doc_with_open_action_to_last_page(2)  # OA -> b's page index 1
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        cat = m.get_document_catalog().get_cos_object()
        oa = cat.get_dictionary_object(_OPEN_ACTION)
        target = oa.get_object(0)
        pages = list(m.get_pages())
        # First source wins => target is the first source's last page (index 1).
        assert pages[1].get_cos_object() is target


def test_dest_open_action_not_overwritten() -> None:
    dest = _doc_with_open_action_to_last_page(2)
    src = _doc_with_open_action_to_last_page(2)
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        cat = m.get_document_catalog().get_cos_object()
        oa = cat.get_dictionary_object(_OPEN_ACTION)
        target = oa.get_object(0)
        pages = list(m.get_pages())
        assert pages[1].get_cos_object() is target


# ---------- named destinations ----------


def _doc_with_named_dest(n: int, name: str) -> PDDocument:
    """Build a doc with /Names /Dests mapping ``name`` -> [lastpage /Fit]."""
    doc = _doc(n)
    last = list(doc.get_pages())[-1]
    dest_array = COSArray()
    dest_array.add(last.get_cos_object())
    dest_array.add(_FIT)
    # /Names /Dests: { /Names [ (name) <<...>> ] }
    names_leaf = COSArray()
    names_leaf.add(COSString(name))
    dest_value = COSDictionary()
    dest_value.set_item(COSName.get_pdf_name("D"), dest_array)
    names_leaf.add(dest_value)
    dests_tree = COSDictionary()
    dests_tree.set_item(_NAMES, names_leaf)
    names_dict = COSDictionary()
    names_dict.set_item(_DESTS, dests_tree)
    doc.get_document_catalog().get_cos_object().set_item(_NAMES, names_dict)
    return doc


def _collect_dest_names(doc: PDDocument) -> list[str]:
    cat = doc.get_document_catalog().get_cos_object()
    names = cat.get_dictionary_object(_NAMES)
    if not isinstance(names, COSDictionary):
        return []
    dests = names.get_dictionary_object(_DESTS)
    if not isinstance(dests, COSDictionary):
        return []
    leaf = dests.get_dictionary_object(_NAMES)
    out: list[str] = []
    if isinstance(leaf, COSArray):
        i = 0
        while i + 1 < leaf.size():
            key = leaf.get_object(i)
            if isinstance(key, COSString):
                out.append(key.get_string())
            i += 2
    return out


def test_named_dests_merged_when_dest_has_none() -> None:
    dest = _doc(1)
    src = _doc_with_named_dest(2, "Chapter1")
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        assert "Chapter1" in _collect_dest_names(m)


def test_named_dests_unioned_from_both_sources() -> None:
    a = _doc_with_named_dest(1, "A_dest")
    b = _doc_with_named_dest(1, "B_dest")
    data = _merge_to_bytes([a, b])
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        names = _collect_dest_names(m)
        assert "A_dest" in names
        assert "B_dest" in names


def test_named_dest_target_resolves_to_cloned_page() -> None:
    dest = _doc(2)
    src = _doc_with_named_dest(2, "TheDest")  # points at src page index 1
    data = _merge_to_bytes([dest, src])
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        cat = m.get_document_catalog().get_cos_object()
        names = cat.get_dictionary_object(_NAMES)
        dests = names.get_dictionary_object(_DESTS)
        leaf = dests.get_dictionary_object(_NAMES)
        dest_value = leaf.get_object(1)
        d_array = dest_value.get_dictionary_object(COSName.get_pdf_name("D"))
        target = d_array.get_object(0)
        pages = list(m.get_pages())
        # merged index = 2 (dest) + 1 (src page index) = 3.
        assert pages[3].get_cos_object() is target


# ---------- optimize mode (page-only) ----------


def test_optimize_mode_sums_pages() -> None:
    a, b = _doc(2), _doc(3)
    data = _merge_to_bytes(
        [a, b], doc_mode=DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    )
    a.close()
    b.close()
    with PDDocument.load(data) as m:
        assert m.get_number_of_pages() == 5


def test_optimize_mode_drops_open_action() -> None:
    # OPTIMIZE_RESOURCES_MODE merges pages only — catalog substructures
    # like /OpenAction are NOT carried over (mirrors upstream).
    dest = _doc(1)
    src = _doc_with_open_action_to_last_page(2)
    data = _merge_to_bytes(
        [dest, src], doc_mode=DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    )
    dest.close()
    src.close()
    with PDDocument.load(data) as m:
        cat = m.get_document_catalog().get_cos_object()
        assert cat.get_dictionary_object(_OPEN_ACTION) is None
        assert m.get_number_of_pages() == 3


# ---------- error / config edges ----------


def test_merge_without_destination_raises() -> None:
    util = PDFMergerUtility()
    util.add_source(_doc(1))
    with pytest.raises(ValueError):
        util.merge_documents()


def test_no_sources_is_a_noop() -> None:
    out = io.BytesIO()
    util = PDFMergerUtility()
    util.set_destination_stream(out)
    util.merge_documents()
    # Nothing written, no exception.
    assert out.getvalue() == b""


def test_closed_source_rejected_by_append_document() -> None:
    dest = PDDocument()
    src = _doc(1)
    src.close()
    util = PDFMergerUtility()
    with pytest.raises(OSError):
        util.append_document(dest, src)
    dest.close()
