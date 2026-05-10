from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI

_IS_MAP = COSName.get_pdf_name("IsMap")


def test_should_track_mouse_position_default_is_false() -> None:
    uri = PDActionURI()
    assert uri.should_track_mouse_position() is False


def test_set_track_mouse_position_round_trip() -> None:
    uri = PDActionURI()

    uri.set_track_mouse_position(True)
    assert uri.should_track_mouse_position() is True

    uri.set_track_mouse_position(False)
    assert uri.should_track_mouse_position() is False


def test_is_map_is_stored_as_cos_boolean() -> None:
    uri = PDActionURI()
    uri.set_track_mouse_position(True)
    raw = uri.get_cos_object()
    assert isinstance(raw.get_item(_IS_MAP), COSBoolean)
