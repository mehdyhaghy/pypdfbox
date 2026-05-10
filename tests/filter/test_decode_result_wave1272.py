"""Wave 1272: parity coverage for ``DecodeResult.get_jpxs_mask`` /
``set_jpxs_mask`` snake-case spelling aliases."""

from __future__ import annotations

from pypdfbox.filter.decode_result import DecodeResult


def test_get_jpxs_mask_initially_none() -> None:
    assert DecodeResult().get_jpxs_mask() is None


def test_set_jpxs_mask_round_trips() -> None:
    sentinel = object()
    result = DecodeResult()
    result.set_jpxs_mask(sentinel)
    assert result.get_jpxs_mask() is sentinel
    # ``set_jpxs_mask`` aliases ``set_jpx_smask``, so the underlying field
    # is the same — both spellings observe the same value.
    assert result.get_jpx_smask() is sentinel


def test_set_jpx_smask_visible_through_jpxs_alias() -> None:
    sentinel = object()
    result = DecodeResult()
    result.set_jpx_smask(sentinel)
    assert result.get_jpxs_mask() is sentinel
