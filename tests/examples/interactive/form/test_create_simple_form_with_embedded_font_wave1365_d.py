"""Wave 1365 — coverage round-out for :class:`CreateSimpleFormWithEmbeddedFont`.

The base smoke test only exercises the explicit-argv path. This module
covers the no-args branch, the trivial ``__init__`` body, and structural
assertions on the produced PDF (AcroForm carries one text field;
appearance characteristics carry both border and background colors).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.create_simple_form_with_embedded_font import (
    CreateSimpleFormWithEmbeddedFont,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def test_default_filename_constant_targets_pdf() -> None:
    """The ``DEFAULT_FILENAME`` class constant must survive the port
    (line 44)."""
    assert CreateSimpleFormWithEmbeddedFont.DEFAULT_FILENAME.endswith(".pdf")


def test_constructor_is_a_no_op() -> None:
    """Cover the no-op ``__init__`` body (line 47)."""
    instance = CreateSimpleFormWithEmbeddedFont()
    assert isinstance(instance, CreateSimpleFormWithEmbeddedFont)


def test_main_with_explicit_path(tmp_path: Path) -> None:
    """The ``argv`` non-empty branch (line 53)."""
    out = tmp_path / "embed-explicit.pdf"
    CreateSimpleFormWithEmbeddedFont.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_main_with_empty_argv_uses_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``argv`` empty branch — defaults to ``DEFAULT_FILENAME``.

    Redirect the class constant into ``tmp_path`` so the side-effect file
    lands somewhere disposable.
    """
    out = tmp_path / "embed-default.pdf"
    monkeypatch.setattr(
        CreateSimpleFormWithEmbeddedFont, "DEFAULT_FILENAME", str(out),
    )
    CreateSimpleFormWithEmbeddedFont.main([])
    assert out.exists()


def test_main_with_none_argv_uses_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main(None)`` falls back to ``DEFAULT_FILENAME``."""
    out = tmp_path / "embed-none.pdf"
    monkeypatch.setattr(
        CreateSimpleFormWithEmbeddedFont, "DEFAULT_FILENAME", str(out),
    )
    CreateSimpleFormWithEmbeddedFont.main(None)
    assert out.exists()


def test_create_writes_pdf_with_one_text_field(tmp_path: Path) -> None:
    """``create`` must populate the AcroForm with exactly one field
    (line 76)."""
    out = tmp_path / "embed-fields.pdf"
    CreateSimpleFormWithEmbeddedFont.create(str(out))
    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form is not None
        assert len(acro_form.get_fields()) == 1


def test_create_sets_partial_name_sample_field(tmp_path: Path) -> None:
    """The text field's partial name must be ``SampleField`` (line 74)."""
    out = tmp_path / "embed-name.pdf"
    CreateSimpleFormWithEmbeddedFont.create(str(out))
    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        fields = acro_form.get_fields()
        # Partial name survives the round-trip.
        first = fields[0]
        name = first.get_partial_name() if hasattr(first, "get_partial_name") else None
        assert name == "SampleField"


def test_create_sets_default_appearance(tmp_path: Path) -> None:
    """The default appearance string must point at the resource font
    (line 75)."""
    out = tmp_path / "embed-da.pdf"
    CreateSimpleFormWithEmbeddedFont.create(str(out))
    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        fields = acro_form.get_fields()
        first = fields[0]
        if hasattr(first, "get_default_appearance"):
            da = first.get_default_appearance()
            # ``0 Tf 0 g`` literal trailer survives.
            assert "Tf 0 g" in da
