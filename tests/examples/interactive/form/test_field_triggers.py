"""Smoke test for :class:`FieldTriggers`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.field_triggers import FieldTriggers


def test_attach_triggers_runs(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "triggers.pdf"
    FieldTriggers.attach_triggers(str(src), str(dst), "SampleField")
    assert dst.exists()
    assert dst.stat().st_size > 0
