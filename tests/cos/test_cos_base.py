from __future__ import annotations

from pypdfbox.cos import COSInteger


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
