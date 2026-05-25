"""Wave 1400 — close residual branch partials across pypdfbox.multipdf.

Each test targets a single uncovered branch flagged by
``pytest --cov=pypdfbox.multipdf --cov-branch`` after wave 1399.

Closed partials:

* ``layer_utility.py:312->315`` — ``create_overlay_x_object`` with a
  ``desired_name`` on a page whose ``/Resources/XObject`` is already
  a populated ``COSDictionary`` — the materialisation branch is
  skipped and the form is added under the existing dict.
* ``layer_utility.py:348->345`` — ``transfer_dict`` where the cloner
  returns ``None`` for a value (unresolvable indirect ref) → the
  ``set_item`` branch is skipped and the loop moves on.
* ``layer_utility.py:364->366`` — ``import_oc_properties`` where the
  cloner returns a non-``COSDictionary`` (e.g. ``None``) for the
  source ``/OCProperties`` dict → no install happens and the
  destination catalog stays empty.
* ``overlay.py:530->532`` — ``_create_overlay_form_x_object`` where
  the cloner returns ``None`` for ``overlay_resources`` → the
  ``set_resources`` call is skipped (form XObject ships without
  ``/Resources``).
* ``pdf_clone_utility.py:140->135, 159->154, 210->208, 223->215`` —
  four sibling defensive branches where the recursive
  ``clone_for_new_document`` call returns ``None`` (because the
  source carried an unresolvable indirect ref) → the cloner skips
  the ``set_item`` / ``add`` and continues with the next entry.
* ``splitter.py:467->491`` — ``create_new_document`` when the
  source document has no ``/Info`` dictionary → the metadata
  copy block is skipped and we fall through directly to the
  catalog-copy code.
* ``splitter.py:692->699, 697->699`` — ``_process_annotations`` for
  a ``PDAnnotationLink`` when the source ``/Annots`` array is
  absent (692 short-circuits) or the indexed candidate isn't a
  ``COSDictionary`` (697 false arm) — both routes land the
  ``source_link_dict`` at ``None``.
* ``splitter.py:771->781`` — ``_finalize_annotation_links`` when no
  source annot dict matches → ``source_ann_dict`` stays ``None``
  and the popup path uses the cloned dict's own ``/Popup``.
* ``splitter.py:890->892`` — ``_is_signature_widget`` where ``/V``
  is a non-Sig dict that lacks ``ByteRange`` → falls through to
  ``return False``.
* ``splitter.py:922->936`` — ``_scrub_acroform`` where ``/Fields``
  isn't a ``COSArray`` (malformed AcroForm) → field-scrub is
  skipped and we go straight to the remaining-keys cleanup.
* ``splitter.py:928->924`` — ``_scrub_acroform`` where a field
  entry is ``None`` (rare malformed PDF) → ``continue`` and the
  None entry is not preserved.
* ``splitter.py:1062->1069`` — ``_resolve_dest_target_page`` when
  the source destination's page lookup raises (caught) and the
  candidate isn't a ``COSDictionary`` → the source_target_page_dict
  stays ``None`` and we fall through to the clone step.
* ``splitter.py:1501->1509`` — ``_clone_struct_element_kid_dict``
  OBJR path with ``/Obj`` that isn't a ``COSDictionary`` → the
  inner clone-or-remove branch is skipped.
* ``splitter.py:1592->1591`` — ``_remove_possible_orphan_annotation``
  where the annot IS in the page's annots array → ``return``
  inside the loop (sibling of the existing 'not in page' test).
* ``splitter.py:1785->1790`` — ``process_resources`` for an XObject
  that's neither a ``PDFormXObject`` nor a ``PDImageXObject`` (e.g.
  a malformed XObject we wrap as a base ``PDXObject``) → the
  ``sp`` stays ``-1`` and the clone is skipped.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.multipdf import LayerUtility, PDFCloneUtility, Splitter
from pypdfbox.multipdf.overlay import Overlay, _LayoutPage
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _page_with_contents(body: bytes = b"q\n0 0 0 RG\nQ\n") -> PDPage:
    page = PDPage()
    s = COSStream()
    s.set_raw_data(body)
    page.set_contents(s)
    return page


def _doc_with_pages(n: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(_page_with_contents())
    return doc


def _unresolved_cos_object() -> COSObject:
    """Return a COSObject whose ``get_object()`` resolves to ``None``
    (no loader, no resolved object). Used to drive the cloner's
    ``cloned is None`` defensive branches without mocking the cloner."""
    return COSObject(99999, 0)


# ============================================================================
# layer_utility.py
# ============================================================================


def test_create_overlay_x_object_with_existing_xobject_dict_uses_it() -> None:
    """Branch 312->315 — page already has ``/Resources/XObject`` as a
    populated ``COSDictionary``. The materialisation branch (lines
    313-314) is skipped, and the new form is added under the existing
    dict via ``set_item``.
    """
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    target = PDDocument()
    page = _page_with_contents()
    target.add_page(page)

    # Pre-seed /Resources/XObject as a real COSDictionary with a sentinel.
    page_dict = page.get_cos_object()
    resources = COSDictionary()
    xobject_dict = COSDictionary()
    xobject_dict.set_item(
        COSName.get_pdf_name("Existing"), COSName.get_pdf_name("Sentinel")
    )
    resources.set_item(COSName.get_pdf_name("XObject"), xobject_dict)
    page_dict.set_item(COSName.get_pdf_name("Resources"), resources)

    util = LayerUtility(target)
    form_stream = COSStream()
    form_stream.set_raw_data(b"")
    form = PDFormXObject(form_stream)
    form.set_bbox(PDRectangle(0, 0, 100, 100))
    util.create_overlay_x_object(page, form, desired_name="MyOverlay")

    # The sentinel survived (we used the existing dict, didn't replace it)
    assert xobject_dict.contains_key(COSName.get_pdf_name("Existing"))
    # The new form landed under the requested key.
    assert xobject_dict.contains_key(COSName.get_pdf_name("MyOverlay"))
    target.close()


def test_transfer_dict_skips_value_that_clones_to_none() -> None:
    """Branch 348->345 — when ``_cloner.clone_for_new_document`` returns
    ``None`` for an entry value (unresolvable indirect ref), the inner
    ``set_item`` is skipped and the loop continues with the next key.
    """
    target = PDDocument()
    util = LayerUtility(target)

    org = COSDictionary()
    # Key in the filter set ('Metadata') but with an unresolvable indirect
    # ref: the cloner will return None and the entry must NOT be copied.
    org.set_item(COSName.get_pdf_name("Metadata"), _unresolved_cos_object())
    # Key NOT in the filter set: ignored regardless.
    org.set_item(COSName.get_pdf_name("ZZZ"), COSName.get_pdf_name("kept"))

    dst = COSDictionary()
    util.transfer_dict(org, dst, frozenset({"Metadata", "Group", "LastModified"}))

    # 'Metadata' was filtered IN but cloned to None → skipped.
    assert not dst.contains_key(COSName.get_pdf_name("Metadata"))
    # 'ZZZ' was filtered OUT → never reached.
    assert not dst.contains_key(COSName.get_pdf_name("ZZZ"))
    target.close()


def test_import_oc_properties_skips_install_when_clone_not_dict() -> None:
    """Branch 364->366 — ``cloner.clone_for_new_document(src_oc.get_cos_object())``
    yields a non-``COSDictionary`` value (here we monkey-patch the
    cloner to return ``None``). The install branch is skipped and the
    target catalog remains without ``/OCProperties``.

    Real-world trigger: pathological source where /OCProperties is
    backed by an unresolvable indirect ref.
    """
    src = PDDocument()
    src_oc = PDOptionalContentProperties()
    src_oc.add_group(PDOptionalContentGroup("src-layer"))
    src.get_document_catalog().set_oc_properties(src_oc)

    dst = PDDocument()
    util = LayerUtility(dst)

    # Force the cloner to refuse the clone (returns None).
    real_clone = util._cloner.clone_for_new_document
    def _refusing(base):
        if base is src_oc.get_cos_object():
            return None
        return real_clone(base)
    util._cloner.clone_for_new_document = _refusing  # type: ignore[method-assign]

    util.import_oc_properties(src)
    # The branch was taken (cloned not a COSDictionary) → no install.
    assert dst.get_document_catalog().get_oc_properties() is None
    src.close()
    dst.close()


# ============================================================================
# overlay.py
# ============================================================================


def test_overlay_create_form_xobject_skips_resources_when_clone_none() -> None:
    """Branch 530->532 — ``cloner.clone_for_new_document(layout_page.overlay_resources)``
    returns ``None`` → ``isinstance(cloned, COSDictionary)`` is false → the
    ``set_resources`` call is skipped, and the form XObject ships without
    ``/Resources``.

    We drive this through the private helper directly because building
    an end-to-end overlay that lands an unresolvable indirect-ref in
    ``overlay_resources`` is heavier than the branch warrants. Calling
    ``_create_overlay_form_x_object`` with a deliberately-fake cloner
    isolates the exact branch.
    """
    input_doc = _doc_with_pages(1)
    overlay = Overlay()
    overlay.set_input_pdf(input_doc)

    # Build a layout page with an *unresolved* indirect-ref as the
    # resources slot — the cloner will return None.
    content = COSStream()
    content.set_raw_data(b"")
    layout = _LayoutPage(
        PDRectangle(0, 0, 100, 100),
        content,
        # Type ignored: branch only checks isinstance at runtime.
        _unresolved_cos_object(),  # type: ignore[arg-type]
        0,
    )

    class _Cloner:
        def clone_for_new_document(self, base):  # noqa: D401, ARG002
            return None

    form = overlay._create_overlay_form_x_object(layout, _Cloner())
    # /Resources branch was skipped — form has no Resources dict installed.
    cos = form.get_cos_object()
    assert cos.get_dictionary_object(COSName.get_pdf_name("Resources")) is None
    input_doc.close()


# ============================================================================
# pdf_clone_utility.py
# ============================================================================


def test_clone_cos_stream_skips_entry_when_clone_returns_none() -> None:
    """Branch 140->135 — a stream dictionary entry resolves to ``None``
    via an unresolvable indirect ref → the cloner skips the
    ``set_item`` and the cloned stream simply lacks that entry.
    """
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src_stream = COSStream()
        src_stream.set_raw_data(b"hello")
        src_stream.set_item(COSName.get_pdf_name("Kept"), COSInteger.get(7))
        src_stream.set_item(
            COSName.get_pdf_name("Lost"), _unresolved_cos_object()
        )

        cloned = cloner.clone_cos_stream(src_stream)
        assert isinstance(cloned, COSStream)
        # 'Kept' survived
        assert cloned.get_dictionary_object(COSName.get_pdf_name("Kept")) == \
            COSInteger.get(7)
        # 'Lost' was dropped because clone returned None.
        assert not cloned.contains_key(COSName.get_pdf_name("Lost"))


def test_clone_cos_dictionary_skips_entry_when_clone_returns_none() -> None:
    """Branch 159->154 — sibling of the stream skip on a plain
    COSDictionary clone path.
    """
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_item(COSName.get_pdf_name("Kept"), COSInteger.get(11))
        src.set_item(COSName.get_pdf_name("Lost"), _unresolved_cos_object())
        cloned = cloner.clone_cos_dictionary(src)
        assert cloned.get_dictionary_object(COSName.get_pdf_name("Kept")) == \
            COSInteger.get(11)
        assert not cloned.contains_key(COSName.get_pdf_name("Lost"))


def test_clone_merge_array_skips_when_source_element_clones_to_none() -> None:
    """Branch 210->208 — array merge where a source element's clone is
    ``None`` (unresolvable indirect ref) → the ``add`` is skipped.
    """
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src_arr = COSArray()
        src_arr.add(COSInteger.get(1))
        src_arr.add(_unresolved_cos_object())
        src_arr.add(COSInteger.get(3))
        tgt_arr = COSArray()
        cloner.clone_merge_cos_base(src_arr, tgt_arr)
        # Only the two integers were merged in; the unresolvable ref
        # was skipped.
        contents = [tgt_arr.get(i) for i in range(tgt_arr.size())]
        assert COSInteger.get(1) in contents
        assert COSInteger.get(3) in contents
        # No None placeholder snuck in.
        assert all(c is not None for c in contents)


def test_clone_merge_dict_skips_new_key_when_clone_returns_none() -> None:
    """Branch 223->215 — dict merge where the source carries a new key
    whose value clones to ``None`` → the ``set_item`` is skipped, and
    the existing target dict is unchanged for that key.
    """
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_item(COSName.get_pdf_name("New"), _unresolved_cos_object())
        target = COSDictionary()
        target.set_item(COSName.get_pdf_name("Existing"), COSInteger.get(42))
        cloner.clone_merge_cos_base(src, target)
        # 'New' was NOT installed (cloned to None).
        assert not target.contains_key(COSName.get_pdf_name("New"))
        # 'Existing' is untouched.
        assert target.get_dictionary_object(COSName.get_pdf_name("Existing")) == \
            COSInteger.get(42)


# ============================================================================
# splitter.py
# ============================================================================


def test_create_new_document_skips_info_when_source_has_none() -> None:
    """Branch 467->491 — source document has no ``/Info`` dictionary.
    ``get_document_information`` on a normal ``PDDocument`` always
    materialises an empty wrapper, so we monkey-patch the source
    document to return ``None`` directly — exercising the exact
    branch ``if src_info is not None:`` false arm at line 467.
    """
    src = _doc_with_pages(2)
    # Make get_document_information return None on this source.
    src.get_document_information = lambda: None  # type: ignore[method-assign]

    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._destination_documents = []
    splitter._page_dict_maps = []
    splitter._annot_dict_maps = []
    splitter._dest_to_fix_per_chunk = []
    splitter._dest_to_link_map_per_chunk = []
    splitter._pending_annot_passes_per_chunk = []
    splitter._signatures_dropped = False
    # Call the helper directly — this is the exact branch.
    dst = splitter.create_new_document()
    # Branch was taken: the metadata copy block at lines 467-489 was
    # skipped and we fell straight through to the catalog-copy code.
    # The destination has its own (auto-created) info wrapper now,
    # since get_document_information on the *destination* materialises
    # a fresh one — but the destination's /Info is empty (no keys
    # copied from src because the branch skipped).
    assert dst is not None
    dst_info_cos = dst.get_document_information().get_cos_object()
    # An empty (or only /Type) info dictionary proves the copy loop
    # didn't run.
    assert dst_info_cos.size() <= 1
    dst.close()
    src.close()


def test_process_annotations_link_with_no_source_array_uses_none_link_dict() -> None:
    """Branch 692->699 — when ``source_annots_array`` is ``None`` (source
    page has no /Annots) the short-circuit ``and`` in the conditional
    leaves the staging code reading ``source_link_dict = None``.

    Driven via direct call to ``_process_annotations`` with a
    controlled source/imported page pair so we don't depend on the
    split() pipeline's heuristics about which pages get annotation
    arrays after import.
    """
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink

    source_page = PDPage()  # source page has NO /Annots
    imported_page = PDPage()
    # imported has a link annotation
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(0, 0, 50, 50))
    imported_page.set_annotations([link])

    splitter = Splitter()
    splitter._current_destination_document = None  # unused by helper
    splitter._annot_dict_map = {}
    splitter._page_dict_map = {}
    splitter._dest_to_fix = []
    splitter._dest_to_link_map = []
    splitter._pending_annot_passes = []
    splitter._signatures_dropped = False
    # Direct call exercises branch 692->699 (source array is None).
    splitter._process_annotations(source_page, imported_page)
    # The annot's clone landed in the map (sanity that we entered the
    # link-iteration body).
    assert any(
        isinstance(v, COSDictionary) for v in splitter._annot_dict_map.values()
    )


def test_process_annotations_link_with_non_dict_candidate() -> None:
    """Branch 697->699 — the source /Annots array has an entry at the
    same index as the link, but it isn't a ``COSDictionary``. The
    ``isinstance`` check is false → source_link_dict stays None.

    Driven directly: source page carries a /Annots array whose
    only element is a non-dict (COSInteger). Imported page carries
    the cloned link.
    """
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink

    source_page = PDPage()
    src_annots = COSArray()
    # Non-dict placeholder at index 0 → 697 false arm.
    src_annots.add(COSInteger.get(42))
    source_page.get_cos_object().set_item(
        COSName.get_pdf_name("Annots"), src_annots
    )

    imported_page = PDPage()
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(0, 0, 50, 50))
    imported_page.set_annotations([link])

    splitter = Splitter()
    splitter._annot_dict_map = {}
    splitter._page_dict_map = {}
    splitter._dest_to_fix = []
    splitter._dest_to_link_map = []
    splitter._pending_annot_passes = []
    splitter._signatures_dropped = False
    splitter._process_annotations(source_page, imported_page)
    # No raise. The clone landed (sanity).
    assert any(
        isinstance(v, COSDictionary) for v in splitter._annot_dict_map.values()
    )


def test_finalize_annotation_links_no_source_match_keeps_none() -> None:
    """Branch 771->781 — ``_finalize_annotation_links`` walks the
    source /Annots array looking for a non-signature, non-popup
    candidate to back the cloned markup annotation. When the source
    array is empty the while loop exits with ``source_ann_dict``
    still ``None`` — exercising the 'no match' arm of the loop.

    Driven via direct call to the helper so the split loop's
    full pipeline (with structure-tree + destination fix-up) isn't
    invoked.
    """
    from pypdfbox.pdmodel.interactive.annotation import (
        PDAnnotationMarkup,
        PDAnnotationText,
    )

    splitter = Splitter()
    splitter._annot_dict_map = {}
    splitter._page_dict_map = {}
    splitter._dest_to_fix = []
    splitter._dest_to_link_map = []
    # _pending_annot_passes is the list of (cloned_list, source_array,
    # imported_page_dict) tuples ``_finalize_annotation_links`` drains.
    cloned_text = PDAnnotationText()
    cloned_text.set_rectangle(PDRectangle(0, 0, 20, 20))
    cloned_markup = PDAnnotationMarkup()
    cloned_markup.set_rectangle(PDRectangle(0, 0, 30, 30))
    cloned = [cloned_text, cloned_markup]
    # Empty source array — the inner while loop walks but finds
    # nothing to consume.
    source_array = COSArray()
    imported_page_dict = COSDictionary()
    splitter._pending_annot_passes = [(cloned, source_array, imported_page_dict)]
    # Must not raise — both arms (the loop empties without finding
    # a match) are exercised.
    splitter._finalize_annotation_links()


def test_is_signature_widget_non_sig_v_dict_falls_through() -> None:
    """Branch 890->892 — ``/V`` is a COSDictionary with /Type != 'Sig'
    and no /ByteRange key → method falls through to ``return False``.
    """
    widget = COSDictionary()
    widget.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    v = COSDictionary()
    v.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("NotSig"))
    # Deliberately no /ByteRange — both inner branches false.
    widget.set_item(COSName.get_pdf_name("V"), v)
    assert Splitter._is_signature_widget(widget) is False


def test_scrub_acroform_fields_not_array_falls_through_to_remaining_keys() -> None:
    """Branch 922->936 — ``/Fields`` is present but not a COSArray
    (malformed AcroForm) → the field-scrub block is skipped and we
    drop straight to the remaining-keys cleanup.
    """
    splitter = Splitter()
    dst = PDDocument()
    catalog = dst.get_document_catalog()
    cos_catalog = catalog.get_cos_object()
    acroform = COSDictionary()
    # Fields is a *dictionary*, not an array — exercises branch 922 false.
    acroform.set_item(COSName.get_pdf_name("Fields"), COSDictionary())
    cos_catalog.set_item(COSName.get_pdf_name("AcroForm"), acroform)
    splitter._scrub_acroform(dst)
    # AcroForm still present — its /Fields shape wasn't normalised
    # because the branch said "not an array".
    af = cos_catalog.get_dictionary_object(COSName.get_pdf_name("AcroForm"))
    assert isinstance(af, COSDictionary)
    dst.close()


def test_scrub_acroform_skips_none_field_entry() -> None:
    """Branch 928->924 — a field entry in the /Fields array is ``None``
    (rare but observed in malformed PDFs). The ``if field is not None``
    branch is false → the None entry is skipped via ``continue`` and
    not preserved.
    """
    splitter = Splitter()
    dst = PDDocument()
    cos_catalog = dst.get_document_catalog().get_cos_object()
    acroform = COSDictionary()
    fields = COSArray()
    # Add a real signature field (will be dropped by the /FT==Sig branch
    # at 926-927), and a None placeholder (drops at 928).
    sig = COSDictionary()
    sig.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
    fields.add(sig)
    fields.add(None)
    acroform.set_item(COSName.get_pdf_name("Fields"), fields)
    cos_catalog.set_item(COSName.get_pdf_name("AcroForm"), acroform)
    splitter._scrub_acroform(dst)
    # Both went away — /Fields became empty → AcroForm removed entirely
    # by the 930-931 + 939-940 cleanup.
    assert not cos_catalog.contains_key(COSName.get_pdf_name("AcroForm"))
    dst.close()


def test_resolve_dest_target_page_with_non_dict_page_falls_through() -> None:
    """Branch 1062->1069 — the source destination's ``get_page()``
    returns something that isn't a ``COSDictionary``. The isinstance
    check is false → ``source_target_page_dict`` stays ``None`` and
    we fall through to the cloning step.

    We exercise this via a real split with a /Dest whose [0] target
    page is a COSName (illegal but not impossible).
    """
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink

    doc = _doc_with_pages(2)
    page0 = doc.get_page(0)
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(0, 0, 10, 10))
    # Build an explicit /Dest array whose first element isn't a dict.
    dest_arr = COSArray()
    dest_arr.add(COSName.get_pdf_name("XYZNotADict"))
    dest_arr.add(COSName.get_pdf_name("Fit"))
    link.get_cos_object().set_item(COSName.get_pdf_name("Dest"), dest_arr)
    page0.set_annotations([link])

    splitter = Splitter()
    splitter.set_split_at_page(1)
    chunks = splitter.split(doc)
    # Splitter survived the malformed destination.
    assert len(chunks) == 2
    for c in chunks:
        c.close()
    doc.close()


def test_remove_possible_orphan_annotation_returns_when_annot_in_page() -> None:
    """Branch 1592->1591 — the source annotation IS present in the host
    page's /Annots array → the inner ``return`` fires before the loop
    completes. Without this case the loop's ``continue-to-next-iter``
    branch was the only one exercised.
    """
    splitter = Splitter()

    # Build the minimum shape ``_remove_possible_orphan_annotation`` needs.
    src_obj = COSDictionary()
    src_obj.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    src_obj.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    host_page = COSDictionary()
    annots = COSArray()
    # Sentinel non-match entry, then the matching src_obj.
    other = COSDictionary()
    annots.add(other)
    annots.add(src_obj)
    host_page.set_item(COSName.get_pdf_name("Annots"), annots)
    src_dict = COSDictionary()
    src_dict.set_item(COSName.get_pdf_name("Pg"), host_page)
    dst_dict = COSDictionary()
    dst_dict.set_item(COSName.get_pdf_name("Obj"), COSDictionary())

    # Call directly. The loop finds src_obj at index 1 → returns
    # before walking past it. /Obj must NOT be removed.
    splitter._remove_possible_orphan_annotation(src_obj, src_dict, None, dst_dict)
    assert dst_dict.contains_key(COSName.get_pdf_name("Obj"))


def test_process_resources_skips_unknown_xobject_subclass(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Branch 1785->1790 — the XObject is neither a ``PDFormXObject``
    nor a ``PDImageXObject``. Neither branch fires, ``sp`` stays at
    ``-1``, and the ``if sp != -1`` clone is skipped.

    We construct a synthetic PDResources whose XObject lookup returns
    a bare ``PDXObject`` (base class) so neither isinstance matches.
    """
    from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
    from pypdfbox.pdmodel.pd_resources import PDResources

    class _FakeResources:
        def get_cos_object(self):  # noqa: D401
            return COSDictionary()

        def get_xobject_names(self):  # noqa: D401
            return [COSName.get_pdf_name("XO1")]

        def get_x_object(self, name):  # noqa: D401, ARG002
            stream = COSStream()
            stream.set_raw_data(b"")
            # Build a bare PDXObject with a non-Form, non-Image subtype.
            # Neither isinstance check matches; the elif at 1785 false-
            # arms straight to 1790.
            return PDXObject(stream, COSName.get_pdf_name("Mystery"))

    splitter = Splitter()
    src_numbers: dict[int, object] = {}
    dst_numbers: dict[int, object] = {}
    # No exception, no clone attempted (sp stayed -1).
    with caplog.at_level(logging.DEBUG):
        splitter.process_resources(_FakeResources(), src_numbers, dst_numbers, set())
    # dst_numbers wasn't populated — the clone step didn't run.
    assert dst_numbers == {}
    # And a real PDResources still works (smoke check that the helper
    # path isn't broken).
    real = PDResources()
    splitter.process_resources(real, src_numbers, dst_numbers, set())


