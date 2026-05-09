from __future__ import annotations

from pypdfbox.fontbox.cmap import CMap


def test_use_cmap_updates_min_and_max_code_lengths_from_parent() -> None:
    parent = CMap("parent")
    parent.add_codespace_range(b"\x00", b"\x7f")
    parent.add_codespace_range(b"\x81\x00\x00\x00", b"\x81\xff\xff\xff")

    child = CMap("child")
    child.add_codespace_range(b"\x20\x00", b"\x20\xff")

    assert child.get_min_code_length() == 2
    assert child.get_max_code_length() == 2

    child.use_cmap(parent)

    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 4
