from __future__ import annotations

from pypdfbox.cos import COSInteger
from pypdfbox.cos.cos_object_key import COSObjectKey


def test_default_flags() -> None:
    i = COSInteger(1)
    assert not i.is_direct()
    assert not i.is_needs_to_be_updated()


def test_set_direct_flag() -> None:
    i = COSInteger(1)
    i.set_direct(True)
    assert i.is_direct()
    i.set_direct(False)
    assert not i.is_direct()


def test_set_needs_to_be_updated_flag() -> None:
    i = COSInteger(1)
    i.set_needs_to_be_updated(True)
    assert i.is_needs_to_be_updated()
    i.set_needs_to_be_updated(False)
    assert not i.is_needs_to_be_updated()


def test_get_cos_object_returns_self() -> None:
    i = COSInteger(7)
    assert i.get_cos_object() is i


def test_default_key_is_none() -> None:
    i = COSInteger(1)
    assert i.get_key() is None


def test_set_key_round_trips() -> None:
    i = COSInteger(1)
    key = COSObjectKey(12, 0)
    i.set_key(key)
    assert i.get_key() is key


def test_set_key_none_clears() -> None:
    i = COSInteger(1)
    i.set_key(COSObjectKey(3, 0))
    i.set_key(None)
    assert i.get_key() is None
