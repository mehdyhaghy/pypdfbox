"""Smoke test for :class:`FillFormField`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.fill_form_field import FillFormField


def test_fill_uses_existing_form(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "filled.pdf"
    # The upstream sample looks for ``sampleField`` (lowercase ``s``);
    # the example survives the missing field via a None guard.
    FillFormField.fill(str(src), str(dst))
    assert dst.exists()
