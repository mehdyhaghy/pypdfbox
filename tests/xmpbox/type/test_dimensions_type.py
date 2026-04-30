from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import DimensionsType


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


def test_pdfbox_camelcase_aliases(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.setW(800.0)
    dim.setH(600.0)
    dim.setUnit("pixel")

    assert dim.getW() == pytest.approx(800.0)
    assert dim.getH() == pytest.approx(600.0)
    assert dim.getUnit() == "pixel"


def test_repr(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.set_w(10.0)
    dim.set_h(20.0)
    dim.set_unit("inch")
    assert repr(dim) == "DimensionsType{10.0 x 20.0 inch}"
