"""Hand-written tests for ``CodespaceRange``."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CodespaceRange


def test_codespace_range_one_byte_linear() -> None:
    rng = CodespaceRange(b"\x00", b"\x20")
    assert rng.get_code_length() == 1
    assert rng.matches(b"\x00") is True
    assert rng.matches(b"\x10") is True
    assert rng.matches(b"\x20") is True
    # Out of range high.
    assert rng.matches(b"\x21") is False


def test_codespace_range_two_byte_rectangular() -> None:
    # <8140> <9FFC>: high byte must be in [0x81, 0x9F] AND low byte in [0x40, 0xFC].
    rng = CodespaceRange(b"\x81\x40", b"\x9F\xFC")
    assert rng.get_code_length() == 2
    assert rng.matches(b"\x81\x40") is True
    assert rng.matches(b"\x9F\xFC") is True
    assert rng.matches(b"\x90\x80") is True
    # 0x80 violates low bound on high byte.
    assert rng.matches(b"\x80\x40") is False
    # 0xA0 violates high bound on high byte.
    assert rng.matches(b"\xA0\x40") is False
    # 0x3F violates low bound on low byte (rectangular, not linear).
    assert rng.matches(b"\x90\x3F") is False


def test_codespace_range_wrong_length_no_match() -> None:
    rng = CodespaceRange(b"\x00", b"\x20")
    assert rng.matches(b"\x00\x10") is False
    assert rng.matches(b"") is False


def test_codespace_range_is_full_match_with_explicit_length() -> None:
    rng = CodespaceRange(b"\x00\x00", b"\x00\xFF")
    # First two bytes of a longer buffer, codeLen=2, valid range.
    assert rng.is_full_match(b"\x00\x10\xff\xff", 2) is True
    # Wrong length.
    assert rng.is_full_match(b"\x00\x10\xff\xff", 3) is False


def test_codespace_range_pdfbox_4923_zero_widening() -> None:
    """One-byte ``<00>`` start is widened to match a multi-byte end."""
    rng = CodespaceRange(b"\x00", b"\xFF\xFF")
    assert rng.get_code_length() == 2
    assert rng.matches(b"\x00\x00") is True
    assert rng.matches(b"\xFF\xFF") is True


def test_codespace_range_mismatched_lengths_rejected() -> None:
    with pytest.raises(ValueError, match="different lengths"):
        CodespaceRange(b"\x01\x02", b"\xFF")


def test_codespace_range_accepts_bytearray_and_memoryview() -> None:
    rng = CodespaceRange(bytearray(b"\x00"), memoryview(b"\xFF"))
    assert rng.get_code_length() == 1
    assert rng.matches(bytearray(b"\x80")) is True
    assert rng.matches(memoryview(b"\x80")) is True


# ---------- dunder helpers ----------


def test_codespace_range_repr_uppercase_hex() -> None:
    text = repr(CodespaceRange(b"\x81\x40", b"\x9F\xFC"))
    assert text == "CodespaceRange(<8140> <9FFC>)"


def test_codespace_range_equality_and_hash() -> None:
    a = CodespaceRange(b"\x00", b"\xFF")
    b = CodespaceRange(b"\x00", b"\xFF")
    c = CodespaceRange(b"\x00", b"\x7F")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert {a, b, c} == {a, c}


def test_codespace_range_equality_against_other_types() -> None:
    rng = CodespaceRange(b"\x00", b"\xFF")
    assert rng != "not a range"
    assert rng != 42
    assert rng != None  # noqa: E711 — explicit equality, not identity
