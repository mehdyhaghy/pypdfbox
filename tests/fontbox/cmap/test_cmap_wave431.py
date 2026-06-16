from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.fontbox.cmap import CMap
from pypdfbox.io import RandomAccessReadBuffer


def test_wave431_to_unicode_guesses_three_and_four_byte_lengths() -> None:
    cmap = CMap("unicode-lengths")
    cmap.add_base_font_character(b"\x01\x02\x03", "three")
    cmap.add_base_font_character(b"\x01\x02\x03\x04", "four")

    assert cmap.to_unicode(0x010203) == "three"
    assert cmap.to_unicode(0x01020304) == "four"


def test_wave431_read_code_stream_truncated_after_partial_prefix() -> None:
    cmap = CMap("truncated")
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")

    # A 1-byte stream under a 2-byte codespace: upstream readCode reads into a
    # zero-initialised ``byte[maxCodeLength]`` and discards the short-read
    # count, so the codespace match runs over the zero-padded buffer and yields
    # the zero-extended code ``0xAB00`` (consuming the single available byte).
    # Verified against the live PDFBox 3.0.7 oracle in wave 1547; the prior
    # ``0xAB`` expectation pinned a pre-fix pypdfbox divergence.
    assert cmap.read_code(io.BytesIO(b"\xab")) == 0xAB00


def test_wave431_read_code_stream_extends_with_random_access_read() -> None:
    cmap = CMap("random-access")
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x81\x40", b"\x81\xff")

    assert cmap.read_code(RandomAccessReadBuffer(b"\x81\x40")) == 0x8140


def test_wave431_read_code_logs_invalid_stream_sequence(caplog: pytest.LogCaptureFixture) -> None:
    cmap = CMap("invalid-stream")
    cmap.add_codespace_range(b"\x81\x40", b"\x81\xff")

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.cmap.cmap"):
        assert cmap.read_code(io.BytesIO(b"\x82\x41")) == 0x8241

    assert "Invalid character code sequence 0x82 0x41 in CMap invalid-stream" in caplog.text


def test_wave431_read_code_logs_invalid_bytes_sequence(caplog: pytest.LogCaptureFixture) -> None:
    cmap = CMap("invalid-bytes")
    cmap.add_codespace_range(b"\x81\x40", b"\x81\xff")

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.cmap.cmap"):
        assert cmap.read_code(b"\x82\x41") == (0x8241, 2)

    assert "Invalid character code sequence 0x82 0x41 in CMap invalid-bytes" in caplog.text


def test_wave431_cid_lookup_lenient_fallbacks_and_ranges() -> None:
    empty = CMap("empty")
    assert empty.to_cid(0x20) == 0
    assert empty.to_cid_with_length(0x20, 1) == 0
    assert empty.to_cid_bytes(b"\x20") == 0

    cmap = CMap("ranges")
    cmap.add_cid_range(b"\x00\x10", b"\x00\x11", 50)
    assert cmap.to_cid_with_length(0x10, 2) == 50
    assert cmap.to_cid_with_length(0x12, 2) == 0
    assert cmap.to_cid_bytes(b"\x00\x10") == 50
    assert cmap.to_cid_bytes(b"\x00\x12") == 0
    assert cmap.to_cid_bytes(b"\x10") == 0


def test_wave431_mutators_validate_and_infer_byte_lengths(caplog: pytest.LogCaptureFixture) -> None:
    cmap = CMap("mutators")

    with pytest.raises(TypeError, match="requires high bytes"):
        cmap.add_codespace_range(b"\x00")
    with pytest.raises(ValueError, match="equal length"):
        cmap.add_cid_range(b"\x00", b"\x00\x01", 1)

    cmap.add_cid_mapping(0x1234, 77)
    assert cmap.to_cid_bytes(b"\x12\x34") == 77

    cmap.add_unicode_mapping(0x7F, "one")
    cmap.add_unicode_mapping(0x1234, "two")
    cmap.add_unicode_mapping(0x010203, "three")
    cmap.add_unicode_mapping(0x01020304, "four")
    assert cmap.get_codes_from_unicode("one") == b"\x7f"
    assert cmap.get_codes_from_unicode("two") == b"\x12\x34"
    assert cmap.get_codes_from_unicode("three") == b"\x01\x02\x03"
    assert cmap.get_codes_from_unicode("four") == b"\x01\x02\x03\x04"

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.cmap.cmap"):
        cmap.add_base_font_character(b"\x01\x02\x03\x04\x05", "too-long")
    assert "more than 4 bytes" in caplog.text
    assert cmap.get_codes_from_unicode("too-long") is None


def test_wave431_use_cmap_merges_lengths_and_inverted_unicode_maps() -> None:
    base = CMap("base")
    base.add_codespace_range(b"\x00", b"\x7f")
    base.add_codespace_range(b"\x81\x40", b"\x81\xff")
    base.add_base_font_character(b"\x00\x41", "two")
    base.add_base_font_character(b"\x01\x02\x03", "three")
    base.add_base_font_character(b"\x01\x02\x03\x04", "four")
    base.add_cid_mapping(b"\x20", 20)
    base.add_cid_range(b"\x00\x30", b"\x00\x31", 30)

    child = CMap("child")
    child.add_codespace_range(b"\x00\x00\x00", b"\x00\x00\xff")
    child.add_cid_mapping(b"\x01", 1)
    child.use_cmap(base)

    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 3
    assert child.get_min_cid_length() == 1
    assert child.get_max_cid_length() == 2
    assert child.get_codes_from_unicode("two") == b"\x00\x41"
    assert child.get_codes_from_unicode("three") == b"\x01\x02\x03"
    assert child.get_codes_from_unicode("four") == b"\x01\x02\x03\x04"
    assert child.to_cid_bytes(b"\x20") == 20
    assert child.to_cid_bytes(b"\x00\x30") == 30


def test_wave431_metadata_helpers_return_none_until_complete() -> None:
    cmap = CMap()
    assert cmap.get_cid_system_info() is None
    assert cmap.get_combined_name() is None
    assert str(cmap) == ""

    cmap.set_registry("Adobe")
    assert cmap.get_cid_system_info() == {
        "Registry": "Adobe",
        "Ordering": None,
        "Supplement": 0,
    }
    assert cmap.get_combined_name() is None

    cmap.set_ordering("Japan1")
    cmap.set_supplement(6)
    assert cmap.get_combined_name() == "Adobe-Japan1-6"
