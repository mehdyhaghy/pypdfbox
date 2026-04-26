from __future__ import annotations

import io

from pypdfbox.fontbox.cmap import CMap, CodespaceRange
from pypdfbox.io import RandomAccessReadBuffer


def test_empty_cmap_read_code_reads_one_byte_without_crashing() -> None:
    cmap = CMap()
    assert cmap.read_code(RandomAccessReadBuffer(b"\x7f")) == 0x7F
    assert cmap.read_code(io.BytesIO(b"")) == 0


def test_codespace_and_unicode_mapping_round_trip() -> None:
    cmap = CMap()
    cmap.add_codespace_range(CodespaceRange(b"\x00", b"\xff"))
    cmap.add_base_font_character(b"A", "Alpha")

    assert cmap.read_code(io.BytesIO(b"A")) == 0x41
    assert cmap.to_unicode(0x41) == "Alpha"
    assert cmap.to_unicode_bytes(b"A") == "Alpha"
    assert cmap.get_codes_from_unicode("Alpha") == b"A"


def test_cid_mapping_and_usecmap_copy() -> None:
    base = CMap("Base")
    base.add_codespace_range(b"\x00\x00", b"\xff\xff")
    base.add_cid_mapping(b"\x00\x20", 32)

    child = CMap("Child")
    child.use_cmap(base)

    assert child.read_cid(io.BytesIO(b"\x00\x20")) == 32
