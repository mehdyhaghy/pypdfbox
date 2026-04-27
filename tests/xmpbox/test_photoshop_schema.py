from __future__ import annotations

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DateType,
    DomXmpParser,
    IntegerType,
    LayerType,
    PhotoshopSchema,
    ProperNameType,
    TextType,
    URIType,
    XMPMetadata,
)


def _photoshop() -> PhotoshopSchema:
    return PhotoshopSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _photoshop()
    assert PhotoshopSchema.NAMESPACE == "http://ns.adobe.com/photoshop/1.0/"
    assert PhotoshopSchema.PREFERRED_PREFIX == "photoshop"
    assert schema.get_namespace() == "http://ns.adobe.com/photoshop/1.0/"
    assert schema.get_prefix() == "photoshop"


def test_local_name_constants_match_upstream() -> None:
    # Verify each upstream constant is mirrored verbatim.
    assert PhotoshopSchema.ANCESTORID == "AncestorID"
    assert PhotoshopSchema.AUTHORS_POSITION == "AuthorsPosition"
    assert PhotoshopSchema.CAPTION_WRITER == "CaptionWriter"
    assert PhotoshopSchema.CATEGORY == "Category"
    assert PhotoshopSchema.CITY == "City"
    assert PhotoshopSchema.COLOR_MODE == "ColorMode"
    assert PhotoshopSchema.COUNTRY == "Country"
    assert PhotoshopSchema.CREDIT == "Credit"
    assert PhotoshopSchema.DATE_CREATED == "DateCreated"
    assert PhotoshopSchema.DOCUMENT_ANCESTORS == "DocumentAncestors"
    assert PhotoshopSchema.HEADLINE == "Headline"
    assert PhotoshopSchema.HISTORY == "History"
    assert PhotoshopSchema.ICC_PROFILE == "ICCProfile"
    assert PhotoshopSchema.INSTRUCTIONS == "Instructions"
    assert PhotoshopSchema.SOURCE == "Source"
    assert PhotoshopSchema.STATE == "State"
    assert PhotoshopSchema.SUPPLEMENTAL_CATEGORIES == "SupplementalCategories"
    assert PhotoshopSchema.TEXT_LAYERS == "TextLayers"
    assert PhotoshopSchema.TRANSMISSION_REFERENCE == "TransmissionReference"
    assert PhotoshopSchema.URGENCY == "Urgency"


def test_default_accessors_return_none() -> None:
    schema = _photoshop()
    assert schema.get_ancestor_id() is None
    assert schema.get_authors_position() is None
    assert schema.get_caption_writer() is None
    assert schema.get_category() is None
    assert schema.get_city() is None
    assert schema.get_color_mode() is None
    assert schema.get_country() is None
    assert schema.get_credit() is None
    assert schema.get_date_created() is None
    assert schema.get_document_ancestors() is None
    assert schema.get_headline() is None
    assert schema.get_history() is None
    assert schema.get_icc_profile() is None
    assert schema.get_instructions() is None
    assert schema.get_source() is None
    assert schema.get_state() is None
    assert schema.get_supplemental_categories() is None
    assert schema.get_transmission_reference() is None
    assert schema.get_urgency() is None


def test_text_property_round_trip_for_each_simple_text_accessor() -> None:
    schema = _photoshop()
    schema.set_ancestor_id("uuid:1")
    schema.set_authors_position("Photographer")
    schema.set_caption_writer("Alice Editor")
    schema.set_category("News")
    schema.set_city("Paris")
    schema.set_country("France")
    schema.set_credit("Reuters")
    schema.set_date_created("2026-04-27T12:00:00Z")
    schema.set_headline("Breaking story")
    schema.set_history("Crop")
    schema.set_icc_profile("sRGB IEC61966-2.1")
    schema.set_instructions("Embargoed")
    schema.set_source("Wire")
    schema.set_state("Ile-de-France")
    schema.set_supplemental_categories("Politics")
    schema.set_transmission_reference("REF-001")

    assert schema.get_ancestor_id() == "uuid:1"
    assert schema.get_authors_position() == "Photographer"
    assert schema.get_caption_writer() == "Alice Editor"
    assert schema.get_category() == "News"
    assert schema.get_city() == "Paris"
    assert schema.get_country() == "France"
    assert schema.get_credit() == "Reuters"
    assert schema.get_date_created() == "2026-04-27T12:00:00Z"
    assert schema.get_headline() == "Breaking story"
    assert schema.get_history() == "Crop"
    assert schema.get_icc_profile() == "sRGB IEC61966-2.1"
    assert schema.get_instructions() == "Embargoed"
    assert schema.get_source() == "Wire"
    assert schema.get_state() == "Ile-de-France"
    assert schema.get_supplemental_categories() == "Politics"
    assert schema.get_transmission_reference() == "REF-001"

    # set_*(None) clears the property.
    schema.set_ancestor_id(None)
    schema.set_authors_position(None)
    schema.set_caption_writer(None)
    schema.set_category(None)
    schema.set_city(None)
    schema.set_country(None)
    schema.set_credit(None)
    schema.set_date_created(None)
    schema.set_headline(None)
    schema.set_history(None)
    schema.set_icc_profile(None)
    schema.set_instructions(None)
    schema.set_source(None)
    schema.set_state(None)
    schema.set_supplemental_categories(None)
    schema.set_transmission_reference(None)

    assert schema.get_ancestor_id() is None
    assert schema.get_authors_position() is None
    assert schema.get_caption_writer() is None
    assert schema.get_category() is None
    assert schema.get_city() is None
    assert schema.get_country() is None
    assert schema.get_credit() is None
    assert schema.get_date_created() is None
    assert schema.get_headline() is None
    assert schema.get_history() is None
    assert schema.get_icc_profile() is None
    assert schema.get_instructions() is None
    assert schema.get_source() is None
    assert schema.get_state() is None
    assert schema.get_supplemental_categories() is None
    assert schema.get_transmission_reference() is None


