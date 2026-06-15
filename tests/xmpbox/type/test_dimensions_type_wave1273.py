"""Wave 1273 round-out: ``DimensionsType.to_string()`` explicit method."""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import DimensionsType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_to_string_empty(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    # Unset fields render as the literal ``null`` — upstream
    # ``DimensionsType.toString()`` concatenates the (null) Float/String field
    # references, which Java renders as ``"null"`` (proven against the live
    # xmpbox 3.0.7 jar in wave 1536's oracle test, ``dim_tostring_empty``).
    assert dim.to_string() == "DimensionsType{null x null null}"


def test_to_string_populated(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.set_w(800.0)
    dim.set_h(600.0)
    dim.set_unit("pixel")
    # Mirrors upstream ``DimensionsType.toString()`` —
    # ``DimensionsType{<w> x <h> <unit>}``.
    assert dim.to_string() == "DimensionsType{800.0 x 600.0 pixel}"


def test_to_string_matches_str(metadata: XMPMetadata) -> None:
    dim = DimensionsType(metadata)
    dim.set_w(1.5)
    dim.set_h(2.5)
    dim.set_unit("inch")
    assert dim.to_string() == str(dim)
    assert dim.to_string() == repr(dim)
