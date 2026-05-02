"""Round-out tests for :class:`PDActionURI` covering the
:meth:`get_is_map` / :meth:`set_is_map` aliases that mirror the raw
PDF dictionary entry name verbatim.
"""

from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionURI

_URI: COSName = COSName.get_pdf_name("URI")
_IS_MAP: COSName = COSName.get_pdf_name("IsMap")


def test_default_subtype_is_uri() -> None:
    action = PDActionURI()
    assert action.get_sub_type() == "URI"


def test_uri_round_trip() -> None:
    action = PDActionURI()
    assert action.get_uri() is None

    action.set_uri("https://example.test/landing")
    assert action.get_uri() == "https://example.test/landing"


def test_uri_set_none_removes_entry() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    assert action.get_cos_object().contains_key(_URI)

    action.set_uri(None)
    assert not action.get_cos_object().contains_key(_URI)
    assert action.get_uri() is None


def test_get_is_map_default_is_false() -> None:
    action = PDActionURI()
    assert action.get_is_map() is False


def test_set_is_map_round_trips() -> None:
    action = PDActionURI()

    action.set_is_map(True)
    assert action.get_is_map() is True
    # Alias on the other accessor pair stays in sync.
    assert action.should_track_mouse_position() is True

    action.set_is_map(False)
    assert action.get_is_map() is False
    assert action.should_track_mouse_position() is False


def test_is_map_aliases_round_trip_via_either_setter() -> None:
    """Setting via ``set_track_mouse_position`` is observable through
    ``get_is_map`` and vice versa."""
    action = PDActionURI()

    action.set_track_mouse_position(True)
    assert action.get_is_map() is True

    action.set_is_map(False)
    assert action.should_track_mouse_position() is False


def test_is_map_stored_as_cos_boolean() -> None:
    action = PDActionURI()
    action.set_is_map(True)

    raw = action.get_cos_object().get_item(_IS_MAP)
    assert isinstance(raw, COSBoolean)


def test_has_uri_tracks_presence() -> None:
    action = PDActionURI()
    assert action.has_uri() is False

    action.set_uri("https://example.test/")
    assert action.has_uri() is True

    action.set_uri(None)
    assert action.has_uri() is False


def test_has_is_map_distinguishes_default_from_explicit_false() -> None:
    """``get_is_map`` collapses absence and explicit ``false`` to
    ``False``; ``has_is_map`` lets callers tell them apart."""
    action = PDActionURI()
    assert action.has_is_map() is False
    assert action.get_is_map() is False

    action.set_is_map(False)
    assert action.has_is_map() is True
    assert action.get_is_map() is False

    action.set_is_map(True)
    assert action.has_is_map() is True
    assert action.get_is_map() is True


def test_get_uri_as_cos_string_returns_raw_entry() -> None:
    action = PDActionURI()
    assert action.get_uri_as_cos_string() is None

    action.set_uri("https://example.test/")
    raw = action.get_uri_as_cos_string()
    assert isinstance(raw, COSString)
    assert raw.get_string() == "https://example.test/"


def test_get_uri_as_cos_string_none_when_not_a_string() -> None:
    """When ``/URI`` is present but not a ``COSString`` (malformed
    producer), the typed accessor declines to surface it."""
    action = PDActionURI()
    action.get_cos_object().set_item(_URI, COSName.get_pdf_name("NotAString"))
    assert action.get_uri_as_cos_string() is None