def test_color_mode_int_round_trip() -> None:
    schema = _photoshop()
    schema.set_color_mode(3)
    assert schema.get_color_mode() == 3
    # IntegerType serialises as the decimal string in upstream.
    assert schema.get_unqualified_text_property_value(PhotoshopSchema.COLOR_MODE) == "3"
    schema.set_color_mode(None)
    assert schema.get_color_mode() is None


def test_color_mode_accepts_string_form_for_parser_round_trip() -> None:
    schema = _photoshop()
    # Parser stores attribute-form values as raw strings.
    schema.set_text_property_value(PhotoshopSchema.COLOR_MODE, "4")
    assert schema.get_color_mode() == 4
    schema.set_text_property_value(PhotoshopSchema.COLOR_MODE, "junk")
    assert schema.get_color_mode() is None


def test_urgency_int_and_string_setter_overloads() -> None:
    schema = _photoshop()
    schema.set_urgency(1)
    assert schema.get_urgency() == 1
    schema.set_urgency("8")
    assert schema.get_urgency() == 8
    schema.set_urgency(None)
    assert schema.get_urgency() is None


def test_document_ancestors_round_trip() -> None:
    schema = _photoshop()
    schema.add_document_ancestors("uuid:parent-1")
    schema.add_document_ancestors("uuid:parent-2")
    assert schema.get_document_ancestors() == ["uuid:parent-1", "uuid:parent-2"]
    schema.set_document_ancestors(["uuid:fresh"])
    assert schema.get_document_ancestors() == ["uuid:fresh"]
    schema.set_document_ancestors(None)
    assert schema.get_document_ancestors() is None


def test_xmp_metadata_add_photoshop_schema_idempotent() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_photoshop_schema() is None
    schema = metadata.add_photoshop_schema()
    assert isinstance(schema, PhotoshopSchema)
    # Idempotent — repeat add returns the same instance.
    assert metadata.add_photoshop_schema() is schema
    assert metadata.get_photoshop_schema() is schema


def test_create_and_add_photoshop_schema_alias() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_photoshop_schema()
    assert isinstance(schema, PhotoshopSchema)
    # Alias is also idempotent through add_photoshop_schema.
    assert metadata.create_and_add_photoshop_schema() is schema


def test_dom_parser_dispatches_attribute_form_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'"
        b" photoshop:City='Paris'"
        b" photoshop:Country='France'"
        b" photoshop:Urgency='1'"
        b" photoshop:ColorMode='3'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PhotoshopSchema)
    assert isinstance(schema, PhotoshopSchema)
    assert schema.get_city() == "Paris"
    assert schema.get_country() == "France"
    assert schema.get_urgency() == 1
    assert schema.get_color_mode() == 3


def test_dom_parser_dispatches_document_ancestors_bag_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'>"
        b"<photoshop:DocumentAncestors>"
        b"<rdf:Bag>"
        b"<rdf:li>uuid:parent-1</rdf:li>"
        b"<rdf:li>uuid:parent-2</rdf:li>"
        b"</rdf:Bag>"
        b"</photoshop:DocumentAncestors>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PhotoshopSchema)
    assert isinstance(schema, PhotoshopSchema)
    assert schema.get_document_ancestors() == ["uuid:parent-1", "uuid:parent-2"]


