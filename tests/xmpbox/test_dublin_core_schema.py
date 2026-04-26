from __future__ import annotations

from pypdfbox.xmpbox import DublinCoreSchema, XMPMetadata


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
