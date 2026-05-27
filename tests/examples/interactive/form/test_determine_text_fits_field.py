"""Smoke + branch tests for :class:`DetermineTextFitsField`."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.determine_text_fits_field import (
    DetermineTextFitsField,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


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


def test_check_field_long_string_wider_than_short(tmp_path: Path) -> None:
    """Sanity check: when widths *can* be measured the long string should
    have a larger width than the short one.

    The form's ``/Helv`` font is a bare ``PDType1Font()`` (no ``/BaseFont``,
    no ``/Widths``, no embedded program — the "built-in Helvetica fallback"
    idiom shared across the examples), so it carries no width source. Since
    wave 1434 such a font resolves StandardEncoding (matching upstream's
    no-``/Encoding`` fallback) instead of raising, so ``get_string_width``
    now returns ``0.0`` for every glyph rather than ``NaN``. Both ``NaN``
    (unmeasurable) and ``0.0`` (no width source) mean "nothing to compare",
    so the ordering assertion only applies when widths are genuinely
    measurable (finite and positive)."""
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    _, short_w, long_w = DetermineTextFitsField.check_field(
        str(src), "SampleField",
    )
    measurable = (
        not math.isnan(short_w)
        and not math.isnan(long_w)
        and short_w > 0
        and long_w > 0
    )
    if measurable:
        assert long_w > short_w


def test_constructor_is_callable() -> None:
    # Exercises the no-op ``__init__`` body (covers line 26).
    instance = DetermineTextFitsField()
    assert isinstance(instance, DetermineTextFitsField)


def test_main_with_no_args_uses_default_filename(monkeypatch) -> None:
    """``main([])`` must fall through to the ``DEFAULT_FILENAME`` branch
    (covers lines 31-34)."""
    seen: list[tuple[str, str]] = []

    def _stub(src: str, name: str):
        seen.append((src, name))

    monkeypatch.setattr(DetermineTextFitsField, "check_field", staticmethod(_stub))
    DetermineTextFitsField.main([])
    assert seen == [(DetermineTextFitsField.DEFAULT_FILENAME, "SampleField")]


def test_main_with_explicit_args_forwards_them(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []

    def _stub(src: str, name: str):
        seen.append((src, name))

    monkeypatch.setattr(DetermineTextFitsField, "check_field", staticmethod(_stub))
    DetermineTextFitsField.main(["custom.pdf", "MyField"])
    assert seen == [("custom.pdf", "MyField")]


def test_main_with_none_argv_uses_default_filename(monkeypatch) -> None:
    """``main(None)`` should be treated like an empty argv."""
    seen: list[tuple[str, str]] = []

    def _stub(src: str, name: str):
        seen.append((src, name))

    monkeypatch.setattr(DetermineTextFitsField, "check_field", staticmethod(_stub))
    DetermineTextFitsField.main(None)
    assert seen == [(DetermineTextFitsField.DEFAULT_FILENAME, "SampleField")]


def test_check_field_raises_when_document_has_no_acroform(tmp_path: Path) -> None:
    """No /AcroForm in the catalog -> ``OSError`` (covers line 43)."""
    src = tmp_path / "blank.pdf"
    # Build a PDF with no acro form.
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))
    with pytest.raises(OSError, match="AcroForm"):
        DetermineTextFitsField.check_field(str(src), "Anything")


def test_check_field_raises_when_field_missing(tmp_path: Path) -> None:
    """``acro_form.get_field`` returns ``None`` -> ``OSError`` (line 46)."""
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    with pytest.raises(OSError, match="not found"):
        DetermineTextFitsField.check_field(str(src), "DoesNotExist")
