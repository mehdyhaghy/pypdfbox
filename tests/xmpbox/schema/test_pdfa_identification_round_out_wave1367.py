"""Branch-coverage round-out (wave 1367) for ``PDFAIdentificationSchema``.

Pins:

* conformance validation (legacy A/B/U + PDF/A-4 e/f) and
  :class:`BadFieldValueException` rejection of other values
* part/rev numeric and string setter symmetry
* amendment/revision/correction alias parity
* typed-property setter installs the expected wrapper
* property removal via ``set_xxx(None)``
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.pdfa_identification_schema import (
    BadFieldValueException,
    PDFAIdentificationSchema,
)
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> PDFAIdentificationSchema:
    return PDFAIdentificationSchema(XMPMetadata.create_xmp_metadata())


@pytest.mark.parametrize("value", ["A", "B", "U", "e", "f"])
def test_conformance_accepts_legal_values(
    schema: PDFAIdentificationSchema, value: str
) -> None:
    schema.set_conformance(value)
    assert schema.get_conformance() == value


@pytest.mark.parametrize("value", ["X", "Z", "a", "b", "1", ""])
def test_conformance_rejects_illegal_values(
    schema: PDFAIdentificationSchema, value: str
) -> None:
    with pytest.raises(BadFieldValueException):
        schema.set_conformance(value)


def test_set_conformance_none_removes(schema: PDFAIdentificationSchema) -> None:
    schema.set_conformance("A")
    schema.set_conformance(None)
    assert schema.get_conformance() is None


def test_conformance_typed_setter_validates(
    schema: PDFAIdentificationSchema,
) -> None:
    text = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PDFAIdentificationSchema.CONFORMANCE,
        "U",
    )
    schema.set_conformance_property(text)
    assert schema.get_conformance() == "U"
    bad = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PDFAIdentificationSchema.CONFORMANCE,
        "X",
    )
    with pytest.raises(BadFieldValueException):
        schema.set_conformance_property(bad)


def test_part_int_and_string_setters_match(
    schema: PDFAIdentificationSchema,
) -> None:
    schema.set_part(3)
    assert schema.get_part() == 3
    schema.set_part_value_with_string("4")
    assert schema.get_part() == 4
    # Garbage string raises ValueError mirroring upstream.
    with pytest.raises(ValueError):
        schema.set_part_value_with_string("ojoj")


def test_part_typed_property_round_trip(
    schema: PDFAIdentificationSchema,
) -> None:
    integer = IntegerType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PDFAIdentificationSchema.PART,
        2,
    )
    schema.set_part_property(integer)
    assert schema.get_part() == 2
    typed = schema.get_part_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 2


def test_amendment_set_get_via_aliases(
    schema: PDFAIdentificationSchema,
) -> None:
    schema.set_amendment("2007")
    assert schema.get_amendment() == "2007"
    assert schema.get_amd() == "2007"
    # set_amd alias
    schema.set_amd("2008")
    assert schema.get_amendment() == "2008"
    schema.set_amendment(None)
    assert schema.get_amendment() is None


def test_revision_string_and_int_paths(
    schema: PDFAIdentificationSchema,
) -> None:
    schema.set_revision("2020")
    assert schema.get_revision() == "2020"
    assert schema.get_rev() == 2020
    schema.set_rev(2025)
    # set_rev stores an int; get_revision still coerces to string.
    assert schema.get_revision() == "2025"
    assert schema.get_rev() == 2025
    with pytest.raises(ValueError):
        schema.set_rev_value_with_string("blah")


def test_revision_typed_property(schema: PDFAIdentificationSchema) -> None:
    integer = IntegerType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PDFAIdentificationSchema.REV,
        2024,
    )
    schema.set_rev_property(integer)
    typed = schema.get_rev_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 2024


def test_correction_set_and_alias(schema: PDFAIdentificationSchema) -> None:
    schema.set_correction("2021")
    assert schema.get_correction() == "2021"
    assert schema.get_corr() == "2021"
    schema.set_corr("2022")
    assert schema.get_correction() == "2022"
    schema.set_correction(None)
    assert schema.get_correction() is None


def test_set_amd_property_typed(schema: PDFAIdentificationSchema) -> None:
    text = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PDFAIdentificationSchema.AMD,
        "amd-2025",
    )
    schema.set_amd_property(text)
    typed = schema.get_amd_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "amd-2025"
    schema.set_amd_property(None)
    assert schema.get_amd_property() is None


def test_get_part_unparseable_returns_none(
    schema: PDFAIdentificationSchema,
) -> None:
    # Direct-stash a bad string (bypasses set_part's int() validation).
    schema.set_property(PDFAIdentificationSchema.PART, "not-a-number")
    assert schema.get_part() is None
