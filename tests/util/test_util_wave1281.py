"""Hand-written tests for the ``pypdfbox.util`` cluster ported in Wave 1281."""

from __future__ import annotations

import io

import pytest

from pypdfbox.util import (
    Hex,
    IterativeMergeSort,
    Matrix,
    NumberFormatUtil,
    SmallMap,
    SmallMapEntry,
    StringUtil,
    Vector,
    XMLUtil,
)


def test_hex_get_string_byte() -> None:
    assert Hex.get_string(0xAB) == "AB"
    assert Hex.get_string(b"\x00\xff") == "00FF"


def test_hex_get_bytes_round_trip() -> None:
    encoded = Hex.get_bytes(b"hi")
    assert encoded == b"6869"
    assert Hex.decode_hex(encoded.decode("ascii")) == b"hi"


def test_hex_get_chars_for_short() -> None:
    assert Hex.get_chars(0x1234) == "1234"


def test_hex_get_chars_utf16_be() -> None:
    assert Hex.get_chars_utf16_be("ab") == "00610062"


def test_hex_write_hex_byte() -> None:
    buf = io.BytesIO()
    Hex.write_hex_byte(0x4F, buf)
    assert buf.getvalue() == b"4F"


def test_hex_decode_base64_skips_whitespace() -> None:
    assert Hex.decode_base64("aGVs\nbG8=") == b"hello"


def test_hex_get_hex_value() -> None:
    assert Hex.get_hex_value("0") == 0
    assert Hex.get_hex_value("F") == 15
    assert Hex.get_hex_value("a") == 10
    assert Hex.get_hex_value("Z") == -256


def test_iterative_merge_sort_sorts_with_comparator() -> None:
    items = [3, 1, 4, 1, 5, 9, 2, 6]
    IterativeMergeSort.sort(items, lambda a, b: a - b)
    assert items == [1, 1, 2, 3, 4, 5, 6, 9]


def test_iterative_merge_sort_noop_on_singleton() -> None:
    items = [42]
    IterativeMergeSort.sort(items, lambda a, b: a - b)
    assert items == [42]


def test_vector_get_and_scale() -> None:
    v = Vector(2.0, 3.0)
    assert v.get_x() == 2.0
    assert v.get_y() == 3.0
    scaled = v.scale(2.0)
    assert scaled.get_x() == 4.0
    assert scaled.get_y() == 6.0
    assert str(v) == "(2.0, 3.0)"


def test_string_util_split_and_tokenize() -> None:
    assert StringUtil.split_on_space("a b c") == ["a", "b", "c"]
    assert StringUtil.tokenize_on_space("a b") == ["a", " ", "b"]


def test_string_util_tokenize_on_space_empty_string_returns_singleton() -> None:
    """``tokenize_on_space("")`` returns ``[""]`` — the empty string is a
    legitimate single token (mirrors Java ``String.split`` behaviour
    where the input is itself the result)."""
    assert StringUtil.tokenize_on_space("") == [""]


def test_string_util_tokenize_on_space_falsy_non_empty_returns_empty() -> None:
    """``tokenize_on_space(None)`` falls into the ``else []`` branch —
    the input is falsy but is not the empty string, so no token is
    emitted. Covers string_util.py line 31."""
    # Type-checker would reject ``None``; we deliberately bypass for the
    # defensive falsy-non-string branch.
    assert StringUtil.tokenize_on_space(None) == []  # type: ignore[arg-type]


def test_number_format_util_basic() -> None:
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(3.14, 2, buf)
    assert buf[:n] == b"3.14"


def test_number_format_util_negative_value() -> None:
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(-2.5, 1, buf)
    assert buf[:n] == b"-2.5"


def test_number_format_util_rejects_nan() -> None:
    buf = bytearray(32)
    assert NumberFormatUtil.format_float_fast(float("nan"), 2, buf) == -1


def test_small_map_put_get_remove() -> None:
    m = SmallMap()
    assert m.is_empty()
    m.put("a", 1)
    m.put("b", 2)
    assert m.size() == 2
    assert m["a"] == 1
    assert m.get("b") == 2
    old = m.put("a", 10)
    assert old == 1
    assert m["a"] == 10
    removed = m.remove("a")
    assert removed == 10
    assert "a" not in m
    assert m.contains_key("b")


def test_small_map_rejects_null() -> None:
    m = SmallMap()
    with pytest.raises(TypeError):
        m.put(None, 1)
    with pytest.raises(TypeError):
        m.put("k", None)


def test_small_map_entry_set() -> None:
    m = SmallMap({"a": 1, "b": 2})
    entries = m.entry_set()
    assert {(e.get_key(), e.get_value()) for e in entries} == {("a", 1), ("b", 2)}
    assert isinstance(entries[0], SmallMapEntry)


def test_xml_util_parses_simple_xml() -> None:
    data = b"<root><a>hi</a></root>"
    doc = XMLUtil.parse(data)
    root = doc.documentElement
    a = root.getElementsByTagName("a")[0]
    assert XMLUtil.get_node_value(a) == "hi"


def test_matrix_default_is_identity() -> None:
    m = Matrix()
    assert m.get_value(0, 0) == 1.0
    assert m.get_value(1, 1) == 1.0
    assert m.get_value(2, 2) == 1.0


def test_matrix_translate_and_scale() -> None:
    m = Matrix.get_translate_instance(3.0, 4.0)
    assert m.get_translate_x() == 3.0
    assert m.get_translate_y() == 4.0
    s = Matrix.get_scale_instance(2.0, 3.0)
    assert s.get_scale_x() == 2.0
    assert s.get_scale_y() == 3.0


def test_matrix_multiply_identity_yields_self() -> None:
    m = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    identity = Matrix()
    out = m.multiply(identity)
    assert out.get_scale_x() == 1.0


def test_matrix_transform_point() -> None:
    m = Matrix.get_translate_instance(10.0, 20.0)
    x, y = m.transform_point(1.0, 2.0)
    assert (x, y) == (11.0, 22.0)


def test_matrix_to_cos_array_round_trip() -> None:
    m = Matrix(1.0, 0.0, 0.0, 1.0, 5.0, 6.0)
    arr = m.to_cos_array()
    rebuilt = Matrix.create_matrix(arr)
    assert rebuilt.get_translate_x() == 5.0
    assert rebuilt.get_translate_y() == 6.0
