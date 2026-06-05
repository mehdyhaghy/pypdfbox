"""Live Apache PDFBox differential parity tests for the FORM-level /AcroForm
dictionary accessor surface (wave 1471).

Earlier form-oracle waves targeted per-FIELD accessors (FieldProbe / FieldTree
/ FieldFlags / qualified-name, waves 1428-1437). This wave pins the *form*
dictionary accessors of :class:`PDAcroForm` as a focused matrix against the
pinned pdfbox-app-3.0.7 jar:

  * ``get_default_appearance()`` (``/DA``)
  * ``get_need_appearances()`` / ``set_need_appearances`` (``/NeedAppearances``)
  * ``get_default_resources()`` font resource names (``/DR``)
  * ``has_xfa()`` / ``get_xfa()`` presence (``/XFA``)
  * ``is_signatures_exist()`` / ``is_append_only()`` + raw ``/SigFlags`` int
  * ``get_calc_order()`` count (``/CO``)
  * ``get_fields()`` count (top-level only) vs ``get_field_tree()`` iteration
    count (all descendants)
  * raw ``/Q`` form-wide quadding integer

The form is built once via pypdfbox and saved to ``tmp_path``; *both*
implementations then load the **same** bytes, so the build itself is part of
the differential surface. The Java side (``AcroFormAccessorProbe``) loads with
a *null* fixup (``getAcroForm(null)``) so PDFBox reports the AcroForm exactly as
parsed — without its ``AcroFormDefaultFixup`` (which would generate missing
widget appearances, clear ``/NeedAppearances``, and inject a ``ZaDb`` font into
``/DR``). pypdfbox performs no such fixup on load, so the null-fixup form is the
apples-to-apples reference for this surface.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "AcroFormAccessorProbe"

_FONT: COSName = COSName.get_pdf_name("Font")
_XFA: COSName = COSName.get_pdf_name("XFA")
_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")

# A minimal but well-formed dynamic XFA payload (just enough that PDFBox's
# getXFA() returns a non-null PDXFAResource).
_XFA_BYTES = (
    b'<?xml version="1.0"?><xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"></xdp:xdp>'
)


def _helvetica_font() -> COSDictionary:
    """A valid standard-14 Helvetica font dictionary for /DR."""
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Font")
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    d.set_name(COSName.get_pdf_name("Encoding"), "WinAnsiEncoding")
    return d


def _build_form(path: Path) -> None:
    """Build + save an AcroForm exercising every form-level accessor.

    Layout:
      * top-level non-terminal field ``address`` with one terminal child
        ``address.city`` -> get_fields() == 2 (address + email), field tree
        == 3 (address, address.city, email),
      * top-level terminal field ``email``,
      * /CO referencing the child -> get_calc_order() == 1,
      * /DR with one Helv font, form /DA, /Q 1 (centered),
      * /NeedAppearances true, /SigFlags 3 (signatures-exist + append-only),
      * an /XFA payload so has_xfa()/get_xfa() are exercised.
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        # Non-terminal parent with one inheriting terminal child.
        parent = PDNonTerminalField(form)
        parent.set_partial_name("address")
        parent.get_cos_object().set_name(COSName.get_pdf_name("FT"), "Tx")

        child = PDTextField(form)
        child.get_cos_object().remove_item(COSName.get_pdf_name("FT"))
        child.set_partial_name("city")
        child_widget = child.get_widgets()[0]
        child_widget.set_rectangle(PDRectangle(50, 700, 200, 20))
        child_widget.set_page(page)
        page.get_annotations().append(child_widget)
        parent.set_children([child])

        # A second top-level terminal field.
        email = PDTextField(form)
        email.set_partial_name("email")
        email.set_default_appearance("/Helv 10 Tf 0 g")
        email_widget = email.get_widgets()[0]
        email_widget.set_rectangle(PDRectangle(50, 740, 200, 20))
        email_widget.set_page(page)
        page.get_annotations().append(email_widget)

        form.set_fields([parent, email])

        # /CO references the child -> calc order count == 1.
        form.set_calc_order([child])

        # Form-level dictionary attributes.
        form.set_need_appearances(True)
        form.set_signature_flags(
            PDAcroForm.FLAG_SIGNATURES_EXIST | PDAcroForm.FLAG_APPEND_ONLY
        )
        form.set_default_appearance("/Helv 0 Tf 0 g")
        form.set_q(PDAcroForm.QUADDING_CENTERED)

        dr = PDResources()
        font_dict = COSDictionary()
        font_dict.set_item(COSName.get_pdf_name("Helv"), _helvetica_font())
        dr.get_cos_object().set_item(_FONT, font_dict)
        form.set_default_resources(dr)

        # /XFA dynamic payload. The spec allows /XFA to be either a stream or
        # an array of name/stream pairs; PDFBox's getXFA wraps whatever COSBase
        # sits at /XFA in a PDXFAResource, so a single stream suffices.
        from pypdfbox.cos import COSStream

        xfa_stream = COSStream()
        with xfa_stream.create_output_stream() as os_:
            os_.write(_XFA_BYTES)
        form.set_xfa(PDXFAResource(xfa_stream))

        doc.save(str(path))
    finally:
        doc.close()


