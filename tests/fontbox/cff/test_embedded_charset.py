"""Hand-written tests for :class:`EmbeddedCharset`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff import CFFCharset, EmbeddedCharset


def test_cid_variant_delegates_to_cid_storage() -> None:
    charset = EmbeddedCharset(is_cid_font=True)
    assert isinstance(charset, CFFCharset)
    assert charset.is_cid_font() is True

    charset.add_cid(0, 0)
    charset.add_cid(7, 99)
    assert charset.get_gid_for_cid(99) == 7
    assert charset.get_cid_for_gid(7) == 99


def test_type1_variant_delegates_to_type1_storage() -> None:
    charset = EmbeddedCharset(is_cid_font=False)
    assert charset.is_cid_font() is False

    charset.add_sid(3, 21, "X")
    assert charset.get_name_for_gid(3) == "X"
    assert charset.get_sid_for_gid(3) == 21
    assert charset.get_gid_for_sid(21) == 3
    assert charset.get_sid("X") == 21


def test_cid_variant_rejects_sid_calls() -> None:
    charset = EmbeddedCharset(is_cid_font=True)
    with pytest.raises(RuntimeError):
        charset.add_sid(0, 0, ".notdef")
    with pytest.raises(RuntimeError):
        charset.get_sid_for_gid(0)
    with pytest.raises(RuntimeError):
        charset.get_name_for_gid(0)


def test_type1_variant_rejects_cid_calls() -> None:
    charset = EmbeddedCharset(is_cid_font=False)
    with pytest.raises(RuntimeError):
        charset.add_cid(0, 0)
    with pytest.raises(RuntimeError):
        charset.get_gid_for_cid(0)
    with pytest.raises(RuntimeError):
        charset.get_cid_for_gid(0)
