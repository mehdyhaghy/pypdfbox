"""Hand-written tests for :class:`CompoundCharacterTokenizer`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import CompoundCharacterTokenizer


def test_rejects_empty_compound_words() -> None:
    with pytest.raises(ValueError):
        CompoundCharacterTokenizer([])


def test_rejects_words_without_separator() -> None:
    with pytest.raises(ValueError):
        CompoundCharacterTokenizer(["84_93"])
    with pytest.raises(ValueError):
        CompoundCharacterTokenizer(["_84_93"])
    with pytest.raises(ValueError):
        CompoundCharacterTokenizer(["84_93_"])


def test_tokenize_when_no_match() -> None:
    tokenizer = CompoundCharacterTokenizer(["_201_", "_202_"])
    assert tokenizer.tokenize("_100_101_102_") == ["_100_101_102_"]


def test_tokenize_single_compound_in_middle() -> None:
    tokenizer = CompoundCharacterTokenizer(["_67_112_96_"])
    assert tokenizer.tokenize("_94_67_112_96_112_91_103_") == [
        "_94",
        "_67_112_96_",
        "_112_91_103_",
    ]
