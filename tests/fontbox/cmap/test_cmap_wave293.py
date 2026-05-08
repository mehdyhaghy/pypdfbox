from __future__ import annotations

from pypdfbox.fontbox.cmap.cmap import CMap


def test_read_code_memoryview_offset_uses_codespace_ranges() -> None:
    cmap = CMap("wave293")
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x81\x40", b"\x81\xff")

    assert cmap.read_code(memoryview(b"\x00\x81\x41"), 1) == (0x8141, 2)


def test_to_unicode_bytes_accepts_memoryview_without_copy_visible_behavior() -> None:
    cmap = CMap("wave293")
    cmap.add_base_font_character(b"\x81\x41", "A")

    assert cmap.to_unicode_bytes(memoryview(b"\x81\x41")) == "A"
