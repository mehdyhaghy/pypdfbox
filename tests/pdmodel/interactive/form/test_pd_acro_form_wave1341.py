"""Wave-1341 coverage-boost tests for
:mod:`pypdfbox.pdmodel.interactive.form.pd_acro_form`.

Targets the residual uncovered branches:

* ``import_fdf`` — empty ``/Fields`` array short-circuit (line 630) and
  the per-field ``partial is None`` skip (line 634);
* ``export_fdf`` — the ``PDDocument``-attached ``cos_doc.get_document_id``
  path that propagates the trailer ``/ID`` to the FDF dictionary
  (lines 692-699, 702);
* ``is_visible_annotation`` — the negative branches for missing /N
  stream, malformed /BBox (size<4, non-numeric, AttributeError on
  ``.value``) (lines 1224, 1227, 1233, 1235-1236);
* ``resolve_transformation_matrix`` — the ``_read_rect`` and
  ``_read_form_geometry`` ``None`` fallbacks (lines 1289, 1292);
* ``build_pages_widgets_map`` — the missing-/P reverse-walk fallback
  (lines 1322, 1328-1345).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary
from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

# ---------- import_fdf empty/skip branches --------------------------------


def test_import_fdf_returns_when_fdf_has_no_fields() -> None:
    """A freshly-built FDFDocument with no ``/Fields`` short-circuits
    ``import_fdf`` (line 630)."""
    form = PDAcroForm()
    fdf = FDFDocument()
    # Default FDFDocument carries no /Fields — exercises the early
    # ``if not fdf_fields: return`` branch.
    assert fdf.get_catalog().get_fdf().get_fields() is None
    try:
        form.import_fdf(fdf)  # must not raise
    finally:
        fdf.close()


def test_import_fdf_skips_fdf_field_with_no_partial_name() -> None:
    """An FDF field whose ``/T`` (partial name) is absent is silently
    skipped (line 634)."""
    form = PDAcroForm()
    matching = PDTextField(form)
    matching.set_partial_name("city")
    form.set_fields([matching])

    fdf = FDFDocument()
    fdf_dict = FDFDictionary()
    fdf.get_catalog().set_fdf(fdf_dict)

    # Field with no /T: should be skipped without raising.
    nameless = FDFField()
    # Field with /T="city" + /V="Paris": should be applied.
    named = FDFField()
    named.set_partial_field_name("city")
    named.set_value("Paris")
    fdf_dict.set_fields([nameless, named])

    try:
        form.import_fdf(fdf)
    finally:
        fdf.close()
    # The named field was applied — the nameless one didn't crash.
    assert matching.get_cos_object().get_string(COSName.get_pdf_name("V")) == "Paris"


# ---------- export_fdf carries trailer /ID across -------------------------


def test_export_fdf_copies_document_id_when_present() -> None:
    """When the owning PDDocument's COSDocument carries a trailer
    ``/ID`` array, ``export_fdf`` propagates it to the FDF dictionary
    (lines 692-699, 702)."""
    doc = PDDocument()
    try:
        # Seed the trailer /ID via the COS layer directly — the public
        # PDDocument.set_document_id takes int, but FDFDictionary.set_id
        # writes a COSArray, so we need to mirror the array path.
        cos_doc = doc.get_document()
        ids = COSArray()
        ids.add(COSString(b"\x00" * 16))
        ids.add(COSString(b"\x01" * 16))
        cos_doc.set_document_id(ids)

        form = PDAcroForm(doc)
        field = PDTextField(form)
        field.set_partial_name("name")
        form.set_fields([field])

        fdf = form.export_fdf()
        try:
            assert isinstance(fdf, FDFDocument)
            # The /Fields entry was set because the form has a field.
            assert fdf.get_catalog().get_fdf().get_fields() is not None
            # The /ID array was propagated.
            assert fdf.get_catalog().get_fdf().get_id() is ids
        finally:
            fdf.close()
    finally:
        doc.close()


def test_export_fdf_omits_id_when_get_document_returns_none() -> None:
    """When the document-shaped object lacks ``get_document``, the /ID
    propagation is skipped without raising (lines 692-696 default
    branch — ``cos_doc is None`` keeps the fdf /ID unset)."""

    class _DocShim:
        def get_document(self) -> None:  # pragma: no cover - shape only
            return None

    form = PDAcroForm()
    # Inject a shape-compatible owner.
    form._document = _DocShim()  # type: ignore[assignment]  # noqa: SLF001
    fdf = form.export_fdf()
    try:
        assert fdf.get_catalog().get_fdf().get_id() is None
    finally:
        fdf.close()


# ---------- is_visible_annotation negative branches -----------------------


def test_is_visible_annotation_returns_false_when_normal_is_not_stream() -> None:
    """``/AP /N`` that is not a COSStream → not visible (line 1224)."""
    widget = COSDictionary()
    ap = COSDictionary()
    # /N is a dictionary, not a stream.
    ap.set_item(COSName.get_pdf_name("N"), COSDictionary())
    widget.set_item(COSName.get_pdf_name("AP"), ap)
    assert PDAcroForm.is_visible_annotation(widget) is False


def test_is_visible_annotation_returns_false_when_bbox_too_short() -> None:
    """``/AP /N /BBox`` with fewer than 4 entries → not visible
    (line 1227)."""
    widget = COSDictionary()
    stream = COSStream()
    bbox = COSArray()
    bbox.add(COSInteger(0))
    bbox.add(COSInteger(0))
    bbox.add(COSInteger(100))
    # Only 3 entries — too short.
    stream.set_item(COSName.get_pdf_name("BBox"), bbox)
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), stream)
    widget.set_item(COSName.get_pdf_name("AP"), ap)
    assert PDAcroForm.is_visible_annotation(widget) is False


def test_is_visible_annotation_returns_false_when_bbox_entry_not_numeric() -> None:
    """A BBox entry that isn't an integer or float → not visible
    (line 1233)."""
    widget = COSDictionary()
    stream = COSStream()
    bbox = COSArray()
    bbox.add(COSInteger(0))
    bbox.add(COSInteger(0))
    bbox.add(COSString(b"100"))  # garbage type
    bbox.add(COSInteger(50))
    stream.set_item(COSName.get_pdf_name("BBox"), bbox)
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), stream)
    widget.set_item(COSName.get_pdf_name("AP"), ap)
    assert PDAcroForm.is_visible_annotation(widget) is False


def test_is_visible_annotation_swallows_attribute_error_on_value() -> None:
    """When iterating /BBox raises ``AttributeError`` (e.g. an entry
    whose ``.value`` is missing because the get_object stub returns a
    surrogate), the helper returns ``False`` (lines 1235-1236)."""

    class _BogusCOSInt:
        # Looks enough like COSInteger to pass the isinstance check via
        # subclass registration, but ``.value`` access blows up. We
        # actually subclass COSInteger so isinstance() matches.
        pass

    # Subclass COSInteger so isinstance(entry, (COSInteger, COSFloat))
    # passes the type guard but ``entry.value`` raises.
    class _BoomInt(COSInteger):
        def __init__(self) -> None:  # type: ignore[no-untyped-def]
            super().__init__(0)

        @property
        def value(self) -> int:  # type: ignore[override]
            raise AttributeError("simulated upstream parse hiccup")

    widget = COSDictionary()
    stream = COSStream()
    bbox = COSArray()
    for _ in range(4):
        bbox.add(_BoomInt())
    stream.set_item(COSName.get_pdf_name("BBox"), bbox)
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), stream)
    widget.set_item(COSName.get_pdf_name("AP"), ap)

    assert PDAcroForm.is_visible_annotation(widget) is False


# ---------- resolve_transformation_matrix None paths ----------------------


def test_resolve_transformation_matrix_returns_none_for_non_numeric_rect() -> None:
    """A /Rect array whose entries aren't numeric → ``_read_rect`` returns
    ``None`` and the caller short-circuits (line 1289)."""
    form = PDAcroForm()
    widget = COSDictionary()
    rect = COSArray()
    # 4 entries, all non-numeric.
    for _ in range(4):
        rect.add(COSString(b"x"))
    widget.set_item(COSName.get_pdf_name("Rect"), rect)
    appearance = COSStream()
    bbox = COSArray()
    for v in (0, 0, 100, 50):
        bbox.add(COSInteger(v))
    appearance.set_item(COSName.get_pdf_name("BBox"), bbox)
    assert form.resolve_transformation_matrix(widget, appearance) is None


def test_resolve_transformation_matrix_returns_none_when_bbox_missing() -> None:
    """A valid /Rect paired with an appearance stream that has no
    /BBox → ``_read_form_geometry`` returns ``(None, identity)``, so the
    caller short-circuits (line 1292)."""
    form = PDAcroForm()
    widget = COSDictionary()
    rect = COSArray()
    for v in (10, 20, 110, 70):
        rect.add(COSInteger(v))
    widget.set_item(COSName.get_pdf_name("Rect"), rect)
    appearance = COSStream()  # no /BBox at all
    assert form.resolve_transformation_matrix(widget, appearance) is None


# ---------- build_pages_widgets_map fallback path -------------------------


def test_build_pages_widgets_map_falls_back_when_widget_lacks_p() -> None:
    """When at least one widget lacks ``/P``, the reverse walk over
    document pages locates its host (lines 1322, 1328-1345)."""
    doc = PDDocument()
    try:
        # Ensure exactly one page.
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
        doc.add_page(page)

        form = PDAcroForm(doc)
        field = PDTextField(form)
        field.set_partial_name("name")
        form.set_fields([field])

        # Wire the widget's /Rect into the page's /Annots without a /P
        # back-pointer so the fallback walk runs.
        widget = field.get_widgets()[0]
        widget_dict = widget.get_cos_object()
        # Make sure no /P key — synthesised widgets don't set one by
        # default, but be explicit.
        widget_dict.remove_item(COSName.get_pdf_name("P"))

        annots = COSArray()
        annots.add(widget_dict)
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

        mapping = form.build_pages_widgets_map([field])
        assert id(page.get_cos_object()) in mapping
        assert id(widget_dict) in mapping[id(page.get_cos_object())]
    finally:
        doc.close()


def test_build_pages_widgets_map_fallback_with_no_document_returns_empty() -> None:
    """If at least one widget lacks /P **and** the form has no owning
    document, the reverse-walk fallback returns the accumulator
    unchanged (line 1330 ``if document is None: return out``)."""
    form = PDAcroForm()  # no document
    field = PDTextField(form)
    field.set_partial_name("orphan")
    form.set_fields([field])
    # The synthesised widget has no /P; no document is available.
    result = form.build_pages_widgets_map([field])
    assert result == {}


def test_build_pages_widgets_map_fallback_rejects_non_pddocument_pages() -> None:
    """The ``pages`` override that isn't a PDDocument short-circuits the
    fallback (line 1334 ``if not isinstance(document, PDDocument): return out``)."""
    form = PDAcroForm()
    field = PDTextField(form)
    field.set_partial_name("orphan")
    form.set_fields([field])
    # Supply a non-PDDocument override.
    result = form.build_pages_widgets_map([field], pages="not a document")
    assert result == {}


def test_build_pages_widgets_map_fallback_iterates_annots_array() -> None:
    """When at least one widget triggers the fallback (no /P, not in any
    annots), the reverse walk inspects every page's annots array and
    matches entries against the widget set (lines 1341-1344)."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
        doc.add_page(page)

        form = PDAcroForm(doc)

        # Field 1 — widget with /P back-pointer.
        field1 = PDTextField(form)
        field1.set_partial_name("one")
        widget1 = field1.get_widgets()[0].get_cos_object()
        widget1.set_item(COSName.get_pdf_name("P"), page.get_cos_object())

        # Field 2 — widget with no /P and *not* in any page's annots.
        # That forces has_missing_page_ref = True so the fallback runs.
        field2 = PDTextField(form)
        field2.set_partial_name("two")
        widget2 = field2.get_widgets()[0].get_cos_object()
        widget2.remove_item(COSName.get_pdf_name("P"))

        # Put widget1 (only) in the page's Annots; widget2 is dangling.
        annots = COSArray()
        annots.add(widget1)
        # Add a non-dictionary entry to exercise the isinstance guard.
        annots.add(COSInteger(0))
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

        form.set_fields([field1, field2])
        mapping = form.build_pages_widgets_map([field1, field2])
        # widget1 reaches the map both via /P and via the fallback loop;
        # widget2 stays unmapped because it isn't in any page.
        assert id(widget1) in mapping[id(page.get_cos_object())]
        assert id(widget2) not in mapping.get(id(page.get_cos_object()), set())
    finally:
        doc.close()


def test_build_pages_widgets_map_fallback_skips_page_without_annots_array() -> None:
    """In the reverse-walk fallback, a page whose ``/Annots`` is not a
    COSArray is skipped (line 1340 ``continue``)."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
        # /Annots present but wrong type — exercise the continue branch.
        page.get_cos_object().set_item(
            COSName.get_pdf_name("Annots"), COSDictionary()
        )
        doc.add_page(page)

        form = PDAcroForm(doc)
        field = PDTextField(form)
        field.set_partial_name("orphan")
        form.set_fields([field])
        # No /P on the widget → fallback runs and walks one bogus page.
        result = form.build_pages_widgets_map([field])
        assert result == {}
    finally:
        doc.close()


if __name__ == "__main__":  # pragma: no cover - manual debug
    pytest.main([__file__, "-v"])
