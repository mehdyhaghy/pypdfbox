from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from pypdfbox.xmpbox import DateType, TextType, XMPBasicSchema, XMPMetadata


def _schema() -> XMPBasicSchema:
    return XMPBasicSchema(XMPMetadata.create_xmp_metadata())


@pytest.mark.parametrize(
    ("setter_name", "property_getter_name", "value_getter_name"),
    [
        ("set_create_date", "get_create_date_property", "get_create_date_value"),
        ("set_modify_date", "get_modify_date_property", "get_modify_date_value"),
        ("set_metadata_date", "get_metadata_date_property", "get_metadata_date_value"),
        ("set_modifier_date", "get_modifier_date_property", "get_modifier_date_value"),
    ],
)
def test_wave421_invalid_string_dates_remain_raw_but_typed_getters_return_none(
    setter_name: str,
    property_getter_name: str,
    value_getter_name: str,
) -> None:
    schema = _schema()

    getattr(schema, setter_name)("not-a-date")

    assert getattr(schema, property_getter_name)() is None
    assert getattr(schema, value_getter_name)() is None


@pytest.mark.parametrize(
    ("setter_name", "getter_name", "property_name"),
    [
        ("set_create_date", "get_create_date_property", XMPBasicSchema.CREATEDATE),
        ("set_modify_date", "get_modify_date_property", XMPBasicSchema.MODIFYDATE),
        ("set_metadata_date", "get_metadata_date_property", XMPBasicSchema.METADATADATE),
        ("set_modifier_date", "get_modifier_date_property", XMPBasicSchema.MODIFIER_DATE),
    ],
)
def test_wave421_python_date_values_are_stored_as_date_type(
    setter_name: str,
    getter_name: str,
    property_name: str,
) -> None:
    schema = _schema()

    getattr(schema, setter_name)(date(2026, 5, 8))

    prop = getattr(schema, getter_name)()
    assert isinstance(prop, DateType)
    assert prop.get_property_name() == property_name
    assert prop.get_value() == datetime(2026, 5, 8, tzinfo=UTC)


@pytest.mark.parametrize(
    ("setter_name", "getter_name", "property_name"),
    [
        ("set_label_property", "get_label", XMPBasicSchema.LABEL),
        ("set_nickname_property", "get_nickname", XMPBasicSchema.NICKNAME),
        ("set_base_url_property", "get_base_url", XMPBasicSchema.BASEURL),
        ("set_creator_tool_property", "get_creator_tool", XMPBasicSchema.CREATORTOOL),
    ],
)
def test_wave421_text_property_setters_are_visible_to_string_getters(
    setter_name: str,
    getter_name: str,
    property_name: str,
) -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    prop = TextType(
        metadata,
        XMPBasicSchema.NAMESPACE,
        XMPBasicSchema.PREFERRED_PREFIX,
        property_name,
        f"value-for-{property_name}",
    )

    getattr(schema, setter_name)(prop)

    assert getattr(schema, getter_name)() == f"value-for-{property_name}"


@pytest.mark.parametrize(
    ("local_name", "property_getter_name"),
    [
        (XMPBasicSchema.LABEL, "get_label_property"),
        (XMPBasicSchema.NICKNAME, "get_nickname_property"),
        (XMPBasicSchema.BASEURL, "get_base_url_property"),
        (XMPBasicSchema.CREATORTOOL, "get_creator_tool_property"),
    ],
)
def test_wave421_text_property_getters_ignore_non_text_storage(
    local_name: str, property_getter_name: str
) -> None:
    schema = _schema()
    schema.set_property(local_name, 42)

    assert getattr(schema, property_getter_name)() is None
