"""Live Apache PDFBox differential parity for FDF / XFDF documents
(``pypdfbox.pdmodel.fdf``).

No FDF/XFDF fixtures ship with the repo, so the parity rig *builds* an FDF
through pypdfbox (a handful of fields — one with nested ``/Kids``, one
multi-select — plus a couple of annotations and a ``/F`` source reference),
saves it as both FDF and XFDF, then runs **both** libraries over the saved
artefacts and asserts they read the same field tree, values, and annotations.

The Java oracle is ``FdfProbe`` (modes ``dump`` / ``roundtrip``). It emits
canonical, line-oriented facts:

* ``F=<source PDF path or - >``
* ``FIELD <fully-qualified-name> | value=<repr> | kids=<n>`` (depth-first)
* ``ANNOT <subtype or -> | rect=<llx,lly,urx,ury or - >``

``_py_dump`` reproduces exactly that format from pypdfbox so the two sides can
be compared line-for-line.

Key behavioural facts confirmed against PDFBox 3.0.7 and baked into the
assertions here:

* A pypdfbox-saved FDF must start with an ``%FDF-`` header — PDFBox's
  ``FDFParser`` rejects a ``%PDF-`` header. (Fixed: ``COSWriter(fdf=True)``.)
* ``FDFDictionary.writeXML`` (the XFDF serialiser) does **not** emit
  ``<annots>`` — XFDF round-trips fields + ``/F`` but drops annotations. This
  is upstream behaviour, so the XFDF comparison only covers fields + ``/F``.
* A multi-select field serialised to XFDF as repeated ``<value>`` elements is
  collapsed to the *last* value on reload by **both** libraries (PDFBox's
  ``FDFField(Element)`` keeps only the last ``<value>``). Asserted as parity,
  not flagged as a bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.fdf import FDFDocument
from pypdfbox.pdmodel.fdf.fdf_annotation_square import FDFAnnotationSquare
from pypdfbox.pdmodel.fdf.fdf_annotation_text import FDFAnnotationText
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- fixture build


def _build_fdf(path_fdf: Path, path_xfdf: Path) -> None:
    """Build a representative FDF via pypdfbox and save it as both FDF and
    XFDF. Fields: a scalar, a parent with one kid, and a multi-select.
    Annotations: a Text and a Square (each with a /Rect). Plus a /F.
    """
    doc = FDFDocument()
    try:
        fdf = doc.get_catalog().get_fdf()

        fs = PDSimpleFileSpecification()
        fs.set_file("source.pdf")
        fdf.set_file(fs)

        f_name = FDFField()
        f_name.set_partial_field_name("name")
        f_name.set_value("Alice")

        f_addr = FDFField()
        f_addr.set_partial_field_name("address")
        kid_city = FDFField()
        kid_city.set_partial_field_name("city")
        kid_city.set_value("Paris")
        f_addr.set_kids([kid_city])

        f_langs = FDFField()
        f_langs.set_partial_field_name("langs")
        f_langs.set_value(["en", "fr"])

        fdf.set_fields([f_name, f_addr, f_langs])

        a_text = FDFAnnotationText()
        a_text.set_page(0)
        a_text.set_rectangle((10.0, 20.0, 30.0, 40.0))

        a_square = FDFAnnotationSquare()
        a_square.set_page(0)
        a_square.set_rectangle((1.5, 2.5, 3.5, 4.5))

        fdf.set_annotations([a_text, a_square])

        doc.save(str(path_fdf))
        doc.save_xfdf(str(path_xfdf))
    finally:
        doc.close()


# --------------------------------------------------------------- py dump helper


def _fmt_num(v: float) -> str:
    """Match the probe's float formatting: drop a trailing ``.0`` for
    integral coordinates so ``10.0`` and ``10`` compare equal."""
    if v == int(v):
        return str(int(v))
    return str(v)


def _value_repr(value: object | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return "[" + "|".join(str(item) for item in value) + "]"
    return str(value)


def _emit_field(field: FDFField, prefix: str, lines: list[str]) -> None:
    partial = field.get_partial_field_name() or ""
    fq = f"{prefix}.{partial}" if prefix and partial else (prefix or partial)
    value_repr = _value_repr(field.get_value())
    kids = field.get_kids()
    kid_count = 0 if kids is None else len(kids)
    lines.append(f"FIELD {fq} | value={value_repr} | kids={kid_count}")
    if kids is not None:
        for kid in kids:
            _emit_field(kid, fq, lines)


def _py_dump(doc: FDFDocument, *, with_annots: bool) -> list[str]:
    """Reproduce the probe's canonical ``dump`` output from pypdfbox.

    ``with_annots=False`` for the XFDF comparison, since the XFDF serialiser
    does not write ``<annots>`` (matches upstream ``FDFDictionary.writeXML``).
    """
    fdf = doc.get_catalog().get_fdf()
    lines: list[str] = []

    fs = fdf.get_file()
    f = "-" if fs is None or fs.get_file() is None else fs.get_file()
    lines.append(f"F={f}")

    fields = fdf.get_fields()
    if fields is not None:
        for field in fields:
            _emit_field(field, "", lines)

    if with_annots:
        annots = fdf.get_annotations()
        if annots is not None:
            for annot in annots:
                subtype = annot.get_subtype() or "-"
                rect = annot.get_rectangle()
                rect_repr = (
                    "-" if rect is None else ",".join(_fmt_num(c) for c in rect)
                )
                lines.append(f"ANNOT {subtype} | rect={rect_repr}")

    return lines


def _java_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln and not ln.startswith("== ")]


# --------------------------------------------------------------------- tests


@requires_oracle
def test_fdf_fields_annotations_match_pdfbox(tmp_path: Path) -> None:
    """pypdfbox and PDFBox read the same field tree, values, kids, /F, and
    annotations from a pypdfbox-saved FDF file."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    # The FDF header must be %FDF- (PDFBox's FDFParser requires it).
    assert fdf_path.read_bytes().startswith(b"%FDF-"), (
        "pypdfbox FDF save must emit an %FDF- header; PDFBox rejects %PDF-"
    )

    java = _java_lines(run_probe_text("FdfProbe", "dump", "fdf", str(fdf_path)))

    doc = Loader.load_fdf(str(fdf_path))
    try:
        py = _py_dump(doc, with_annots=True)
    finally:
        doc.close()

    assert py == java