def test_clone_struct_element_kid_dict_objr_non_dict_obj() -> None:
    """Branch 1501->1509 — OBJR struct kid whose ``/Obj`` isn't a
    ``COSDictionary``. The inner clone-or-remove branch (1501-1508)
    is skipped; we fall directly to the size check at 1509.
    """
    splitter = Splitter()
    splitter._struct_dict_map = {}
    splitter._annot_dict_map = {}
    splitter._id_set = set()
    splitter._role_set = set()
    splitter._page_dict_map = {}

    src = COSDictionary()
    src.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("OBJR"))
    # /Obj is an array, not a dict → isinstance(src_obj, COSDictionary) is False.
    src.set_item(COSName.get_pdf_name("Obj"), COSArray())
    dst_parent = COSDictionary()
    # The dispatcher entry point is ``_k_create_clone`` — it walks
    # COSObject / Array / Dictionary and ends up calling
    # ``_k_clone_dictionary`` for our src.
    result = splitter._k_create_clone(src, dst_parent, None, _PageTreeStub())
    # After the OBJR branch skips (src_obj wasn't a dict), dst has
    # only /Type, dst.size() == 1 → return None at line 1512.
    assert result is None


class _PageTreeStub:
    def index_of(self, page_dict):  # noqa: D401, ARG002
        return 0
