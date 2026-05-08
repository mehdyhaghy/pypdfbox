from __future__ import annotations

import pytest

from pypdfbox.xmpbox import GPSCoordinateType, TypeMapping, XMPMetadata


@pytest.fixture
def mapping() -> TypeMapping:
    return TypeMapping(XMPMetadata.create_xmp_metadata())


def test_wave298_type_mapping_knows_gps_coordinate(mapping: TypeMapping) -> None:
    assert mapping.is_simple_type_known("GPSCoordinate") is True

    prop = mapping.instanciate_simple_property(
        "http://ns.adobe.com/exif/1.0/",
        "exif",
        "GPSLatitude",
        "48,51,30N",
        "GPSCoordinate",
    )

    assert isinstance(prop, GPSCoordinateType)
    assert prop.get_string_value() == "48,51,30N"
    assert prop.parse() == (48, 51.0, 30.0, "N")


def test_wave298_type_mapping_creates_gps_coordinate(
    mapping: TypeMapping,
) -> None:
    prop = mapping.create_gps_coordinate(
        "http://ns.adobe.com/exif/1.0/",
        "exif",
        "GPSLongitude",
        "2,17.5E",
    )

    assert isinstance(prop, GPSCoordinateType)
    assert prop.get_namespace() == "http://ns.adobe.com/exif/1.0/"
    assert prop.get_prefix() == "exif"
    assert prop.get_property_name() == "GPSLongitude"
    assert prop.parse() == (2, 17.5, 0.0, "E")
