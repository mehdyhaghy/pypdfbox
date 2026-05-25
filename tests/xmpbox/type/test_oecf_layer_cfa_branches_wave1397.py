"""Wave 1397 branch-coverage tests for the OECF / Layer / CFAPattern
structured-type accessor loops.

Closes False-branch arrows where the typed accessor walks an
:class:`ArrayProperty` and filters out items of the wrong shape:

* ``OECFType.get_names`` 96->93 — ``get_string_value`` returns non-str
* ``OECFType.get_values`` 129->126 — ``get_value`` returns ``None``
* ``LayerType.set_layer_name_property(None)`` 68->70 — property absent
* ``LayerType.set_layer_text_property(None)`` 92->94 — property absent
* ``CFAPatternType.get_values`` 87->86 — non-IntegerType child
* ``CFAPatternType.get_values`` 89->86 — IntegerType child with None value
"""

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
from pypdfbox.xmpbox.type.cfa_pattern_type import CFAPatternType
from pypdfbox.xmpbox.type.layer_type import LayerType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_oecf_get_names_skips_textproperty_with_corrupt_string_value(
    metadata: XMPMetadata,
) -> None:
    """Closes OECFType.get_names 96->93: a TextType whose backing
    ``_text_value`` is not a string is skipped."""
    oecf = OECFType(metadata)
    seq = ArrayProperty(
        metadata, None, "exif", OECFType.NAMES, Cardinality.Seq,
    )
    # First child is well-formed; second has a non-string backing value
    # (only reachable via direct attribute injection — set_value enforces str).
    good = TextType(metadata, None, "rdf", "li", "alpha")
    bad = TextType(metadata, None, "rdf", "li", "placeholder")
    bad._text_value = 42  # noqa: SLF001 — intentional corruption to hit the guard
    seq.add_property(good)
    seq.add_property(bad)
    oecf.add_property(seq)
    assert oecf.get_names() == ["alpha"]


def test_oecf_get_values_skips_real_child_with_none_value(
    metadata: XMPMetadata,
) -> None:
    """Closes OECFType.get_values 129->126: a RealType whose value is
    ``None`` is skipped."""
    oecf = OECFType(metadata)
    seq = ArrayProperty(
        metadata, None, "exif", OECFType.VALUES, Cardinality.Seq,
    )
    good = RealType(metadata, None, "rdf", "li", 1.5)
    none_val = RealType(metadata, None, "rdf", "li", 2.5)
    none_val._real_value = None  # noqa: SLF001 — bypass set_value to hit guard
    seq.add_property(good)
    seq.add_property(none_val)
    oecf.add_property(seq)
    assert oecf.get_values() == [1.5]


def test_layer_set_layer_name_property_none_when_absent_is_noop(
    metadata: XMPMetadata,
) -> None:
    """Closes LayerType.set_layer_name_property 68->70: clearing when
    no LayerName is present is a quiet no-op."""
    layer = LayerType(metadata)
    # Pre-state: no LayerName property installed.
    assert layer.get_layer_name_property() is None
    layer.set_layer_name_property(None)
    # Post-state: still nothing — and no exception raised.
    assert layer.get_layer_name_property() is None


def test_layer_set_layer_text_property_none_when_absent_is_noop(
    metadata: XMPMetadata,
) -> None:
    """Closes LayerType.set_layer_text_property 92->94: clearing when
    no LayerText is present is a quiet no-op."""
    layer = LayerType(metadata)
    assert layer.get_layer_text_property() is None
    layer.set_layer_text_property(None)
    assert layer.get_layer_text_property() is None


def test_cfa_pattern_get_values_skips_non_integertype_child(
    metadata: XMPMetadata,
) -> None:
    """Closes CFAPatternType.get_values 87->86: a non-IntegerType
    child in the Values Seq is filtered out."""
    cfa = CFAPatternType(metadata)
    seq = ArrayProperty(
        metadata, None, "exif", CFAPatternType.VALUES, Cardinality.Seq,
    )
    int_child = IntegerType(metadata, None, "rdf", "li", 1)
    text_child = TextType(metadata, None, "rdf", "li", "not-an-int")
    seq.add_property(int_child)
    seq.add_property(text_child)
    cfa.add_property(seq)
    assert cfa.get_values() == [1]


def test_cfa_pattern_get_values_skips_integer_with_none_value(
    metadata: XMPMetadata,
) -> None:
    """Closes CFAPatternType.get_values 89->86: an IntegerType whose
    backing value is ``None`` is skipped."""
    cfa = CFAPatternType(metadata)
    seq = ArrayProperty(
        metadata, None, "exif", CFAPatternType.VALUES, Cardinality.Seq,
    )
    good = IntegerType(metadata, None, "rdf", "li", 2)
    none_val = IntegerType(metadata, None, "rdf", "li", 3)
    none_val._integer_value = None  # noqa: SLF001 — bypass set_value to hit guard
    seq.add_property(good)
    seq.add_property(none_val)
    cfa.add_property(seq)
    assert cfa.get_values() == [2]
