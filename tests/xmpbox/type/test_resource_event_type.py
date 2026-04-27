from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import ResourceEventType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    e = ResourceEventType(metadata)
    assert e.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"
    assert e.get_prefix() == "stEvt"


def test_namespace_registered_at_construction(metadata: XMPMetadata) -> None:
    e = ResourceEventType(metadata)
    ns_map = e.get_all_namespaces_with_prefix()
    assert ns_map.get("http://ns.adobe.com/xap/1.0/sType/ResourceEvent#") == "stEvt"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    e = ResourceEventType(metadata)
    assert e.get_action() is None
    assert e.get_when() is None
    assert e.get_software_agent() is None
    assert e.get_instance_id() is None
    assert e.get_parameters() is None
    assert e.get_changed() is None


def test_set_and_get_string_fields(metadata: XMPMetadata) -> None:
    e = ResourceEventType(metadata)
    e.set_action("converted")
    e.set_software_agent("ImageMagick 7")
    e.set_instance_id("xmp.iid:abc-123")
    e.set_parameters("from=jpg, to=png")
    e.set_changed("/format")
    assert e.get_action() == "converted"
    assert e.get_software_agent() == "ImageMagick 7"
    assert e.get_instance_id() == "xmp.iid:abc-123"
    assert e.get_parameters() == "from=jpg, to=png"
    assert e.get_changed() == "/format"


def test_when(metadata: XMPMetadata) -> None:
    e = ResourceEventType(metadata)
    when = datetime(2025, 6, 7, 8, 9, 10, tzinfo=UTC)
    e.set_when(when)
    assert e.get_when() == when


def test_field_constants() -> None:
    assert ResourceEventType.ACTION == "action"
    assert ResourceEventType.CHANGED == "changed"
    assert ResourceEventType.INSTANCE_ID == "instanceID"
    assert ResourceEventType.PARAMETERS == "parameters"
    assert ResourceEventType.SOFTWARE_AGENT == "softwareAgent"
    assert ResourceEventType.WHEN == "when"
