"""Hand-written tests for :class:`CFAPatternType`.

Mirrors the upstream Java definition at
``xmpbox/src/main/java/org/apache/xmpbox/type/CFAPatternType.java`` (PDFBox
3.0). The upstream type carries three fields:

* ``Columns`` — Integer, simple.
* ``Rows`` — Integer, simple.
* ``Values`` — Seq<Integer> (cardinality ``Seq``).

PDFBox 3.0 does **not** ship a dedicated ``CFAPatternTypeTest`` Java file —
the type surface is exercised indirectly through ``DomXmpParserTest``.
These tests cover the read/write contract for the typed accessors so the
class is callable without a parsed XMP packet.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import ArrayProperty, CFAPatternType, IntegerType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    cfa = CFAPatternType(metadata)
    assert cfa.get_namespace() == "http://ns.adobe.com/exif/1.0/"
    assert cfa.get_prefered_prefix() == "exif"


def test_field_types_match_upstream_property_annotations() -> None:
    """Mirror of upstream ``@PropertyType`` annotations on CFAPatternType."""
    assert CFAPatternType._FIELD_TYPES["Columns"] == "Integer"
    assert CFAPatternType._FIELD_TYPES["Rows"] == "Integer"
    assert CFAPatternType._FIELD_TYPES["Values"] == "Integer"


def test_initial_fields_empty(metadata: XMPMetadata) -> None:
    cfa = CFAPatternType(metadata)
    assert cfa.get_columns() is None
    assert cfa.get_rows() is None
    assert cfa.get_values() is None
    assert cfa.get_values_property() is None


def test_set_and_get_columns(metadata: XMPMetadata) -> None:
    cfa = CFAPatternType(metadata)
    cfa.set_columns(2)
    assert cfa.get_columns() == 2
    prop = cfa.get_columns_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 2


def test_set_and_get_rows(metadata: XMPMetadata) -> None:
    cfa = CFAPatternType(metadata)
    cfa.set_rows(3)
    assert cfa.get_rows() == 3
    prop = cfa.get_rows_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 3


def test_add_value_builds_seq_array(metadata: XMPMetadata) -> None:
    cfa = CFAPatternType(metadata)
    cfa.add_value(0)
    cfa.add_value(1)
    cfa.add_value(2)
    cfa.add_value(1)

    seq = cfa.get_values_property()
    assert isinstance(seq, ArrayProperty)
    children = seq.get_all_properties()
    assert len(children) == 4
    assert all(isinstance(c, IntegerType) for c in children)
    assert cfa.get_values() == [0, 1, 2, 1]


def test_full_cfa_pattern_round_trip(metadata: XMPMetadata) -> None:
    """End-to-end build & read mirroring a 2x2 colour-filter array."""
    cfa = CFAPatternType(metadata)
    cfa.set_columns(2)
    cfa.set_rows(2)
    for v in (0, 1, 1, 2):
        cfa.add_value(v)

    assert cfa.get_columns() == 2
    assert cfa.get_rows() == 2
    assert cfa.get_values() == [0, 1, 1, 2]
