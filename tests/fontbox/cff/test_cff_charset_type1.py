"""Hand-written tests for :class:`CFFCharsetType1`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff import CFFCharsetType1


def test_is_cid_font_false() -> None:
    assert CFFCharsetType1().is_cid_font() is False


def test_add_and_lookup_sid() -> None:
    charset = CFFCharsetType1()
    charset.add_sid(gid=0, sid=0, name=".notdef")
    charset.add_sid(gid=1, sid=1, name="space")
    charset.add_sid(gid=2, sid=42, name="A")

    assert charset.get_sid_for_gid(0) == 0
    assert charset.get_sid_for_gid(2) == 42
    assert charset.get_gid_for_sid(42) == 2
    assert charset.get_sid("A") == 42
    assert charset.get_name_for_gid(2) == "A"


def test_missing_lookups_default_zero_or_none() -> None:
    charset = CFFCharsetType1()
    assert charset.get_sid_for_gid(99) == 0
    assert charset.get_gid_for_sid(99) == 0
    assert charset.get_sid("nope") == 0
    assert charset.get_name_for_gid(99) is None


@pytest.mark.parametrize(
    "method,args",
    [("add_cid", (0, 0)), ("get_gid_for_cid", (0,)), ("get_cid_for_gid", (0,))],
)
def test_cid_methods_raise(method: str, args: tuple) -> None:
    charset = CFFCharsetType1()
    with pytest.raises(RuntimeError, match="Not a CIDFont"):
        getattr(charset, method)(*args)