@requires_oracle
def test_xfdf_fields_match_pdfbox(tmp_path: Path) -> None:
    """pypdfbox and PDFBox read the same field tree, values, and /F from a
    pypdfbox-saved XFDF file. Annotations are excluded — the XFDF serialiser
    does not write <annots> (upstream FDFDictionary.writeXML)."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    java = _java_lines(run_probe_text("FdfProbe", "dump", "xfdf", str(xfdf_path)))

    doc = Loader.load_xfdf(str(xfdf_path))
    try:
        py = _py_dump(doc, with_annots=False)
    finally:
        doc.close()

    assert py == java


@requires_oracle
def test_xfdf_does_not_carry_annotations(tmp_path: Path) -> None:
    """Documented divergence-free behaviour: the XFDF serialiser drops
    annotations on both sides. PDFBox's dump of the saved XFDF carries no
    ANNOT line, and so does pypdfbox's reload."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    java = run_probe_text("FdfProbe", "dump", "xfdf", str(xfdf_path))
    assert "ANNOT" not in java

    doc = Loader.load_xfdf(str(xfdf_path))
    try:
        annots = doc.get_catalog().get_fdf().get_annotations()
    finally:
        doc.close()
    # No <annots> element in the XFDF → get_annotations() returns None.
    assert annots is None


