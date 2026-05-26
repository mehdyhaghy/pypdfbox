"""Hand-written tests for :class:`FlashType`.

Mirrors the upstream Java definition at
``xmpbox/src/main/java/org/apache/xmpbox/type/FlashType.java`` (PDFBox 3.0).
The upstream type carries five simple fields:

* ``Fired`` — Boolean.
* ``Function`` — Boolean.
* ``RedEyeMode`` — Boolean.
* ``Mode`` — Integer.
* ``Return`` — Integer.

PDFBox 3.0 ships no dedicated ``FlashTypeTest`` Java file — the type surface
is exercised indirectly through ``DomXmpParserTest``. These tests cover the
read/write contract for the typed accessors.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import FlashType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    flash = FlashType(metadata)
    assert flash.get_namespace() == "http://ns.adobe.com/exif/1.0/"
    assert flash.get_prefered_prefix() == "exif"


def test_field_types_match_upstream_property_annotations() -> None:
    assert FlashType._FIELD_TYPES["Fired"] == "Boolean"
    assert FlashType._FIELD_TYPES["Function"] == "Boolean"
    assert FlashType._FIELD_TYPES["RedEyeMode"] == "Boolean"
    assert FlashType._FIELD_TYPES["Mode"] == "Integer"
    assert FlashType._FIELD_TYPES["Return"] == "Integer"


def test_initial_fields_empty(metadata: XMPMetadata) -> None:
    flash = FlashType(metadata)
    assert flash.get_fired() is None
    assert flash.get_function() is None
    assert flash.get_red_eye_mode() is None
    assert flash.get_mode() is None
    assert flash.get_return() is None


def test_set_and_get_boolean_flags(metadata: XMPMetadata) -> None:
    flash = FlashType(metadata)
    flash.set_fired(True)
    flash.set_function(False)
    flash.set_red_eye_mode(True)
    assert flash.get_fired() is True
    assert flash.get_function() is False
    assert flash.get_red_eye_mode() is True


def test_set_and_get_integer_codes(metadata: XMPMetadata) -> None:
    flash = FlashType(metadata)
    flash.set_mode(1)
    flash.set_return(2)
    assert flash.get_mode() == 1
    assert flash.get_return() == 2


def test_full_round_trip(metadata: XMPMetadata) -> None:
    flash = FlashType(metadata)
    flash.set_fired(True)
    flash.set_function(False)
    flash.set_red_eye_mode(False)
    flash.set_mode(3)
    flash.set_return(0)

    assert flash.get_fired() is True
    assert flash.get_function() is False
    assert flash.get_red_eye_mode() is False
    assert flash.get_mode() == 3
    assert flash.get_return() == 0
