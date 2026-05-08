from __future__ import annotations

import pytest

from pypdfbox.xmpbox import GPSCoordinateType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_gps_coordinate_parse_accepts_boundary_values(metadata: XMPMetadata) -> None:
    coord = GPSCoordinateType(metadata, None, None, "gps", "0,59,59W")

    assert coord.parse() == (0, 59.0, 59.0, "W")


@pytest.mark.parametrize(
    "value",
    [
        "-1,0,0N",
        "1,60,0N",
        "1,0,60N",
        "1,nan,0N",
        "1,0,infN",
    ],
)
def test_gps_coordinate_parse_rejects_out_of_range_parts(
    metadata: XMPMetadata, value: str
) -> None:
    coord = GPSCoordinateType(metadata, None, None, "gps", value)

    assert coord.parse() is None


@pytest.mark.parametrize(
    ("degrees", "minutes", "seconds"),
    [
        (-1, 0, 0),
        (1, 60, 0),
        (1, 0, 60),
    ],
)
def test_gps_coordinate_format_dms_rejects_out_of_range_parts(
    degrees: int, minutes: int, seconds: int
) -> None:
    with pytest.raises(ValueError):
        GPSCoordinateType.format_dms(degrees, minutes, seconds, "N")


@pytest.mark.parametrize("minutes", [-0.1, 60.0, float("nan"), float("inf")])
def test_gps_coordinate_format_dm_rejects_out_of_range_minutes(
    minutes: float,
) -> None:
    with pytest.raises(ValueError):
        GPSCoordinateType.format_dm(1, minutes, "E")