def test_dom_parser_get_namespace_table_includes_photoshop() -> None:
    table = DomXmpParser().get_namespace_table()
    assert table.get("photoshop") == "http://ns.adobe.com/photoshop/1.0/"


# --- Wave 32: typed *_property accessors -----------------------------


def _typed_text_field(metadata: XMPMetadata, name: str, value: str) -> TextType:
    return TextType(metadata, PhotoshopSchema.NAMESPACE, "photoshop", name, value)


def test_ancestor_id_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    assert schema.get_ancestor_id_property() is None
    field = URIType(
        metadata, PhotoshopSchema.NAMESPACE, "photoshop", PhotoshopSchema.ANCESTORID, "uuid:1"
    )
    schema.set_ancestor_id_property(field)
    # typed getter returns the same instance.
    assert schema.get_ancestor_id_property() is field
    # string-form getter reflects the typed value.
    assert schema.get_ancestor_id() == "uuid:1"
    schema.set_ancestor_id_property(None)
    assert schema.get_ancestor_id_property() is None
    assert schema.get_ancestor_id() is None


def test_authors_position_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    assert schema.get_authors_position_property() is None
    field = _typed_text_field(metadata, PhotoshopSchema.AUTHORS_POSITION, "Photographer")
    schema.set_authors_position_property(field)
    assert schema.get_authors_position_property() is field
    assert schema.get_authors_position() == "Photographer"


def test_caption_writer_typed_round_trip_returns_proper_name_type() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    field = ProperNameType(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        PhotoshopSchema.CAPTION_WRITER,
        "Alice Editor",
    )
    schema.set_caption_writer_property(field)
    typed = schema.get_caption_writer_property()
    assert typed is field
    assert isinstance(typed, ProperNameType)
    assert typed.get_value() == "Alice Editor"


def test_simple_text_setter_then_typed_getter_wraps_on_the_fly() -> None:
    """String-form setter writes a plain string; typed getter wraps it."""
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())
    schema.set_city("Paris")
    typed = schema.get_city_property()
    assert isinstance(typed, TextType)
    assert typed.get_value() == "Paris"
    assert typed.get_property_name() == PhotoshopSchema.CITY


def test_color_mode_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    assert schema.get_color_mode_property() is None
    field = IntegerType(
        metadata, PhotoshopSchema.NAMESPACE, "photoshop", PhotoshopSchema.COLOR_MODE, 3
    )
    schema.set_color_mode_property(field)
    assert schema.get_color_mode_property() is field
    # string-form integer getter still returns int.
    assert schema.get_color_mode() == 3


def test_color_mode_typed_getter_wraps_string_storage() -> None:
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())
    schema.set_color_mode(4)
    typed = schema.get_color_mode_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 4


def test_date_created_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    assert schema.get_date_created_property() is None
    field = DateType(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        PhotoshopSchema.DATE_CREATED,
        "2026-04-27T12:00:00Z",
    )
    schema.set_date_created_property(field)
    assert schema.get_date_created_property() is field
    # String getter surfaces the original string-form storage.
    assert schema.get_date_created() == field.get_string_value()


def test_urgency_typed_round_trip_int_and_string_construction() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    field_int = IntegerType(
        metadata, PhotoshopSchema.NAMESPACE, "photoshop", PhotoshopSchema.URGENCY, 1
    )
    schema.set_urgency_property(field_int)
    assert schema.get_urgency() == 1
    assert schema.get_urgency_property() is field_int
    # IntegerType also accepts decimal strings.
    field_str = IntegerType(
        metadata, PhotoshopSchema.NAMESPACE, "photoshop", PhotoshopSchema.URGENCY, "8"
    )
    schema.set_urgency_property(field_str)
    assert schema.get_urgency() == 8


def test_typed_property_setter_with_none_clears_property() -> None:
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())
    schema.set_city("Paris")
    schema.set_city_property(None)
    assert schema.get_city() is None
    assert schema.get_city_property() is None


