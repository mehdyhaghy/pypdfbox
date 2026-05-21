"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSArray.java
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSFloat, COSInteger, COSName, COSString


def test_create() -> None:
    cos_array = COSArray()
    assert cos_array.size() == 0
    # Upstream: ``new COSArray(null)`` → IllegalArgumentException. Our
    # constructor treats ``None`` as the no-arg sentinel; covering that
    # overload would require shadowing positional ``None`` with a custom
    # sentinel and brings no value. Skipping just that assertion.

    cos_array = COSArray([COSName.A, COSName.B, COSName.C])  # type: ignore[attr-defined]
    assert cos_array.size() == 3
    assert cos_array.get(0) == COSName.A  # type: ignore[attr-defined]
    assert cos_array.get(1) == COSName.B  # type: ignore[attr-defined]
    assert cos_array.get(2) == COSName.C  # type: ignore[attr-defined]


def test_convert_string_to_cos_name_and_back() -> None:
    cos_array = COSArray.of_cos_names(
        [
            COSName.A.get_name(),  # type: ignore[attr-defined]
            COSName.B.get_name(),  # type: ignore[attr-defined]
            COSName.C.get_name(),  # type: ignore[attr-defined]
        ]
    )
    assert cos_array.size() == 3
    assert cos_array.get(0) == COSName.A  # type: ignore[attr-defined]
    assert cos_array.get(1) == COSName.B  # type: ignore[attr-defined]
    assert cos_array.get(2) == COSName.C  # type: ignore[attr-defined]

    cos_name_string_list = cos_array.to_cos_name_string_list()
    assert len(cos_name_string_list) == 3
    assert cos_name_string_list[0] == COSName.A.get_name()  # type: ignore[attr-defined]
    assert cos_name_string_list[1] == COSName.B.get_name()  # type: ignore[attr-defined]
    assert cos_name_string_list[2] == COSName.C.get_name()  # type: ignore[attr-defined]


def test_convert_string_to_cos_string_and_back() -> None:
    cos_array = COSArray.of_cos_strings(["A", "B", "C"])
    assert cos_array.size() == 3
    assert cos_array.get_string(0) == "A"
    assert cos_array.get_string(1) == "B"
    assert cos_array.get_string(2) == "C"

    cos_string_string_list = cos_array.to_cos_string_string_list()
    assert len(cos_string_string_list) == 3
    assert cos_string_string_list[0] == "A"
    assert cos_string_string_list[1] == "B"
    assert cos_string_string_list[2] == "C"


def test_convert_integer_to_cos_string_and_back() -> None:
    cos_array = COSArray.of_cos_integers([1, 2, 3])
    assert cos_array.size() == 3
    assert cos_array.get_int(0) == 1
    assert cos_array.get_int(1) == 2
    assert cos_array.get_int(2) == 3

    cos_number_integer_list = cos_array.to_cos_number_integer_list()
    assert len(cos_number_integer_list) == 3
    assert cos_number_integer_list[0] == 1
    assert cos_number_integer_list[1] == 2
    assert cos_number_integer_list[2] == 3

    # Arrays with null values.
    cos_array = COSArray([COSInteger.get(1), None, COSInteger.get(3)])  # type: ignore[list-item]
    assert cos_array.size() == 3
    assert cos_array.get_int(0) == 1
    assert cos_array.get(1) is None
    assert cos_array.get_int(2) == 3
    cos_number_integer_list = cos_array.to_cos_number_integer_list()
    assert len(cos_number_integer_list) == 3
    assert cos_number_integer_list[0] == 1
    assert cos_number_integer_list[1] is None
    assert cos_number_integer_list[2] == 3


