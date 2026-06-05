"""Wave 1484 — ``PDDocumentCatalog.get_acro_form()`` applies the default fixup.

Upstream's no-arg ``getAcroForm()`` is
``getAcroForm(new AcroFormDefaultFixup(document))`` (PDFBox 3.0.7,
``PDDocumentCatalog.java:111-113``). The default fixup runs
``AcroFormDefaultsProcessor`` which injects the Adobe defaults onto a
form that lacks them:

* ``/DA`` is set to ``/Helv 0 Tf 0 g`` when empty
  (``AcroFormDefaultsProcessor.java`` ``adobeDefaultAppearanceString``).
* ``/Helv`` (Helvetica) and ``/ZaDb`` (ZapfDingbats) are injected into
  ``/DR``'s ``/Font`` sub-dictionary (PDFBOX-3732).

The two-arg overload ``get_acro_form(None)`` mirrors upstream's
``getAcroForm(null)`` — no fixup, the form is returned exactly as parsed.

The literal values below were confirmed against live Apache PDFBox 3.0.7
via the ``AcroFormDefaultFixupProbe`` oracle (see
``tests/pdmodel/fixup/oracle`` differential). These hand-written tests
pin them and pass WITHOUT the oracle.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")
_ADOBE_DA = "/Helv 0 Tf 0 g "


def _build_form_doc_no_da_dr() -> PDDocument:
    """A one-text-field form with neither /DA nor /DR set."""
    doc = PDDocument()
    doc.add_page(PDPage())
    form = PDAcroForm(doc)
    fields = COSArray()
    field = COSDictionary()
    field.set_item(_FT, COSName.get_pdf_name("Tx"))
    field.set_string(_T, "field1")
    fields.add(field)
    form.get_cos_object().set_item(_FIELDS, fields)
    doc.get_document_catalog().set_acro_form(form)
    return doc


def _roundtrip(doc: PDDocument, tmp_path: Path) -> PDDocument:
    out = tmp_path / "form.pdf"
    doc.save(str(out))
    doc.close()
    return PDDocument.load(str(out))


def _dr_font_names(form: PDAcroForm) -> list[str]:
    dr = form.get_default_resources()
    if dr is None:
        return []
    return sorted(n.get_name() for n in dr.get_font_names())


def test_no_arg_get_acro_form_sets_adobe_default_appearance(tmp_path: Path) -> None:
    doc = _roundtrip(_build_form_doc_no_da_dr(), tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        assert form.get_default_appearance() == _ADOBE_DA
    finally:
        doc.close()


def test_no_arg_get_acro_form_injects_helv_and_zadb(tmp_path: Path) -> None:
    doc = _roundtrip(_build_form_doc_no_da_dr(), tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert _dr_font_names(form) == ["Helv", "ZaDb"]
    finally:
        doc.close()


def test_no_arg_get_acro_form_preserves_fields(tmp_path: Path) -> None:
    doc = _roundtrip(_build_form_doc_no_da_dr(), tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert len(form.get_fields()) == 1
    finally:
        doc.close()


def test_null_fixup_leaves_form_unfixed(tmp_path: Path) -> None:
    """``get_acro_form(None)`` mirrors ``getAcroForm(null)`` — no defaults."""
    doc = _roundtrip(_build_form_doc_no_da_dr(), tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form(None)
        assert form is not None
        assert form.get_default_appearance() == ""
        assert _dr_font_names(form) == []
    finally:
        doc.close()


def test_formless_pdf_stays_none_under_fixup(tmp_path: Path) -> None:
    """A PDF with no /AcroForm gets no form materialised by the fixup."""
    doc = PDDocument()
    doc.add_page(PDPage())
    out = tmp_path / "formless.pdf"
    doc.save(str(out))
    doc.close()
    doc = PDDocument.load(str(out))
    try:
        assert doc.get_document_catalog().get_acro_form() is None
    finally:
        doc.close()


def test_default_fixup_is_idempotent(tmp_path: Path) -> None:
    """Repeated no-arg calls re-apply the (idempotent) default fixup.

    Upstream creates a fresh ``AcroFormDefaultFixup`` per no-arg call, so
    it is re-applied every time — but the defaults processor only mutates
    when the entry is missing, so the second call is a no-op and the
    observable state is unchanged.
    """
    doc = _roundtrip(_build_form_doc_no_da_dr(), tmp_path)
    try:
        first = doc.get_document_catalog().get_acro_form()
        first_da = first.get_default_appearance()
        first_fonts = _dr_font_names(first)
        second = doc.get_document_catalog().get_acro_form()
        assert second.get_default_appearance() == first_da
        assert _dr_font_names(second) == first_fonts
    finally:
        doc.close()
