"""Wave-1348 coverage-boost tests for ``pypdfbox.pdmodel.pd_document``.

Closes residual gaps after waves 1323 / 1332:

* ``prepare_visible_signature`` happy path (lines 1308-1327) — walks
  the template's COSDocument pool, finds the Annot + Sig field, and
  copies /Rect, /AP, /DR onto the destination widget + AcroForm;
* ``assign_acro_form_default_resource`` merge branch (lines 1379-1386)
  — when the destination AcroForm already has a /DR with an /XObject
  sub-dict, merge the template's /XObject entries in;
* ``_import_page_acroform_fixup`` skip + dedupe branches (lines 1505,
  1523, 1525, 1559-1562):
    * a non-dictionary entry in /Annots is skipped (1505);
    * a /Parent chain that climbs more than one level (1523);
    * a `seen` short-circuit when two widget annots resolve to the
      same root field (1525);
    * the ``already`` short-circuit when a root is already in the
      AcroForm's /Fields array (1559-1562).
"""

from __future__ import annotations

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm


def _pool_add(visual_signature: COSDocument, dict_obj: COSDictionary) -> None:
    """Register ``dict_obj`` as a fresh indirect object in
    ``visual_signature``'s object pool."""
    # Allocate a unique key from the doc's current highest object number.
    existing = visual_signature.get_object_keys()
    next_num = max((k.object_number for k in existing), default=0) + 1
    cos_object = visual_signature.get_object_from_pool(
        COSObjectKey(next_num, 0)
    )
    cos_object.set_object(dict_obj)


# ---------- prepare_visible_signature happy path -------------------------


def test_prepare_visible_signature_skips_non_dictionary_pool_entries() -> None:
    """Non-COSDictionary entries in the visual-signature pool must be
    skipped without aborting the iteration (line 1311 — the ``continue``
    after the type guard)."""
    doc = PDDocument()
    try:
        acro = PDAcroForm(doc)
        widget = PDAnnotationWidget()
        template = COSDocument()
        # First pool entry: a COSString — not a dict.
        _pool_add(template, COSString(b"noise"))
        # Annot dict with /Rect.
        annot = COSDictionary()
        annot.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
        )
        rect = COSArray()
        for v in (5, 6, 7, 8):
            rect.add(COSInteger.get(v))
        annot.set_item(COSName.get_pdf_name("Rect"), rect)
        _pool_add(template, annot)
        # Sig field with /AP.
        sig_field = COSDictionary()
        sig_field.set_item(
            COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig")
        )
        sig_field.set_item(COSName.get_pdf_name("AP"), COSDictionary())
        _pool_add(template, sig_field)

        doc.prepare_visible_signature(widget, acro, template)
        assert widget.get_appearance() is not None
    finally:
        doc.close()


def test_prepare_visible_signature_wires_template_into_widget() -> None:
    """A template containing both a signature Annot and a Sig field with
    /AP must wire the widget's rectangle + appearance and seed the
    AcroForm's /DR (lines 1308-1327)."""
    doc = PDDocument()
    try:
        acro = PDAcroForm(doc)
        widget = PDAnnotationWidget()
        template = COSDocument()
        # 1) Annot dict carrying /Rect.
        annot = COSDictionary()
        annot.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
        )
        rect = COSArray()
        for v in (1, 2, 3, 4):
            rect.add(COSInteger.get(v))
        annot.set_item(COSName.get_pdf_name("Rect"), rect)
        _pool_add(template, annot)
        # 2) Sig field dict with /FT /Sig + /AP dict.
        sig_field = COSDictionary()
        sig_field.set_item(
            COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig")
        )
        ap_dict = COSDictionary()
        sig_field.set_item(COSName.get_pdf_name("AP"), ap_dict)
        # Embed a /DR so the merge / install branch is exercised.
        dr_dict = COSDictionary()
        sig_field.set_item(COSName.get_pdf_name("DR"), dr_dict)
        _pool_add(template, sig_field)

        doc.prepare_visible_signature(widget, acro, template)

        # Widget now has the template's /Rect and a wrapped appearance.
        rect_out = widget.get_rectangle()
        assert rect_out is not None
        assert rect_out.get_lower_left_x() == 1.0
        assert widget.get_appearance() is not None
        # AcroForm now carries the template's /DR.
        assert acro.get_default_resources() is not None
    finally:
        doc.close()


# ---------- assign_acro_form_default_resource: XObject merge branch ------


def test_assign_acro_form_default_resource_merges_xobject_into_existing() -> None:
    """When the AcroForm already has a /DR with an /XObject sub-dict,
    the template's /XObject entries are merged in (lines 1379-1386)."""
    doc = PDDocument()
    try:
        acro = PDAcroForm(doc)
        # Seed the AcroForm with a /DR containing an /XObject.
        existing_dr = COSDictionary()
        existing_xobj = COSDictionary()
        existing_xobj.set_item(
            COSName.get_pdf_name("Old"), COSName.get_pdf_name("OldRef")
        )
        existing_dr.set_item(COSName.get_pdf_name("XObject"), existing_xobj)
        acro.get_cos_object().set_item(COSName.get_pdf_name("DR"), existing_dr)
        # Build the template with its own /DR /XObject.
        template = COSDictionary()
        new_dr = COSDictionary()
        new_xobj = COSDictionary()
        new_xobj.set_item(
            COSName.get_pdf_name("New"), COSName.get_pdf_name("NewRef")
        )
        new_dr.set_item(COSName.get_pdf_name("XObject"), new_xobj)
        template.set_item(COSName.get_pdf_name("DR"), new_dr)

        PDDocument.assign_acro_form_default_resource(acro, template)

        # Old entries preserved + new ones merged in.
        merged = existing_dr.get_dictionary_object(
            COSName.get_pdf_name("XObject")
        )
        assert isinstance(merged, COSDictionary)
        assert merged.get_dictionary_object(COSName.get_pdf_name("Old")) is not None
        assert merged.get_dictionary_object(COSName.get_pdf_name("New")) is not None
    finally:
        doc.close()


