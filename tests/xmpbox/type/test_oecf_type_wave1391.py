"""Wave 1391 — coverage round-out for :class:`OECFType`."""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    ArrayProperty,
    Cardinality,
    IntegerType,
    OECFType,
    RealType,
    TextType,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    assert oecf.get_namespace() == "http://ns.adobe.com/exif/1.0/"
    assert oecf.get_prefered_prefix() == "exif"


def test_field_types_match_upstream_property_annotations() -> None:
    assert OECFType._FIELD_TYPES["Columns"] == "Integer"
    assert OECFType._FIELD_TYPES["Rows"] == "Integer"
    assert OECFType._FIELD_TYPES["Names"] == "Text"
    assert OECFType._FIELD_TYPES["Values"] == "Real"


def test_initial_fields_all_empty(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    assert oecf.get_columns() is None
    assert oecf.get_rows() is None
    assert oecf.get_columns_property() is None
    assert oecf.get_rows_property() is None
    assert oecf.get_names() is None
    assert oecf.get_values() is None
    assert oecf.get_names_property() is None
    assert oecf.get_values_property() is None


def test_set_and_get_columns(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.set_columns(2)
    assert oecf.get_columns() == 2
    prop = oecf.get_columns_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 2


def test_set_and_get_rows(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.set_rows(3)
    assert oecf.get_rows() == 3
    prop = oecf.get_rows_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 3


def test_add_name_builds_seq_array(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.add_name("R")
    oecf.add_name("G")
    oecf.add_name("B")
    seq = oecf.get_names_property()
    assert isinstance(seq, ArrayProperty)
    children = seq.get_all_properties()
    assert len(children) == 3
    assert all(isinstance(c, TextType) for c in children)
    assert oecf.get_names() == ["R", "G", "B"]


def test_add_name_reuses_existing_seq(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.add_name("R")
    first_seq = oecf.get_names_property()
    oecf.add_name("G")
    assert oecf.get_names_property() is first_seq


def test_add_value_builds_seq_array(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.add_value(0.1)
    oecf.add_value(0.5)
    oecf.add_value(0.9)
    seq = oecf.get_values_property()
    assert isinstance(seq, ArrayProperty)
    children = seq.get_all_properties()
    assert len(children) == 3
    assert all(isinstance(c, RealType) for c in children)
    assert oecf.get_values() == pytest.approx([0.1, 0.5, 0.9])


def test_add_value_reuses_existing_seq(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.add_value(1.0)
    first_seq = oecf.get_values_property()
    oecf.add_value(2.0)
    assert oecf.get_values_property() is first_seq


def test_full_oecf_round_trip(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    oecf.set_columns(1)
    oecf.set_rows(3)
    for name in ("R", "G", "B"):
        oecf.add_name(name)
    for v in (0.0, 0.5, 1.0):
        oecf.add_value(v)
    assert oecf.get_columns() == 1
    assert oecf.get_rows() == 3
    assert oecf.get_names() == ["R", "G", "B"]
    assert oecf.get_values() == pytest.approx([0.0, 0.5, 1.0])


def test_get_names_skips_non_text_children(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    seq = ArrayProperty(
        metadata, None, oecf.get_prefered_prefix(), OECFType.NAMES, Cardinality.Seq
    )
    seq.add_property(TextType(metadata, None, "rdf", "li", "ok"))
    seq.add_property(IntegerType(metadata, None, "rdf", "li", 7))
    oecf.add_property(seq)
    assert oecf.get_names() == ["ok"]


def test_get_values_skips_non_real_children(metadata: XMPMetadata) -> None:
    oecf = OECFType(metadata)
    seq = ArrayProperty(
        metadata, None, oecf.get_prefered_prefix(), OECFType.VALUES, Cardinality.Seq
    )
    seq.add_property(RealType(metadata, None, "rdf", "li", 1.5))
    seq.add_property(TextType(metadata, None, "rdf", "li", "not-real"))
    oecf.add_property(seq)
    assert oecf.get_values() == pytest.approx([1.5])
