from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import DateType, ProperNameType, ResourceEventType, TextType, VersionType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    assert version.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/Version#"
    assert version.get_prefix() == "stVer"
    assert version.get_preferred_prefix() == "stVer"


def test_namespace_registered_at_construction(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    ns_map = version.get_all_namespaces_with_prefix()
    assert ns_map.get("http://ns.adobe.com/xap/1.0/sType/Version#") == "stVer"


def test_field_constants() -> None:
    assert VersionType.COMMENTS == "comments"
    assert VersionType.EVENT == "event"
    assert VersionType.MODIFIER == "modifier"
    assert VersionType.MODIFY_DATE == "modifyDate"
    assert VersionType.VERSION == "version"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    assert version.get_comments() is None
    assert version.get_event() is None
    assert version.get_modifier() is None
    assert version.get_modify_date() is None
    assert version.get_version() is None


def test_set_and_get_simple_fields(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    when = datetime(2025, 7, 8, 9, 10, 11, tzinfo=UTC)

    version.set_comments("preflight pass")
    version.set_modifier("Ada")
    version.set_modify_date(when)
    version.set_version("v2")

    assert version.get_comments() == "preflight pass"
    assert version.get_modifier() == "Ada"
    assert version.get_modify_date() == when
    assert version.get_version() == "v2"


def test_simple_fields_use_registered_types(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    version.set_comments("reviewed")
    version.set_modifier("Ada")
    version.set_modify_date(datetime(2025, 7, 8, tzinfo=UTC))
    version.set_version("v3")

    assert isinstance(version.get_property(VersionType.COMMENTS), TextType)
    assert isinstance(version.get_property(VersionType.MODIFIER), ProperNameType)
    assert isinstance(version.get_property(VersionType.MODIFY_DATE), DateType)
    assert isinstance(version.get_property(VersionType.VERSION), TextType)


def test_set_event_stores_nested_resource_event(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    event = ResourceEventType(metadata)
    event.set_action("saved")

    version.set_event(event)

    assert version.get_event() is event
    assert event.get_property_name() == VersionType.EVENT
    assert event.get_action() == "saved"


def test_get_event_property_returns_carrier(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    assert version.get_event_property() is None

    event = ResourceEventType(metadata)
    event.set_action("saved")
    version.set_event(event)

    assert version.get_event_property() is event


def test_get_modify_date_property_returns_carrier(metadata: XMPMetadata) -> None:
    version = VersionType(metadata)
    assert version.get_modify_date_property() is None

    when = datetime(2025, 7, 8, 9, 10, 11, tzinfo=UTC)
    version.set_modify_date(when)

    carrier = version.get_modify_date_property()
    assert isinstance(carrier, DateType)
    assert carrier.get_value() == when