@requires_oracle
def test_fdf_round_trip_pypdfbox_save_java_reload(tmp_path: Path) -> None:
    """Round-trip contract: a pypdfbox-saved FDF, when re-saved by PDFBox as
    both FDF and XFDF and reloaded, yields the same fields PDFBox first read.

    The probe's ``roundtrip`` mode does PDFBox-side load → save(FDF) +
    saveXFDF → reload-each → dump. We assert:

    * the re-saved FDF block matches what pypdfbox reads from the *original*
      FDF (field tree + values + /F + annotations all survive a full PDFBox
      FDF round-trip);
    * the re-saved XFDF block matches what pypdfbox reads from the *XFDF*
      (fields + /F; annotations dropped by the XFDF serialiser, and the
      multi-select ``langs`` collapses to its last value — both libraries
      behave identically on the XFDF path)."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    out_fdf = tmp_path / "rt.fdf"
    out_xfdf = tmp_path / "rt.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    raw = run_probe_text(
        "FdfProbe",
        "roundtrip",
        "fdf",
        str(fdf_path),
        str(out_fdf),
        str(out_xfdf),
    )

    # Split the probe output into its two reload blocks.
    fdf_block: list[str] = []
    xfdf_block: list[str] = []
    target: list[str] | None = None
    for line in raw.splitlines():
        if line == "== fdf ==":
            target = fdf_block
        elif line == "== xfdf ==":
            target = xfdf_block
        elif line and target is not None:
            target.append(line)

    # pypdfbox's own reading of the original FDF — baseline for the FDF block.
    doc_fdf = Loader.load_fdf(str(fdf_path))
    try:
        py_full = _py_dump(doc_fdf, with_annots=True)
    finally:
        doc_fdf.close()

    # pypdfbox's own reading of the saved XFDF — baseline for the XFDF block.
    # (The XFDF serialiser drops annotations and the multi-select collapses to
    # its last value, so this is the correct parity baseline, not the FDF one.)
    doc_xfdf = Loader.load_xfdf(str(xfdf_path))
    try:
        py_xfdf = _py_dump(doc_xfdf, with_annots=False)
    finally:
        doc_xfdf.close()

    # A full PDFBox FDF round-trip preserves the whole field tree + annots.
    assert fdf_block == py_full
    # The XFDF round-trip preserves fields + /F (annotations dropped).
    assert xfdf_block == py_xfdf


@requires_oracle
def test_fdf_saved_by_pypdfbox_round_trips_through_pypdfbox(tmp_path: Path) -> None:
    """Pure-pypdfbox FDF round-trip: save → reload reproduces the field tree,
    values, kids, /F, and annotations (sanity check independent of Java)."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    doc = Loader.load_fdf(str(fdf_path))
    try:
        dump = _py_dump(doc, with_annots=True)
    finally:
        doc.close()

    assert dump == [
        "F=source.pdf",
        "FIELD name | value=Alice | kids=0",
        "FIELD address | value=- | kids=1",
        "FIELD address.city | value=Paris | kids=0",
        "FIELD langs | value=[en|fr] | kids=0",
        "ANNOT Text | rect=10,20,30,40",
        "ANNOT Square | rect=1.5,2.5,3.5,4.5",
    ]


# --------------------------------------------- AcroForm import parity fixtures


def _add_widget_rect(
    field_dict: COSDictionary,
    page: PDPage,
    rect: tuple[float, float, float, float],
) -> None:
    """Make ``field_dict`` a merged-widget field (no /Kids) anchored on
    ``page`` with a /Rect — gives the import-time appearance generator a
    rectangle so the build matches a real form widget."""
    field_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    field_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    arr = COSArray()
    for v in rect:
        arr.add(COSFloat(float(v)))
    field_dict.set_item(COSName.get_pdf_name("Rect"), arr)
    field_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    if not isinstance(annots, COSArray):
        annots = COSArray()
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    annots.add(field_dict)


def _form_xobject() -> COSStream:
    """A minimal /AP /N appearance form XObject (empty content)."""
    s = COSStream()
    s.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    s.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    bbox = COSArray()
    for v in (0.0, 0.0, 20.0, 20.0):
        bbox.add(COSFloat(v))
    s.set_item(COSName.get_pdf_name("BBox"), bbox)
    s.set_raw_data(b"q Q\n")
    return s


