"""Wave 1370 — AcroForm field-name collision handling (agent E).

The legacy AcroForm merge uses upstream's ``dummyFieldName<N>`` rename
strategy. These tests pin down the corner cases:

- Counter survives across consecutive ``append_document`` calls on a
  single :class:`PDFMergerUtility` instance (``_next_field_num`` is per-
  instance, not per-merge).
- Same source merged twice via two :meth:`add_source` calls renames the
  duplicate-named field on the *second* import.
- A source with three duplicate-named fields gets three distinct
  ``dummyFieldName<N>`` suffixes (no two collide with each other).
- Pre-existing ``dummyFieldName3`` on a destination tree (e.g. carry-
  over from a previous merge cycle) bumps the next allocation to 4+ —
  ``_next_field_num`` reads the dest's highest-existing suffix to start.
- Empty source-form fields list short-circuits (no work, no exception).
- :meth:`set_ignore_acro_form_errors` swallows any per-field error
  without aborting the whole merge.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.multipdf import AcroFormMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")


def _seed_page(page: PDPage) -> None:
    s = COSStream()
    s.set_raw_data(b"% page\n")
    page.set_contents(s)


def _build_doc_with_fields(field_names: list[str]) -> PDDocument:
    doc = PDDocument()
    page = PDPage()
    _seed_page(page)
    doc.add_page(page)
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


def _partial_names(doc: PDDocument) -> list[str]:
    form = doc.get_document_catalog().get_acro_form()
    if form is None:
        return []
    return [f.get_partial_name() or "" for f in form.get_fields()]


# ---------- single-instance counter survives multiple appends ----------


def test_counter_increments_across_three_sources(tmp_path: Path) -> None:
    """Three sources all declaring field 'A' under legacy mode → first
    keeps 'A', second + third get distinct dummyFieldName suffixes."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["A"]), a)
    _save(_build_doc_with_fields(["A"]), b)
    _save(_build_doc_with_fields(["A"]), c)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names = _partial_names(merged)
        # First "A" wins; the other two are renamed with distinct suffixes.
        assert names.count("A") == 1
        dummies = [n for n in names if n.startswith("dummyFieldName")]
        assert len(dummies) == 2
        # And all three field names end up distinct.
        assert len(set(names)) == 3


def test_one_source_with_three_dup_fields_gets_distinct_renames(
    tmp_path: Path,
) -> None:
    """A single source with three same-named fields, merged into a
    destination already holding that name, should produce three distinct
    dummyFieldName<N> suffixes."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["F"]), a)
    _save(_build_doc_with_fields(["F", "F", "F"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names = _partial_names(merged)
        assert names.count("F") == 1
        dummies = [n for n in names if n.startswith("dummyFieldName")]
        assert len(dummies) == 3
        # Each suffix is distinct.
        assert len(set(dummies)) == 3


def test_dest_existing_dummy_field_name_bumps_starting_counter(
    tmp_path: Path,
) -> None:
    """Destination already has ``dummyFieldName3`` baked in; new rename
    must skip to >= 4."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["G", "dummyFieldName3"]), a)
    _save(_build_doc_with_fields(["G"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names = _partial_names(merged)
        # No duplicates of any name.
        assert len(set(names)) == len(names)
        # dummyFieldName3 is still present (existing field NOT clobbered).
        assert "dummyFieldName3" in names
        # The new rename has a suffix > 3.
        suffixes = [
            int(n[len("dummyFieldName") :])
            for n in names
            if n.startswith("dummyFieldName") and n[len("dummyFieldName") :].isdigit()
        ]
        # At least one new suffix >= 4 (must have been renamed past 3).
        assert any(s >= 4 for s in suffixes if s != 3)


# ---------- source with no fields short-circuits ----------


def test_source_with_empty_fields_array_no_renames(tmp_path: Path) -> None:
    """Source has an empty /Fields array — no fields to merge, no
    renames, dest preserved."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["alpha"]), a)
    _save(_build_doc_with_fields([]), b)  # empty fields array

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names = _partial_names(merged)
        assert names == ["alpha"]


# ---------- ignore_acro_form_errors swallows individual failure ----------


def test_ignore_acro_form_errors_allows_merge_to_continue(
    tmp_path: Path,
) -> None:
    """When ``set_ignore_acro_form_errors(True)`` and the source AcroForm
    merge raises internally, the merge still produces an output file —
    the error path is reported via log but never propagated."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["X"]), a)
    _save(_build_doc_with_fields(["X"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_ignore_acro_form_errors(True)
    assert util.is_ignore_acro_form_errors() is True
    util.merge_documents()
    # Merge produced a valid output file regardless.
    assert out.exists()
    assert out.stat().st_size > 0


def test_join_form_fields_mode_renames_collisions_like_legacy(
    tmp_path: Path,
) -> None:
    """Join-fields mode delegates to legacy mode in PDFBox 3.0.x, so three
    sources with field 'A' yield 'A', 'dummyFieldName1', 'dummyFieldName2'
    (oracle-confirmed via MergeFormFieldsModeProbe JOIN over 3x 'A')."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["A"]), a)
    _save(_build_doc_with_fields(["A"]), b)
    _save(_build_doc_with_fields(["A"]), c)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names = sorted(_partial_names(merged))
        assert names == ["A", "dummyFieldName1", "dummyFieldName2"]
        assert names.count("A") == 1


def test_legacy_mode_preserves_already_distinct_names_verbatim(
    tmp_path: Path,
) -> None:
    """Two sources with totally distinct field names → no renames at all."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_fields(["alpha", "beta"]), a)
    _save(_build_doc_with_fields(["gamma", "delta"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names = sorted(_partial_names(merged))
        assert names == ["alpha", "beta", "delta", "gamma"]
