from __future__ import annotations

from typing import Any

from fontTools.misc.psCharStrings import T2CharString  # type: ignore[import-untyped]

from pypdfbox.fontbox.cff.type2_char_string import Type2CharString


def test_list_constructor_preserves_sequence_for_parity_accessors() -> None:
    program: list[Any] = [500, 10, 20, "rmoveto", "endchar"]

    cs = Type2CharString(None, "F", "A", 3, program)

    assert cs.is_sequence_empty() is False
    assert cs.get_last_sequence_entry() == "endchar"


def test_list_constructor_stringifies_preserved_command_objects() -> None:
    class FakeCmd:
        def __init__(self, name: str) -> None:
            self.name = name

    cs = Type2CharString(
        None,
        "F",
        "A",
        3,
        [500, 10, 20, FakeCmd("rmoveto"), FakeCmd("endchar")],
    )

    text = str(cs)

    assert text == "[500  10  20  rmoveto  endchar]"


def test_string_falls_back_to_underlying_fonttools_program() -> None:
    underlying = T2CharString(program=[500, 10, 20, "rmoveto", "endchar"])
    cs = Type2CharString(None, "F", "A", 3, underlying)

    assert str(cs) == "[500  10  20  rmoveto  endchar]"
