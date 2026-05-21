"""Branch-coverage round-out (wave 1367) for ``ExifSchema``.

Pins LangAlt round-trip on the ``UserComment`` field, Seq cardinality
for ``ComponentsConfiguration`` / ``ISOSpeedRatings``, Integer
typed/string interop on enum properties, Rational property parsing,
GPS coordinate round-trip and property removal that clears the slot.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.exif_schema import ExifSchema
from pypdfbox.xmpbox.type import (
    GPSCoordinateType,
    IntegerType,
    LangAlt,
    RationalType,
    TextType,
)
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> ExifSchema:
    return ExifSchema(XMPMetadata.create_xmp_metadata())


def test_user_comment_lang_alt_default_then_per_lang(schema: ExifSchema) -> None:
    schema.set_user_comment("Generic comment")
    schema.add_user_comment("fr", "Commentaire")
    assert schema.get_user_comment() == "Generic comment"
    assert schema.get_user_comment("fr") == "Commentaire"
    langs = schema.get_user_comment_languages()
    assert langs is not None
    assert "x-default" in langs
    assert "fr" in langs


def test_user_comment_typed_lang_alt_builder(schema: ExifSchema) -> None:
    schema.set_user_comment("Hello")
    schema.add_user_comment("es", "Hola")
    la = schema.get_user_comment_property()
    assert isinstance(la, LangAlt)
    children = la.get_all_properties()
    assert len(children) == 2


def test_user_comment_remove_specific_language(schema: ExifSchema) -> None:
    schema.set_user_comment("default")
    schema.add_user_comment("de", "Hallo")
    schema.remove_user_comment("de")
    langs = schema.get_user_comment_languages()
    assert langs is not None
    assert "de" not in langs
    assert "x-default" in langs


def test_user_comment_property_returns_none_when_unset(schema: ExifSchema) -> None:
    assert schema.get_user_comment_property() is None


def test_components_configuration_seq_round_trip(schema: ExifSchema) -> None:
    for value in (1, 2, 3, 0):
        schema.add_components_configuration(value)
    out = schema.get_components_configuration()
    assert out == ["1", "2", "3", "0"]


def test_color_space_integer_typed_round_trip(schema: ExifSchema) -> None:
    integer = IntegerType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.COLOR_SPACE,
        65535,
    )
    schema.set_color_space_property(integer)
    assert schema.get_color_space() == 65535
    typed = schema.get_color_space_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 65535


def test_color_space_string_fallback(schema: ExifSchema) -> None:
    schema.set_color_space("  1 ")
    assert schema.get_color_space() == 1
    # Unparseable string -> integer getter returns None.
    schema.set_property(ExifSchema.COLOR_SPACE, "not-an-int")
    assert schema.get_color_space() is None


def test_color_space_set_none_clears(schema: ExifSchema) -> None:
    schema.set_color_space(1)
    schema.set_color_space(None)
    assert schema.get_color_space() is None
    assert schema.get_color_space_property() is None


def test_color_space_rejects_bool(schema: ExifSchema) -> None:
    with pytest.raises(TypeError):
        schema.set_color_space(True)


def test_exposure_time_rational_round_trip(schema: ExifSchema) -> None:
    rational = RationalType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.EXPOSURE_TIME,
        "1/250",
    )
    schema.set_exposure_time_property(rational)
    assert schema.get_exposure_time() == "1/250"
    typed = schema.get_exposure_time_property()
    assert isinstance(typed, RationalType)


def test_exposure_time_string_set_then_typed_get(schema: ExifSchema) -> None:
    schema.set_exposure_time("1/125")
    typed = schema.get_exposure_time_property()
    assert isinstance(typed, RationalType)
    assert typed.get_string_value() == "1/125"


def test_gps_latitude_typed_round_trip(schema: ExifSchema) -> None:
    coord = GPSCoordinateType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.GPS_LATITUDE,
        "37,46,30N",
    )
    schema.set_gps_latitude_property(coord)
    assert schema.get_gps_latitude() == "37,46,30N"
    typed = schema.get_gps_latitude_property()
    assert isinstance(typed, GPSCoordinateType)


def test_exif_version_typed_via_text(schema: ExifSchema) -> None:
    text = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.EXIF_VERSION,
        "0220",
    )
    schema.set_exif_version_property(text)
    assert schema.get_exif_version() == "0220"
    typed = schema.get_exif_version_property()
    assert isinstance(typed, TextType)


def test_set_exif_version_none_removes(schema: ExifSchema) -> None:
    schema.set_exif_version("0231")
    schema.set_exif_version(None)
    assert schema.get_exif_version() is None
    assert schema.get_exif_version_property() is None


def test_unset_user_comment_returns_none(schema: ExifSchema) -> None:
    assert schema.get_user_comment() is None
    assert schema.get_user_comment_languages() is None
