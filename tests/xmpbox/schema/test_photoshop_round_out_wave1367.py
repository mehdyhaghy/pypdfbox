"""Branch-coverage round-out (wave 1367) for ``PhotoshopSchema``.

Pins Integer (ColorMode / Urgency) typed/string interop, TextLayers Seq
cardinality + clear / remove paths, the DocumentAncestors Bag
ArrayProperty synthesis path, and removal-clears-from-/Description for
typed properties.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.photoshop_schema import PhotoshopSchema
from pypdfbox.xmpbox.type import (
    ArrayProperty,
    Cardinality,
    IntegerType,
    LayerType,
    ProperNameType,
    TextType,
    URIType,
)
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> PhotoshopSchema:
    return PhotoshopSchema(XMPMetadata.create_xmp_metadata())


def test_color_mode_typed_round_trip(schema: PhotoshopSchema) -> None:
    schema.set_color_mode_property(
        IntegerType(
            schema.get_metadata(),
            schema.get_namespace(),
            schema.get_prefix(),
            PhotoshopSchema.COLOR_MODE,
            3,
        )
    )
    assert schema.get_color_mode() == 3
    typed = schema.get_color_mode_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 3


def test_color_mode_string_form_parses(schema: PhotoshopSchema) -> None:
    schema.set_color_mode("4")
    assert schema.get_color_mode() == 4


def test_color_mode_rejects_bool(schema: PhotoshopSchema) -> None:
    with pytest.raises(TypeError):
        schema.set_color_mode(True)


def test_urgency_string_form(schema: PhotoshopSchema) -> None:
    schema.set_urgency(5)
    assert schema.get_urgency() == 5
    schema.set_urgency(None)
    assert schema.get_urgency() is None


def test_text_layers_seq_round_trip(schema: PhotoshopSchema) -> None:
    layer = LayerType(schema.get_metadata())
    layer.set_layer_name("Background")
    layer.set_layer_text("Sample text")
    schema.add_text_layer(layer)
    layers = schema.get_text_layers()
    assert layers is not None and len(layers) == 1
    assert layers[0].get_layer_name() == "Background"


def test_text_layers_add_text_layers_helper(schema: PhotoshopSchema) -> None:
    schema.add_text_layers("Header", "Top")
    schema.add_text_layers("Footer", "Bottom")
    layers = schema.get_text_layers()
    assert layers is not None and len(layers) == 2
    assert [layer.get_layer_name() for layer in layers] == ["Header", "Footer"]


def test_remove_text_layer_by_name(schema: PhotoshopSchema) -> None:
    schema.add_text_layers("A", "first")
    schema.add_text_layers("B", "second")
    schema.remove_text_layer("A")
    layers = schema.get_text_layers()
    assert layers is not None and len(layers) == 1
    assert layers[0].get_layer_name() == "B"


def test_clear_text_layers_keeps_container(schema: PhotoshopSchema) -> None:
    schema.add_text_layers("A", "first")
    schema.add_text_layers("B", "second")
    schema.clear_text_layers()
    # Container itself remains but is empty.
    layers = schema.get_text_layers()
    assert layers == []
    array = schema.get_text_layers_property()
    assert isinstance(array, ArrayProperty)
    assert array.get_array_type() == Cardinality.Seq


def test_set_text_layers_none_clears(schema: PhotoshopSchema) -> None:
    schema.add_text_layers("A", "first")
    schema.set_text_layers(None)
    assert schema.get_text_layers() is None
    assert schema.get_text_layers_property() is None


def test_document_ancestors_bag_round_trip(schema: PhotoshopSchema) -> None:
    schema.add_document_ancestors("docA")
    schema.add_document_ancestors("docB")
    schema.add_document_ancestors("docC")
    assert schema.get_document_ancestors() == ["docA", "docB", "docC"]
    schema.remove_document_ancestor("docB")
    assert schema.get_document_ancestors() == ["docA", "docC"]


def test_document_ancestors_property_synthesis(schema: PhotoshopSchema) -> None:
    schema.add_document_ancestors("docA")
    schema.add_document_ancestors("docB")
    bag = schema.get_document_ancestors_property()
    assert isinstance(bag, ArrayProperty)
    children = bag.get_all_properties()
    assert all(isinstance(c, TextType) for c in children)
    assert len(children) == 2


def test_set_document_ancestors_replaces(schema: PhotoshopSchema) -> None:
    schema.add_document_ancestors("old")
    schema.set_document_ancestors(["new1", "new2"])
    assert schema.get_document_ancestors() == ["new1", "new2"]
    schema.set_document_ancestors(None)
    assert schema.get_document_ancestors() is None


def test_caption_writer_typed_via_proper_name(schema: PhotoshopSchema) -> None:
    name = ProperNameType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PhotoshopSchema.CAPTION_WRITER,
        "Jane Doe",
    )
    schema.set_caption_writer_property(name)
    assert schema.get_caption_writer() == "Jane Doe"
    typed = schema.get_caption_writer_property()
    assert isinstance(typed, ProperNameType)


def test_ancestor_id_typed_via_uri(schema: PhotoshopSchema) -> None:
    uri = URIType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        PhotoshopSchema.ANCESTORID,
        "urn:uuid:ancestor",
    )
    schema.set_ancestor_id_property(uri)
    assert schema.get_ancestor_id() == "urn:uuid:ancestor"
    typed = schema.get_ancestor_id_property()
    assert isinstance(typed, URIType)


def test_set_credit_none_clears(schema: PhotoshopSchema) -> None:
    schema.set_credit("Photographer")
    schema.set_credit(None)
    assert schema.get_credit() is None
    assert schema.get_credit_property() is None
