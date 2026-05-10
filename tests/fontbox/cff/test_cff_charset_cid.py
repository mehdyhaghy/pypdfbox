"""Hand-written tests for :class:`CFFCharsetCID`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff import CFFCharsetCID


def test_is_cid_font_true() -> None:
    assert CFFCharsetCID().is_cid_font() is True


def test_add_and_get_cid() -> None:
    charset = CFFCharsetCID()
    charset.add_cid(gid=5, cid=123)
    charset.add_cid(gid=6, cid=456)

    assert charset.get_gid_for_cid(123) == 5
    assert charset.get_gid_for_cid(456) == 6
    assert charset.get_cid_for_gid(5) == 123
    assert charset.get_cid_for_gid(6) == 456


def test_missing_returns_zero() -> None:
    charset = CFFCharsetCID()
    assert charset.get_gid_for_cid(999) == 0
    assert charset.get_cid_for_gid(999) == 0


@pytest.mark.parametrize(
    "method,args",
    [
        ("add_sid", (0, 0, ".notdef")),
        ("get_sid_for_gid", (0,)),
        ("get_gid_for_sid", (0,)),
        ("get_sid", (".notdef",)),
        ("get_name_for_gid", (0,)),
    ],
)
def test_type1_methods_raise(method: str, args: tuple) -> None:
    charset = CFFCharsetCID()
    with pytest.raises(RuntimeError, match="Not a Type 1-equivalent font"):
        getattr(charset, method)(*args)
