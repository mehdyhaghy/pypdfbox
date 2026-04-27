from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DateType,
    DublinCoreSchema,
    LangAlt,
    MIMEType,
    ProperNameType,
    TextType,
    XMPMetadata,
)


def _dc() -> DublinCoreSchema:
    return DublinCoreSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    dc = _dc()
    assert dc.get_namespace() == "http://purl.org/dc/elements/1.1/"
    assert dc.get_prefix() == "dc"


def test_default_title_round_trip() -> None:
    dc = _dc()
    dc.set_title("Hello")
    assert dc.get_title() == "Hello"


def test_localized_title() -> None:
    dc = _dc()
    dc.set_title("Hello")
    dc.add_title("fr", "Bonjour")
    assert dc.get_title() == "Hello"
    assert dc.get_title("fr") == "Bonjour"
    langs = dc.get_title_languages() or []
    assert "x-default" in langs and "fr" in langs


def test_creator_seq_order_preserved() -> None:
    dc = _dc()
    dc.add_creator("Alice")
    dc.add_creator("Bob")
    assert dc.get_creators() == ["Alice", "Bob"]
    dc.remove_creator("Alice")
    assert dc.get_creators() == ["Bob"]


def test_subject_bag() -> None:
    dc = _dc()
    dc.add_subject("xml")
    dc.add_subject("pdf")
    assert dc.get_subjects() == ["xml", "pdf"]


def test_simple_text_properties() -> None:
    dc = _dc()
    dc.set_format("application/pdf")
    dc.set_identifier("urn:doc:1")
    dc.set_source("origin")
    dc.set_coverage("global")
    assert dc.get_format() == "application/pdf"
    assert dc.get_identifier() == "urn:doc:1"
    assert dc.get_source() == "origin"
    assert dc.get_coverage() == "global"


def test_description_default_and_lang() -> None:
    dc = _dc()
    dc.set_description("desc")
    dc.add_description("de", "Beschreibung")
    assert dc.get_description() == "desc"
    assert dc.get_description("de") == "Beschreibung"


# ---------------------------------------------------------------------------
# Wave 32 — typed accessor parity (TextType / LangAlt / ArrayProperty)
# ---------------------------------------------------------------------------


def test_typed_initially_null() -> None:
    dc = _dc()
    assert dc.get_title_property() is None
    assert dc.get_description_property() is None
    assert dc.get_rights_property() is None
    assert dc.get_creators_property() is None
    assert dc.get_contributors_property() is None
    assert dc.get_publishers_property() is None
    assert dc.get_languages_property() is None
    assert dc.get_relations_property() is None
    assert dc.get_subjects_property() is None
    assert dc.get_types_property() is None
    assert dc.get_dates_property() is None
    assert dc.get_coverage_property() is None
    assert dc.get_format_property() is None
    assert dc.get_identifier_property() is None
    assert dc.get_source_property() is None


def test_coverage_property_round_trip() -> None:
    dc = _dc()
    dc.set_coverage("global")
    prop = dc.get_coverage_property()
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "global"
    assert prop.get_property_name() == DublinCoreSchema.COVERAGE


def test_set_coverage_property_via_typed() -> None:
    dc = _dc()
    text = TextType(
        XMPMetadata.create_xmp_metadata(),
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.PREFERRED_PREFIX,
        DublinCoreSchema.COVERAGE,
        "europe",
    )
    dc.set_coverage_property(text)
    assert dc.get_coverage() == "europe"


def test_format_property_returns_mime_type() -> None:
    dc = _dc()
    dc.set_format("application/pdf")
    prop = dc.get_format_property()
    assert isinstance(prop, MIMEType)
    assert prop.get_string_value() == "application/pdf"


