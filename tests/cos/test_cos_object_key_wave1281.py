"""Wave 1281 parity round-out: COSObjectKey port additions.

Covers the methods that needed to be added on the existing class to
match upstream Java API surface — ``compute_internal_hash``,
``get_internal_hash``, ``get_number`` / ``get_generation`` /
``get_stream_index``, ``compare_to``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey


def test_compute_internal_hash_matches_upstream_packing() -> None:
    # Upstream packs ``num << 16 | gen`` into a long.
    h = COSObjectKey.compute_internal_hash(5, 3)
    assert h == (5 << 16) | 3


def test_get_internal_hash_roundtrip() -> None:
    k = COSObjectKey(42, 7)
    assert k.get_internal_hash() == (42 << 16) | 7


def test_get_number_and_generation_accessors() -> None:
    k = COSObjectKey(123, 1)
    assert k.get_number() == 123
    assert k.get_generation() == 1


def test_stream_index_default_minus_one() -> None:
    k = COSObjectKey(5, 0)
    assert k.get_stream_index() == -1


def test_stream_index_supplied() -> None:
    k = COSObjectKey(5, 0, 9)
    assert k.get_stream_index() == 9
    # Generation/number unaffected.
    assert k.get_generation() == 0
    assert k.get_number() == 5


def test_compare_to_orders_by_packed_value() -> None:
    a = COSObjectKey(1, 0)
    b = COSObjectKey(1, 1)
    c = COSObjectKey(2, 0)
    assert a.compare_to(b) < 0
    assert b.compare_to(a) > 0
    assert a.compare_to(a) == 0
    assert c.compare_to(b) > 0


def test_negative_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        COSObjectKey(-1, 0)
    with pytest.raises(ValueError):
        COSObjectKey(1, -2)


def test_repr_includes_index() -> None:
    assert "index=4" in repr(COSObjectKey(2, 0, 4))


def test_str_pdf_indirect_syntax() -> None:
    assert str(COSObjectKey(7, 0)) == "7 0 R"
