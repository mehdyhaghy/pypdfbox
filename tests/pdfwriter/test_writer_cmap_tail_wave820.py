from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.fontbox.cmap import CMap
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_xref_entry_le_ge_compare_by_object_number_only() -> None:
    entry = COSWriterXRefEntry(offset=99, key=COSObjectKey(4, 7), free=True)
    same_object = COSWriterXRefEntry(offset=1, key=COSObjectKey(4, 0))
    later = COSWriterXRefEntry(offset=0, key=COSObjectKey(8, 0))

    assert entry <= same_object
    assert entry >= same_object
    assert entry <= later
    assert later >= entry


def test_use_cmap_expands_code_length_bounds_from_parent() -> None:
    parent = CMap("parent")
    parent.add_codespace_range(b"\x00", b"\x7f")
    parent.add_codespace_range(b"\x81\x02\x00", b"\x81\x02\xff")
    parent.add_base_font_character(b"\x81\x02\x03", "long")

    child = CMap("child")
    child.add_codespace_range(b"\x81\x40", b"\x81\xff")

    child.use_cmap(parent)

    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 3
    assert child.read_code(b"\x00\x81\x02\x03") == (0, 1)
    assert child.read_code(b"\x81\x02\x03") == (0x810203, 3)
    assert child.get_codes_from_unicode("long") == b"\x81\x02\x03"
