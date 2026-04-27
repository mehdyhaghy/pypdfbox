"""
Tests for the value-type-description alias module.

The alias module re-exports :class:`PDFATypeType` under the schema-level
naming :class:`PDFAValueTypeDescriptionType`. There is no independent class
here — these tests just pin the alias semantics so callers can rely on
``isinstance`` identity across both names.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import PDFATypeType, PDFAValueTypeDescriptionType
from pypdfbox.xmpbox.type.pdfa_value_type_description_type import (
    PDFAValueTypeDescriptionType as DirectAlias,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_alias_is_pdfa_type_type() -> None:
    assert PDFAValueTypeDescriptionType is PDFATypeType


def test_direct_alias_is_pdfa_type_type() -> None:
    assert DirectAlias is PDFATypeType


def test_alias_instance_is_pdfa_type_type(metadata: XMPMetadata) -> None:
    inst = PDFAValueTypeDescriptionType(metadata)
    assert isinstance(inst, PDFATypeType)


def test_alias_instance_namespace(metadata: XMPMetadata) -> None:
    inst = PDFAValueTypeDescriptionType(metadata)
    assert inst.get_namespace() == "http://www.aiim.org/pdfa/ns/type#"
    assert inst.get_prefix() == "pdfaType"
