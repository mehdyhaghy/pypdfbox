"""Live PDFBox differential parity for the interactive surface
(``pypdfbox.pdmodel.interactive`` — annotations + AcroForm fields).

Two Java probes back this module:

* ``AnnotProbe`` — for every page, one canonical line per annotation:
  ``page <idx> <subtype> rect=<x0>,<y0>,<x1>,<y1> contents=<0|1> apN=<0|1>``.
  Lines are sorted within a page so the comparison is independent of the
  ``/Annots`` array order. Rect corners are rounded to the nearest int so
  float-formatting differences can never produce a spurious mismatch.
* ``FieldProbe`` — one canonical line per field in ``getFieldTree()``:
  ``<fqName>\t<fieldType>\t<valueAsString>\t<defaultValue>``. Lines are
  sorted by the tab-joined record so the comparison is independent of the
  tree-walk order. ``valueAsString`` is ``PDField.getValueAsString()`` and
  ``defaultValue`` is the canonical render of the inheritable ``/DV`` entry.

Every field is **exact-match** against Apache PDFBox's own accessors — there
is no rendering slack to hide behind. A mismatch is a real bug.

Divergence found and FIXED (wave 1409): ``PDChoice.getValueAsString`` was
comma-joining the selected options (``"a,c"``); upstream returns
``Arrays.toString(getValue().toArray())`` — bracketed, ``", "``-joined
(``"[a, c]"``, ``"[]"`` when empty). Confirmed via ``FieldProbe`` against
``AcroFormsBasicFields.pdf`` and fixed in ``pd_choice.py``.

Documented (NOT fixed here): ``PDDocumentCatalog.get_acro_form(None)`` does
not apply upstream's ``AcroFormDefaultFixup`` (pypdfbox documents this — the
no-arg path is the unfixed AcroForm). For the fixtures here the field tree
and values are identical with or without the fixup, so parity holds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
_INTERACTIVE = _FIXTURES / "pdmodel" / "interactive"

# Fixtures that carry annotations (Square/Circle/Popup/Widget/etc.).
_ANNOT_FIXTURES = [
    (_INTERACTIVE / "annotation" / "AnnotationTypes.pdf", "annotation_types"),
    (_INTERACTIVE / "form" / "AcroFormsBasicFields.pdf", "basic_widgets"),
    (_INTERACTIVE / "form" / "AcroFormsRotation.pdf", "rotation_widgets"),
    (_INTERACTIVE / "form" / "MultilineFields.pdf", "multiline_widgets"),
]

# AcroForm fixtures spanning text / button / choice / signature field types.
_FORM_FIXTURES = [
    (_INTERACTIVE / "form" / "AcroFormsBasicFields.pdf", "basic_fields"),
    (_INTERACTIVE / "form" / "AcroFormsRotation.pdf", "rotation_fields"),
    (_INTERACTIVE / "form" / "MultilineFields.pdf", "multiline_fields"),
    (_INTERACTIVE / "form" / "CombTest.pdf", "comb"),
    (_INTERACTIVE / "form" / "ControlCharacters.pdf", "control_characters"),
    (_INTERACTIVE / "form" / "DifferentDALevels.pdf", "different_da_levels"),
    (
        _INTERACTIVE / "form" / "PDFBOX-3656-SF1199AEG (Complete).pdf",
        "pdfbox_3656",
    ),
    (
        _INTERACTIVE / "form" / "PDFBOX-3835-input-acrobat-wrap.pdf",
        "pdfbox_3835",
    ),
    (_INTERACTIVE / "form" / "PDFBOX-5784.pdf", "pdfbox_5784"),
    (
        _INTERACTIVE / "form" / "PDFBOX3812-acrobat-multiline-auto.pdf",
        "pdfbox_3812",
    ),
    (_INTERACTIVE / "form" / "AlignmentTests.pdf", "alignment"),
]

_DV = COSName.get_pdf_name("DV")


# ---------- pypdfbox renderers (must match the Java probes char-for-char) ----------


def _rect(rect: object) -> str:
    if rect is None:
        return "none"
    return (
        f"{round(rect.get_lower_left_x())},{round(rect.get_lower_left_y())},"  # type: ignore[attr-defined]
        f"{round(rect.get_upper_right_x())},{round(rect.get_upper_right_y())}"  # type: ignore[attr-defined]
    )


def _py_annotations(fixture: Path) -> str:
    """Build the same per-page annotation report ``AnnotProbe`` emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        for idx, page in enumerate(doc.get_pages()):
            page_lines: list[str] = []
            for annot in page.get_annotations():
                subtype = annot.get_subtype() or "?"
                rect = _rect(annot.get_rectangle())
                contents = 1 if annot.get_contents() is not None else 0
                ap = annot.get_appearance()
                ap_n = 1 if (ap is not None and ap.get_normal_appearance() is not None) else 0
                page_lines.append(
                    f"page {idx} {subtype} rect={rect} "
                    f"contents={contents} apN={ap_n}"
                )
            page_lines.sort()
            lines.extend(page_lines)
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


