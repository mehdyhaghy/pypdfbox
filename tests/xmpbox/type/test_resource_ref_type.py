from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import ArrayProperty, ResourceRefType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    r = ResourceRefType(metadata)
    assert r.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/ResourceRef#"
    assert r.get_prefix() == "stRef"


def test_namespace_registered_at_construction(metadata: XMPMetadata) -> None:
    r = ResourceRefType(metadata)
    ns_map = r.get_all_namespaces_with_prefix()
    assert ns_map.get("http://ns.adobe.com/xap/1.0/sType/ResourceRef#") == "stRef"


def test_set_and_get_string_fields(metadata: XMPMetadata) -> None:
    r = ResourceRefType(metadata)
    r.set_document_id("uuid:doc-123")
    r.set_instance_id("uuid:inst-456")
    r.set_file_path("/tmp/file.pdf")
    r.set_manage_to("http://manager.example.com/to")
    r.set_manage_ui("http://manager.example.com/ui")
    r.set_manager("ContentManager")
    r.set_manager_variant("Variant1")
    r.set_part_mapping("part-mapping")
    r.set_rendition_params("rendition-params")
    r.set_version_id("v1")
    r.set_mask_markers("none")
    r.set_rendition_class("default")
    r.set_from_part("/from")
    r.set_to_part("/to")
    assert r.get_document_id() == "uuid:doc-123"
    assert r.get_instance_id() == "uuid:inst-456"
    assert r.get_file_path() == "/tmp/file.pdf"
    assert r.get_manage_to() == "http://manager.example.com/to"
    assert r.get_manage_ui() == "http://manager.example.com/ui"
    assert r.get_manager() == "ContentManager"
    assert r.get_manager_variant() == "Variant1"
    assert r.get_part_mapping() == "part-mapping"
    assert r.get_rendition_params() == "rendition-params"
    assert r.get_version_id() == "v1"
    assert r.get_mask_markers() == "none"
    assert r.get_rendition_class() == "default"
    assert r.get_from_part() == "/from"
    assert r.get_to_part() == "/to"


def test_last_modify_date(metadata: XMPMetadata) -> None:
    r = ResourceRefType(metadata)
    when = datetime(2024, 5, 1, 12, 0, 0, tzinfo=UTC)
    r.set_last_modify_date(when)
    assert r.get_last_modify_date() == when


def test_alternate_paths(metadata: XMPMetadata) -> None:
    r = ResourceRefType(metadata)
    assert r.get_alternate_paths() is None
    r.add_alternate_path("/a/b")
    r.add_alternate_path("/c/d")
    paths = r.get_alternate_paths()
    assert paths == ["/a/b", "/c/d"]
    seq = r.get_alternate_paths_property()
    assert isinstance(seq, ArrayProperty)


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    r = ResourceRefType(metadata)
    assert r.get_document_id() is None
    assert r.get_instance_id() is None
    assert r.get_file_path() is None
    assert r.get_last_modify_date() is None