class _Facts:
    def __init__(self) -> None:
        self.form_present = "false"
        self.da = ""
        self.need_appearances = "false"
        self.dr_fonts: list[str] = []
        self.has_xfa = "false"
        self.xfa_present = "false"
        self.sig_exist = "false"
        self.append_only = "false"
        self.sig_flags = 0
        self.calc_order = 0
        self.fields = 0
        self.field_tree = 0
        self.q = 0


def _parse(text: str) -> _Facts:
    facts = _Facts()
    for line in text.splitlines():
        if not line:
            continue
        key, _, value = line.partition("\t")
        if key == "FORMPRESENT":
            facts.form_present = value
        elif key == "DA":
            facts.da = value
        elif key == "NEEDAPPEARANCES":
            facts.need_appearances = value
        elif key == "DRFONTS":
            facts.dr_fonts = value.split(",") if value else []
        elif key == "HASXFA":
            facts.has_xfa = value
        elif key == "XFAPRESENT":
            facts.xfa_present = value
        elif key == "SIGEXIST":
            facts.sig_exist = value
        elif key == "APPENDONLY":
            facts.append_only = value
        elif key == "SIGFLAGS":
            facts.sig_flags = int(value)
        elif key == "CALCORDER":
            facts.calc_order = int(value)
        elif key == "FIELDS":
            facts.fields = int(value)
        elif key == "FIELDTREE":
            facts.field_tree = int(value)
        elif key == "Q":
            facts.q = int(value)
    return facts


def _esc(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _java_facts(path: Path) -> _Facts:
    return _parse(run_probe_text(_PROBE, str(path)))


def _py_facts(path: Path) -> _Facts:
    """Reproduce the probe's facts from a reloaded pypdfbox document."""
    doc = PDDocument.load(str(path))
    try:
        # Mirror the probe's getAcroForm(null): no default fixup, so both
        # sides report the dictionary exactly as parsed (wave 1484 made the
        # no-arg form apply AcroFormDefaultFixup like upstream).
        form = doc.get_document_catalog().get_acro_form(None)
        facts = _Facts()
        if form is None:
            facts.form_present = "false"
            return facts
        facts.form_present = "true"
        facts.da = _esc(form.get_default_appearance() or "")
        facts.need_appearances = "true" if form.get_need_appearances() else "false"

        dr = form.get_default_resources()
        if dr is not None:
            facts.dr_fonts = sorted(n.name for n in dr.get_font_names())

        facts.has_xfa = "true" if form.has_xfa() else "false"
        facts.xfa_present = "true" if form.get_xfa() is not None else "false"
        facts.sig_exist = "true" if form.is_signatures_exist() else "false"
        facts.append_only = "true" if form.is_append_only() else "false"
        facts.sig_flags = form.get_cos_object().get_int(_SIG_FLAGS, 0)
        facts.calc_order = len(form.get_calc_order())
        facts.fields = len(form.get_fields())
        facts.field_tree = sum(1 for _ in form.get_field_tree())
        facts.q = form.get_q()
        return facts
    finally:
        doc.close()


@requires_oracle
def test_form_present_and_simple_attrs_match_pdfbox(tmp_path: Path) -> None:
    """/DA, /NeedAppearances, /Q and form presence match PDFBox."""
    pdf = tmp_path / "accessors.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert py.form_present == java.form_present == "true"
    assert py.da == java.da == "/Helv 0 Tf 0 g"
    assert py.need_appearances == java.need_appearances == "true"
    assert py.q == java.q == PDAcroForm.QUADDING_CENTERED


@requires_oracle
def test_default_resources_fonts_match_pdfbox(tmp_path: Path) -> None:
    """/DR font resource names match PDFBox."""
    pdf = tmp_path / "accessors.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert py.dr_fonts == java.dr_fonts == ["Helv"]


@requires_oracle
def test_xfa_presence_matches_pdfbox(tmp_path: Path) -> None:
    """has_xfa() and get_xfa()-presence match PDFBox for an /XFA payload."""
    pdf = tmp_path / "accessors.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert py.has_xfa == java.has_xfa == "true"
    assert py.xfa_present == java.xfa_present == "true"


@requires_oracle
def test_signature_flags_match_pdfbox(tmp_path: Path) -> None:
    """isSignaturesExist / isAppendOnly and the raw /SigFlags int match."""
    pdf = tmp_path / "accessors.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert py.sig_exist == java.sig_exist == "true"
    assert py.append_only == java.append_only == "true"
    assert py.sig_flags == java.sig_flags == (
        PDAcroForm.FLAG_SIGNATURES_EXIST | PDAcroForm.FLAG_APPEND_ONLY
    )


@requires_oracle
def test_fields_vs_field_tree_counts_match_pdfbox(tmp_path: Path) -> None:
    """get_fields() (top-level) vs get_field_tree() (all descendants) and
    get_calc_order() counts match PDFBox."""
    pdf = tmp_path / "accessors.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    # 2 top-level (address, email); 3 in the tree (+ address.city).
    assert py.fields == java.fields == 2
    assert py.field_tree == java.field_tree == 3
    assert py.calc_order == java.calc_order == 1
