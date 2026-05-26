from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common import (
    PDFDocEncoding,
    contains_char,
    decode_bytes,
    encode_bytes,
    get_char_code,
)

# The 41 deviations from ISO-8859-1 listed in ISO 32000-1:2008 §D.3
# table D.2. Each tuple is (byte_code, unicode_char).
_DEVIATIONS: tuple[tuple[int, str], ...] = (
    (0x18, "˘"),
    (0x19, "ˇ"),
    (0x1A, "ˆ"),
    (0x1B, "˙"),
    (0x1C, "˝"),
    (0x1D, "˛"),
    (0x1E, "˚"),
    (0x1F, "˜"),
    (0x80, "•"),
    (0x81, "†"),
    (0x82, "‡"),
    (0x83, "…"),
    (0x84, "—"),
    (0x85, "–"),
    (0x86, "ƒ"),
    (0x87, "⁄"),
    (0x88, "‹"),
    (0x89, "›"),
    (0x8A, "−"),
    (0x8B, "‰"),
    (0x8C, "„"),
    (0x8D, "“"),
    (0x8E, "”"),
    (0x8F, "‘"),
    (0x90, "’"),
    (0x91, "‚"),
    (0x92, "™"),
    (0x93, "ﬁ"),
    (0x94, "ﬂ"),
    (0x95, "Ł"),
    (0x96, "Œ"),
    (0x97, "Š"),
    (0x98, "Ÿ"),
    (0x99, "Ž"),
    (0x9A, "ı"),
    (0x9B, "ł"),
    (0x9C, "œ"),
    (0x9D, "š"),
    (0x9E, "ž"),
    (0xA0, "€"),
)


# Bytes that have no Unicode counterpart in PDFDocEncoding (table D.2).
_UNDEFINED_CODES: tuple[int, ...] = (
    *range(0x18, 0x20),  # later overridden by deviations — see below
    *range(0x7F, 0xA1),
    0xAD,
)


def test_iso_8859_1_block_round_trip() -> None:
    # Codes that are *not* in any deviation/undefined hole map to chr(i).
    for i in range(256):
        if 0x17 < i < 0x20:
            continue
        if 0x7E < i < 0xA1:
            continue
        if i == 0xAD:
            continue
        assert decode_bytes(bytes([i])) == chr(i)
        assert encode_bytes(chr(i)) == bytes([i])


def test_deviations_round_trip() -> None:
    for code, char in _DEVIATIONS:
        assert decode_bytes(bytes([code])) == char
        assert encode_bytes(char) == bytes([code])


def test_control_codes_0x00_to_0x17_pass_through() -> None:
    # 0x00..0x17 are valid control codes that map to chr(i) (table D.2).
    for i in range(0x18):
        assert decode_bytes(bytes([i])) == chr(i)
        assert encode_bytes(chr(i)) == bytes([i])


def test_control_block_0x18_0x1F_uses_deviations() -> None:
    # Codes 0x18..0x1F deviate from ISO-8859-1 (table D.2 block 1).
    expected = {
        0x18: "˘",
        0x19: "ˇ",
        0x1A: "ˆ",
        0x1B: "˙",
        0x1C: "˝",
        0x1D: "˛",
        0x1E: "˚",
        0x1F: "˜",
    }
    for code, char in expected.items():
        assert decode_bytes(bytes([code])) == char


def test_undefined_codes_map_to_replacement_character() -> None:
    # 0x7F and 0x9F have no Unicode counterpart (marked "undefined" in
    # table D.2) — upstream substitutes U+FFFD REPLACEMENT CHARACTER.
    assert decode_bytes(bytes([0x7F])) == "�"
    assert decode_bytes(bytes([0x9F])) == "�"


def test_holes_decode_to_replacement_character() -> None:
    # Codes inside the 0x80..0xA0 block that are explicitly flagged
    # "undefined" in table D.2 (only 0x9F here) decode to U+FFFD.
    for i in range(0x80, 0xA1):
        if i in {code for code, _ in _DEVIATIONS}:
            continue
        # All others are undefined holes.
        assert decode_bytes(bytes([i])) == "�"


def test_soft_hyphen_0xad_decodes_to_nul() -> None:
    # 0xAD (SOFT HYPHEN) is left entirely unmapped by PDFDocEncoding — it is
    # never assigned, so upstream's int[] CODE_TO_UNI slot stays 0 and
    # toString casts it to (char) 0 = U+0000. Verified live against PDFBox
    # 3.0.7 (oracle ActionProbe, fixture PDFBOX-5840). NOT U+FFFD.
    assert decode_bytes(bytes([0xAD])) == "\u0000"