def test_typed_round_trip_for_all_simple_text_accessors() -> None:
    """Sweep every simple-Text typed accessor, mirroring upstream's parameter set."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    # Map upstream local-name -> pypdfbox snake_case accessor stem.
    text_accessors: tuple[tuple[str, str], ...] = (
        (PhotoshopSchema.AUTHORS_POSITION, "authors_position"),
        (PhotoshopSchema.CATEGORY, "category"),
        (PhotoshopSchema.CITY, "city"),
        (PhotoshopSchema.COUNTRY, "country"),
        (PhotoshopSchema.CREDIT, "credit"),
        (PhotoshopSchema.HEADLINE, "headline"),
        (PhotoshopSchema.HISTORY, "history"),
        (PhotoshopSchema.ICC_PROFILE, "icc_profile"),
        (PhotoshopSchema.INSTRUCTIONS, "instructions"),
        (PhotoshopSchema.SOURCE, "source"),
        (PhotoshopSchema.STATE, "state"),
        (PhotoshopSchema.SUPPLEMENTAL_CATEGORIES, "supplemental_categories"),
        (PhotoshopSchema.TRANSMISSION_REFERENCE, "transmission_reference"),
    )
    for name, stem in text_accessors:
        getter = "get_" + stem + "_property"
        setter = "set_" + stem + "_property"
        field = _typed_text_field(metadata, name, f"value-for-{name}")
        getattr(schema, setter)(field)
        assert getattr(schema, getter)() is field


def _make_layer(metadata: XMPMetadata, name: str, text: str) -> LayerType:
    layer = LayerType(metadata)
    layer.set_layer_name(name)
    layer.set_layer_text(text)
    return layer


def test_text_layers_default_returns_none() -> None:
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())
    assert schema.get_text_layers() is None
    assert schema.get_text_layers_property() is None


def test_text_layers_typed_round_trip_set_get() -> None:
    """Round-trip a list of two LayerType instances through set/get_text_layers."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    layers_in = [
        _make_layer(metadata, "Background", "Hello"),
        _make_layer(metadata, "Foreground", "World"),
    ]
    schema.set_text_layers(layers_in)
    layers_out = schema.get_text_layers()
    assert layers_out is not None
    assert len(layers_out) == 2
    # Each layer round-trips its LayerName + LayerText.
    assert layers_out[0].get_layer_name() == "Background"
    assert layers_out[0].get_layer_text() == "Hello"
    assert layers_out[1].get_layer_name() == "Foreground"
    assert layers_out[1].get_layer_text() == "World"


def test_text_layers_set_none_clears_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    schema.set_text_layers([_make_layer(metadata, "L", "T")])
    schema.set_text_layers(None)
    assert schema.get_text_layers() is None
    assert schema.get_text_layers_property() is None
    assert schema.get_property(PhotoshopSchema.TEXT_LAYERS) is None


def test_add_text_layer_appends_to_seq() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    schema.add_text_layer(_make_layer(metadata, "first", "alpha"))
    schema.add_text_layer(_make_layer(metadata, "second", "beta"))
    layers = schema.get_text_layers()
    assert layers is not None
    assert [layer.get_layer_name() for layer in layers] == ["first", "second"]
    assert [layer.get_layer_text() for layer in layers] == ["alpha", "beta"]


def test_remove_text_layer_drops_matching_layer_name() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    schema.set_text_layers([
        _make_layer(metadata, "keep", "a"),
        _make_layer(metadata, "drop", "b"),
        _make_layer(metadata, "also-keep", "c"),
    ])
    schema.remove_text_layer("drop")
    layers = schema.get_text_layers()
    assert layers is not None
    assert [layer.get_layer_name() for layer in layers] == ["keep", "also-keep"]


def test_remove_text_layer_no_match_is_noop() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    schema.set_text_layers([_make_layer(metadata, "only", "x")])
    schema.remove_text_layer("missing")
    layers = schema.get_text_layers()
    assert layers is not None
    assert len(layers) == 1
    assert layers[0].get_layer_name() == "only"


def test_remove_text_layer_when_property_absent_is_noop() -> None:
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())
    schema.remove_text_layer("anything")
    assert schema.get_text_layers() is None


def test_text_layers_property_round_trip_via_array_property() -> None:
    """Parametric upstream-test path: set/get the raw ArrayProperty Seq."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    seq = ArrayProperty(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        PhotoshopSchema.TEXT_LAYERS,
        Cardinality.Seq,
    )
    seq.add_property(_make_layer(metadata, "L1", "T1"))
    schema.set_text_layers_property(seq)
    assert schema.get_text_layers_property() is seq
    # Stored under the upstream local-name with the typed-list view available.
    assert schema.get_property(PhotoshopSchema.TEXT_LAYERS) is seq
    layers = schema.get_text_layers()
    assert layers is not None
    assert len(layers) == 1
    assert layers[0].get_layer_name() == "L1"


def test_text_layers_property_setter_with_none_clears_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    schema.add_text_layer(_make_layer(metadata, "x", "y"))
    schema.set_text_layers_property(None)
    assert schema.get_text_layers_property() is None
    assert schema.get_text_layers() is None
