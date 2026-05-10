"""Synthetic upstream-shape tests for ``CFFFont``.

Apache PDFBox does not ship a ``CFFFontTest.java`` (the class is exercised
indirectly via ``CFFParserTest``). This module covers the package-private
setters and the ``toString()`` mirror that pypdfbox exposes for parity
with the upstream Java surface (see Java refs in each test).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont


class _SubFont(CFFFont):
    """Minimal concrete subclass — upstream ``CFFFont`` is abstract on
    ``getType2CharString``; pypdfbox provides a default implementation
    so we can instantiate the base class directly here."""


def test_set_name_overrides_get_name() -> None:
    """Upstream Java line 59: ``void setName(String name)``."""
    font = _SubFont()
    assert font.get_name() == ""
    font.set_name("Helvetica")
    assert font.get_name() == "Helvetica"
    font.set_name(None)
    assert font.get_name() == ""


def test_set_charset_round_trip() -> None:
    """Upstream Java line 128: ``void setCharset(CFFCharset charset)``."""
    font = _SubFont()
    assert font.get_charset() == []
    font.set_charset([".notdef", "A", "B"])
    assert font.get_charset() == [".notdef", "A", "B"]
    # mutation of the returned list must not bleed back
    font.get_charset().append("C")
    assert font.get_charset() == [".notdef", "A", "B"]
    font.set_charset(None)
    assert font.get_charset() == []


def test_set_data_round_trip() -> None:
    """Upstream Java line 146: ``void setData(CFFParser.ByteSource source)``
    paired with line 158 ``byte[] getData()``."""
    font = _SubFont()
    assert font.get_data() == b""
    font.set_data(b"\x01\x00\x04\x01")
    assert font.get_data() == b"\x01\x00\x04\x01"
    # bytearray and memoryview both accepted, returned as bytes
    font.set_data(bytearray(b"abc"))
    assert font.get_data() == b"abc"
    assert isinstance(font.get_data(), bytes)
    font.set_data(None)
    assert font.get_data() == b""


def test_set_global_subr_index_round_trip() -> None:
    """Upstream Java line 178: ``void setGlobalSubrIndex(byte[][])``
    paired with line 188 ``List<byte[]> getGlobalSubrIndex()``."""
    font = _SubFont()
    assert font.get_global_subr_index() == []
    font.set_global_subr_index([b"\x01\x02", b"\x03"])
    assert font.get_global_subr_index() == [b"\x01\x02", b"\x03"]
    font.set_global_subr_index(None)
    assert font.get_global_subr_index() == []


def test_add_value_to_top_dict_then_get_top_dict() -> None:
    """Upstream Java lines 70-86: ``addValueToTopDict`` / ``getTopDict``."""
    font = _SubFont()
    font.add_value_to_top_dict("FullName", "Sample Regular")
    assert font.get_top_dict()["FullName"] == "Sample Regular"
    # null-guard parity (upstream skips ``null`` values)
    font.add_value_to_top_dict("Skipped", None)
    assert "Skipped" not in font.get_top_dict()


def test_get_font_b_box_diverges_on_missing_bbox() -> None:
    """Upstream Java line 103 throws ``IOException`` when the FontBBox
    is short; pypdfbox returns ``[0,0,0,0]`` for ergonomics. Documented
    in the docstring; this test pins the divergence."""
    font = _SubFont()
    assert font.get_font_b_box() == [0.0, 0.0, 0.0, 0.0]
    font.add_value_to_top_dict("FontBBox", [-100, -200, 1000, 800])
    assert font.get_font_b_box() == [-100.0, -200.0, 1000.0, 800.0]


def test_get_font_matrix_default() -> None:
    """Upstream Java line 92: ``getFontMatrix`` returns Top DICT's
    ``FontMatrix``. With no parsed Top DICT pypdfbox returns the CFF
    spec default ``[0.001 0 0 0.001 0 0]``."""
    font = _SubFont()
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_to_string_mirrors_repr() -> None:
    """Upstream Java line 205: ``String toString()``."""
    font = _SubFont()
    font.set_name("X")
    s = font.to_string()
    assert s == repr(font)
    assert "name=X" in s
    assert "topDict=" in s
    assert "charset=" in s
    assert "charStrings=" in s


def test_get_type2_char_string_is_abstract_in_upstream() -> None:
    """Upstream Java line 202 declares ``getType2CharString`` abstract.
    pypdfbox provides a default implementation that returns an empty
    Type2CharString wrapper for out-of-range / unparsed fonts so callers
    can probe ``get_path() == []`` rather than catching IOException."""
    font = _SubFont()
    cs = font.get_type2_char_string(0)
    assert cs is not None
    # No charset yet -> empty path / zero width
    assert cs.get_path() == []


def test_set_charset_does_not_share_list_reference() -> None:
    """Defensive copy parity — upstream ``Arrays.asList`` would expose
    the array; pypdfbox copies on set/get so tests can't accidentally
    mutate parser internals."""
    font = _SubFont()
    src = [".notdef", "A"]
    font.set_charset(src)
    src.append("B")
    assert font.get_charset() == [".notdef", "A"]


def test_set_global_subr_index_does_not_share_list_reference() -> None:
    font = _SubFont()
    src = [b"\x01"]
    font.set_global_subr_index(src)
    src.append(b"\x02")
    assert font.get_global_subr_index() == [b"\x01"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Times-Roman", "Times-Roman"),
        ("", ""),
    ],
)
def test_set_name_parametrized(name: str, expected: str) -> None:
    font = _SubFont()
    font.set_name(name)
    assert font.get_name() == expected
