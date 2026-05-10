"""Wave 1275 — explicit ``to_string()`` parity for Attribute.

Mirrors ``AttributeTest.toString()`` shape from
``xmpbox/src/test/java/org/apache/xmpbox/type/AttributeTest.java`` (the
upstream test class only exercises getters; we add explicit ``toString``
parity coverage here).
"""

from __future__ import annotations

from pypdfbox.xmpbox import Attribute


def test_to_string_matches_upstream_format() -> None:
    att = Attribute("nsUri", "localName", "value")
    assert att.to_string() == "[attr:{nsUri}localName=value]"


def test_str_delegates_to_to_string() -> None:
    att = Attribute("nsUri", "localName", "value")
    assert str(att) == att.to_string()


def test_repr_delegates_to_to_string() -> None:
    att = Attribute("nsUri", "localName", "value")
    assert repr(att) == att.to_string()


def test_to_string_with_none_namespace() -> None:
    att = Attribute(None, "name", "v")
    assert att.to_string() == "[attr:{None}name=v]"
