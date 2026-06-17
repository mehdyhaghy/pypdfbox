"""Live PDFBox differential parity for ``PDFMergerUtility`` AcroForm field
merging when source documents carry COLLIDING field names
(``pypdfbox.multipdf.pdf_merger_utility`` legacy mode).

The sibling ``test_merge_oracle.py`` pins the headline collision case (two
sources each declaring ``sharedField`` → one kept verbatim, one renamed to
``dummyFieldName<N>``). This module drills into the *exact rename rule* PDFBox's
legacy merge uses, which is subtler than "rename any duplicate":

PDFBox checks each cloned source field against the destination form's *current*
field set as it appends them — the lookup is live, not snapshotted up front. So
a freshly appended source field becomes visible to the next source field's
collision check within the same merge. Consequently:

* a source field colliding with the destination → renamed (``dummyFieldName<N>``);
* two same-named fields arriving together from ONE source → the first lands
  verbatim, the second now sees it in the destination and is also renamed
  (PDFBox dedups them against each other through the live lookup);
* the rename counter is monotonic and advances across all sources.

Each case merges the controlled source set through Java PDFBox
(``MergeFormFieldsProbe``) and through pypdfbox and asserts the merged
fully-qualified field-name multiset agrees exactly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")
_TX = COSName.get_pdf_name("Tx")
_FIELDS = COSName.get_pdf_name("Fields")


# ----------------------------------------------------------------- builders


def _make_field(name: str) -> COSDictionary:
    field = COSDictionary()
    field.set_item(_FT, _TX)
    field.set_string(_T, name)
    return field


def _form_pdf(out: Path, field_names: list[str]) -> None:
    """A one-page PDF whose AcroForm declares a top-level text field per name in
    ``field_names`` (duplicate names allowed — they are written verbatim)."""
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.LETTER))
    form = PDAcroForm(doc)
    fields = COSArray()
    for name in field_names:
        fields.add(_make_field(name))
    form.get_cos_object().set_item(_FIELDS, fields)
    doc.get_document_catalog().set_acro_form(form)
    doc.save(str(out))
    doc.close()


# ------------------------------------------------------------- fact readers


def _qpdf_check(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _parse_probe(text: str) -> list[str]:
    fields: list[str] = []
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "field":
            fields.append(rest)
    fields.sort()
    return fields


def _merge_py(sources: list[Path], dest: Path) -> None:
    merger = PDFMergerUtility()
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _read_py_fields(path: Path) -> list[str]:
    doc = PDDocument.load(path)
    try:
        fields: list[str] = []
        form = doc.get_document_catalog().get_acro_form()
        if form is not None:
            for field in form.get_field_tree():
                fqn = field.get_fully_qualified_name()
                fields.append("<null>" if fqn is None else fqn)
        fields.sort()
        return fields
    finally:
        doc.close()


def _run_case(tmp_path: Path, sources: list[Path]) -> tuple[list[str], list[str]]:
    java_out = tmp_path / "java.pdf"
    java_fields = _parse_probe(
        run_probe_text(
            "MergeFormFieldsProbe", str(java_out), *[str(s) for s in sources]
        )
    )
    py_out = tmp_path / "py.pdf"
    _merge_py(sources, py_out)
    py_fields = _read_py_fields(py_out)

    py_rc, py_log = _qpdf_check(py_out)
    assert py_rc <= 3, f"pypdfbox merge failed qpdf --check (rc={py_rc}):\n{py_log}"
    return py_fields, java_fields


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
def test_collision_with_destination_renames_matches_pdfbox(tmp_path: Path) -> None:
    """Field colliding with the destination form is renamed; the verbatim one
    survives. Mirrors the canonical legacy-merge rename."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    a = src / "a.pdf"
    b = src / "b.pdf"
    _form_pdf(a, ["sharedField"])
    _form_pdf(b, ["sharedField"])

    py_fields, java_fields = _run_case(tmp_path, [a, b])

    assert py_fields == java_fields, (
        f"collision rename divergence:\n  pypdfbox: {py_fields}\n  PDFBox:   {java_fields}"
    )
    assert "sharedField" in py_fields
    assert len(py_fields) == 2
    renamed = [f for f in py_fields if f != "sharedField"]
    assert len(renamed) == 1
    assert renamed[0].startswith("dummyFieldName")


@requires_oracle
@_requires_qpdf
def test_intra_source_duplicate_dedup_matches_pdfbox(tmp_path: Path) -> None:
    """Two same-named fields arriving together from ONE source: the first lands
    verbatim, the second sees it via the live destination lookup and is renamed
    to ``dummyFieldName<N>``. pypdfbox queries ``get_field`` against the dest
    form's running ``/Fields`` array exactly as PDFBox does, so the second
    duplicate is renamed identically. (Regression pin for the live-lookup
    semantics — a snapshot-up-front implementation would keep both verbatim and
    diverge here.)
    """
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    # dest seed: one distinct field so the merged /Fields array is non-empty
    # before the colliding source is appended.
    a = src / "a.pdf"
    b = src / "b.pdf"
    _form_pdf(a, ["destField"])
    _form_pdf(b, ["dup", "dup"])  # two same-named fields in one source

    py_fields, java_fields = _run_case(tmp_path, [a, b])

    assert py_fields == java_fields, (
        f"intra-source duplicate divergence:\n"
        f"  pypdfbox: {py_fields}\n  PDFBox:   {java_fields}"
    )


@requires_oracle
@_requires_qpdf
def test_multi_source_collision_counter_monotonic_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """Three sources all declaring ``sharedField``: the first lands verbatim, the
    next two each collide with the destination and get a fresh
    ``dummyFieldName<N>``. The rename counter must advance monotonically."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(3):
        p = src / f"s{i}.pdf"
        _form_pdf(p, ["sharedField"])
        paths.append(p)

    py_fields, java_fields = _run_case(tmp_path, paths)

    assert py_fields == java_fields, (
        f"multi-source collision divergence:\n"
        f"  pypdfbox: {py_fields}\n  PDFBox:   {java_fields}"
    )
    assert "sharedField" in py_fields
    assert len(py_fields) == 3
    renamed = sorted(f for f in py_fields if f != "sharedField")
    assert len(renamed) == 2
    assert all(r.startswith("dummyFieldName") for r in renamed)