# ---------- _import_page_acroform_fixup branches ------------------------


def test_import_page_acroform_skips_non_dictionary_annot_entries() -> None:
    """An /Annots array element that isn't a COSDictionary must be
    skipped (line 1505) without aborting the loop."""
    doc = PDDocument()
    try:
        page_dict = COSDictionary()
        annots = COSArray()
        # First entry: a stray name — not a dict.
        annots.add(COSName.get_pdf_name("Stray"))
        # Second entry: a real widget annot with a /T so it lands in
        # the AcroForm's /Fields array.
        widget = COSDictionary()
        widget.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
        )
        widget.set_string(COSName.get_pdf_name("T"), "FieldA")
        annots.add(widget)
        page_dict.set_item(COSName.get_pdf_name("Annots"), annots)

        doc._import_page_acroform_fixup(page_dict)

        acro = doc.get_document_catalog().get_acro_form()
        assert acro is not None
        fields = acro.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        assert isinstance(fields, COSArray)
        # The widget made it through; the stray didn't crash the loop.
        assert fields.size() == 1
    finally:
        doc.close()


def test_import_page_acroform_climbs_multi_level_parent_chain() -> None:
    """The /Parent climb continues past the first level (line 1523).
    Constructs a widget → middle parent → top root chain."""
    doc = PDDocument()
    try:
        # Top-most field root.
        top_root = COSDictionary()
        top_root.set_string(COSName.get_pdf_name("T"), "Top")
        # Middle parent.
        middle = COSDictionary()
        middle.set_item(COSName.get_pdf_name("Parent"), top_root)
        # Widget annot.
        widget = COSDictionary()
        widget.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
        )
        widget.set_item(COSName.get_pdf_name("Parent"), middle)

        page_dict = COSDictionary()
        annots = COSArray()
        annots.add(widget)
        page_dict.set_item(COSName.get_pdf_name("Annots"), annots)

        doc._import_page_acroform_fixup(page_dict)

        acro = doc.get_document_catalog().get_acro_form()
        fields = acro.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        # The TOP root got promoted, not the middle parent.
        assert isinstance(fields, COSArray)
        assert fields.size() == 1
        assert fields.get_object(0) is top_root
    finally:
        doc.close()


def test_import_page_acroform_dedupes_widgets_sharing_root() -> None:
    """Two widget annots whose /Parent chains resolve to the same root
    field must only enroll the root once (line 1525 — ``id(root) in seen``)."""
    doc = PDDocument()
    try:
        shared_root = COSDictionary()
        shared_root.set_string(COSName.get_pdf_name("T"), "Shared")
        widget_a = COSDictionary()
        widget_a.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
        )
        widget_a.set_item(COSName.get_pdf_name("Parent"), shared_root)
        widget_b = COSDictionary()
        widget_b.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
        )
        widget_b.set_item(COSName.get_pdf_name("Parent"), shared_root)

        page_dict = COSDictionary()
        annots = COSArray()
        annots.add(widget_a)
        annots.add(widget_b)
        page_dict.set_item(COSName.get_pdf_name("Annots"), annots)

        doc._import_page_acroform_fixup(page_dict)

        acro = doc.get_document_catalog().get_acro_form()
        fields = acro.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        assert isinstance(fields, COSArray)
        assert fields.size() == 1  # not 2
        assert fields.get_object(0) is shared_root
    finally:
        doc.close()


def test_import_page_acroform_skips_root_already_in_fields() -> None:
    """When the AcroForm already lists the imported root in its /Fields
    array (identity-equal), the second import is a no-op
    (lines 1559-1562)."""
    doc = PDDocument()
    try:
        # Pre-seed AcroForm with a root that will also be referenced
        # via a widget on the imported page.
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        root = COSDictionary()
        root.set_string(COSName.get_pdf_name("T"), "Existing")
        fields = COSArray()
        fields.add(root)
        acro.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)
        # Widget on the page points back to the same root.
        widget = COSDictionary()
        widget.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
        )
        widget.set_item(COSName.get_pdf_name("Parent"), root)
        page_dict = COSDictionary()
        annots = COSArray()
        annots.add(widget)
        page_dict.set_item(COSName.get_pdf_name("Annots"), annots)

        doc._import_page_acroform_fixup(page_dict)

        # Fields still has just one entry.
        out_fields = acro.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        assert isinstance(out_fields, COSArray)
        assert out_fields.size() == 1
        assert out_fields.get_object(0) is root
    finally:
        doc.close()
