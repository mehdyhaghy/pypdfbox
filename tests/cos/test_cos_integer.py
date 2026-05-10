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


def test_to_string_matches_upstream_format() -> None:
    # Upstream COSInteger.toString() returns "COSInt{<value>}".
    assert COSInteger(42).to_string() == "COSInt{42}"
    assert COSInteger(-1).to_string() == "COSInt{-1}"
    assert COSInteger(0).to_string() == "COSInt{0}"


def test_hash_code_matches_long_recipe() -> None:
    # Java: (int)(value ^ (value >> 32)). For values that fit in 32 bits
    # the high half is 0 (or -1 for negatives) so the bottom half dominates.
    assert COSInteger(0).hash_code() == 0
    assert COSInteger(1).hash_code() == 1
    # 0xFFFFFFFF -> top half 0, bottom half 0xFFFFFFFF -> -1 (signed int32)
    assert COSInteger(0xFFFFFFFF).hash_code() == -1
    # Equal values yield equal hash codes.
    assert COSInteger(12345).hash_code() == COSInteger(12345).hash_code()


def test_get_invalid_factory() -> None:
    sentinel_max = COSInteger.get_invalid(True)
    sentinel_min = COSInteger.get_invalid(False)
    assert sentinel_max.long_value() == 2**63 - 1
    assert sentinel_min.long_value() == -(2**63)
    assert sentinel_max.is_valid() is False
    assert sentinel_min.is_valid() is False
    # Each call returns a fresh instance (matches Java private factory).
    assert COSInteger.get_invalid(True) is not COSInteger.get_invalid(True)


def test_out_of_range_sentinels_built_via_get_invalid() -> None:
    # Module-level sentinels carry the same shape as get_invalid output.
    assert COSInteger.OUT_OF_RANGE_MAX.long_value() == 2**63 - 1  # type: ignore[attr-defined]
    assert COSInteger.OUT_OF_RANGE_MIN.long_value() == -(2**63)  # type: ignore[attr-defined]
    assert not COSInteger.OUT_OF_RANGE_MAX.is_valid()  # type: ignore[attr-defined]
    assert not COSInteger.OUT_OF_RANGE_MIN.is_valid()  # type: ignore[attr-defined]
