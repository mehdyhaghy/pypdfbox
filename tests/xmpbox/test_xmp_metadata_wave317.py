from __future__ import annotations

from pypdfbox.xmpbox import DublinCoreSchema, XMPMetadata


def test_wave317_create_and_add_dublin_core_schema_installs_fresh() -> None:
    metadata = XMPMetadata.create_xmp_metadata()

    first = metadata.create_and_add_dublin_core_schema()
    second = metadata.create_and_add_dublin_core_schema()

    assert isinstance(first, DublinCoreSchema)
    assert isinstance(second, DublinCoreSchema)
    assert first is not second
    assert first.get_about() == ""
    assert second.get_about() == ""
    assert metadata.get_all_schemas() == [first, second]
    assert metadata.get_dublin_core_schema() is first


def test_wave317_add_dublin_core_schema_remains_idempotent() -> None:
    metadata = XMPMetadata.create_xmp_metadata()

    first = metadata.add_dublin_core_schema()

    assert metadata.add_dublin_core_schema() is first
    assert metadata.get_all_schemas() == [first]
