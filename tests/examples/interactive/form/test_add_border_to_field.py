"""Smoke test for the :class:`AddBorderToField` example port."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.add_border_to_field import AddBorderToField
from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


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


def test_constructor_is_callable() -> None:
    """Cover the no-op ``__init__`` (line 31)."""
    instance = AddBorderToField()
    assert isinstance(instance, AddBorderToField)


def test_main_with_two_args_runs(tmp_path: Path) -> None:
    """Cover ``main`` (lines 39-46) when both src and dst args are provided."""
    src = tmp_path / "form-main.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "border-main.pdf"
    AddBorderToField.main([str(src), str(dst)])
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_main_with_one_arg_uses_default_dst(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the branch where ``argv`` has only the source (line 45 falls
    through to ``RESULT_FILENAME``). We patch the class constant so the
    write lands in ``tmp_path`` instead of ``target/``."""
    src = tmp_path / "form-one.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "border-default.pdf"
    monkeypatch.setattr(AddBorderToField, "RESULT_FILENAME", str(dst))
    AddBorderToField.main([str(src)])
    assert dst.exists()


def test_main_with_no_args_uses_both_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the no-args path: both src and dst come from class constants
    (line 44 — ``argv[0] if argv`` is False)."""
    src = tmp_path / "default-form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "default-border.pdf"
    monkeypatch.setattr(CreateSimpleForm, "DEFAULT_FILENAME", str(src))
    monkeypatch.setattr(AddBorderToField, "RESULT_FILENAME", str(dst))
    AddBorderToField.main(None)
    assert dst.exists()


def test_add_border_raises_when_no_acroform(tmp_path: Path) -> None:
    """Cover the ``acro_form is None`` guard (line 55)."""
    src = tmp_path / "no-form.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(src))
    finally:
        doc.close()
    dst = tmp_path / "no-form-out.pdf"
    with pytest.raises(OSError, match="no AcroForm"):
        AddBorderToField.add_border(str(src), str(dst), "SampleField")


def test_add_border_raises_when_field_missing(tmp_path: Path) -> None:
    """Cover the ``field is None`` guard (line 58)."""
    src = tmp_path / "form-missing.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "out-missing.pdf"
    with pytest.raises(OSError, match="not found"):
        AddBorderToField.add_border(str(src), str(dst), "NotARealField")