def _build_form_pdf(path_pdf: Path) -> None:
    """Build an AcroForm PDF whose fields mirror the import FDF: a text
    ``name``, a combo ``color`` (a choice — exercises string coercion), a
    checkbox ``agree`` carrying real ``Yes``/``Off`` on-state appearances (so
    the on-value is valid on *both* libraries — PDFBox's ``PDButton.checkValue``
    rejects an on-value with no matching appearance state), and a hierarchical
    ``address`` parent with a ``city`` text child (the FQN case)."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        name = PDTextField(form)
        name.set_partial_name("name")
        _add_widget_rect(name.get_cos_object(), page, (10.0, 700.0, 210.0, 720.0))

        color = PDComboBox(form)
        color.set_partial_name("color")
        color.set_options(["Red", "Green", "Blue"])
        _add_widget_rect(color.get_cos_object(), page, (10.0, 650.0, 210.0, 670.0))

        agree = PDCheckBox(form)
        agree.set_partial_name("agree")
        _add_widget_rect(agree.get_cos_object(), page, (10.0, 600.0, 30.0, 620.0))
        ap_n = COSDictionary()
        ap_n.set_item(COSName.get_pdf_name("Yes"), _form_xobject())
        ap_n.set_item(COSName.get_pdf_name("Off"), _form_xobject())
        ap = COSDictionary()
        ap.set_item(COSName.get_pdf_name("N"), ap_n)
        agree.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
        agree.get_cos_object().set_name(COSName.get_pdf_name("AS"), "Off")

        address = PDNonTerminalField(form)
        address.set_partial_name("address")
        city = PDTextField(form, None, address)
        city.set_partial_name("city")
        _add_widget_rect(city.get_cos_object(), page, (10.0, 550.0, 210.0, 570.0))
        address.set_children([city])

        form.set_fields([name, color, agree, address])
        doc.save(str(path_pdf))
    finally:
        doc.close()


def _build_import_fdf(path_fdf: Path) -> None:
    """Build the FDF whose values are imported into the AcroForm: a text
    value, a choice value, a checkbox name value, and a hierarchical
    ``address`` → ``city`` value (exercises the kids-tree import walk)."""
    doc = FDFDocument()
    try:
        fdf = doc.get_catalog().get_fdf()

        f_name = FDFField()
        f_name.set_partial_field_name("name")
        f_name.set_value("Alice")

        f_color = FDFField()
        f_color.set_partial_field_name("color")
        f_color.set_value("Green")

        # Checkbox: a /V name (not a string) — exercises name coercion.
        f_agree = FDFField()
        f_agree.set_partial_field_name("agree")
        f_agree.get_cos_object().set_item(
            COSName.get_pdf_name("V"), COSName.get_pdf_name("Yes")
        )

        f_addr = FDFField()
        f_addr.set_partial_field_name("address")
        f_city = FDFField()
        f_city.set_partial_field_name("city")
        f_city.set_value("Paris")
        f_addr.set_kids([f_city])

        fdf.set_fields([f_name, f_color, f_agree, f_addr])
        doc.save(str(path_fdf))
    finally:
        doc.close()


def _cos_value_repr(v: object | None) -> str:
    """Match the probe's ``cosValueRepr``: name string / decoded string /
    ``[a|b|c]`` array, else ``str``."""
    from pypdfbox.cos import COSString

    if v is None:
        return "-"
    if isinstance(v, COSName):
        return v.name
    if isinstance(v, COSString):
        return v.get_string()
    if isinstance(v, COSArray):
        parts = []
        for item in v:
            if isinstance(item, COSString):
                parts.append(item.get_string())
            elif isinstance(item, COSName):
                parts.append(item.name)
            else:
                parts.append(str(item))
        return "[" + "|".join(parts) + "]"
    return str(v)


def _py_import_dump(form: PDAcroForm) -> list[str]:
    """Reproduce the probe's ``import`` mode output from pypdfbox: a
    depth-first ``IMPORT <fqn> | value=<repr> | type=<COS-class or - >``
    line per field (parents before children)."""
    lines: list[str] = []

    def walk(field: object) -> None:
        cos = field.get_cos_object()  # type: ignore[attr-defined]
        v = cos.get_dictionary_object(COSName.get_pdf_name("V"))
        type_name = "-" if v is None else type(v).__name__
        fqn = field.get_fully_qualified_name()  # type: ignore[attr-defined]
        lines.append(
            f"IMPORT {fqn} | value={_cos_value_repr(v)} | type={type_name}"
        )
        if isinstance(field, PDNonTerminalField):
            for child in field.get_children():
                walk(child)

    for top in form.get_fields():
        walk(top)
    return lines


# ------------------------------------------------------- import parity tests


@requires_oracle
def test_fdf_import_into_acroform_matches_pdfbox(tmp_path: Path) -> None:
    """High-value case: build an AcroForm PDF + a matching FDF via pypdfbox,
    then have *both* PDFBox and pypdfbox load the PDF, import the FDF, and
    report each field's post-import /V value and COS type. The hierarchical
    ``address.city`` FQN transfer and the per-type coercion (text/choice →
    string, checkbox → name) must match line-for-line."""
    pdf_path = tmp_path / "form.pdf"
    fdf_path = tmp_path / "data.fdf"
    _build_form_pdf(pdf_path)
    _build_import_fdf(fdf_path)

    java = [
        ln
        for ln in run_probe_text(
            "FdfProbe", "import", str(pdf_path), str(fdf_path)
        ).splitlines()
        if ln
    ]

    doc = PDDocument.load(str(pdf_path))
    fdf = Loader.load_fdf(str(fdf_path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        form.import_fdf(fdf)
        py = _py_import_dump(form)
    finally:
        fdf.close()
        doc.close()

    assert py == java


@requires_oracle
def test_fdf_import_values_and_coercion(tmp_path: Path) -> None:
    """Pin the exact post-import facts (independent of Java) so a regression
    in value transfer or type coercion is caught even without the oracle:
    text/choice land as COSString, the checkbox name lands as COSName, the
    non-terminal ``address`` parent keeps no /V, and the kid ``address.city``
    receives its value through the hierarchical import walk."""
    pdf_path = tmp_path / "form.pdf"
    fdf_path = tmp_path / "data.fdf"
    _build_form_pdf(pdf_path)
    _build_import_fdf(fdf_path)

    doc = PDDocument.load(str(pdf_path))
    fdf = Loader.load_fdf(str(fdf_path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        form.import_fdf(fdf)
        dump = _py_import_dump(form)
    finally:
        fdf.close()
        doc.close()

    assert dump == [
        "IMPORT name | value=Alice | type=COSString",
        "IMPORT color | value=Green | type=COSString",
        "IMPORT agree | value=Yes | type=COSName",
        "IMPORT address | value=- | type=-",
        "IMPORT address.city | value=Paris | type=COSString",
    ]


@requires_oracle
def test_fdf_export_then_reimport_round_trip(tmp_path: Path) -> None:
    """Round-trip: import an FDF into an AcroForm, export the form back to a
    fresh FDF, then re-import that exported FDF into a clean copy of the same
    form. The twice-imported field values must equal the once-imported ones —
    export must faithfully snapshot every transferred /V (incl. the nested
    ``address.city``)."""
    pdf_path = tmp_path / "form.pdf"
    fdf_path = tmp_path / "data.fdf"
    _build_form_pdf(pdf_path)
    _build_import_fdf(fdf_path)

    # First import, then export to a new FDF.
    doc = PDDocument.load(str(pdf_path))
    fdf = Loader.load_fdf(str(fdf_path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        form.import_fdf(fdf)
        once = _py_import_dump(form)
        exported = form.export_fdf()
    finally:
        fdf.close()
        doc.close()

    # Re-import the exported FDF into a clean copy of the form.
    doc2 = PDDocument.load(str(pdf_path))
    try:
        form2 = doc2.get_document_catalog().get_acro_form()
        form2.import_fdf(exported)
        twice = _py_import_dump(form2)
    finally:
        exported.close()
        doc2.close()

    assert twice == once


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q", "--no-cov"]))
