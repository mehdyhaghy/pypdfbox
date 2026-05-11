"""Smoke test for :class:`PrintFields`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.print_fields import PrintFields
from pypdfbox.pdmodel.pd_document import PDDocument


def test_print_fields_lists_sample_field(tmp_path: Path, capsys) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    with PDDocument.load(str(src)) as doc:
        PrintFields().print_fields(doc)
    out = capsys.readouterr().out
    assert "SampleField" in out