def test_contains_char_for_representable_chars() -> None:
    assert contains_char("A")
    assert contains_char("€")
    assert contains_char("ﬁ")
    assert contains_char("\x00")  # NUL is in PDFDocEncoding


def test_contains_char_rejects_non_representable() -> None:
    assert not contains_char("中")
    assert not contains_char("­")  # soft hyphen — undefined
    assert not contains_char("")  # control code, not in PDFDocEncoding
    assert not contains_char("")  # not a single char
    assert not contains_char("AB")


def test_get_char_code_basic() -> None:
    assert get_char_code("A") == 0x41
    assert get_char_code("€") == 0xA0
    assert get_char_code("ﬁ") == 0x93
    assert get_char_code("中") is None
    assert get_char_code("AB") is None


def test_encode_unmappable_falls_back_to_zero() -> None:
    # Mirrors upstream getOrDefault(c, 0).
    assert encode_bytes("中") == b"\x00"
    assert encode_bytes("A中B") == b"A\x00B"


def test_decode_full_byte_range_does_not_raise() -> None:
    # decode_bytes must handle every possible byte value.
    decoded = decode_bytes(bytes(range(256)))
    assert len(decoded) == 256


def test_decode_empty_bytes() -> None:
    assert decode_bytes(b"") == ""


def test_encode_empty_string() -> None:
    assert encode_bytes("") == b""


def test_decode_accepts_bytearray_and_memoryview() -> None:
    assert decode_bytes(bytearray(b"AB")) == "AB"
    assert decode_bytes(memoryview(b"AB")) == "AB"


def test_class_facade_matches_module_functions() -> None:
    sample = "Hello — €"
    encoded = encode_bytes(sample)
    assert PDFDocEncoding.get_bytes(sample) == encoded
    assert PDFDocEncoding.to_string(encoded) == sample
    assert PDFDocEncoding.contains_char("A") is True
    assert PDFDocEncoding.contains_char("中") is False
    assert PDFDocEncoding.get_char_code("€") == 0xA0


def test_class_set_updates_both_directions() -> None:
    # Mirrors upstream private ``PDFDocEncoding.set(int, char)``: the class
    # facade should expose the same registration entry-point so ported
    # code can call ``PDFDocEncoding.set(...)`` directly.
    private_char = ""  # Unicode Private Use Area
    original_char = decode_bytes(bytes([0x7F]))
    assert get_char_code(private_char) is None
    try:
        PDFDocEncoding.set(0x7F, private_char)
        assert decode_bytes(bytes([0x7F])) == private_char
        assert get_char_code(private_char) == 0x7F
        assert encode_bytes(private_char) == bytes([0x7F])
    finally:
        PDFDocEncoding.set(0x7F, original_char)


def test_class_set_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        PDFDocEncoding.set(-1, "A")
    with pytest.raises(ValueError):
        PDFDocEncoding.set(256, "A")
    with pytest.raises(ValueError):
        PDFDocEncoding.set(0x7F, "ab")


def test_round_trip_every_pdfdocencoding_byte() -> None:
    # Every byte that decodes to a defined character must round-trip back to
    # itself through encode_bytes. The undefined slots don't: 0x7F / 0x9F
    # decode to U+FFFD (unmappable -> 0), and 0xAD is unmapped and decodes to
    # U+0000 which encodes back to 0x00 (the NUL identity), not 0xAD.
    for i in range(256):
        if i == 0xAD:
            continue
        decoded = decode_bytes(bytes([i]))
        if decoded == "�":
            # Undefined codes don't round-trip — encoding U+FFFD goes to
            # 0 (the unmappable fallback).
            continue
        assert encode_bytes(decoded) == bytes([i]), f"failed round-trip for byte 0x{i:02X}"


def test_deviations_disjoint_from_iso_8859_1() -> None:
    # Sanity: every deviation code points to a Unicode value that is
    # *not* simply chr(code) — confirms the deviation table replaces,
    # not duplicates, the ISO-8859-1 baseline.
    for code, char in _DEVIATIONS:
        assert char != chr(code)


def test_pdfbox_3864_chars_below_256() -> None:
    # Equivalent of upstream PDFBox-3864 regression: every BMP character
    # below 256 must encode/decode-round-trip to itself via the
    # PDF text-string contract (UTF-16BE BOM for non-PDFDocEncoded chars,
    # PDFDocEncoding bytes otherwise).
    for i in range(256):
        char = chr(i)
        if contains_char(char):
            assert decode_bytes(encode_bytes(char)) == char
        else:
            # Non-PDFDocEncoded chars get a 0 byte from encode_bytes —
            # callers are expected to use the UTF-16BE-BOM path instead.
            assert encode_bytes(char) == b"\x00"
