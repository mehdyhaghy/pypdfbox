"""Hand-written tests for ``PrivateType1CharStringReader``."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.private_type1_char_string_reader import (
    PrivateType1CharStringReader,
)


def test_abstract_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        PrivateType1CharStringReader()  # type: ignore[abstract]


def test_subclass_must_implement_method() -> None:
    class Empty(PrivateType1CharStringReader):
        pass

    with pytest.raises(TypeError):
        Empty()  # type: ignore[abstract]


def test_concrete_subclass_returns_type1_char_string() -> None:
    sentinel = object()

    class Reader(PrivateType1CharStringReader):
        def get_type1_char_string(self, name: str) -> object:  # type: ignore[override]
            assert name == "A"
            return sentinel

    reader = Reader()
    assert reader.get_type1_char_string("A") is sentinel
