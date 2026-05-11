"""Smoke test for :class:`DetermineTextFitsField`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.determine_text_fits_field import (
    DetermineTextFitsField,
)


def test_check_field_returns_widths(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    width, will_fit, will_not_fit = DetermineTextFitsField.check_field(
        str(src), "SampleField",
    )
    assert width > 0
    # NaN guards: the lite port may surface NaN when font widths cannot
    # be measured; the helper must still return three floats.
    assert isinstance(will_fit, float)
    assert isinstance(will_not_fit, float)
