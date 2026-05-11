"""Smoke test for :class:`FieldRemover`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.field_remover import FieldRemover
from pypdfbox.pdmodel.pd_document import PDDocument


def test_field_remover_removes_field(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "removed.pdf"
    removed = FieldRemover().remove(str(src), str(dst), "SampleField")
    assert removed is True
    assert dst.exists()
    with PDDocument.load(str(dst)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form is None or acro_form.get_field("SampleField") is None


def test_field_remover_unknown_field_returns_false(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "removed.pdf"
    assert FieldRemover().remove(str(src), str(dst), "MissingField") is False
