"""Smoke test for :class:`CreateMultiWidgetsForm`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_multi_widgets_form import (
    CreateMultiWidgetsForm,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def test_create_multi_widgets_form_runs(tmp_path: Path) -> None:
    out = tmp_path / "multi.pdf"
    CreateMultiWidgetsForm.main([str(out)])
    assert out.exists()
    with PDDocument.load(str(out)) as doc:
        assert doc.get_number_of_pages() == 2
