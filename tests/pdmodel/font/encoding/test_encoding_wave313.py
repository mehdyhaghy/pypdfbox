from __future__ import annotations

from pypdfbox.pdmodel.font.encoding import BuiltInEncoding, WinAnsiEncoding


def test_wave313_get_name_rejects_bool_code_even_when_integer_key_exists() -> None:
    enc = BuiltInEncoding({1: "one", 65: "A"})

    assert enc.get_name(True) == ".notdef"
    assert enc.to_glyph_name(True) == ".notdef"
    assert enc.get_name(1) == "one"


def test_wave313_lookup_helpers_tolerate_malformed_inputs() -> None:
    enc = WinAnsiEncoding.INSTANCE

    assert enc.get_name("65") == ".notdef"
    assert enc.to_glyph_name([65]) == ".notdef"
    assert enc.get_code(["A"]) is None
    assert enc.contains_name(["A"]) is False
    assert enc.contains_code(True) is False
    assert enc.get_code("A") == 65
