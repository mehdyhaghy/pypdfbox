"""Upstream port of ``PDFieldTest.java``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDFieldTest.java``
(PDFBox 3.0.x). Translated method-by-method per the project's "Test Porting
Conventions". JUnit 5 idioms collapsed to pytest. Java
``IllegalArgumentException`` maps to Python ``ValueError`` (see
``PDField.set_partial_name`` for the divergence note).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


@pytest.fixture
def env() -> tuple[PDDocument, PDAcroForm, PDTextField]:
    """Mirrors upstream ``@BeforeEach setUp``."""
    document = PDDocument()
    acro_form = PDAcroForm(document)
    text_field = PDTextField(acro_form)
    yield document, acro_form, text_field
    document.close()


# ---------- /T partial name ----------


def test_partial_name(env) -> None:
    _, _, text_field = env
    assert text_field.get_partial_name() is None

    text_field.set_partial_name("testField")
    assert text_field.get_partial_name() == "testField"

    text_field.set_partial_name("anotherField")
    assert text_field.get_partial_name() == "anotherField"


def test_set_partial_name_null(env) -> None:
    """Upstream tags this @Test commented out; we honour the asserted
    behaviour: setting a null partial name does not throw."""
    _, _, text_field = env
    text_field.set_partial_name(None)
    assert text_field.get_partial_name() is None


def test_partial_name_with_period_throws(env) -> None:
    _, _, text_field = env
    with pytest.raises(ValueError, match="period character"):
        text_field.set_partial_name("test.field")


# ---------- fully-qualified name ----------


def test_fully_qualified_name(env) -> None:
    _, _, text_field = env
    text_field.set_partial_name("childField")
    assert text_field.get_fully_qualified_name() == "childField"


def test_fully_qualified_name_null_partial_name(env) -> None:
    _, _, text_field = env
    # pypdfbox returns "" rather than None for a missing /T (see PDField);
    # this differs intentionally from upstream's null.
    fqn = text_field.get_fully_qualified_name()
    assert fqn in ("", None)


def test_fully_qualified_name_with_parent(env) -> None:
    _, acro_form, _ = env
    parent_field = PDNonTerminalField(acro_form)
    parent_field.set_partial_name("parentField")

    child_field = PDTextField(acro_form, COSDictionary(), parent_field)
    child_field.set_partial_name("childField")

    assert child_field.get_fully_qualified_name() == "parentField.childField"


# ---------- /TU alternate field name ----------


def test_alternate_field_name(env) -> None:
    _, _, text_field = env
    assert text_field.get_alternate_field_name() is None

    text_field.set_alternate_field_name("Alternate Name For Field")
    assert text_field.get_alternate_field_name() == "Alternate Name For Field"

    text_field.set_alternate_field_name("New Alternate Name")
    assert text_field.get_alternate_field_name() == "New Alternate Name"


# ---------- /TM mapping name ----------


def test_mapping_name(env) -> None:
    _, _, text_field = env
    assert text_field.get_mapping_name() is None

    text_field.set_mapping_name("mappingName")
    assert text_field.get_mapping_name() == "mappingName"

    text_field.set_mapping_name("newMappingName")
    assert text_field.get_mapping_name() == "newMappingName"


# ---------- /Ff bit accessors ----------


def test_read_only_flag(env) -> None:
    _, _, text_field = env
    assert text_field.is_read_only() is False

    text_field.set_read_only(True)
    assert text_field.is_read_only() is True

    text_field.set_read_only(False)
    assert text_field.is_read_only() is False


def test_required_flag(env) -> None:
    _, _, text_field = env
    assert text_field.is_required() is False

    text_field.set_required(True)
    assert text_field.is_required() is True

    text_field.set_required(False)
    assert text_field.is_required() is False


def test_no_export_flag(env) -> None:
    _, _, text_field = env
    assert text_field.is_no_export() is False

    text_field.set_no_export(True)
    assert text_field.is_no_export() is True

    text_field.set_no_export(False)
    assert text_field.is_no_export() is False


def test_multiple_flags_independently(env) -> None:
    _, _, text_field = env
    text_field.set_read_only(True)
    text_field.set_required(True)
    text_field.set_no_export(False)

    assert text_field.is_read_only() is True
    assert text_field.is_required() is True
    assert text_field.is_no_export() is False

    text_field.set_read_only(False)
    assert text_field.is_read_only() is False
    assert text_field.is_required() is True
    assert text_field.is_no_export() is False


def test_set_field_flags_zero_and_clearing(env) -> None:
    _, _, text_field = env
    text_field.set_read_only(True)
    text_field.set_required(True)
    text_field.set_no_export(True)

    assert text_field.is_read_only() is True
    assert text_field.is_required() is True
    assert text_field.is_no_export() is True

    text_field.set_field_flags(0)

    assert text_field.is_read_only() is False
    assert text_field.is_required() is False
    assert text_field.is_no_export() is False
    assert text_field.get_field_flags() == 0


# ---------- field type / value / widgets ----------


def test_get_field_type(env) -> None:
    _, _, text_field = env
    field_type = text_field.get_field_type()
    assert field_type is not None
    assert field_type == "Tx"


def test_set_value_and_get_value_as_string(env) -> None:
    _, _, text_field = env
    # Mirrors upstream: getValueAsString returns "" when no value is set.
    assert text_field.get_value_as_string() == ""


def test_get_widgets(env) -> None:
    _, _, text_field = env
    widgets = text_field.get_widgets()
    assert widgets is not None
    assert len(widgets) >= 0


# ---------- /AA additional actions ----------


def test_get_actions_non_null(env) -> None:
    _, _, text_field = env
    assert text_field.get_actions() is None

    aa_dict = COSDictionary()
    text_field.get_cos_object().set_item(COSName.get_pdf_name("AA"), aa_dict)

    assert text_field.get_actions() is not None


def test_get_actions(env) -> None:
    _, _, text_field = env
    assert text_field.get_actions() is None


# ---------- toString ----------


def test_to_string_with_value(env) -> None:
    _, _, text_field = env
    text_field.set_partial_name("fieldWithValue")

    s = str(text_field)
    assert s is not None
    assert "PDTextField" in s
    assert "fieldWithValue" in s


def test_to_string(env) -> None:
    _, _, text_field = env
    text_field.set_partial_name("myField")

    s = str(text_field)
    assert s is not None
    assert "myField" in s
    assert "PDTextField" in s


# ---------- AcroForm / parent / cos object ----------


def test_get_acro_form(env) -> None:
    _, acro_form, text_field = env
    assert text_field.get_acro_form() is not None
    assert text_field.get_acro_form() is acro_form


def test_get_parent(env) -> None:
    _, acro_form, text_field = env
    assert text_field.get_parent() is None

    parent = PDNonTerminalField(acro_form)
    child_field = PDTextField(acro_form, COSDictionary(), parent)
    assert child_field.get_parent() is parent


def test_get_cos_object(env) -> None:
    _, _, text_field = env
    assert text_field.get_cos_object() is not None
    assert isinstance(text_field.get_cos_object(), COSDictionary)


# ---------- equality / hash ----------


def test_equals(env) -> None:
    _, acro_form, _ = env
    field1 = PDTextField(acro_form)
    field2 = PDTextField(acro_form)

    field1.set_partial_name("testField")
    field3 = PDTextField(acro_form, field1.get_cos_object(), None)
    assert field1 == field3

    field2.set_partial_name("differentField")
    assert field1 != field2

    assert field1 == field1  # noqa: PLR0124 — upstream asserts identity equality

    assert field1 != None  # noqa: E711 — explicit None comparison
    assert field1 != "not a field"


def test_hash_code(env) -> None:
    _, acro_form, _ = env
    field1 = PDTextField(acro_form)
    field2 = PDTextField(acro_form, field1.get_cos_object(), None)

    assert hash(field1) == hash(field2)

    h1 = hash(field1)
    h2 = hash(field1)
    assert h1 == h2


# ---------- composite ----------


def test_multiple_properties_together(env) -> None:
    _, _, text_field = env
    text_field.set_partial_name("complexField")
    text_field.set_alternate_field_name("Complex Field")
    text_field.set_mapping_name("complex_field")
    text_field.set_read_only(True)
    text_field.set_required(True)

    assert text_field.get_partial_name() == "complexField"
    assert text_field.get_alternate_field_name() == "Complex Field"
    assert text_field.get_mapping_name() == "complex_field"
    assert text_field.is_read_only() is True
    assert text_field.is_required() is True
