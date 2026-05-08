from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata, XMPSchema


def _schema() -> XMPSchema:
    return XMPSchema(
        XMPMetadata.create_xmp_metadata(),
        namespace_uri="http://example.com/ns#",
        prefix="ex",
    )


def test_has_property_is_raw_presence_check_for_falsy_values() -> None:
    schema = _schema()

    assert schema.has_property("Title") is False

    schema.set_text_property_value("Title", "")
    assert schema.has_property("Title") is True

    schema.set_property("Items", [])
    schema.set_property("Labels", {})
    assert schema.has_property("Items") is True
    assert schema.has_property("Labels") is True


def test_clear_property_is_idempotent_and_clears_only_target() -> None:
    schema = _schema()
    schema.set_text_property_value("Title", "hello")
    schema.set_text_property_value("Creator", "alice")

    schema.clear_property("Title")

    assert schema.has_property("Title") is False
    assert schema.get_property("Title") is None
    assert schema.has_property("Creator") is True
    assert schema.get_unqualified_text_property_value("Creator") == "alice"

    schema.clear_property("Title")
    assert schema.has_property("Creator") is True


def test_clear_removes_all_raw_properties() -> None:
    schema = _schema()
    schema.set_text_property_value("Title", "hello")
    schema.add_unqualified_bag_value("subject", "pdf")
    schema.set_unqualified_language_property_value("description", None, "default")

    schema.clear()

    assert schema.get_all_properties() == {}
    assert schema.has_property("Title") is False
    assert schema.get_unqualified_bag_value_list("subject") is None
    assert schema.get_unqualified_language_property_value("description") is None
