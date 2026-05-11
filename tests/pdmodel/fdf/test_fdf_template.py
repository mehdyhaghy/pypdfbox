from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary
from pypdfbox.pdmodel.fdf import FDFField, FDFTemplate
from pypdfbox.pdmodel.fdf.fdf_field import FDFNamedPageReference


def test_default_constructor_empty() -> None:
    template = FDFTemplate()
    assert isinstance(template.get_cos_object(), COSDictionary)


def test_template_reference_when_absent() -> None:
    template = FDFTemplate()
    assert template.get_template_reference() is None


def test_template_reference_roundtrip() -> None:
    template = FDFTemplate()
    ref = FDFNamedPageReference()
    template.set_template_reference(ref)
    out = template.get_template_reference()
    assert out is not None
    assert out.get_cos_object() is ref.get_cos_object()


def test_template_reference_none_clears() -> None:
    template = FDFTemplate()
    template.set_template_reference(FDFNamedPageReference())
    template.set_template_reference(None)
    assert template.get_template_reference() is None


def test_fields_when_absent() -> None:
    template = FDFTemplate()
    assert template.get_fields() is None


def test_fields_roundtrip() -> None:
    template = FDFTemplate()
    field1 = FDFField()
    field1.set_partial_field_name("a")
    field2 = FDFField()
    field2.set_partial_field_name("b")
    template.set_fields([field1, field2])
    out = template.get_fields()
    assert out is not None
    assert len(out) == 2
    assert out[0].get_partial_field_name() == "a"
    assert out[1].get_partial_field_name() == "b"


def test_should_rename_default_false() -> None:
    template = FDFTemplate()
    assert template.should_rename() is False


def test_should_rename_set_true() -> None:
    template = FDFTemplate()
    template.set_rename(True)
    assert template.should_rename() is True


def test_should_rename_with_existing_boolean() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("Rename", COSBoolean.get_boolean(True))
    template = FDFTemplate(dictionary)
    assert template.should_rename() is True
