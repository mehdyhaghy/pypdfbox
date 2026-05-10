"""Hand-written tests for ``CIDKeyedType2CharString``."""

from __future__ import annotations

from pypdfbox.fontbox.cff import CIDKeyedType2CharString, Type2CharString


def test_cid_keyed_carries_cid() -> None:
    cs = CIDKeyedType2CharString(
        font=None,
        font_name="Test",
        cid=42,
        gid=7,
        sequence=None,
    )
    assert cs.get_cid() == 42
    assert cs.get_gid() == 7
    # Glyph name follows upstream's "%04x" formatting.
    assert cs.get_name() == "002a"


def test_cid_keyed_is_type2_subclass() -> None:
    cs = CIDKeyedType2CharString(
        font=None,
        font_name="Test",
        cid=1,
        gid=0,
        sequence=None,
    )
    assert isinstance(cs, Type2CharString)


def test_cid_keyed_zero_padding() -> None:
    cs = CIDKeyedType2CharString(
        font=None,
        font_name="Test",
        cid=0,
        gid=0,
        sequence=None,
    )
    assert cs.get_name() == "0000"
