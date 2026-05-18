"""Smoke test for :class:`FillFormField`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.fill_form_field import FillFormField


def _build_form_with(field_names: list[str], path: Path) -> None:
    """Build a tiny AcroForm carrying the requested field names so the
    fill_form_field example's ``get_field`` lookups land on real fields."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        resources = PDResources()
        resources.put(COSName.get_pdf_name("Helv"), PDType1Font())
        acro_form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro_form)
        acro_form.set_default_resources(resources)
        acro_form.set_default_appearance("/Helv 0 Tf 0 g")
        fields = []
        for name in field_names:
            field = PDTextField(acro_form)
            field.set_partial_name(name)
            field.set_default_appearance("/Helv 12 Tf 0 0 0 rg")
            fields.append(field)
        acro_form.set_fields(fields)
        doc.save(str(path))


def test_fill_uses_existing_form(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "filled.pdf"
    # The upstream sample looks for ``sampleField`` (lowercase ``s``);
    # the example survives the missing field via a None guard.
    FillFormField.fill(str(src), str(dst))
    assert dst.exists()


def test_fill_constructor_is_callable() -> None:
    """Exercise the no-op ``__init__`` body (covers line 29)."""
    instance = FillFormField()
    assert isinstance(instance, FillFormField)


def test_fill_main_with_explicit_argv_drives_fill(tmp_path: Path) -> None:
    """Drive ``main([src, dst])`` so the explicit-argv branch runs."""
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "filled.pdf"
    FillFormField.main([str(src), str(dst)])
    assert dst.exists()


def test_fill_main_with_default_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the empty-argv branch — both DEFAULT_TEMPLATE and
    DEFAULT_OUTPUT are taken; we redirect them to a temp dir so the
    test doesn't depend on the upstream resources path."""
    src = tmp_path / "template.pdf"
    dst = tmp_path / "out.pdf"
    CreateSimpleForm.create(str(src))
    monkeypatch.setattr(FillFormField, "DEFAULT_TEMPLATE", str(src))
    monkeypatch.setattr(FillFormField, "DEFAULT_OUTPUT", str(dst))
    FillFormField.main([])
    assert dst.exists()


def test_fill_main_with_none_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main(None)`` must also fall back to DEFAULT_TEMPLATE / OUTPUT."""
    src = tmp_path / "template.pdf"
    dst = tmp_path / "out.pdf"
    CreateSimpleForm.create(str(src))
    monkeypatch.setattr(FillFormField, "DEFAULT_TEMPLATE", str(src))
    monkeypatch.setattr(FillFormField, "DEFAULT_OUTPUT", str(dst))
    FillFormField.main(None)
    assert dst.exists()


def test_fill_actually_sets_value_when_field_present(tmp_path: Path) -> None:
    """Build a form whose field name matches what FillFormField looks
    for (``sampleField``) so the ``field is not None`` branch executes
    and ``set_value("Text Entry")`` actually fires."""
    src = tmp_path / "form.pdf"
    dst = tmp_path / "filled.pdf"
    _build_form_with(["sampleField"], src)
    FillFormField.fill(str(src), str(dst))
    assert dst.exists()


def test_fill_with_nested_field_name(tmp_path: Path) -> None:
    """Build a non-terminal field ``fieldsContainer`` with a child
    ``nestedSampleField`` so the example's second ``get_field`` lookup
    returns a real field and the nested-branch ``set_value`` runs."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

    src = tmp_path / "form.pdf"
    dst = tmp_path / "filled.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        resources = PDResources()
        resources.put(COSName.get_pdf_name("Helv"), PDType1Font())
        acro_form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro_form)
        acro_form.set_default_resources(resources)
        acro_form.set_default_appearance("/Helv 0 Tf 0 g")

        parent = PDNonTerminalField(acro_form)
        parent.set_partial_name("fieldsContainer")
        child = PDTextField(acro_form)
        child.set_partial_name("nestedSampleField")
        child.set_default_appearance("/Helv 12 Tf 0 0 0 rg")
        parent.set_children([child])
        acro_form.set_fields([parent])
        doc.save(str(src))

    FillFormField.fill(str(src), str(dst))
    assert dst.exists()
