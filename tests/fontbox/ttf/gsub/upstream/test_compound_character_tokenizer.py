"""Upstream-ported tests for :class:`CompoundCharacterTokenizer`.

Translated from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/CompoundCharacterTokenizerTest.java``
upstream Apache PDFBox 3.0.x.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import CompoundCharacterTokenizer


def test_tokenize_happy_path_2() -> None:
    tokenizer = CompoundCharacterTokenizer({"_84_93_", "_104_82_", "_104_87_"})
    tokens = tokenizer.tokenize("_84_112_93_104_82_61_96_102_93_104_87_110_")
    assert tokens == [
        "_84_112_93",
        "_104_82_",
        "_61_96_102_93",
        "_104_87_",
        "_110_",
    ]


def test_tokenize_happy_path_3() -> None:
    tokenizer = CompoundCharacterTokenizer({"_67_112_96_", "_74_112_76_"})
    tokens = tokenizer.tokenize("_67_112_96_103_93_108_93_")
    assert tokens == ["_67_112_96_", "_103_93_108_93_"]


def test_tokenize_happy_path_4() -> None:
    tokenizer = CompoundCharacterTokenizer({"_67_112_96_", "_74_112_76_"})
    tokens = tokenizer.tokenize("_94_67_112_96_112_91_103_")
    assert tokens == ["_94", "_67_112_96_", "_112_91_103_"]


def test_tokenize_happy_path_5() -> None:
    tokenizer = CompoundCharacterTokenizer({"_67_112_", "_76_112_"})
    tokens = tokenizer.tokenize("_94_167_112_91_103_")
    assert tokens == ["_94_167_112_91_103_"]


def test_tokenize_happy_path_6() -> None:
    tokenizer = CompoundCharacterTokenizer(
        ["_100_", "_101_", "_102_", "_103_", "_104_"]
    )
    tokens = tokenizer.tokenize("_100_101_102_103_104_")
    assert tokens == ["_100_", "_101_", "_102_", "_103_", "_104_"]


def test_tokenize_happy_path_7() -> None:
    tokenizer = CompoundCharacterTokenizer(["_100_101_", "_102_", "_103_104_"])
    tokens = tokenizer.tokenize("_100_101_102_103_104_")
    assert tokens == ["_100_101_", "_102_", "_103_104_"]


def test_tokenize_happy_path_8() -> None:
    tokenizer = CompoundCharacterTokenizer(
        ["_100_101_102_", "_101_102_", "_103_104_"]
    )
    tokens = tokenizer.tokenize("_100_101_102_103_104_")
    assert tokens == ["_100_101_102_", "_103_104_"]


def test_tokenize_happy_path_9() -> None:
    # Upstream test sends the duplicate via ``HashSet``. We mirror the
    # same input through a list with a duplicate entry — the
    # tokenizer doesn't care about uniqueness inside its compiled
    # alternation regex.
    tokenizer = CompoundCharacterTokenizer(["_101_102_", "_101_102_"])
    tokens = tokenizer.tokenize("_100_101_102_103_104_")
    assert tokens == ["_100", "_101_102_", "_103_104_"]


def test_tokenize_happy_path_10() -> None:
    tokenizer = CompoundCharacterTokenizer({"_201_", "_202_"})
    tokens = tokenizer.tokenize("_100_101_102_103_104_")
    assert tokens == ["_100_101_102_103_104_"]
