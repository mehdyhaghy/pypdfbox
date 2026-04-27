from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent


def test_fresh_intent_sets_type_output_intent() -> None:
    intent = PDOutputIntent()
    cos = intent.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "OutputIntent"  # type: ignore[attr-defined]


def test_subtype_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    assert intent.get_subtype() == "GTS_PDFA1"


def test_info_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_info("sRGB IEC61966-2.1")
    assert intent.get_info() == "sRGB IEC61966-2.1"


def test_output_condition_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition("commercial offset press")
    assert intent.get_output_condition() == "commercial offset press"


def test_output_condition_identifier_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition_identifier("CGATS TR 001")
    assert intent.get_output_condition_identifier() == "CGATS TR 001"


def test_registry_name_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_registry_name("http://www.color.org")
    assert intent.get_registry_name() == "http://www.color.org"


def test_dest_output_profile_round_trip_cos_stream() -> None:
    intent = PDOutputIntent()
    profile = COSStream()
    intent.set_dest_output_profile(profile)
    # get_dest_output_profile now returns a typed PDStream wrapping the
    # underlying COSStream; raw access is via get_dest_output_profile_cos.
    assert intent.get_dest_output_profile_cos() is profile


def test_wrap_existing_dictionary_preserves_type() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("S"), "GTS_PDFX")
    intent = PDOutputIntent(raw)
    assert intent.get_subtype() == "GTS_PDFX"
    assert intent.get_cos_object() is raw


def test_set_subtype_none_removes_key() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    intent.set_subtype(None)
    assert intent.get_subtype() is None


def test_set_dest_output_profile_none_removes_key() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())
    intent.set_dest_output_profile(None)
    assert intent.get_dest_output_profile() is None
