from __future__ import annotations

import pytest

from pypdfbox.cos import COSInteger


def test_value_round_trips() -> None:
    i = COSInteger(42)
    assert i.value == 42
    assert i.int_value() == 42
    assert i.long_value() == 42
    assert i.float_value() == 42.0


def test_negative_and_large() -> None:
    assert COSInteger(-1).value == -1
    assert COSInteger(2**60).value == 2**60


def test_small_int_cache_returns_same_instance() -> None:
    a = COSInteger.get(0)
    b = COSInteger.get(0)
    assert a is b
    assert COSInteger.get(-100) is COSInteger.get(-100)
    assert COSInteger.get(256) is COSInteger.get(256)


def test_outside_cache_range_returns_new_instance() -> None:
    a = COSInteger.get(257)
    b = COSInteger.get(257)
    assert a is not b
    assert a == b


def test_predefined_constants() -> None:
    assert COSInteger.ZERO.value == 0  # type: ignore[attr-defined]
    assert COSInteger.ONE.value == 1  # type: ignore[attr-defined]
    assert COSInteger.ZERO is COSInteger.get(0)  # type: ignore[attr-defined]


def test_bool_is_rejected() -> None:
    # Python booleans subclass int — explicitly reject to avoid silent
    # COSInteger(True) → integer(1) confusion.
    with pytest.raises(TypeError):
        COSInteger(True)


def test_get_rejects_bool() -> None:
    # The factory goes through a cache for 0/1, so it must enforce the same
    # type contract as the constructor before checking cached integers.
    with pytest.raises(TypeError):
        COSInteger.get(True)
    with pytest.raises(TypeError):
        COSInteger.get(False)


def test_equality_and_hashing() -> None:
    assert COSInteger(7) == COSInteger(7)
    assert hash(COSInteger(7)) == hash(COSInteger(7))


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    i = COSInteger(99)
    i.accept(v)
    assert v.calls == [("integer", i)]
