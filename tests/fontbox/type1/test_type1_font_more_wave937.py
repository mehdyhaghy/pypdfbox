from __future__ import annotations

from . import test_type1_font_more as more_tests


def test_wave937_make_font_installs_optional_encoding_charstrings_and_cache() -> None:
    encoding = {65: "A"}
    charstrings = {"A": object()}

    font = more_tests._make_font(encoding=encoding, charstrings=charstrings)

    assert font._t1.font["Encoding"] is encoding
    assert font._t1.font["CharStrings"] is charstrings
    assert font._charstrings is charstrings

