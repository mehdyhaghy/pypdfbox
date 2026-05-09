from __future__ import annotations

from tests.fontbox.cff import test_type1_char_string as type1_mod


def test_wave1213_commands_only_returns_first_tuple_entries() -> None:
    assert type1_mod._commands_only(
        [
            ("moveto", 10, 20),
            ("lineto", 30, 40),
            ("closepath",),
        ]
    ) == ["moveto", "lineto", "closepath"]
