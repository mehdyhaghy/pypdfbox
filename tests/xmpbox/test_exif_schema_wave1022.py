from __future__ import annotations

from tests.xmpbox import test_exif_schema_wave390 as wave390


def test_wave390_non_string_simple_property_get_value_returns_stored_value() -> None:
    schema = wave390._exif()  # noqa: SLF001
    prop = wave390._NonStringSimpleProperty(  # noqa: SLF001
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        "tmp",
        123,
    )

    assert prop.get_value() == 123
