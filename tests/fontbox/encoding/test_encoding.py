from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding import Encoding


class _DummyEncoding(Encoding):
    def __init__(self) -> None:
        super().__init__()
        self.add(65, "A")
        self.add(66, "B")

    def get_encoding_name(self) -> str:
        return "Dummy"


class _DummyEncodingDup(Encoding):
    def __init__(self) -> None:
        super().__init__()
        self.add(65, "A")
        # second mapping for same name; add() must NOT overwrite reverse
        self.add(200, "A")

    def get_encoding_name(self) -> str:
        return "DummyDup"


def test_get_name_returns_mapping() -> None:
    enc = _DummyEncoding()
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"


def test_get_name_returns_notdef_for_unmapped() -> None:
    enc = _DummyEncoding()
    assert enc.get_name(0) == ".notdef"
    assert enc.get_name(999) == ".notdef"


def test_get_code_returns_mapping_or_none() -> None:
    enc = _DummyEncoding()
    assert enc.get_code("A") == 65
    assert enc.get_code("B") == 66
    assert enc.get_code("missing") is None


def test_get_codes_returns_fresh_snapshot() -> None:
    enc = _DummyEncoding()
    a = enc.get_codes()
    b = enc.get_codes()
    assert a == b
    assert a is not b
    a[1234] = "MUTATED"
    assert 1234 not in enc.get_codes()


def test_contains_handles_codes_and_names() -> None:
    enc = _DummyEncoding()
    assert 65 in enc
    assert 999 not in enc
    assert "A" in enc
    assert "missing" not in enc
    # bool should not be treated as int
    assert (True in enc) is False


def test_add_preserves_existing_reverse_mapping() -> None:
    enc = _DummyEncodingDup()
    # forward map: both codes map to "A"
    assert enc.get_name(65) == "A"
    assert enc.get_name(200) == "A"
    # reverse: first add wins
    assert enc.get_code("A") == 65


def test_overwrite_replaces_reverse_mapping() -> None:
    class E(Encoding):
        def __init__(self) -> None:
            super().__init__()
            self.add(65, "A")
            self.overwrite(65, "X")

        def get_encoding_name(self) -> str:
            return "E"

    enc = E()
    assert enc.get_name(65) == "X"
    assert enc.get_code("X") == 65
    assert enc.get_code("A") is None


def test_get_encoding_name_default_raises() -> None:
    class E(Encoding):
        def __init__(self) -> None:
            super().__init__()

    with pytest.raises(NotImplementedError):
        E().get_encoding_name()


def test_add_character_encoding_alias_matches_add() -> None:
    # ``add_character_encoding`` is the snake_case spelling of upstream
    # fontbox base ``Encoding.addCharacterEncoding``.
    class E(Encoding):
        def __init__(self) -> None:
            super().__init__()
            self.add_character_encoding(65, "A")
            self.add_character_encoding(66, "B")

        def get_encoding_name(self) -> str:
            return "E"

    enc = E()
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"
    assert enc.get_code("A") == 65
    assert enc.get_code("B") == 66
