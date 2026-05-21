from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave311_simple_property_accessors(
    metadata: XMPMetadata,
) -> None:
    field = TextType(metadata, "ns", "pre", "name", "initial")

    assert field.get_namespace() == "ns"
    assert field.get_prefix() == "pre"
    assert field.get_value() == "initial"
    assert field.get_string_value() == "initial"
    assert field.get_raw_value() == "initial"


def test_wave311_simple_property_set_value_validates_and_updates_value(
    metadata: XMPMetadata,
) -> None:
    field = TextType(metadata, "ns", "pre", "name", "initial")

    field.set_value("updated")

    assert field.get_value() == "updated"
    assert field.get_string_value() == "updated"

    with pytest.raises(ValueError):
        field.set_value(12)
