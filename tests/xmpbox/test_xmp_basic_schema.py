from __future__ import annotations

from pypdfbox.xmpbox import XMPBasicSchema, XMPMetadata


def _basic() -> XMPBasicSchema:
    return XMPBasicSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix() -> None:
    b = _basic()
    assert b.get_namespace() == "http://ns.adobe.com/xap/1.0/"
    assert b.get_prefix() == "xmp"


def test_creator_tool() -> None:
    b = _basic()
    b.set_creator_tool("pypdfbox 0.0.1")
    assert b.get_creator_tool() == "pypdfbox 0.0.1"


def test_dates_are_iso_strings_in_cluster_one() -> None:
    b = _basic()
    b.set_create_date("2026-04-25T12:00:00Z")
    b.set_modify_date("2026-04-26T08:30:00Z")
    b.set_metadata_date("2026-04-26T08:30:00Z")
    assert b.get_create_date() == "2026-04-25T12:00:00Z"
    assert b.get_modify_date() == "2026-04-26T08:30:00Z"
    assert b.get_metadata_date() == "2026-04-26T08:30:00Z"


def test_label_nickname_baseurl() -> None:
    b = _basic()
    b.set_label("draft")
    b.set_nickname("doc1")
    b.set_base_url("https://example.com/")
    assert b.get_label() == "draft"
    assert b.get_nickname() == "doc1"
    assert b.get_base_url() == "https://example.com/"


def test_identifier_bag() -> None:
    b = _basic()
    b.add_identifier("id-a")
    b.add_identifier("id-b")
    assert b.get_identifiers() == ["id-a", "id-b"]
