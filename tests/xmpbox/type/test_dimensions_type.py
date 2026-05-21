from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import DimensionsType, RealType, TextType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    assert dim.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/Dimensions#"
    assert dim.get_prefix() == "stDim"
    assert dim.get_prefered_prefix() == "stDim"


def test_initial_fields_empty(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    assert dim.get_w() is None
    assert dim.get_h() is None
    assert dim.get_unit() is None


def test_set_and_get_dimensions(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.set_w(800.0)
    dim.set_h(600.0)
    dim.set_unit("pixel")
    assert dim.get_w() == pytest.approx(800.0)
    assert dim.get_h() == pytest.approx(600.0)
    assert dim.get_unit() == "pixel"


def test_repr(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.set_w(10.0)
    dim.set_h(20.0)
    dim.set_unit("inch")
    assert repr(dim) == "DimensionsType{10.0 x 20.0 inch}"


def test_str_mirrors_upstream_to_string(metadata: XMPMetadata) -> None:
    """str(dim) mirrors upstream DimensionsType.toString() output."""
    dim = DimensionsType(metadata)
    dim.set_w(10.0)
    dim.set_h(20.0)
    dim.set_unit("inch")
    assert str(dim) == "DimensionsType{10.0 x 20.0 inch}"


def test_typed_property_accessors_return_carrier(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.set_w(800.0)
    dim.set_h(600.0)
    dim.set_unit("pixel")

    w_prop = dim.get_w_property()
    h_prop = dim.get_h_property()
    unit_prop = dim.get_unit_property()

    assert isinstance(w_prop, RealType)
    assert isinstance(h_prop, RealType)
    assert isinstance(unit_prop, TextType)
    assert w_prop.get_value() == pytest.approx(800.0)
    assert h_prop.get_value() == pytest.approx(600.0)
    assert unit_prop.get_string_value() == "pixel"


def test_typed_property_accessors_return_none_when_unset(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    assert dim.get_w_property() is None
    assert dim.get_h_property() is None
    assert dim.get_unit_property() is None
