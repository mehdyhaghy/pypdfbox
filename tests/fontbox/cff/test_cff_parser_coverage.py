"""Coverage-boost tests for
:class:`pypdfbox.fontbox.cff.cff_parser.CFFParser`.

These tests target the static byte-stream helpers, DICT readers,
encoding / charset / FDSelect readers, OTF wrapper helpers and per-
font-class dispatchers that the high-level ``parse`` shim wraps. They
exist independently of any installed system font so they can run on a
CI host that has no STIX/Hiragino fixtures.

Each test name is the upstream branch being exercised so future bisects
can map a coverage regression straight back to the operation under
test.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.fontbox.cff.cff_built_in_encoding import Supplement
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import (
    CFFParser,
    _BytesSource,
    _extract_cff_table,
    _strip_otf_wrapper,
)
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.dict_data import DictData, Entry
from pypdfbox.fontbox.cff.embedded_charset import EmbeddedCharset
from pypdfbox.fontbox.cff.fd_select import Format0FDSelect, Format3FDSelect
from pypdfbox.fontbox.cff.format0_encoding import Format0Encoding
from pypdfbox.fontbox.cff.format1_charset import Format1Charset
from pypdfbox.fontbox.cff.format1_encoding import Format1Encoding
from pypdfbox.fontbox.cff.format2_charset import Format2Charset
from pypdfbox.fontbox.cff.header import Header

# ---------------------------------------------------------------------
# _BytesSource — module-private helper.
# ---------------------------------------------------------------------


def test_bytes_source_round_trips_bytes() -> None:
    src = _BytesSource(b"abc")
    assert src.get_bytes() == b"abc"


def test_bytes_source_coerces_bytearray() -> None:
    src = _BytesSource(bytearray(b"xyz"))
    assert src.get_bytes() == b"xyz"


def test_bytes_source_coerces_memoryview() -> None:
    mv = memoryview(b"abcdef")[1:4]
    src = _BytesSource(mv)
    assert src.get_bytes() == b"bcd"


# ---------------------------------------------------------------------
# OTF wrapper helpers (``_strip_otf_wrapper`` / ``_extract_cff_table``).
# ---------------------------------------------------------------------


def test_strip_otf_wrapper_passes_short_input_through() -> None:
    # Less than 4 bytes: helper returns as-is.
    assert _strip_otf_wrapper(b"abc") == b"abc"


def test_strip_otf_wrapper_passes_plain_cff_through() -> None:
    # Non-OTF magic: helper returns unchanged.
    assert _strip_otf_wrapper(b"\x01\x00\x04\x01rest") == b"\x01\x00\x04\x01rest"


def test_strip_otf_wrapper_rejects_ttcf() -> None:
    with pytest.raises(OSError, match="True Type Collection"):
        _strip_otf_wrapper(b"ttcf" + b"\x00" * 16)


def test_strip_otf_wrapper_rejects_pure_truetype() -> None:
    with pytest.raises(OSError, match="OpenType fonts containing a true type"):
        _strip_otf_wrapper(b"\x00\x01\x00\x00" + b"\x00" * 16)


def test_extract_cff_table_returns_inner_cff_payload() -> None:
    # Build minimal OTF: header (12 bytes) + 1 directory record (16) +
    # an inline "CFF " payload immediately after.
    payload = b"CFFPAYLOAD"
    header = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    cff_offset = 12 + 16  # right after the directory record
    record = b"CFF " + struct.pack(">I", 0) + struct.pack(
        ">II", cff_offset, len(payload)
    )
    otf = header + record + payload
    assert _extract_cff_table(otf) == payload


def test_extract_cff_table_raises_on_truncated_header() -> None:
    with pytest.raises(OSError, match="Truncated OTF header"):
        _extract_cff_table(b"OTTO\x00\x01")


def test_extract_cff_table_raises_on_truncated_directory() -> None:
    # Declare 1 table but provide no directory record.
    bad = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    with pytest.raises(OSError, match="Truncated OTF table directory"):
        _extract_cff_table(bad)


def test_extract_cff_table_raises_when_cff_missing() -> None:
    # One non-CFF directory record, no payload.
    header = b"OTTO" + struct.pack(">HHHH", 1, 0, 0, 0)
    record = b"abcd" + struct.pack(">III", 0, 0, 0)
    with pytest.raises(OSError, match="CFF tag not found"):
        _extract_cff_table(header + record)


# ---------------------------------------------------------------------
# Static byte-stream helpers (read_tag_name / read_long / read_off_size
# / read_header / read_*index*).
# ---------------------------------------------------------------------


def test_read_tag_name_decodes_iso8859() -> None:
    inp = DataInputByteArray(b"CFF \xff\xff")
    assert CFFParser.read_tag_name(inp) == "CFF "


def test_read_long_combines_two_unsigned_shorts() -> None:
    # 0x12345678
    inp = DataInputByteArray(b"\x12\x34\x56\x78")
    assert CFFParser.read_long(inp) == 0x12345678


def test_read_off_size_accepts_valid_range() -> None:
    inp = DataInputByteArray(b"\x01\x02\x03\x04")
    assert CFFParser.read_off_size(inp) == 1
    assert CFFParser.read_off_size(inp) == 2
    assert CFFParser.read_off_size(inp) == 3
    assert CFFParser.read_off_size(inp) == 4


def test_read_off_size_rejects_zero() -> None:
    inp = DataInputByteArray(b"\x00\x00")
    with pytest.raises(OSError, match=r"Illegal \(< 1 or > 4\) offSize value 0"):
        CFFParser.read_off_size(inp)


def test_read_off_size_rejects_too_large() -> None:
    inp = DataInputByteArray(b"\x05\x00")
    with pytest.raises(OSError, match=r"Illegal \(< 1 or > 4\) offSize value 5"):
        CFFParser.read_off_size(inp)


def test_read_header_returns_populated_header() -> None:
    # major=1, minor=0, hdrSize=4, offSize=2
    inp = DataInputByteArray(b"\x01\x00\x04\x02\x00")
    hdr = CFFParser.read_header(inp)
    assert isinstance(hdr, Header)
    assert (hdr.major, hdr.minor, hdr.hdr_size, hdr.off_size) == (1, 0, 4, 2)


def test_read_index_data_offsets_zero_count_returns_empty() -> None:
    # count = 0 → empty list, off_size byte not consumed.
    inp = DataInputByteArray(b"\x00\x00trailing")
    assert CFFParser.read_index_data_offsets(inp) == []


def test_read_index_data_returns_per_entry_byte_slices() -> None:
    # INDEX with 2 entries: "ab" and "cde"
    # count(2) off_size(1) offsets(1, 3, 6) data("abcde")
    payload = b"\x00\x02\x01\x01\x03\x06abcde"
    inp = DataInputByteArray(payload + b"trailing")
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"ab", b"cde"]


def test_read_index_data_offsets_rejects_offset_past_eof() -> None:
    # count=1 off_size=1 offsets(1, 99) — 99 > buffer length
    payload = b"\x00\x01\x01\x01\x63"
    inp = DataInputByteArray(payload)
    with pytest.raises(OSError, match="illegal offset value"):
        CFFParser.read_index_data_offsets(inp)


def test_read_string_index_data_decodes_iso8859() -> None:
    # 2 strings: "Hi" and "bye"
    payload = b"\x00\x02\x01\x01\x03\x06Hibye"
    inp = DataInputByteArray(payload)
    assert CFFParser.read_string_index_data(inp) == ["Hi", "bye"]


def test_read_string_index_data_empty_when_count_zero() -> None:
    inp = DataInputByteArray(b"\x00\x00rest")
    assert CFFParser.read_string_index_data(inp) == []


# ---------------------------------------------------------------------
# DICT readers — read_entry, read_integer_number, read_real_number,
# read_operator, read_dict_data.
# ---------------------------------------------------------------------


def test_read_integer_number_b0_in_one_byte_range() -> None:
    # b0 in [32, 246] → b0 - 139. 139 → 0, 247 not in this branch.
    # Use b0=139 directly (caller is read_entry); we feed a stub
    # DataInput with no extra byte needed.
    inp = DataInputByteArray(b"")
    assert CFFParser.read_integer_number(inp, 139) == 0
    assert CFFParser.read_integer_number(inp, 246) == 246 - 139


def test_read_integer_number_b0_247_to_250_positive_two_byte() -> None:
    # b0=247, b1=10 → (247-247)*256 + 10 + 108 = 118
    inp = DataInputByteArray(b"\x0a")
    assert CFFParser.read_integer_number(inp, 247) == 118


def test_read_integer_number_b0_251_to_254_negative_two_byte() -> None:
    # b0=251, b1=0 → -(251-251)*256 - 0 - 108 = -108
    inp = DataInputByteArray(b"\x00")
    assert CFFParser.read_integer_number(inp, 251) == -108


def test_read_integer_number_b0_28_short() -> None:
    # b0=28 followed by signed short -1 (0xFFFF)
    inp = DataInputByteArray(b"\xff\xff")
    assert CFFParser.read_integer_number(inp, 28) == -1


def test_read_integer_number_b0_29_int() -> None:
    # b0=29 followed by signed int 0x12345678
    inp = DataInputByteArray(b"\x12\x34\x56\x78")
    assert CFFParser.read_integer_number(inp, 29) == 0x12345678


def test_read_integer_number_rejects_unsupported_b0() -> None:
    inp = DataInputByteArray(b"")
    with pytest.raises(ValueError):
        CFFParser.read_integer_number(inp, 30)


def test_read_real_number_decodes_simple_decimal() -> None:
    # Nibbles: 1, '.', 5, F → "1.5"
    # bytes: 1A 5F
    inp = DataInputByteArray(b"\x1a\x5f")
    assert CFFParser.read_real_number(inp) == 1.5


def test_read_real_number_decodes_negative() -> None:
    # Nibbles: E, 2, F → "-2"
    inp = DataInputByteArray(b"\xe2\xff")
    assert CFFParser.read_real_number(inp) == -2.0


def test_read_real_number_decodes_positive_exponent() -> None:
    # Nibbles: 1, B, 3, F → "1E3"
    inp = DataInputByteArray(b"\x1b\x3f")
    assert CFFParser.read_real_number(inp) == 1000.0


def test_read_real_number_decodes_negative_exponent() -> None:
    # Nibbles: 1, C, 3, F → "1E-3"
    inp = DataInputByteArray(b"\x1c\x3f")
    assert abs(CFFParser.read_real_number(inp) - 0.001) < 1e-9


def test_read_real_number_appends_missing_exponent_digit() -> None:
    # Stream ends with the exponent marker still "open" (no digits
    # after B): the parser appends a trailing "0" to keep the float
    # valid. Nibbles: 2, B, F → original "2E", patched to "2E0" = 2.0
    inp = DataInputByteArray(b"\x2b\xff")
    assert CFFParser.read_real_number(inp) == 2.0


def test_read_operator_one_byte_returns_mnemonic() -> None:
    inp = DataInputByteArray(b"")  # no follow-up byte
    # b0=0 → "version"
    assert CFFParser.read_operator(inp, 0) == "version"


def test_read_operator_two_byte_consumes_b1() -> None:
    # b0=12, b1=0 → "Copyright"
    inp = DataInputByteArray(b"\x00")
    assert CFFParser.read_operator(inp, 12) == "Copyright"


def test_read_dict_data_full_stream_until_eof() -> None:
    # One entry: operand 100 (b0=239 → 100) + operator "version" (0)
    inp = DataInputByteArray(b"\xef\x00")
    dict_ = CFFParser.read_dict_data(inp)
    entry = dict_.get_entry("version")
    assert entry is not None
    assert entry.get_number(0) == 100


def test_read_dict_data_with_explicit_window() -> None:
    # Skip leading byte; read just one entry: operand 5 (b0=144 →
    # 144-139=5) + operator 1 ("Notice").
    payload = b"junk\x90\x01trailing"
    inp = DataInputByteArray(payload)
    dict_ = CFFParser.read_dict_data(inp, offset=4, dict_size=2)
    entry = dict_.get_entry("Notice")
    assert entry is not None
    assert entry.get_number(0) == 5


def test_read_entry_rejects_invalid_b0_byte() -> None:
    inp = DataInputByteArray(b"\x1f")  # 31 is reserved
    with pytest.raises(OSError, match="invalid DICT data b0 byte: 31"):
        CFFParser.read_entry(inp)


# ---------------------------------------------------------------------
# SID / string helpers.
# ---------------------------------------------------------------------


def test_read_string_returns_standard_string_for_small_sid() -> None:
    parser = CFFParser()
    assert parser.read_string(0) == ".notdef"
    assert parser.read_string(1) == "space"


def test_read_string_resolves_via_string_index() -> None:
    parser = CFFParser()
    parser._string_index = ["custom1", "custom2"]
    # SID 391 → first custom string
    assert parser.read_string(391) == "custom1"
    assert parser.read_string(392) == "custom2"


def test_read_string_falls_back_to_sid_placeholder() -> None:
    parser = CFFParser()
    parser._string_index = []  # no custom strings
    assert parser.read_string(500) == "SID500"


def test_read_string_rejects_negative_index() -> None:
    parser = CFFParser()
    with pytest.raises(OSError, match="negative index"):
        parser.read_string(-1)


def test_get_string_returns_none_when_entry_missing() -> None:
    parser = CFFParser()
    dict_ = DictData()
    assert parser.get_string(dict_, "FontName") is None


def test_get_string_resolves_through_read_string() -> None:
    parser = CFFParser()
    dict_ = DictData()
    entry = Entry()
    entry.operator_name = "FontName"
    entry.add_operand(1)  # SID 1 → "space"
    dict_.add(entry)
    assert parser.get_string(dict_, "FontName") == "space"


# ---------------------------------------------------------------------
# ROS / parse_ros.
# ---------------------------------------------------------------------


def test_parse_ros_returns_none_when_absent() -> None:
    parser = CFFParser()
    assert parser.parse_ros(DictData()) is None


def test_parse_ros_builds_cid_font_from_triplet() -> None:
    parser = CFFParser()
    dict_ = DictData()
    entry = Entry()
    entry.operator_name = "ROS"
    # Registry SID=1 ("space"), Ordering SID=2 ("exclam"), Supplement=0
    entry.add_operand(1)
    entry.add_operand(2)
    entry.add_operand(0)
    dict_.add(entry)
    cid = parser.parse_ros(dict_)
    assert isinstance(cid, CFFCIDFont)
    assert cid.get_registry() == "space"
    assert cid.get_ordering() == "exclam"
    assert cid.get_supplement() == 0


def test_parse_ros_rejects_short_triplet() -> None:
    parser = CFFParser()
    dict_ = DictData()
    entry = Entry()
    entry.operator_name = "ROS"
    entry.add_operand(1)
    dict_.add(entry)
    with pytest.raises(OSError, match="ROS entry must have 3 elements"):
        parser.parse_ros(dict_)


# ---------------------------------------------------------------------
# Encodings (Format0 / Format1 / supplement / dispatcher).
# ---------------------------------------------------------------------


def test_read_format0_encoding_populates_codes() -> None:
    parser = CFFParser()
    # Embedded Type 1 charset with 2 explicit (gid → sid) entries.
    # Use small SIDs so ``read_string`` resolves through the standard-
    # string table — that's the real upstream code path.
    charset = EmbeddedCharset(is_cid_font=False)
    charset.add_sid(0, 0, ".notdef")
    charset.add_sid(1, 1, "space")  # SID 1 → "space"
    charset.add_sid(2, 2, "exclam")  # SID 2 → "exclam"
    # Format 0 body: nCodes byte (2), then 2 single-byte codes.
    inp = DataInputByteArray(b"\x02\x41\x42")
    encoding = parser.read_format0_encoding(inp, charset, 0)
    assert isinstance(encoding, Format0Encoding)
    assert encoding.n_codes == 2
    assert encoding.get_name(0x41) == "space"
    assert encoding.get_name(0x42) == "exclam"


def test_read_format1_encoding_populates_ranges() -> None:
    parser = CFFParser()
    charset = EmbeddedCharset(is_cid_font=False)
    charset.add_sid(0, 0, ".notdef")
    charset.add_sid(1, 1, "space")
    charset.add_sid(2, 2, "exclam")
    # 1 range: first=0x41, nLeft=1 → covers two glyphs (gid 1, 2)
    inp = DataInputByteArray(b"\x01\x41\x01")
    encoding = parser.read_format1_encoding(inp, charset, 1)
    assert isinstance(encoding, Format1Encoding)
    assert encoding.get_name(0x41) == "space"
    assert encoding.get_name(0x42) == "exclam"


def test_read_supplement_attaches_extra_codes() -> None:
    parser = CFFParser()
    encoding = Format0Encoding(0)
    # nSups=1, code=0x80, sid=2 ("exclam")
    inp = DataInputByteArray(b"\x01\x80\x00\x02")
    parser.read_supplement(inp, encoding)
    assert len(encoding.supplement) == 1
    sup = encoding.supplement[0]
    assert isinstance(sup, Supplement)
    assert sup.code == 0x80
    assert sup.sid == 2
    assert sup.name == "exclam"


def test_read_encoding_dispatches_format0_with_supplement_bit() -> None:
    parser = CFFParser()
    charset = EmbeddedCharset(is_cid_font=False)
    charset.add_sid(0, 0, ".notdef")
    # Format byte = 0 | 0x80 → format 0 with trailing supplement
    # nCodes=0, then nSups=0 supplement.
    inp = DataInputByteArray(b"\x80\x00\x00")
    encoding = parser.read_encoding(inp, charset)
    assert isinstance(encoding, Format0Encoding)
    assert encoding.supplement == ()


def test_read_encoding_dispatches_format1() -> None:
    parser = CFFParser()
    charset = EmbeddedCharset(is_cid_font=False)
    charset.add_sid(0, 0, ".notdef")
    # Format byte = 1, nRanges = 0
    inp = DataInputByteArray(b"\x01\x00")
    encoding = parser.read_encoding(inp, charset)
    assert isinstance(encoding, Format1Encoding)


def test_read_encoding_rejects_unknown_format() -> None:
    parser = CFFParser()
    charset = EmbeddedCharset(is_cid_font=False)
    inp = DataInputByteArray(b"\x05")
    with pytest.raises(OSError, match="Invalid encoding base format"):
        parser.read_encoding(inp, charset)


# ---------------------------------------------------------------------
# FDSelect (Format0 / Format3 / dispatcher).
# ---------------------------------------------------------------------


def test_read_format0_fd_select_one_byte_per_glyph() -> None:
    inp = DataInputByteArray(b"\x00\x01\x02\x03")
    fds = CFFParser.read_format0_fd_select(inp, n_glyphs=4)
    assert isinstance(fds, Format0FDSelect)


def test_read_format3_fd_select_parses_ranges_and_sentinel() -> None:
    # nRanges=2, (first=0, fd=0), (first=10, fd=1), sentinel=20
    inp = DataInputByteArray(b"\x00\x02\x00\x00\x00\x00\x0a\x01\x00\x14")
    fds = CFFParser.read_format3_fd_select(inp)
    assert isinstance(fds, Format3FDSelect)


def test_read_fd_select_dispatches_format0() -> None:
    inp = DataInputByteArray(b"\x00\x00\x01")
    fds = CFFParser.read_fd_select(inp, n_glyphs=2)
    assert isinstance(fds, Format0FDSelect)


def test_read_fd_select_dispatches_format3() -> None:
    inp = DataInputByteArray(b"\x03\x00\x01\x00\x00\x00\x00\x05")
    fds = CFFParser.read_fd_select(inp, n_glyphs=5)
    assert isinstance(fds, Format3FDSelect)


def test_read_fd_select_rejects_unknown_format() -> None:
    inp = DataInputByteArray(b"\x02")
    with pytest.raises(ValueError):
        CFFParser.read_fd_select(inp, n_glyphs=1)


# ---------------------------------------------------------------------
# Charsets (Format0 / Format1 / Format2 — both CID and Type1 variants).
# ---------------------------------------------------------------------


def test_read_format0_charset_type1_resolves_sid_names() -> None:
    parser = CFFParser()
    # 3 glyphs total; payload contains (n_glyphs - 1) SIDs as Card16s.
    # SID 1 → "space", SID 2 → "exclam"
    inp = DataInputByteArray(b"\x00\x01\x00\x02")
    charset = parser.read_format0_charset(inp, n_glyphs=3, is_cid_font=False)
    assert charset.get_name_for_gid(0) == ".notdef"
    assert charset.get_name_for_gid(1) == "space"
    assert charset.get_name_for_gid(2) == "exclam"


def test_read_format0_charset_cid_populates_cid_map() -> None:
    parser = CFFParser()
    # n_glyphs=3: 2 CIDs (10, 20).
    inp = DataInputByteArray(b"\x00\x0a\x00\x14")
    charset = parser.read_format0_charset(inp, n_glyphs=3, is_cid_font=True)
    assert charset.get_cid_for_gid(1) == 10
    assert charset.get_cid_for_gid(2) == 20


def test_read_format1_charset_type1_expands_range() -> None:
    parser = CFFParser()
    # 1 range: first=1, nLeft=1 → SIDs 1, 2 across gids 1, 2 (3 glyphs total)
    inp = DataInputByteArray(b"\x00\x01\x01")
    charset = parser.read_format1_charset(inp, n_glyphs=3, is_cid_font=False)
    assert charset.get_name_for_gid(1) == "space"
    assert charset.get_name_for_gid(2) == "exclam"


def test_read_format1_charset_cid_stores_range_mapping() -> None:
    parser = CFFParser()
    # 1 range: first=0, nLeft=1 (covers 2 glyphs); 3 glyphs total
    inp = DataInputByteArray(b"\x00\x00\x01")
    charset = parser.read_format1_charset(inp, n_glyphs=3, is_cid_font=True)
    assert isinstance(charset, Format1Charset)


def test_read_format2_charset_type1_expands_range() -> None:
    parser = CFFParser()
    # 1 range: first=1, nLeft=1 (2-byte) → SIDs 1, 2; 3 glyphs total
    inp = DataInputByteArray(b"\x00\x01\x00\x01")
    charset = parser.read_format2_charset(inp, n_glyphs=3, is_cid_font=False)
    assert charset.get_name_for_gid(1) == "space"
    assert charset.get_name_for_gid(2) == "exclam"


def test_read_format2_charset_cid_stores_range_mapping() -> None:
    parser = CFFParser()
    inp = DataInputByteArray(b"\x00\x00\x00\x01")
    charset = parser.read_format2_charset(inp, n_glyphs=3, is_cid_font=True)
    assert isinstance(charset, Format2Charset)


def test_read_charset_dispatches_all_three_formats() -> None:
    parser = CFFParser()
    # Format 0, 2 glyphs (1 SID)
    inp0 = DataInputByteArray(b"\x00\x00\x01")
    cs0 = parser.read_charset(inp0, n_glyphs=2, is_cid_font=False)
    assert cs0.get_name_for_gid(1) == "space"
    # Format 1, 2 glyphs
    inp1 = DataInputByteArray(b"\x01\x00\x01\x00")
    cs1 = parser.read_charset(inp1, n_glyphs=2, is_cid_font=False)
    assert cs1 is not None
    # Format 2, 2 glyphs
    inp2 = DataInputByteArray(b"\x02\x00\x01\x00\x00")
    cs2 = parser.read_charset(inp2, n_glyphs=2, is_cid_font=False)
    assert cs2 is not None


def test_read_charset_rejects_unknown_format() -> None:
    parser = CFFParser()
    inp = DataInputByteArray(b"\x05")
    with pytest.raises(OSError, match="Incorrect charset format 5"):
        parser.read_charset(inp, n_glyphs=1, is_cid_font=False)


# ---------------------------------------------------------------------
# Private dict materialisation.
# ---------------------------------------------------------------------


def test_read_private_dict_returns_default_values_for_empty_input() -> None:
    priv = CFFParser.read_private_dict(DictData())
    # All defaults
    assert priv["BlueScale"] == 0.039625
    assert priv["BlueShift"] == 7
    assert priv["BlueFuzz"] == 1
    assert priv["ForceBold"] is False
    assert priv["LanguageGroup"] == 0
    assert abs(priv["ExpansionFactor"] - 0.06) < 1e-9
    assert priv["defaultWidthX"] == 0
    assert priv["nominalWidthX"] == 0
    assert priv["BlueValues"] is None
    assert priv["StdHW"] is None


def test_read_private_dict_propagates_explicit_overrides() -> None:
    dict_ = DictData()
    e = Entry()
    e.operator_name = "BlueScale"
    e.add_operand(0.5)
    dict_.add(e)
    e2 = Entry()
    e2.operator_name = "defaultWidthX"
    e2.add_operand(500)
    dict_.add(e2)
    priv = CFFParser.read_private_dict(dict_)
    assert priv["BlueScale"] == 0.5
    assert priv["defaultWidthX"] == 500


# ---------------------------------------------------------------------
# Misc helpers.
# ---------------------------------------------------------------------


def test_as_list_returns_python_list() -> None:
    assert CFFParser.as_list(1, 2, 3) == [1, 2, 3]
    assert CFFParser.as_list() == []


def test_concatenate_matrix_handles_identity_dest() -> None:
    dest = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    concat = [2.0, 0.0, 0.0, 3.0, 5.0, 7.0]
    CFFParser.concatenate_matrix(dest, concat)
    # Identity * concat = concat-like, with the upstream-bug-preserving
    # ``d1`` substitution in slot [1] (which is 0 here since d1=1, b2=0).
    # a1=1 b1=0 c1=0 d1=1 x1=0 y1=0
    assert dest[0] == 2.0  # a1*a2 + b1*c2 = 1*2 + 0*0
    assert dest[1] == 0.0  # a1*b2 + b1*d1 = 1*0 + 0*1
    assert dest[2] == 0.0  # c1*a2 + d1*c2 = 0*2 + 1*0
    assert dest[3] == 3.0  # c1*b2 + d1*d2 = 0*0 + 1*3
    assert dest[4] == 5.0  # x1*a2 + y1*c2 + x2
    assert dest[5] == 7.0


# ---------------------------------------------------------------------
# parse_font + parse_first_sub_font_ros via fontTools-built fixture.
# ---------------------------------------------------------------------


def _build_minimal_cff_bytes() -> bytes:
    """Construct a minimal Type 1-flavoured CFF byte stream using
    fontTools' :class:`FontBuilder` so the parser end-to-end gets
    exercised without depending on a system font fixture.
    """
    from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
    from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415

    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", "A"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({ord("A"): "A"})
    # Each glyph needs a real T2CharString — bare lists don't carry the
    # ``private`` attribute :meth:`setupCFF` writes back to.
    cs_notdef = T2CharString()
    cs_notdef.program = ["endchar"]
    cs_a = T2CharString()
    cs_a.program = ["endchar"]
    fb.setupCFF(
        psName="TestFont",
        fontInfo={"FullName": "Test Font", "FamilyName": "Test"},
        charStringsDict={".notdef": cs_notdef, "A": cs_a},
        privateDict={},
    )
    buf = io.BytesIO()
    fb.font["CFF "].cff.compile(buf, fb.font, isCFF2=False)
    return buf.getvalue()


_BUILT_CFF: bytes | None
try:
    _BUILT_CFF = _build_minimal_cff_bytes()
except Exception:  # noqa: BLE001
    _BUILT_CFF = None


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_parse_built_cff_returns_type1_font() -> None:
    assert _BUILT_CFF is not None
    parser = CFFParser()
    fonts = parser.parse(_BUILT_CFF)
    assert len(fonts) == 1
    assert isinstance(fonts[0], CFFType1Font)
    assert fonts[0].get_name() == "TestFont"


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_parse_font_dispatch_returns_matching_font() -> None:
    assert _BUILT_CFF is not None
    parser = CFFParser()
    inp = DataInputByteArray(_BUILT_CFF)
    font = parser.parse_font(inp, "TestFont", b"")
    assert font.get_name() == "TestFont"


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_parse_font_returns_first_when_name_unknown() -> None:
    assert _BUILT_CFF is not None
    parser = CFFParser()
    inp = DataInputByteArray(_BUILT_CFF)
    font = parser.parse_font(inp, "DoesNotExist", b"")
    # Falls back to first font (upstream surfaces it the same way via
    # the for-loop exhausting without a hit).
    assert font.get_name() == "TestFont"


class _StubHeaders:
    def __init__(self) -> None:
        self.error: str | None = None
        self.ros: tuple[str | None, str | None, int | None] | None = None

    def set_error(self, msg: str) -> None:
        self.error = msg

    def set_otf_ros(self, registry: str | None, ordering: str | None,
                    supplement: int | None) -> None:
        self.ros = (registry, ordering, supplement)


def test_parse_first_sub_font_ros_reports_error_on_bad_input() -> None:
    parser = CFFParser()
    headers = _StubHeaders()
    parser.parse_first_sub_font_ros(b"ttcf" + b"\x00" * 16, headers)
    assert headers.error is not None
    assert "True Type Collection" in headers.error


@pytest.mark.skipif(
    _BUILT_CFF is None, reason="fontTools FontBuilder unavailable for CFF build"
)
def test_parse_first_sub_font_ros_skips_non_cid_font() -> None:
    assert _BUILT_CFF is not None
    parser = CFFParser()
    headers = _StubHeaders()
    parser.parse_first_sub_font_ros(_BUILT_CFF, headers)
    # Built font is name-keyed → set_otf_ros not called.
    assert headers.ros is None
    assert headers.error is None
