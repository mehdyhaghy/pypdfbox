"""Tests for ``pypdfbox.multipdf.k_cloner``."""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.multipdf.k_cloner import KCloner


class _StubPageTree:
    def index_of(self, _: object) -> int:
        return -1


def test_k_cloner_passthrough_scalar_without_splitter() -> None:
    cloner = KCloner(_StubPageTree())
    val = COSInteger(5)
    assert cloner.create_clone(val, None, None) is val


def test_k_cloner_passthrough_dict_without_splitter() -> None:
    cloner = KCloner(_StubPageTree())
    d = COSDictionary()
    assert cloner.create_clone(d, None, None) is d


def test_k_cloner_returns_none_for_none() -> None:
    cloner = KCloner(_StubPageTree())
    assert cloner.create_clone(None, None, None) is None
