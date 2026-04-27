from __future__ import annotations

from pypdfbox.xmpbox import (
    DomXmpParser,
    PhotoshopSchema,
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
