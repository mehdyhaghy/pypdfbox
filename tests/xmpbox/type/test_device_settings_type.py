"""Hand-written tests for :class:`DeviceSettingsType`.

Mirrors the upstream Java definition at
``xmpbox/src/main/java/org/apache/xmpbox/type/DeviceSettingsType.java``
(PDFBox 3.0). The upstream type carries three fields:

* ``Columns`` — Integer, simple.
* ``Rows`` — Integer, simple.
* ``Settings`` — Seq<Text> (cardinality ``Seq``).

PDFBox 3.0 ships no dedicated ``DeviceSettingsTypeTest`` Java file — the type
surface is exercised indirectly through ``DomXmpParserTest``. These tests
cover the read/write contract for the typed accessors.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    ArrayProperty,
    DeviceSettingsType,
    IntegerType,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    ds = DeviceSettingsType(metadata)
    assert ds.get_namespace() == "http://ns.adobe.com/exif/1.0/"
    assert ds.get_prefered_prefix() == "exif"


def test_field_types_match_upstream_property_annotations() -> None:
    assert DeviceSettingsType._FIELD_TYPES["Columns"] == "Integer"
    assert DeviceSettingsType._FIELD_TYPES["Rows"] == "Integer"
    assert DeviceSettingsType._FIELD_TYPES["Settings"] == "Text"


def test_initial_fields_empty(metadata: XMPMetadata) -> None:
    ds = DeviceSettingsType(metadata)
    assert ds.get_columns() is None
    assert ds.get_rows() is None
    assert ds.get_settings() is None
    assert ds.get_settings_property() is None


def test_set_and_get_columns(metadata: XMPMetadata) -> None:
    ds = DeviceSettingsType(metadata)
    ds.set_columns(4)
    assert ds.get_columns() == 4
    prop = ds.get_columns_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 4


def test_set_and_get_rows(metadata: XMPMetadata) -> None:
    ds = DeviceSettingsType(metadata)
    ds.set_rows(2)
    assert ds.get_rows() == 2
    prop = ds.get_rows_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 2


def test_add_setting_builds_seq_array(metadata: XMPMetadata) -> None:
    ds = DeviceSettingsType(metadata)
    ds.add_setting("alpha")
    ds.add_setting("beta")

    seq = ds.get_settings_property()
    assert isinstance(seq, ArrayProperty)
    assert len(seq.get_all_properties()) == 2
    assert ds.get_settings() == ["alpha", "beta"]


def test_full_round_trip(metadata: XMPMetadata) -> None:
    ds = DeviceSettingsType(metadata)
    ds.set_columns(3)
    ds.set_rows(1)
    for s in ("one", "two", "three"):
        ds.add_setting(s)

    assert ds.get_columns() == 3
    assert ds.get_rows() == 1
    assert ds.get_settings() == ["one", "two", "three"]
