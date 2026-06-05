"""Live differential oracle: ``get_acro_form()`` default-fixup parity.

Compares Apache PDFBox 3.0.7's no-arg ``getAcroForm()`` (which applies
``AcroFormDefaultFixup``) and ``getAcroForm(null)`` against pypdfbox on the
same input bytes, via the ``AcroFormDefaultFixupProbe`` probe.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from tests.oracle.harness import requires_oracle, run_probe_text

_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")


def _build_form_doc(tmp_path: Path) -> Path:
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
    out = tmp_path / "form_no_da_dr.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _parse_probe(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "\t" in line:
            key, _, value = line.partition("\t")
            result[key] = value
    return result


def _dr_fonts(form: PDAcroForm) -> str:
    dr = form.get_default_resources()
    if dr is None:
        return ""
    return ",".join(sorted(n.get_name() for n in dr.get_font_names()))


@requires_oracle
def test_default_fixup_matches_pdfbox(tmp_path: Path) -> None:
    pdf = _build_form_doc(tmp_path)
    java = _parse_probe(run_probe_text("AcroFormDefaultFixupProbe", str(pdf)))

    # null-fixup parity
    doc = PDDocument.load(str(pdf))
    try:
        null_form = doc.get_document_catalog().get_acro_form(None)
        assert (null_form is not None) == (java["NULL_FORMPRESENT"] == "true")
        assert null_form.get_default_appearance() == java["NULL_DA"]
        assert _dr_fonts(null_form) == java["NULL_DRFONTS"]
        assert str(len(null_form.get_fields())) == java["NULL_FIELDS"]
    finally:
        doc.close()

    # default-fixup parity
    doc = PDDocument.load(str(pdf))
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert (form is not None) == (java["FIXUP_FORMPRESENT"] == "true")
        assert form.get_default_appearance() == java["FIXUP_DA"]
        assert _dr_fonts(form) == java["FIXUP_DRFONTS"]
        assert str(len(form.get_fields())) == java["FIXUP_FIELDS"]
    finally:
        doc.close()
