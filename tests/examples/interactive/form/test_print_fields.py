"""Tests for :class:`PrintFields`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.print_fields import PrintFields
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import PDNonTerminalField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_print_fields_lists_sample_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    with PDDocument.load(str(src)) as doc:
        PrintFields().print_fields(doc)
    out = capsys.readouterr().out
    assert "SampleField" in out
    assert "1 top-level fields" in out
    assert "type=PDTextField" in out


def test_print_fields_handles_doc_without_acroform(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        PrintFields().print_fields(doc)
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "0 top-level fields" in out


def test_print_fields_handles_empty_acroform(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.get_document_catalog().set_acro_form(PDAcroForm(doc))
        PrintFields().print_fields(doc)
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "0 top-level fields were found on the form" in out


# ---------------------------------------------------------------------------
# process_field — terminal vs non-terminal walking
# ---------------------------------------------------------------------------


def _build_acroform_with_nested_fields(doc: PDDocument) -> PDAcroForm:
    """Create an AcroForm whose root field is a non-terminal containing
    a single terminal text-field child. Exercises the recursive walk."""
    acro = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(acro)

    # Build the COS skeleton manually so we can set /Kids without relying
    # on PDNonTerminalField.set_children (which adopts parent linkage).
    ft_name = COSName.get_pdf_name("FT")
    t_name = COSName.get_pdf_name("T")
    parent_dict = COSDictionary()
    parent_dict.set_string(t_name, "Group")
    child_dict = COSDictionary()
    child_dict.set_item(ft_name, COSName.get_pdf_name("Tx"))
    child_dict.set_string(t_name, "Inner")
    child_dict.set_string(COSName.get_pdf_name("V"), "child-value")
    kids = COSArray()
    kids.add(child_dict)
    parent_dict.set_item(COSName.get_pdf_name("Kids"), kids)

    parent = PDNonTerminalField(acro, parent_dict)
    acro.set_fields([parent])
    return acro


def _build_two_level_nonterminal_tree(doc: PDDocument) -> None:
    """Create non-terminal A containing non-terminal B containing a
    terminal text field. Exercises the ``parent != partial_name``
    branch on line 49 of print_fields."""
    acro = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(acro)
    ft = COSName.get_pdf_name("FT")
    t = COSName.get_pdf_name("T")
    kids = COSName.get_pdf_name("Kids")

    leaf = COSDictionary()
    leaf.set_item(ft, COSName.get_pdf_name("Tx"))
    leaf.set_string(t, "Leaf")
    leaf.set_string(COSName.get_pdf_name("V"), "leaf-value")

    inner = COSDictionary()
    inner.set_string(t, "Inner")
    inner_kids = COSArray()
    inner_kids.add(leaf)
    inner.set_item(kids, inner_kids)

    outer = COSDictionary()
    outer.set_string(t, "Outer")
    outer_kids = COSArray()
    outer_kids.add(inner)
    outer.set_item(kids, outer_kids)

    root = PDNonTerminalField(acro, outer)
    acro.set_fields([root])


def test_process_field_appends_to_parent_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        _build_two_level_nonterminal_tree(doc)
        PrintFields().print_fields(doc)
    finally:
        doc.close()
    out = capsys.readouterr().out
    # Parent path gets extended into "Outer.Inner" once the recursion
    # descends into the inner non-terminal node.
    assert "Outer.Inner" in out
    assert "Leaf" in out


def test_process_field_walks_non_terminal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        _build_acroform_with_nested_fields(doc)
        PrintFields().print_fields(doc)
    finally:
        doc.close()
    out = capsys.readouterr().out
    # Parent line, then indented child line with type tag.
    assert "Group" in out
    assert "Inner" in out
    assert "type=PDTextField" in out


def test_process_field_handles_value_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When ``get_value_as_string`` raises, ``process_field`` swallows
    it and emits an empty value (covers the ``except`` branch)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        field = PDTextField(acro)
        field.set_partial_name("BadField")
        acro.set_fields([field])

        # Monkeypatch the bound method to raise; PrintFields must
        # catch and continue.
        def _raise() -> str:
            raise RuntimeError("boom")

        field.get_value_as_string = _raise  # type: ignore[method-assign]
        PrintFields().print_fields(doc)
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "BadField" in out
    assert "type=PDTextField" in out


def test_process_field_handles_none_partial_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When a terminal field has no /T entry ``get_partial_name``
    returns ``None`` — the formatter must omit the trailing
    ``.<partial>`` segment."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        # Build a field without /T using the raw COS dictionary.
        f_dict = COSDictionary()
        f_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
        field = PDTextField(acro, f_dict, None)
        acro.set_fields([field])
        PrintFields().print_fields(doc)
    finally:
        doc.close()
    out = capsys.readouterr().out
    # The leaf line should not end with ".None"; partial omitted.
    assert "type=PDTextField" in out


# ---------------------------------------------------------------------------
# main / usage
# ---------------------------------------------------------------------------


def test_main_with_zero_args_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PrintFields.main([])
    err = capsys.readouterr().err
    assert "usage:" in err
    assert "PrintFields" in err


def test_main_with_two_args_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PrintFields.main(["a.pdf", "b.pdf"])
    assert "usage:" in capsys.readouterr().err


def test_main_with_none_argv_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PrintFields.main(None)
    assert "usage:" in capsys.readouterr().err


def test_main_runs_with_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    PrintFields.main([str(src)])
    out = capsys.readouterr().out
    assert "SampleField" in out


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    PrintFields.usage()
    out = capsys.readouterr()
    assert "usage:" in out.err
    assert "PrintFields" in out.err
    assert out.out == ""


def test_print_fields_constructor() -> None:
    assert PrintFields() is not None


def test_module_main_guard_resolves() -> None:
    mod = sys.modules["pypdfbox.examples.interactive.form.print_fields"]
    assert mod.PrintFields is PrintFields