def test_identifier_property_round_trip() -> None:
    dc = _dc()
    dc.set_identifier_property(
        TextType(
            XMPMetadata.create_xmp_metadata(),
            DublinCoreSchema.NAMESPACE,
            DublinCoreSchema.PREFERRED_PREFIX,
            DublinCoreSchema.IDENTIFIER,
            "urn:doc:42",
        )
    )
    assert dc.get_identifier() == "urn:doc:42"
    prop = dc.get_identifier_property()
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "urn:doc:42"


def test_source_property_round_trip() -> None:
    dc = _dc()
    dc.set_source("origin")
    prop = dc.get_source_property()
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "origin"


def test_title_property_returns_lang_alt() -> None:
    dc = _dc()
    dc.set_title("Hello")
    dc.add_title("fr", "Bonjour")
    prop = dc.get_title_property()
    assert isinstance(prop, LangAlt)
    # x-default first in the alt-array order.
    children = prop.get_all_properties()
    first_attr = children[0].get_attribute("xml:lang")
    assert first_attr is not None
    assert first_attr.get_value() == "x-default"
    assert prop.get_language_value(None) == "Hello"
    assert prop.get_language_value("fr") == "Bonjour"
    assert "x-default" in prop.get_languages()
    assert "fr" in prop.get_languages()


def test_description_property_lang_alt_round_trip() -> None:
    dc = _dc()
    dc.set_description("desc")
    dc.add_description("de", "Beschreibung")
    prop = dc.get_description_property()
    assert isinstance(prop, LangAlt)
    assert prop.get_language_value(None) == "desc"
    assert prop.get_language_value("de") == "Beschreibung"
    langs = dc.get_description_languages() or []
    assert "x-default" in langs and "de" in langs


def test_rights_lang_alt_round_trip() -> None:
    dc = _dc()
    dc.add_rights(None, "All rights reserved")
    dc.add_rights("fr", "Tous droits reserves")
    assert dc.get_rights() == "All rights reserved"
    assert dc.get_rights("fr") == "Tous droits reserves"
    langs = dc.get_rights_languages() or []
    assert "x-default" in langs and "fr" in langs
    prop = dc.get_rights_property()
    assert isinstance(prop, LangAlt)
    assert prop.get_language_value("fr") == "Tous droits reserves"


def test_set_lang_alt_property_round_trip() -> None:
    dc = _dc()
    metadata = XMPMetadata.create_xmp_metadata()
    la = LangAlt(metadata, DublinCoreSchema.NAMESPACE, "dc", DublinCoreSchema.TITLE)
    la.set_language_value(None, "Default Title")
    la.set_language_value("ja", "タイトル")
    dc.set_title_property(la)
    assert dc.get_title() == "Default Title"
    assert dc.get_title("ja") == "タイトル"
    rebuilt = dc.get_title_property()
    assert isinstance(rebuilt, LangAlt)
    assert rebuilt.get_language_value("ja") == "タイトル"


def test_creators_property_is_seq_of_proper_name() -> None:
    dc = _dc()
    dc.add_creator("Alice")
    dc.add_creator("Bob")
    prop = dc.get_creators_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Seq
    children = prop.get_all_properties()
    assert len(children) == 2
    assert all(isinstance(c, ProperNameType) for c in children)
    assert [c.get_string_value() for c in children] == ["Alice", "Bob"]


def test_set_creators_property_replaces_seq() -> None:
    dc = _dc()
    dc.add_creator("Alice")
    metadata = XMPMetadata.create_xmp_metadata()
    fresh = ArrayProperty(
        metadata,
        DublinCoreSchema.NAMESPACE,
        "dc",
        DublinCoreSchema.CREATOR,
        Cardinality.Seq,
    )
    fresh.add_property(
        ProperNameType(
            metadata,
            DublinCoreSchema.NAMESPACE,
            "dc",
            DublinCoreSchema.CREATOR,
            "Carol",
        )
    )
    fresh.add_property(
        ProperNameType(
            metadata,
            DublinCoreSchema.NAMESPACE,
            "dc",
            DublinCoreSchema.CREATOR,
            "Dave",
        )
    )
    dc.set_creators_property(fresh)
    assert dc.get_creators() == ["Carol", "Dave"]


