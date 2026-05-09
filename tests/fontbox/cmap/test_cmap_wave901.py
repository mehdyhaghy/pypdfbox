from __future__ import annotations

from pypdfbox.fontbox.cmap import CMap


def test_wave901_use_cmap_raises_child_max_code_length() -> None:
    parent = CMap("parent")
    parent._max_code_length = 4  # noqa: SLF001 - isolate use_cmap fallback guard

    child = CMap("child")
    child.add_codespace_range(b"\x20\x00", b"\x20\xff")

    assert child.get_min_code_length() == 2
    assert child.get_max_code_length() == 2

    child.use_cmap(parent)

    assert child.get_min_code_length() == 2
    assert child.get_max_code_length() == 4


def test_wave901_use_cmap_lowers_child_min_code_length() -> None:
    parent = CMap("parent")
    parent._min_code_length = 1  # noqa: SLF001 - isolate use_cmap fallback guard

    child = CMap("child")
    child.add_codespace_range(b"\x20\x00", b"\x20\xff")

    assert child.get_min_code_length() == 2
    assert child.get_max_code_length() == 2

    child.use_cmap(parent)

    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 2
