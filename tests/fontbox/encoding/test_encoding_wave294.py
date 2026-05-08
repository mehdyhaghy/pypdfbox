from __future__ import annotations

from pypdfbox.fontbox.encoding import Encoding


class _Wave294Encoding(Encoding):
    def __init__(self) -> None:
        super().__init__()
        self.add(1, "one")
        self.add(65, "A")

    def get_encoding_name(self) -> str:
        return "Wave294"


def test_get_name_rejects_bool_code_even_when_integer_key_exists() -> None:
    enc = _Wave294Encoding()

    assert enc.get_name(True) == ".notdef"
    assert enc.get_name(1) == "one"


def test_get_name_returns_notdef_for_malformed_code_inputs() -> None:
    enc = _Wave294Encoding()

    assert enc.get_name("65") == ".notdef"
    assert enc.get_name([65]) == ".notdef"


def test_get_code_returns_none_for_malformed_name_inputs() -> None:
    enc = _Wave294Encoding()

    assert enc.get_code(None) is None
    assert enc.get_code(65) is None
    assert enc.get_code(["A"]) is None
    assert enc.get_code("A") == 65
