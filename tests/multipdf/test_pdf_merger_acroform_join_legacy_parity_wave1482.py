"""Wave 1482 — PDFMergerUtility AcroForm JOIN-vs-LEGACY mode parity.

In Apache PDFBox 3.0.x ``PDFMergerUtility.acroFormJoinFieldsMode`` is a thin
delegate to ``acroFormLegacyMode`` (verified by reading
``PDFMergerUtility.java:1278`` and confirmed live via the
``MergeFormFieldsModeProbe`` oracle). Therefore JOIN_FORM_FIELDS_MODE and
PDFBOX_LEGACY_MODE produce byte-identical AcroForm field sets: a destination
field-name collision is renamed to ``dummyFieldNameN`` under BOTH modes.

pypdfbox previously diverged — its JOIN path appended source fields verbatim
(two fields both named ``name``). This file pins the corrected, oracle-matching
behaviour: JOIN mode renames collisions exactly like legacy mode.

The hand-written tests below assert the literal oracle values without needing
the oracle. A trailing ``@requires_oracle`` differential test compares the live
PDFBox output for both modes against pypdfbox on identical input bytes.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import AcroFormMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from tests.oracle.harness import requires_oracle, run_probe_text

_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")


def _build_acroform_doc(field_names: list[str]) -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage())
    form = PDAcroForm(doc)
    fields = COSArray()
    for name in field_names:
        field = COSDictionary()
        field.set_item(_FT, COSName.get_pdf_name("Tx"))
        field.set_string(_T, name)
        fields.add(field)
    form.get_cos_object().set_item(_FIELDS, fields)
    doc.get_document_catalog().set_acro_form(form)
    return doc


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def _merge(mode: AcroFormMergeMode, srcs: list[Path], out: Path) -> list[str]:
    util = PDFMergerUtility()
    util.add_sources([str(p) for p in srcs])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(mode)
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        return sorted(f.get_partial_name() or "" for f in form.get_fields())


def test_join_mode_renames_single_collision_to_dummy1(tmp_path: Path) -> None:
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _save(_build_acroform_doc(["name"]), a)
    _save(_build_acroform_doc(["name"]), b)
    names = _merge(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE, [a, b], tmp_path / "o.pdf")
    assert names == ["dummyFieldName1", "name"]


def test_join_and_legacy_modes_are_identical(tmp_path: Path) -> None:
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _save(_build_acroform_doc(["name"]), a)
    _save(_build_acroform_doc(["name"]), b)
    legacy = _merge(
        AcroFormMergeMode.PDFBOX_LEGACY_MODE, [a, b], tmp_path / "ol.pdf"
    )
    join = _merge(
        AcroFormMergeMode.JOIN_FORM_FIELDS_MODE, [a, b], tmp_path / "oj.pdf"
    )
    assert join == legacy == ["dummyFieldName1", "name"]


def test_join_mode_three_collisions(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.pdf", tmp_path / "b.pdf", tmp_path / "c.pdf"
    _save(_build_acroform_doc(["A"]), a)
    _save(_build_acroform_doc(["A"]), b)
    _save(_build_acroform_doc(["A"]), c)
    names = _merge(
        AcroFormMergeMode.JOIN_FORM_FIELDS_MODE, [a, b, c], tmp_path / "o.pdf"
    )
    assert names == ["A", "dummyFieldName1", "dummyFieldName2"]


def test_join_mode_distinct_names_unchanged(tmp_path: Path) -> None:
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _save(_build_acroform_doc(["alpha", "beta"]), a)
    _save(_build_acroform_doc(["gamma"]), b)
    names = _merge(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE, [a, b], tmp_path / "o.pdf")
    assert names == ["alpha", "beta", "gamma"]


@requires_oracle
def test_oracle_join_equals_legacy_on_collision(tmp_path: Path) -> None:
    """Live PDFBox: JOIN and LEGACY emit identical field sets, and pypdfbox
    matches both, on the same input bytes."""
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _save(_build_acroform_doc(["name"]), a)
    _save(_build_acroform_doc(["name"]), b)

    def _oracle(mode: str) -> list[str]:
        out = tmp_path / f"oracle_{mode}.pdf"
        text = run_probe_text(
            "MergeFormFieldsModeProbe", mode, str(out), str(a), str(b)
        )
        fields = [
            line[len("field ") :]
            for line in text.splitlines()
            if line.startswith("field ")
        ]
        return sorted(fields)

    oracle_legacy = _oracle("LEGACY")
    oracle_join = _oracle("JOIN")
    assert oracle_join == oracle_legacy == ["dummyFieldName1", "name"]

    py_legacy = _merge(
        AcroFormMergeMode.PDFBOX_LEGACY_MODE, [a, b], tmp_path / "py_legacy.pdf"
    )
    py_join = _merge(
        AcroFormMergeMode.JOIN_FORM_FIELDS_MODE, [a, b], tmp_path / "py_join.pdf"
    )
    assert py_legacy == oracle_legacy
    assert py_join == oracle_join
