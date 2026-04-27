"""Hand-written tests for ``BFCharRange`` (pypdfbox addition)."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import BFCharEntry, BFCharRange


def test_single_target_size_one() -> None:
    rng = BFCharRange(b"\x00\x41", b"\x00\x41", target="A")
    assert rng.size() == 1
    entries = rng.entries()
    assert entries == [BFCharEntry(b"\x00\x41", "A")]


def test_single_target_increments_last_codepoint() -> None:
    """Adobe semantics: ``bfrange <0000> <0003> <0041>`` -> A, B, C, D."""
    rng = BFCharRange(b"\x00\x00", b"\x00\x03", target="A")
    assert rng.size() == 4
    targets = [e.get_unicode() for e in rng]
    assert targets == ["A", "B", "C", "D"]


def test_single_target_multi_byte_unicode() -> None:
    """Only the trailing code unit is incremented (PDF 9.10.3)."""
    rng = BFCharRange(b"\x00\x00", b"\x00\x02", target="AA")
    targets = [e.get_unicode() for e in rng]
    # "AA", "AB", "AC"
    assert targets == ["AA", "AB", "AC"]


def test_explicit_targets_list() -> None:
    rng = BFCharRange(
        b"\x00\x00",
        b"\x00\x02",
        targets=["alpha", "beta", "gamma"],
    )
    targets = [e.get_unicode() for e in rng]
    assert targets == ["alpha", "beta", "gamma"]


def test_iter_yields_bf_char_entry_instances() -> None:
    rng = BFCharRange(b"\x10", b"\x12", target="X")
    for entry in rng:
        assert isinstance(entry, BFCharEntry)


def test_codes_are_consecutive_with_correct_byte_length() -> None:
    rng = BFCharRange(b"\x00\xfe", b"\x01\x01", target="z")
    codes = [e.get_code() for e in rng]
    assert codes == [b"\x00\xfe", b"\x00\xff", b"\x01\x00", b"\x01\x01"]


def test_rejects_unequal_start_end_lengths() -> None:
    with pytest.raises(ValueError):
        BFCharRange(b"\x00", b"\x00\x10", target="A")


def test_rejects_oversized_codes() -> None:
    with pytest.raises(ValueError):
        BFCharRange(b"\x00" * 5, b"\x01" * 5, target="A")


def test_rejects_end_before_start() -> None:
    with pytest.raises(ValueError):
        BFCharRange(b"\x00\x10", b"\x00\x05", target="A")


def test_rejects_both_or_neither_target() -> None:
    with pytest.raises(ValueError):
        BFCharRange(b"\x00", b"\x05", target="A", targets=["A", "B"])
    with pytest.raises(ValueError):
        BFCharRange(b"\x00", b"\x05")


def test_targets_list_too_short_rejected() -> None:
    with pytest.raises(ValueError):
        BFCharRange(b"\x00", b"\x04", targets=["A", "B"])


def test_accessors() -> None:
    rng = BFCharRange(b"\x00\x00", b"\x00\x10", target="A")
    assert rng.get_start() == b"\x00\x00"
    assert rng.get_end() == b"\x00\x10"
    assert rng.get_target() == "A"
    assert rng.get_targets() is None
    assert rng.get_code_length() == 2
    assert rng.size() == 17


def test_equality_and_hash() -> None:
    a = BFCharRange(b"\x00", b"\x05", target="A")
    b = BFCharRange(b"\x00", b"\x05", target="A")
    c = BFCharRange(b"\x00", b"\x05", target="B")
    assert a == b
    assert a != c
    assert a != 42
    assert hash(a) == hash(b)


def test_can_feed_cmap_add_char_mapping() -> None:
    """Materialised entries can be pushed into a real ``CMap``."""
    from pypdfbox.fontbox.cmap import CMap

    cmap = CMap("test")
    cmap.add_codespace_range(b"\x00", b"\xff")
    rng = BFCharRange(b"\x41", b"\x43", target="A")
    for entry in rng:
        cmap.add_base_font_character(entry.get_code(), entry.get_unicode())
    assert cmap.to_unicode_bytes(b"\x41") == "A"
    assert cmap.to_unicode_bytes(b"\x42") == "B"
    assert cmap.to_unicode_bytes(b"\x43") == "C"


def test_repr_single_target() -> None:
    rng = BFCharRange(b"\x00", b"\x05", target="A")
    assert "BFCharRange" in repr(rng)
    assert "00" in repr(rng) and "05" in repr(rng)


def test_repr_targets_list() -> None:
    rng = BFCharRange(b"\x00", b"\x01", targets=["a", "b"])
    r = repr(rng)
    assert "BFCharRange" in r
    assert "['a', 'b']" in r
