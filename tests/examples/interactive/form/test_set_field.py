"""Smoke test for :class:`SetField`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.set_field import SetField
from pypdfbox.pdmodel.pd_document import PDDocument


def test_set_field_updates_value(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    with PDDocument.load(str(src)) as doc:
        SetField().set_field(doc, "SampleField", "new value")


def test_calculate_output_filename() -> None:
    assert SetField.calculate_output_filename("foo.pdf") == "foo_filled.pdf"
    assert SetField.calculate_output_filename("foo.PDF") == "foo_filled.pdf"
    assert SetField.calculate_output_filename("foo") == "foo_filled.pdf"
