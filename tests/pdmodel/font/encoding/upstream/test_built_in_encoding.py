"""Ported upstream tests for ``BuiltInEncoding``.

Upstream PDFBox 3.0 has **no** ``BuiltInEncodingTest.java``
(`pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/encoding/`). The class
is exercised indirectly through font loading tests for Type 1 / Type 3 /
TrueType fonts.

This file therefore covers the small contract surface of
``BuiltInEncoding`` that a direct upstream test would have asserted, in the
same style as the upstream JUnit tests for sibling encoding classes.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.encoding import BuiltInEncoding


def test_construction_from_map():
    # Mirrors what upstream callers do: pass a Map<Integer, String>.
    code_to_name = {65: "A", 66: "B", 67: "C"}
    enc = BuiltInEncoding(code_to_name)
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"
    assert enc.get_name(67) == "C"


def test_get_cos_object_throws():
    # Upstream throws ``UnsupportedOperationException("Built-in encodings
    # cannot be serialized")``. Python port raises ``NotImplementedError``
    # with the same message — both signal "do not call".
    enc = BuiltInEncoding({65: "A"})
    with pytest.raises(NotImplementedError, match="cannot be serialized"):
        enc.get_cos_object()


def test_get_encoding_name():
    enc = BuiltInEncoding({})
    assert enc.get_encoding_name() == "built-in (TTF)"
