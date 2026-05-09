"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/UnmodifiableCOSDictionaryTest.java
"""

from __future__ import annotations

import datetime as dt
import operator
from collections.abc import Callable

import pytest

from pypdfbox.cos import COSDictionary, COSName


def _readonly() -> COSDictionary:
    return COSDictionary().as_unmodifiable_dictionary()


def _assert_readonly(action: Callable[[], object]) -> None:
    with pytest.raises(TypeError, match="unmodifiable"):
        action()


def test_unmodifiable_cos_dictionary() -> None:
    unmodifiable = _readonly()

    _assert_readonly(unmodifiable.clear)
    _assert_readonly(lambda: unmodifiable.remove_item(COSName.A))
    _assert_readonly(lambda: unmodifiable.add_all(COSDictionary()))
    _assert_readonly(lambda: unmodifiable.set_flag(COSName.A, 0, True))
    _assert_readonly(lambda: unmodifiable.set_needs_to_be_updated(True))


def test_unmodifiable_view_is_live() -> None:
    dictionary = COSDictionary()
    unmodifiable = dictionary.as_unmodifiable_dictionary()

    dictionary.set_name(COSName.A, "A")

    assert unmodifiable.get_name(COSName.A) == "A"
    assert unmodifiable.contains_key("A")


def test_set_item() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_item(COSName.A, COSName.A))
    _assert_readonly(lambda: unmodifiable.set_item("A", COSName.A))
    _assert_readonly(lambda: operator.setitem(unmodifiable, COSName.A, COSName.A))


def test_set_boolean() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_boolean(COSName.A, True))
    _assert_readonly(lambda: unmodifiable.set_boolean("A", True))


def test_set_name() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_name(COSName.A, "A"))
    _assert_readonly(lambda: unmodifiable.set_name("A", "A"))


def test_set_date() -> None:
    unmodifiable = _readonly()
    date = dt.datetime(2026, 5, 9, 12, 34, 56)

    _assert_readonly(lambda: unmodifiable.set_date(COSName.A, date))
    _assert_readonly(lambda: unmodifiable.set_date("A", date))


def test_set_embedded_date() -> None:
    unmodifiable = _readonly()
    date = dt.datetime(2026, 5, 9, 12, 34, 56)

    _assert_readonly(lambda: unmodifiable.set_embedded_date(COSName.PARAMS, COSName.A, date))


def test_set_string() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_string(COSName.A, "A"))
    _assert_readonly(lambda: unmodifiable.set_string("A", "A"))


def test_set_embedded_string() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_embedded_string(COSName.PARAMS, COSName.A, "A"))


def test_set_int() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_int(COSName.A, 0))
    _assert_readonly(lambda: unmodifiable.set_int("A", 0))


def test_set_embedded_int() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_embedded_int(COSName.PARAMS, COSName.A, 0))


def test_set_long() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_long(COSName.A, 0))
    _assert_readonly(lambda: unmodifiable.set_long("A", 0))


def test_set_float() -> None:
    unmodifiable = _readonly()

    _assert_readonly(lambda: unmodifiable.set_float(COSName.A, 0.0))
    _assert_readonly(lambda: unmodifiable.set_float("A", 0.0))
