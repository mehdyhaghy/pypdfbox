"""Wave 1275 — explicit ``to_string()`` parity for NameRecord."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.name_record import NameRecord


def test_to_string_matches_upstream_format() -> None:
    nr = NameRecord()
    nr.set_platform_id(3)
    nr.set_platform_encoding_id(1)
    nr.set_language_id(0x0409)
    nr.set_name_id(6)
    nr.set_string("Helvetica")
    assert nr.to_string() == "platform=3 pEncoding=1 language=1033 name=6 Helvetica"


def test_str_delegates_to_to_string() -> None:
    nr = NameRecord()
    nr.set_platform_id(0)
    nr.set_platform_encoding_id(0)
    nr.set_language_id(0)
    nr.set_name_id(0)
    nr.set_string(None)
    assert str(nr) == nr.to_string()


def test_repr_delegates_to_to_string() -> None:
    nr = NameRecord()
    nr.set_platform_id(1)
    nr.set_string("foo")
    assert repr(nr) == nr.to_string()


def test_to_string_with_none_string() -> None:
    nr = NameRecord()
    nr.set_platform_id(1)
    nr.set_platform_encoding_id(2)
    nr.set_language_id(3)
    nr.set_name_id(4)
    nr.set_string(None)
    assert nr.to_string() == "platform=1 pEncoding=2 language=3 name=4 None"
