from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionURI, PDURIDictionary

_URI: COSName = COSName.get_pdf_name("URI")
_IS_MAP: COSName = COSName.get_pdf_name("IsMap")
_BASE: COSName = COSName.get_pdf_name("Base")


def test_uri_action_defaults_and_uri_cos_round_trip() -> None:
    action = PDActionURI()
    assert action.get_uri() is None
    assert action.has_uri() is False
    assert action.is_empty() is True
    assert action.get_uri_as_cos_string() is None

    action.set_uri("https://example.test/path?q=1")

    assert action.get_uri() == "https://example.test/path?q=1"
    assert action.has_uri() is True
    assert action.is_empty() is False
    raw_uri = action.get_cos_object().get_dictionary_object(_URI)
    assert isinstance(raw_uri, COSString)

    wrapped = PDActionURI(action.get_cos_object())
    assert wrapped.get_cos_object() is action.get_cos_object()
    assert wrapped.get_uri() == "https://example.test/path?q=1"
    assert wrapped.get_uri_as_cos_string() is raw_uri


def test_uri_action_track_mouse_and_is_map_aliases_clear_to_default() -> None:
    action = PDActionURI()
    assert action.should_track_mouse_position() is False
    assert action.get_is_map() is False
    assert action.has_is_map() is False

    action.set_track_mouse_position(True)
    assert action.should_track_mouse_position() is True
    assert action.get_is_map() is True
    assert action.has_is_map() is True
    assert action.get_cos_object().get_item(_IS_MAP) is COSBoolean.TRUE

    action.clear_track_mouse_position()
    assert action.should_track_mouse_position() is False
    assert action.get_is_map() is False
    assert action.has_is_map() is False
    assert action.get_cos_object().get_item(_IS_MAP) is None

    action.set_is_map(False)
    assert action.should_track_mouse_position() is False
    assert action.get_is_map() is False
    assert action.has_is_map() is True
    assert action.get_cos_object().get_item(_IS_MAP) is COSBoolean.FALSE

    action.clear_is_map()
    assert action.has_is_map() is False


def test_uri_action_clear_uri_removes_only_uri_entry() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    action.set_track_mouse_position(True)

    action.clear_uri()

    assert action.get_uri() is None
    assert action.has_uri() is False
    assert action.should_track_mouse_position() is True
    assert action.has_is_map() is True


def test_uri_action_malformed_shapes_return_defaults_without_raising() -> None:
    raw = COSDictionary()
    raw.set_item(_URI, COSDictionary())
    raw.set_item(_IS_MAP, COSName.get_pdf_name("NotBoolean"))

    action = PDActionURI(raw)

    assert action.get_cos_object() is raw
    assert action.has_uri() is True
    assert action.get_uri() is None
    assert action.get_uri_as_cos_string() is None
    assert action.has_is_map() is True
    assert action.get_is_map() is False
    assert action.should_track_mouse_position() is False


def test_uri_dictionary_base_defaults_clear_and_cos_round_trip() -> None:
    uri_dict = PDURIDictionary()
    assert uri_dict.get_base() is None
    assert uri_dict.has_base() is False
    assert uri_dict.is_empty() is True
    assert uri_dict.get_base_as_cos_string() is None

    uri_dict.set_base("https://base.example.test/docs/")

    assert uri_dict.get_base() == "https://base.example.test/docs/"
    assert uri_dict.has_base() is True
    assert uri_dict.is_empty() is False
    raw_base = uri_dict.get_cos_object().get_dictionary_object(_BASE)
    assert isinstance(raw_base, COSString)

    wrapped = PDURIDictionary(uri_dict.get_cos_object())
    assert wrapped.get_cos_object() is uri_dict.get_cos_object()
    assert wrapped.get_base() == "https://base.example.test/docs/"
    assert wrapped.get_base_as_cos_string() is raw_base

    wrapped.clear_base()
    assert uri_dict.get_base() is None
    assert uri_dict.has_base() is False
    assert uri_dict.is_empty() is True


def test_uri_dictionary_malformed_base_shape_is_tolerated() -> None:
    raw = COSDictionary()
    raw.set_item(_BASE, COSDictionary())

    uri_dict = PDURIDictionary(raw)

    assert uri_dict.get_cos_object() is raw
    assert uri_dict.has_base() is True
    assert uri_dict.get_base() is None
    assert uri_dict.get_base_as_cos_string() is None
    assert uri_dict.is_empty() is False

    uri_dict.clear_base()
    assert uri_dict.has_base() is False
    assert raw.get_dictionary_object(_BASE) is None
