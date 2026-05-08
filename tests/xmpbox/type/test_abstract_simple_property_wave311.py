from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave311_simple_property_pdfbox_camelcase_aliases(
    metadata: XMPMetadata,
) -> None:
    field = TextType(metadata, "ns", "pre", "name", "initial")

    assert field.getNamespace() == "ns"
    assert field.getPrefix() == "pre"
    assert field.getValue() == "initial"
    assert field.getStringValue() == "initial"
    assert field.getRawValue() == "initial"


def test_wave311_simple_property_set_value_alias_validates_and_updates_value(
    metadata: XMPMetadata,
) -> None:
    field = TextType(metadata, "ns", "pre", "name", "initial")

    field.setValue("updated")

    assert field.getValue() == "updated"
    assert field.getStringValue() == "updated"

    with pytest.raises(ValueError):
        field.setValue(12)
