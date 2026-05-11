"""Smoke test for the :class:`AddBorderToField` example port."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.add_border_to_field import AddBorderToField
from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm


def test_add_border_runs(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "border.pdf"
    AddBorderToField.add_border(str(src), str(dst), "SampleField")
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_add_border_default_filenames_constant() -> None:
    # The class-level filename constant must survive the port for parity
    # with samples that import it (e.g. dependent examples build on it).
    assert AddBorderToField.RESULT_FILENAME.endswith("AddBorderToField.pdf")
