"""Smoke + coverage tests for :class:`SetField`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.set_field import SetField
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.pd_document import PDDocument

# ---------------------------------------------------------------------------
# Existing smoke-level coverage
# ---------------------------------------------------------------------------


def test_set_field_updates_value(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    with PDDocument.load(str(src)) as doc:
        SetField().set_field(doc, "SampleField", "new value")


def test_calculate_output_filename() -> None:
    assert SetField.calculate_output_filename("foo.pdf") == "foo_filled.pdf"
    assert SetField.calculate_output_filename("foo.PDF") == "foo_filled.pdf"
    assert SetField.calculate_output_filename("foo") == "foo_filled.pdf"


# ---------------------------------------------------------------------------
# Branch coverage
# ---------------------------------------------------------------------------


def test_set_field_warns_when_acro_form_missing(capsys: pytest.CaptureFixture[str]) -> None:
    """No /AcroForm in catalog -> emit usage warning to stderr, return early."""
    with PDDocument() as doc:
        SetField().set_field(doc, "Anything", "irrelevant")
    captured = capsys.readouterr()
    assert "No field found with name:Anything" in captured.err


def test_set_field_warns_when_field_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AcroForm present, but the named field isn't -> stderr warning."""
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    with PDDocument.load(str(src)) as doc:
        SetField().set_field(doc, "DoesNotExist", "x")
    captured = capsys.readouterr()
    assert "No field found with name:DoesNotExist" in captured.err


def test_set_field_check_box_check_path() -> None:
    """Hand-roll a checkbox field so the PDCheckBox / non-empty branch runs."""
    with PDDocument() as doc:
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        cb = PDCheckBox(acro)
        cb.set_partial_name("Agree")
        acro.set_fields([*acro.get_fields(), cb])
        SetField().set_field(doc, "Agree", "Yes")


def test_set_field_check_box_uncheck_path() -> None:
    """Empty value on a checkbox triggers the un_check branch."""
    with PDDocument() as doc:
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        cb = PDCheckBox(acro)
        cb.set_partial_name("Agree")
        acro.set_fields([*acro.get_fields(), cb])
        SetField().set_field(doc, "Agree", "")


# ---------------------------------------------------------------------------
# main() / set_field_args() / usage()
# ---------------------------------------------------------------------------


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    SetField.usage()
    captured = capsys.readouterr()
    assert "SetField" in captured.err


def test_main_wrong_arg_count_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    SetField.main([])
    err = capsys.readouterr().err
    assert "SetField" in err


def test_main_wrong_arg_count_with_none(capsys: pytest.CaptureFixture[str]) -> None:
    """``main(None)`` -> empty argv -> usage."""
    SetField.main(None)
    err = capsys.readouterr().err
    assert "SetField" in err


def test_set_field_args_three_args_writes_filled_pdf(tmp_path: Path) -> None:
    """3-arg path: loads, sets, saves to ``*_filled.pdf``."""
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    SetField.main([str(src), "SampleField", "from-cli"])
    out = tmp_path / "form_filled.pdf"
    assert out.exists()
    assert out.stat().st_size > 0


def test_set_field_args_wrong_count_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    SetField().set_field_args(["only", "two"])
    err = capsys.readouterr().err
    assert "SetField" in err
