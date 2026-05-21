from __future__ import annotations

from pypdfbox.xmpbox import ArrayProperty, Cardinality, TextType, XMPMetadata


def test_wave319_array_property_elements_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    array = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Seq)
    array.add_property(TextType(metadata, "ns", "p", "li", "first"))
    array.add_property(TextType(metadata, "ns", "p", "li", "second"))

    assert array.get_array_type() is Cardinality.Seq
    assert array.get_elements_as_string() == ["first", "second"]