def test_convert_float_to_cos_string_and_back() -> None:
    float_array_start = [1.0, 0.1, 0.02]
    cos_array = COSArray()
    cos_array.set_float_array(float_array_start)

    assert cos_array.size() == 3
    assert cos_array.get(0) == COSFloat(1.0)
    assert cos_array.get(1) == COSFloat(0.1)
    assert cos_array.get(2) == COSFloat(0.02)

    cos_number_float_list = cos_array.to_cos_number_float_list()
    assert len(cos_number_float_list) == 3
    assert cos_number_float_list[0] == pytest.approx(1.0)
    assert cos_number_float_list[1] == pytest.approx(0.1)
    assert cos_number_float_list[2] == pytest.approx(0.02)

    float_array_end = cos_array.to_float_array()
    assert len(float_array_end) == 3
    assert float_array_end[0] == pytest.approx(1.0)
    assert float_array_end[1] == pytest.approx(0.1)
    assert float_array_end[2] == pytest.approx(0.02)

    # Arrays with null values.
    cos_array = COSArray([COSFloat(1.0), None, COSFloat(0.02)])  # type: ignore[list-item]
    assert cos_array.size() == 3
    assert cos_array.get(0) == COSFloat(1.0)
    assert cos_array.get(1) is None
    assert cos_array.get(2) == COSFloat(0.02)

    cos_number_float_list = cos_array.to_cos_number_float_list()
    assert len(cos_number_float_list) == 3
    assert cos_number_float_list[0] == pytest.approx(1.0)
    assert cos_number_float_list[1] is None
    assert cos_number_float_list[2] == pytest.approx(0.02)

    float_array_end = cos_array.to_float_array()
    # Per upstream: a null value is represented as 0 in the float array.
    assert float_array_end == pytest.approx([1.0, 0.0, 0.02])


def test_get_set_name() -> None:
    cos_array = COSArray()
    cos_array.grow_to_size(3)
    cos_array.set_name(0, "A")
    cos_array.set_name(1, "B")
    cos_array.set_name(2, "C")
    assert cos_array.size() == 3
    assert cos_array.get_name(0) == "A"
    assert cos_array.get_name(1) == "B"
    assert cos_array.get_name(2) == "C"
    assert cos_array.get_name(3, "NULL") == "NULL"
    assert cos_array.index_of(COSName.A) == 0  # type: ignore[attr-defined]
    assert cos_array.index_of(COSName.B) == 1  # type: ignore[attr-defined]
    assert cos_array.index_of(COSName.C) == 2  # type: ignore[attr-defined]
    assert cos_array.index_of(COSName.D) == -1  # type: ignore[attr-defined]
    cos_array.set_name(1, "D")
    assert cos_array.size() == 3
    assert cos_array.get_name(1) == "D"


def test_get_set_int() -> None:
    cos_array = COSArray()
    cos_array.grow_to_size(3)
    cos_array.set_int(0, 0)
    cos_array.set_int(1, 1)
    cos_array.set_int(2, 2)
    assert cos_array.size() == 3
    assert cos_array.get_int(0) == 0
    assert cos_array.get_int(1) == 1
    assert cos_array.get_int(2) == 2
    assert cos_array.get_int(3, 0) == 0
    assert cos_array.index_of(COSInteger.get(0)) == 0
    assert cos_array.index_of(COSInteger.get(1)) == 1
    assert cos_array.index_of(COSInteger.get(2)) == 2
    assert cos_array.index_of(COSInteger.get(3)) == -1
    cos_array.set_int(1, 3)
    assert cos_array.size() == 3
    assert cos_array.get_int(1) == 3


def test_get_set_string() -> None:
    cos_array = COSArray()
    cos_array.grow_to_size(3)
    cos_array.set_string(0, "Test1")
    cos_array.set_string(1, "Test2")
    cos_array.set_string(2, "Test3")
    assert cos_array.size() == 3
    assert cos_array.get_string(0) == "Test1"
    assert cos_array.get_string(1) == "Test2"
    assert cos_array.get_string(2) == "Test3"
    assert cos_array.get_string(3, "NULL") == "NULL"
    assert cos_array.index_of(COSString("Test1")) == 0
    assert cos_array.index_of(COSString("Test2")) == 1
    assert cos_array.index_of(COSString("Test3")) == 2
    assert cos_array.index_of(COSString("Test4")) == -1
    cos_array.set_string(1, "Test4")
    assert cos_array.size() == 3
    assert cos_array.get_string(1) == "Test4"


