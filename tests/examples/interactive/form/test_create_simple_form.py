"""Smoke test for the :class:`CreateSimpleForm` example port."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.pdmodel.pd_document import PDDocument


def test_create_simple_form_runs(tmp_path: Path) -> None:
    out = tmp_path / "simple.pdf"
    CreateSimpleForm.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_create_simple_form_field_persisted(tmp_path: Path) -> None:
    out = tmp_path / "simple.pdf"
    CreateSimpleForm.create(str(out))
    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form is not None
        field = acro_form.get_field("SampleField")
        assert field is not None
