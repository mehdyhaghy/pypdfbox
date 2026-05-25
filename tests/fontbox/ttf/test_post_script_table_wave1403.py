"""Wave 1403 — branch round-out for :class:`PostScriptTable`.

Closes the partial arc ``[117,113]`` — the ``name is not None`` False
branch inside :meth:`_read_format_2_5`: when a glyph's index is in the
valid Mac-glyph range but the WGL4 name lookup yields ``None``, the slot
is left blank and the loop continues.

The range guard at line 115 means ``wgl4_names.get_glyph_name`` always
returns a real string for in-range indices, so the only way to exercise
the defensive ``None`` fall-through is to monkeypatch the lookup — a
test-only override that leaves production behaviour untouched.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf import post_script_table as pst_module
from pypdfbox.fontbox.ttf.post_script_table import PostScriptTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _StubTTF:
    def __init__(self, num_glyphs: int = 0, name: str = "TestFont") -> None:
        self.num_glyphs = num_glyphs
        self.name = name

    def get_name(self) -> str:
        return self.name

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs


def _pack_fixed(whole: int, frac: int = 0) -> bytes:
    return struct.pack(">hH", whole, frac)


def _pack_header(fmt_whole: int, fmt_frac: int = 0) -> bytes:
    return (
        _pack_fixed(fmt_whole, fmt_frac)
        + _pack_fixed(0, 0)
        + struct.pack(">hh", -100, 50)
        + struct.pack(">IIIII", 0, 0, 0, 0, 0)
    )


def test_format_2_5_none_glyph_name_leaves_slot_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid in-range index whose WGL4 name resolves to ``None`` takes
    the ``name is not None`` False arc ([117,113]); the name slot stays
    the empty-string default."""
    # gid 0 -> 0 + 1 + 0 = 1 (a valid Mac-glyph index).
    body = struct.pack(">b", 0)
    blob = _pack_header(2, fmt_frac=0x8000) + body
    # Force the in-range lookup to report no name.
    monkeypatch.setattr(pst_module.wgl4_names, "get_glyph_name", lambda _index: None)

    table = PostScriptTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=1), MemoryTTFDataStream(blob))

    names = table.get_glyph_names()
    assert names == [""]