def test_remove() -> None:
    cos_array = COSArray.of_cos_integers([1, 2, 3, 4, 5, 6])
    cos_array.clear()
    assert cos_array.size() == 0

    cos_array = COSArray.of_cos_integers([1, 2, 3, 4, 5, 6])
    assert cos_array.remove_at(2) == COSInteger.get(3)
    # 1,2,4,5,6 should be left
    assert cos_array.size() == 5
    assert cos_array.get_int(0) == 1
    assert cos_array.get_int(2) == 4

    # 1,2,4,6 should be left
    assert cos_array.remove_object(COSInteger.get(5)) is True
    assert cos_array.size() == 4
    assert cos_array.get_int(0) == 1
    assert cos_array.get_int(2) == 4
    assert cos_array.get_int(3) == 6

    cos_array = COSArray.of_cos_integers([1, 2, 3, 4, 5, 6])
    cos_array.remove_all([COSInteger.get(3), COSInteger.get(4)])
    # 1,2,5,6 should be left
    assert cos_array.size() == 4
    assert cos_array.get_int(1) == 2
    assert cos_array.get_int(2) == 5

    cos_array = COSArray.of_cos_integers([1, 2, 3, 4, 5, 6])
    cos_array.retain_all([COSInteger.get(3), COSInteger.get(4)])
    # 3,4 should be left
    assert cos_array.size() == 2
    assert cos_array.get_int(0) == 3
    assert cos_array.get_int(1) == 4


def test_grow_to_size() -> None:
    cos_array = COSArray()
    assert cos_array.size() == 0
    cos_array.grow_to_size(2)
    # COSArray has 2 empty (null) slots
    assert cos_array.size() == 2
    # Already size 2 — nothing happens.
    cos_array.grow_to_size(2, COSInteger.get(0))
    assert cos_array.size() == 2
    # Increase size, fill the new elements with the given value.
    cos_array.grow_to_size(4, COSInteger.get(1))
    assert cos_array.size() == 4
    cos_number_integer_list = cos_array.to_cos_number_integer_list()
    assert len(cos_number_integer_list) == 4
    assert cos_number_integer_list[0] is None
    assert cos_number_integer_list[2] == 1
    assert cos_number_integer_list[3] == 1


def test_to_list() -> None:
    cos_array = COSArray.of_cos_integers([0, 1, 2, 3, 4, 5])
    items = cos_array.to_list()
    assert len(items) == 6
    assert items[0] == COSInteger.get(0)
    assert items[5] == COSInteger.get(5)


def test_pdfbox_collection_methods() -> None:
    cos_array = COSArray()
    assert cos_array.is_empty() is True

    cos_array.add_all([COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)])
    assert cos_array.size() == 3
    assert cos_array.index_of(COSInteger.get(2)) == 1
    assert cos_array.index_of(COSInteger.get(4)) == -1
    assert cos_array.to_list() == [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)]

    assert cos_array.remove_at(0) == COSInteger.get(1)
    assert cos_array.remove_object(COSInteger.get(3)) is True
    assert cos_array.to_list() == [COSInteger.get(2)]

    assert cos_array.remove_all([COSInteger.get(2)]) is True
    cos_array.add_all([COSInteger.get(4), COSInteger.get(5), COSInteger.get(6)])
    assert cos_array.retain_all([COSInteger.get(4), COSInteger.get(6)]) is True
    assert cos_array.to_cos_number_integer_list() == [4, 6]


def test_pdfbox_typed_accessors() -> None:
    cos_array = COSArray()
    cos_array.grow_to_size(6)
    cos_array.set_name(0, "A")
    cos_array.set_int(1, 2)
    cos_array.set_float(2, 3.5)
    cos_array.set_boolean(3, True)
    cos_array.set_string(4, "text")

    assert cos_array.get_name(0) == "A"
    assert cos_array.get_int(1) == 2
    assert cos_array.get_float(2) == pytest.approx(3.5)
    assert cos_array.get_boolean(3) is True
    assert cos_array.get_string(4) == "text"
    assert cos_array.get_name(8, "fallback") == "fallback"
    assert cos_array.get_int(8, 99) == 99

    cos_array.set_float_array([1.0, 2.5])
    assert cos_array.to_float_array() == pytest.approx([1.0, 2.5])
    assert cos_array.to_cos_number_float_list() == pytest.approx([1.0, 2.5])

    name_array = COSArray.of_cos_names(["A", "B"])
    assert name_array.to_cos_name_string_list() == ["A", "B"]
    string_array = COSArray.of_cos_strings(["A", "B"])
    assert string_array.to_cos_string_string_list() == ["A", "B"]


def test_pdfbox_object_resolution() -> None:
    target = COSString("target")
    cos_array = COSArray([COSBoolean.TRUE, target])  # type: ignore[attr-defined]

    assert cos_array.get_object(1) == target
    assert cos_array.index_of_object(target) == 1
