"""Hand-written tests for the public ``CIDRange`` typed value class."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CIDRange
from pypdfbox.fontbox.cmap.cmap import _CIDRange


def test_cid_range_basic_attributes() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.get_code_length() == 1


def test_cid_range_map_int_within_range() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.map_int(0, 1) == 65
    assert rng.map_int(20, 1) == 85


def test_cid_range_map_int_out_of_range() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.map_int(21, 1) == -1
    assert rng.map_int(-1, 1) == -1


def test_cid_range_map_int_wrong_length() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.map_int(10, 2) == -1


def test_cid_range_map_bytes() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.map_bytes(b"\x00") == 65
    assert rng.map_bytes(b"\x14") == 85
    assert rng.map_bytes(b"\x1e") == -1  # 30, out of range
    assert rng.map_bytes(b"\x00\x0a") == -1  # wrong length


def test_cid_range_map_bytes_accepts_bytearray_and_memoryview() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.map_bytes(bytearray(b"\x05")) == 70
    assert rng.map_bytes(memoryview(b"\x05")) == 70


def test_cid_range_unmap() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng.unmap(65) == 0
    assert rng.unmap(85) == 20
    assert rng.unmap(64) == -1
    assert rng.unmap(86) == -1


def test_cid_range_extend_contiguous() -> None:
    rng = CIDRange(0, 10, 100, 2)
    assert rng.extend(11, 15, 111, 2) is True
    # Range now covers 0..15 -> 100..115
    assert rng.map_int(15, 2) == 115


def test_cid_range_extend_non_contiguous_rejected() -> None:
    rng = CIDRange(0, 10, 100, 2)
    # Gap (12 instead of 11) — must be refused.
    assert rng.extend(12, 20, 111, 2) is False
    # Wrong CID continuation.
    assert rng.extend(11, 20, 200, 2) is False
    # Wrong code length.
    assert rng.extend(11, 20, 111, 1) is False


def test_cid_range_two_byte_round_trip() -> None:
    rng = CIDRange(256, 280, 65, 2)
    assert rng.map_bytes(b"\x01\x00") == 65
    assert rng.map_bytes(b"\x01\x18") == 89  # 280 -> 89
    assert rng.unmap(65) == 256
    assert rng.unmap(89) == 280


def test_legacy_alias_points_at_public_class() -> None:
    """``_CIDRange`` is kept as an alias for backwards compatibility."""
    assert _CIDRange is CIDRange
    instance = _CIDRange(0, 5, 10, 1)
    assert isinstance(instance, CIDRange)


def test_cid_range_used_by_cmap_add_cid_range() -> None:
    """``CMap.add_cid_range`` stores ``CIDRange`` instances internally."""
    from pypdfbox.fontbox.cmap import CMap

    cmap = CMap("dummy")
    cmap.add_cid_range(b"\x00\x01", b"\x00\x05", 100)
    assert cmap.to_cid_with_length(0x0001, 2) == 100
    assert cmap.to_cid_with_length(0x0005, 2) == 104
    assert cmap.to_cid_with_length(0x0006, 2) == 0


@pytest.mark.parametrize(
    ("frm", "to", "unicode_", "length"),
    [
        (0, 0xFF, 1, 1),
        (0, 0xFFFF, 1, 2),
        (0, 0xFFFFFF, 1, 3),
    ],
)
def test_cid_range_various_lengths(
    frm: int, to: int, unicode_: int, length: int
) -> None:
    rng = CIDRange(frm, to, unicode_, length)
    assert rng.get_code_length() == length
    assert rng.map_int(frm, length) == unicode_
    assert rng.map_int(to, length) == unicode_ + (to - frm)


# ---------- dunder helpers ----------


def test_cid_range_repr_includes_field_values() -> None:
    text = repr(CIDRange(0, 20, 65, 1))
    assert "from=0" in text
    assert "to=20" in text
    assert "unicode=65" in text
    assert "code_length=1" in text


def test_cid_range_equality_and_hash() -> None:
    a = CIDRange(0, 20, 65, 1)
    b = CIDRange(0, 20, 65, 1)
    c = CIDRange(0, 21, 65, 1)
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    # Usable as a set element.
    assert {a, b, c} == {a, c}


def test_cid_range_equality_against_other_types() -> None:
    rng = CIDRange(0, 20, 65, 1)
    assert rng != "not a range"
    assert rng != 42
    assert rng != None  # noqa: E711 — explicit equality, not identity