def _esc(value: str | None) -> str:
    if value is None:
        return "none"
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _inheritable_dv(field: object):  # type: ignore[no-untyped-def]
    """Walk field -> parent chain, then the AcroForm root, for ``/DV`` —
    mirrors ``FieldProbe.inheritable``."""
    current = field
    while current is not None:
        item = current.get_cos_object().get_dictionary_object(_DV)  # type: ignore[attr-defined]
        if item is not None:
            return item
        current = current.get_parent()  # type: ignore[attr-defined]
    return field.get_acro_form().get_cos_object().get_dictionary_object(_DV)  # type: ignore[attr-defined]


def _default_value(field: object) -> str:  # type: ignore[no-untyped-def]
    dv = _inheritable_dv(field)
    if dv is None:
        return "none"
    if isinstance(dv, COSString):
        return _esc(dv.get_string())
    if isinstance(dv, COSName):
        return _esc(dv.name)
    return "present"


def _py_fields(fixture: Path) -> str:
    """Build the same field report ``FieldProbe`` emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        form = doc.get_document_catalog().get_acro_form()
        if form is not None:
            for field in form.get_field_tree():
                name = field.get_fully_qualified_name()
                ftype = field.get_field_type() or "?"
                value = _esc(field.get_value_as_string())
                dv = _default_value(field)
                lines.append(f"{name}\t{ftype}\t{value}\t{dv}")
            lines.sort()
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


# ---------- differential tests ----------


@requires_oracle
@pytest.mark.parametrize(
    "fixture, _label",
    _ANNOT_FIXTURES,
    ids=[label for _, label in _ANNOT_FIXTURES],
)
def test_annotations_match_pdfbox(fixture: Path, _label: str) -> None:
    java = run_probe_text("AnnotProbe", str(fixture))
    py = _py_annotations(fixture)
    assert py == java


@requires_oracle
@pytest.mark.parametrize(
    "fixture, _label",
    _FORM_FIXTURES,
    ids=[label for _, label in _FORM_FIXTURES],
)
def test_form_fields_match_pdfbox(fixture: Path, _label: str) -> None:
    java = run_probe_text("FieldProbe", str(fixture))
    py = _py_fields(fixture)
    assert py == java


@requires_oracle
def test_annotation_fixtures_actually_carry_annotations() -> None:
    """Guard: at least one annotation fixture must be non-empty, so a probe
    that silently emits nothing can't make the parity tests vacuously pass."""
    report = _py_annotations(_INTERACTIVE / "annotation" / "AnnotationTypes.pdf")
    assert report.strip() != ""


@requires_oracle
def test_form_fixtures_actually_carry_fields() -> None:
    """Guard: the basic AcroForm fixture must enumerate fields."""
    report = _py_fields(_INTERACTIVE / "form" / "AcroFormsBasicFields.pdf")
    assert report.strip() != ""