def test_contributors_property_is_bag() -> None:
    dc = _dc()
    dc.add_contributor("Eve")
    dc.add_contributor("Frank")
    prop = dc.get_contributors_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert [c.get_string_value() for c in prop.get_all_properties()] == [
        "Eve",
        "Frank",
    ]
    dc.remove_contributor("Eve")
    assert dc.get_contributors() == ["Frank"]


def test_publishers_property_is_bag() -> None:
    dc = _dc()
    dc.add_publisher("Acme")
    prop = dc.get_publishers_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert prop.get_elements_as_string() == ["Acme"]
    dc.remove_publisher("Acme")
    assert dc.get_publishers() == []


def test_languages_property_is_bag_of_text() -> None:
    dc = _dc()
    dc.add_language("en")
    dc.add_language("fr")
    prop = dc.get_languages_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert prop.get_elements_as_string() == ["en", "fr"]
    dc.remove_language("en")
    assert dc.get_languages() == ["fr"]


def test_relations_property_round_trip() -> None:
    dc = _dc()
    dc.add_relation("doc-A")
    dc.add_relation("doc-B")
    assert dc.get_relations() == ["doc-A", "doc-B"]
    prop = dc.get_relations_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert prop.get_elements_as_string() == ["doc-A", "doc-B"]
    dc.remove_relation("doc-A")
    assert dc.get_relations() == ["doc-B"]


def test_subjects_property_round_trip() -> None:
    dc = _dc()
    dc.add_subject("xml")
    dc.add_subject("pdf")
    prop = dc.get_subjects_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert prop.get_elements_as_string() == ["xml", "pdf"]


def test_types_property_round_trip() -> None:
    dc = _dc()
    dc.add_type("novel")
    dc.add_type("poem")
    assert dc.get_types() == ["novel", "poem"]
    prop = dc.get_types_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert prop.get_elements_as_string() == ["novel", "poem"]
    dc.remove_type("novel")
    assert dc.get_types() == ["poem"]


def test_dates_property_round_trip() -> None:
    dc = _dc()
    when = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    later = datetime(2025, 6, 7, 8, 9, 10, tzinfo=UTC)
    dc.add_date(when)
    dc.add_date(later)
    dates = dc.get_dates()
    assert dates is not None
    assert dates[0] == when
    assert dates[1] == later
    prop = dc.get_dates_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Seq
    children = prop.get_all_properties()
    assert all(isinstance(c, DateType) for c in children)
    assert children[0].get_value() == when


def test_dates_remove() -> None:
    dc = _dc()
    when = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    dc.add_date(when)
    dc.remove_date(when)
    assert dc.get_dates() == []


def test_set_creators_property_with_text_type_children_works() -> None:
    """Setter accepts TextType (parent class of ProperName) too — upstream parity."""
    dc = _dc()
    metadata = XMPMetadata.create_xmp_metadata()
    arr = ArrayProperty(
        metadata,
        DublinCoreSchema.NAMESPACE,
        "dc",
        DublinCoreSchema.CREATOR,
        Cardinality.Seq,
    )
    arr.add_property(
        TextType(
            metadata,
            DublinCoreSchema.NAMESPACE,
            "dc",
            DublinCoreSchema.CREATOR,
            "Mallory",
        )
    )
    dc.set_creators_property(arr)
    assert dc.get_creators() == ["Mallory"]


def test_typed_setters_visible_to_string_accessors() -> None:
    """Cross-surface contract: typed setter writes are read-back via string API."""
    dc = _dc()
    metadata = XMPMetadata.create_xmp_metadata()
    text = MIMEType(
        metadata,
        DublinCoreSchema.NAMESPACE,
        "dc",
        DublinCoreSchema.FORMAT,
        "image/jpeg",
    )
    dc.set_format_property(text)
    assert dc.get_format() == "image/jpeg"
