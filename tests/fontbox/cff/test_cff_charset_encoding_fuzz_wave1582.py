"""Wave 1582 — CFF charset + encoding parsing fuzz / parity (Agent C).

Hammers the on-disk charset and encoding readers in
``pypdfbox.fontbox.cff.cff_parser.CFFParser`` against hand-computed
oracle values derived straight from the CFF spec (Adobe Technote #5176
§13 charsets, §12 encodings) and from upstream PDFBox 3.0.7
``CFFParser.readCharset`` / ``readEncoding``.

Charset formats:
* **0** — one Card16 SID (or CID) per glyph after the implicit GID-0
  ``.notdef``.
* **1** — ``(first: Card16, nLeft: Card8)`` ranges; range spans
  ``nLeft + 1`` glyphs.
* **2** — ``(first: Card16, nLeft: Card16)`` ranges.

Encoding formats:
* **0** — ``nCodes`` one-byte codes, one per GID starting at GID 1.
* **1** — ``nRanges`` ``(first: Card8, nLeft: Card8)`` ranges.
* the supplement table (high bit ``0x80`` of the format byte) appends
  extra ``(code, SID)`` mappings.

Predefined charsets (ISOAdobe=0, Expert=1, ExpertSubset=2) and encodings
(Standard=0, Expert=1) are resolved to the predefined tables, not parsed
as offsets — exercised through their singleton getters here.
"""

from __future__ import annotations

import pytest
from fontTools.cffLib import cffStandardStrings

from pypdfbox.fontbox.cff.cff_expert_charset import CFFExpertCharset
from pypdfbox.fontbox.cff.cff_expert_encoding import CFFExpertEncoding
from pypdfbox.fontbox.cff.cff_expert_subset_charset import CFFExpertSubsetCharset
from pypdfbox.fontbox.cff.cff_iso_adobe_charset import CFFISOAdobeCharset
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_standard_encoding import CFFStandardEncoding
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.format0_encoding import Format0Encoding
from pypdfbox.fontbox.cff.format1_charset import Format1Charset
from pypdfbox.fontbox.cff.format1_encoding import Format1Encoding
from pypdfbox.fontbox.cff.format2_charset import Format2Charset


def _u16(value: int) -> bytes:
    return value.to_bytes(2, "big")


def _u8(value: int) -> bytes:
    return bytes([value])


# ---------------------------------------------------------------------------
# Charset format 0 — one SID/CID per glyph
# ---------------------------------------------------------------------------


def test_format0_type1_maps_each_gid_to_explicit_sid() -> None:
    parser = CFFParser()
    # GID 0 = .notdef (implicit), GIDs 1..3 → SIDs 1 (space), 2 (exclam),
    # 3 (quotedbl).
    payload = _u8(0) + _u16(1) + _u16(2) + _u16(3)
    inp = DataInputByteArray(payload)
    cs = parser.read_charset(inp, n_glyphs=4, is_cid_font=False)
    assert cs.get_name_for_gid(0) == ".notdef"
    assert cs.get_sid_for_gid(0) == 0
    assert cs.get_sid_for_gid(1) == 1
    assert cs.get_sid_for_gid(2) == 2
    assert cs.get_sid_for_gid(3) == 3
    assert cs.get_name_for_gid(1) == cffStandardStrings[1]
    assert cs.get_name_for_gid(3) == cffStandardStrings[3]


def test_format0_gid0_notdef_is_implicit_not_read() -> None:
    # n_glyphs=1 → no SID bytes to read; GID 0 is implicit. The format-
    # specific reader assumes the format byte is already consumed, so we
    # pass an empty buffer.
    parser = CFFParser()
    inp = DataInputByteArray(b"\x00")  # one harmless byte, never read
    cs = parser.read_format0_charset(inp, n_glyphs=1, is_cid_font=False)
    assert cs.get_name_for_gid(0) == ".notdef"
    assert cs.get_sid_for_gid(0) == 0
    # No SID bytes consumed for the single implicit .notdef glyph.
    assert inp.get_position() == 0


def test_format0_type1_sid_to_gid_reverse_lookup() -> None:
    parser = CFFParser()
    # Direct format-0 reader: format byte already consumed by the caller.
    payload = _u16(5) + _u16(9)
    inp = DataInputByteArray(payload)
    cs = parser.read_format0_charset(inp, n_glyphs=3, is_cid_font=False)
    assert cs.get_gid_for_sid(5) == 1
    assert cs.get_gid_for_sid(9) == 2
    # Unknown SID → 0 (upstream returns GID 0).
    assert cs.get_gid_for_sid(123) == 0


def test_format0_cid_uses_cid_not_sid_semantics() -> None:
    parser = CFFParser()
    # CID-keyed: the Card16 values are CIDs, surfaced via get_cid_for_gid.
    payload = _u16(100) + _u16(200) + _u16(300)
    inp = DataInputByteArray(payload)
    cs = parser.read_format0_charset(inp, n_glyphs=4, is_cid_font=True)
    assert cs.is_cid_font()
    assert cs.get_cid_for_gid(0) == 0
    assert cs.get_cid_for_gid(1) == 100
    assert cs.get_cid_for_gid(2) == 200
    assert cs.get_cid_for_gid(3) == 300
    assert cs.get_gid_for_cid(200) == 2


def test_format0_high_sid_falls_back_to_sid_string() -> None:
    parser = CFFParser()
    # SID 60000 is well past the standard-string table and no string index
    # is set → read_string returns "SID60000".
    payload = _u16(60000)
    inp = DataInputByteArray(payload)
    cs = parser.read_format0_charset(inp, n_glyphs=2, is_cid_font=False)
    assert cs.get_name_for_gid(1) == "SID60000"
    assert cs.get_sid_for_gid(1) == 60000


# ---------------------------------------------------------------------------
# Charset format 1 — (first, nLeft Card8) ranges
# ---------------------------------------------------------------------------


def test_format1_type1_single_range_expands_inclusive_of_nleft() -> None:
    parser = CFFParser()
    # first=10, nLeft=3 → 4 glyphs (GID 1..4) with SIDs 10,11,12,13.
    payload = _u8(1) + _u16(10) + _u8(3)
    inp = DataInputByteArray(payload)
    cs = parser.read_charset(inp, n_glyphs=5, is_cid_font=False)
    assert isinstance(cs, Format1Charset)
    assert [cs.get_sid_for_gid(g) for g in range(5)] == [0, 10, 11, 12, 13]
    assert cs.get_name_for_gid(4) == cffStandardStrings[13]


def test_format1_type1_zero_nleft_is_one_glyph() -> None:
    parser = CFFParser()
    # nLeft=0 → range of exactly one glyph. (format byte pre-consumed)
    payload = _u16(7) + _u8(0) + _u16(8) + _u8(0)
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=3, is_cid_font=False)
    assert cs.get_sid_for_gid(1) == 7
    assert cs.get_sid_for_gid(2) == 8


def test_format1_type1_two_ranges_consecutive_gids() -> None:
    parser = CFFParser()
    # range A: first=1, nLeft=1 → GID 1,2 (SID 1,2)
    # range B: first=20, nLeft=2 → GID 3,4,5 (SID 20,21,22)
    payload = _u16(1) + _u8(1) + _u16(20) + _u8(2)
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=6, is_cid_font=False)
    assert [cs.get_sid_for_gid(g) for g in range(6)] == [0, 1, 2, 20, 21, 22]


def test_format1_cid_range_mapping_forward_and_reverse() -> None:
    parser = CFFParser()
    # CID-keyed: first=1000, nLeft=4 → GID 1..5 map to CID 1000..1004.
    payload = _u16(1000) + _u8(4)
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=6, is_cid_font=True)
    assert isinstance(cs, Format1Charset)
    assert cs.get_cid_for_gid(1) == 1000
    assert cs.get_cid_for_gid(5) == 1004
    assert cs.get_gid_for_cid(1000) == 1
    assert cs.get_gid_for_cid(1004) == 5


def test_format1_cid_nleft_255_full_byte_range() -> None:
    parser = CFFParser()
    payload = _u16(0) + _u8(255)
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=257, is_cid_font=True)
    assert cs.get_cid_for_gid(1) == 0
    assert cs.get_cid_for_gid(256) == 255


def test_format1_type1_sid_to_gid_reverse() -> None:
    parser = CFFParser()
    payload = _u16(50) + _u8(2)
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=4, is_cid_font=False)
    # SID 50→GID1, 51→GID2, 52→GID3.
    assert cs.get_gid_for_sid(50) == 1
    assert cs.get_gid_for_sid(52) == 3


# ---------------------------------------------------------------------------
# Charset format 2 — (first, nLeft Card16) ranges
# ---------------------------------------------------------------------------


def test_format2_type1_single_range_16bit_nleft() -> None:
    parser = CFFParser()
    # first=1, nLeft=3 (Card16) → 4 glyphs, SIDs 1..4.
    payload = _u8(2) + _u16(1) + _u16(3)
    inp = DataInputByteArray(payload)
    cs = parser.read_charset(inp, n_glyphs=5, is_cid_font=False)
    assert isinstance(cs, Format2Charset)
    assert [cs.get_sid_for_gid(g) for g in range(5)] == [0, 1, 2, 3, 4]


def test_format2_cid_wide_range() -> None:
    parser = CFFParser()
    # first=2000, nLeft=999 → 1000 glyphs, CID 2000..2999.
    payload = _u16(2000) + _u16(999)
    inp = DataInputByteArray(payload)
    cs = parser.read_format2_charset(inp, n_glyphs=1001, is_cid_font=True)
    assert cs.get_cid_for_gid(1) == 2000
    assert cs.get_cid_for_gid(1000) == 2999
    assert cs.get_gid_for_cid(2999) == 1000


def test_format2_nleft_uses_two_bytes_not_one() -> None:
    parser = CFFParser()
    # If a parser mistakenly read nLeft as a single byte it would consume
    # only 0x01 (=1 extra) and then misalign. With Card16 nLeft=0x0102=258
    # we cover 259 glyphs.
    payload = _u16(1) + _u16(0x0102)
    inp = DataInputByteArray(payload)
    cs = parser.read_format2_charset(inp, n_glyphs=260, is_cid_font=True)
    assert cs.get_cid_for_gid(259) == 1 + 258
    # All 4 range bytes consumed exactly (format byte pre-consumed).
    assert inp.get_position() == 4


def test_format2_type1_two_single_glyph_ranges() -> None:
    parser = CFFParser()
    payload = _u16(3) + _u16(0) + _u16(4) + _u16(0)
    inp = DataInputByteArray(payload)
    cs = parser.read_format2_charset(inp, n_glyphs=3, is_cid_font=False)
    assert cs.get_sid_for_gid(1) == 3
    assert cs.get_sid_for_gid(2) == 4


# ---------------------------------------------------------------------------
# Charset dispatch / error cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_format", [3, 4, 200, 255])
def test_charset_unknown_format_rejected(bad_format: int) -> None:
    parser = CFFParser()
    inp = DataInputByteArray(_u8(bad_format))
    with pytest.raises(OSError, match=f"Incorrect charset format {bad_format}"):
        parser.read_charset(inp, n_glyphs=1, is_cid_font=False)


def test_charset_dispatch_selects_correct_reader() -> None:
    parser = CFFParser()
    f0 = DataInputByteArray(_u8(0) + _u16(1))
    f1 = DataInputByteArray(_u8(1) + _u16(1) + _u8(0))
    f2 = DataInputByteArray(_u8(2) + _u16(1) + _u16(0))
    assert not isinstance(
        parser.read_charset(f0, 2, False), (Format1Charset, Format2Charset)
    )
    assert isinstance(parser.read_charset(f1, 2, False), Format1Charset)
    assert isinstance(parser.read_charset(f2, 2, False), Format2Charset)


# ---------------------------------------------------------------------------
# Encoding format 0 — one code per GID
# ---------------------------------------------------------------------------


def _type1_charset_with_sids(parser: CFFParser, sids: list[int]) -> object:
    """Build a format-0 Type1 charset where GID g (1-based) → sids[g-1].

    The format-specific reader assumes the format byte is already
    consumed, so the payload holds only the SID Card16 sequence.
    """
    payload = b"".join(_u16(s) for s in sids)
    inp = DataInputByteArray(payload)
    return parser.read_format0_charset(inp, n_glyphs=len(sids) + 1, is_cid_font=False)


def test_encoding_format0_maps_codes_to_glyph_names() -> None:
    parser = CFFParser()
    # charset: GID1→SID1(space), GID2→SID2(exclam).
    charset = _type1_charset_with_sids(parser, [1, 2])
    # encoding format 0: nCodes=2, codes 65 ('A') and 66 ('B').
    enc_bytes = _u8(0) + _u8(2) + _u8(65) + _u8(66)
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert isinstance(enc, Format0Encoding)
    assert enc.n_codes == 2
    assert enc.get_name(65) == "space"
    assert enc.get_name(66) == "exclam"
    assert enc.get_name(0) == ".notdef"


def test_encoding_format0_notdef_at_code_zero_implicit() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1])
    enc_bytes = _u8(0) + _u8(1) + _u8(40)
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    # The parser always adds (0, 0, .notdef) before the table loop.
    assert enc.get_name(0) == ".notdef"
    assert enc.get_name(40) == "space"


def test_encoding_format0_code_to_sid_via_charset() -> None:
    parser = CFFParser()
    # GID1 carries SID 3 (quotedbl).
    charset = _type1_charset_with_sids(parser, [3])
    enc_bytes = _u8(0) + _u8(1) + _u8(34)  # code 34 (") → glyph quotedbl
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert enc.get_name(34) == "quotedbl"
    assert enc.get_code("quotedbl") == 34


# ---------------------------------------------------------------------------
# Encoding format 1 — (first, nLeft) ranges
# ---------------------------------------------------------------------------


def test_encoding_format1_single_range() -> None:
    parser = CFFParser()
    # charset: GID1→SID1(space), GID2→SID2(exclam), GID3→SID3(quotedbl).
    charset = _type1_charset_with_sids(parser, [1, 2, 3])
    # encoding format 1: nRanges=1, first code=65, nLeft=2 → codes 65,66,67
    # assigned to GID 1,2,3.
    enc_bytes = _u8(1) + _u8(1) + _u8(65) + _u8(2)
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert isinstance(enc, Format1Encoding)
    assert enc.n_ranges == 1
    assert enc.get_name(65) == "space"
    assert enc.get_name(66) == "exclam"
    assert enc.get_name(67) == "quotedbl"


def test_encoding_format1_nleft_inclusive() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1, 2])
    # nLeft=1 → 2 codes (first, first+1).
    enc_bytes = _u8(1) + _u8(1) + _u8(97) + _u8(1)
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert enc.get_name(97) == "space"
    assert enc.get_name(98) == "exclam"
    # code 99 was never assigned.
    assert enc.get_name(99) == ".notdef"


def test_encoding_format1_two_ranges() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1, 2, 3, 4])
    # range A: first=10, nLeft=0 → code 10 → GID1
    # range B: first=20, nLeft=2 → codes 20,21,22 → GID2,3,4
    enc_bytes = _u8(1) + _u8(2) + _u8(10) + _u8(0) + _u8(20) + _u8(2)
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert enc.get_name(10) == "space"
    assert enc.get_name(20) == "exclam"
    assert enc.get_name(22) == cffStandardStrings[4]


def test_encoding_unknown_base_format_rejected() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1])
    inp = DataInputByteArray(_u8(2))  # base format 2 is invalid
    with pytest.raises(OSError, match="Invalid encoding base format 2"):
        parser.read_encoding(inp, charset)


# ---------------------------------------------------------------------------
# Encoding supplement (0x80 bit)
# ---------------------------------------------------------------------------


def test_encoding_format0_supplement_appends_extra_mappings() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1])
    # format byte 0x80 → base 0 + supplement. nCodes=1, code 65.
    # Then supplement: nSups=1, (code=200, sid=2 (exclam)).
    enc_bytes = (
        _u8(0x80) + _u8(1) + _u8(65) + _u8(1) + _u8(200) + _u16(2)
    )
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert enc.get_name(65) == "space"
    # Supplemental mapping added.
    assert enc.get_name(200) == "exclam"
    assert len(enc.supplement) == 1
    assert enc.supplement[0].code == 200
    assert enc.supplement[0].sid == 2


def test_encoding_format1_supplement_bit_does_not_change_base_class() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1])
    # format byte 0x81 → base format 1 + supplement.
    # nRanges=1: first code=50, nLeft=0 → code 50 → GID1 (SID1, space).
    # supplement: nSups=1, (code=99, sid=3 quotedbl).
    enc_bytes = (
        _u8(0x81) + _u8(1) + _u8(50) + _u8(0) + _u8(1) + _u8(99) + _u16(3)
    )
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert isinstance(enc, Format1Encoding)
    assert enc.get_name(50) == "space"
    assert enc.get_name(99) == "quotedbl"
    assert len(enc.supplement) == 1


def test_encoding_no_supplement_bit_leaves_supplement_empty() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1])
    enc_bytes = _u8(0) + _u8(1) + _u8(65)
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert enc.supplement == ()
    # No extra bytes consumed for a supplement table.
    assert inp.get_position() == 3


def test_encoding_supplement_multiple_entries() -> None:
    parser = CFFParser()
    charset = _type1_charset_with_sids(parser, [1])
    # base 0, nCodes=1 code 65; supplement nSups=2:
    # (code=128,sid=2 exclam),(code=129,sid=3 quotedbl).
    enc_bytes = (
        _u8(0x80)
        + _u8(1)
        + _u8(65)
        + _u8(2)
        + _u8(128)
        + _u16(2)
        + _u8(129)
        + _u16(3)
    )
    inp = DataInputByteArray(enc_bytes)
    enc = parser.read_encoding(inp, charset)
    assert len(enc.supplement) == 2
    assert enc.get_name(128) == "exclam"
    assert enc.get_name(129) == "quotedbl"


# ---------------------------------------------------------------------------
# Predefined charsets / encodings (resolved to tables, not parsed as offsets)
# ---------------------------------------------------------------------------


def test_predefined_iso_adobe_charset_gid_equals_sid() -> None:
    cs = CFFISOAdobeCharset.get_instance()
    # ISOAdobe: GID == SID for the predefined glyphs; GID1 → "space".
    assert cs.get_sid_for_gid(1) == 1
    assert cs.get_name_for_gid(1) == "space"
    assert cs.get_gid_for_sid(1) == 1


def test_predefined_expert_charset_resolves() -> None:
    cs = CFFExpertCharset.get_instance()
    # GID 0 is .notdef in every charset.
    assert cs.get_name_for_gid(0) == ".notdef"
    # Expert charset is non-trivially populated.
    assert cs.get_sid_for_gid(1) != 0


def test_predefined_expert_subset_charset_resolves() -> None:
    cs = CFFExpertSubsetCharset.get_instance()
    assert cs.get_name_for_gid(0) == ".notdef"
    assert cs.get_sid_for_gid(1) != 0


def test_predefined_charset_singletons_are_shared() -> None:
    assert CFFISOAdobeCharset.get_instance() is CFFISOAdobeCharset.get_instance()
    assert CFFExpertCharset.get_instance() is CFFExpertCharset.get_instance()


def test_predefined_standard_encoding_maps_ascii() -> None:
    enc = CFFStandardEncoding.get_instance()
    # Standard encoding: code 65 → "A".
    assert enc.get_name(65) == "A"
    assert enc.get_name(97) == "a"
    assert enc.get_code("A") == 65


def test_predefined_expert_encoding_resolves() -> None:
    enc = CFFExpertEncoding.get_instance()
    # Expert encoding is populated and differs from standard for many codes.
    assert enc is CFFExpertEncoding.get_instance()
    # At least one code maps to a non-notdef name.
    assert any(
        enc.get_name(c) != ".notdef" for c in range(256)
    )


# ---------------------------------------------------------------------------
# name <-> SID <-> GID round-trips
# ---------------------------------------------------------------------------


def test_name_sid_gid_roundtrip_format0() -> None:
    parser = CFFParser()
    # GID1→SID1(space), GID2→SID2(exclam), GID3→SID3(quotedbl).
    cs = _type1_charset_with_sids(parser, [1, 2, 3])
    for gid, name in ((1, "space"), (2, "exclam"), (3, "quotedbl")):
        sid = cs.get_sid_for_gid(gid)
        assert cs.get_name_for_gid(gid) == name
        assert cs.get_sid(name) == sid
        assert cs.get_gid_for_sid(sid) == gid


def test_name_sid_gid_roundtrip_format1_range() -> None:
    parser = CFFParser()
    # first SID 1, nLeft 2 → GID1..3 → SID1..3. (format byte pre-consumed)
    payload = _u16(1) + _u8(2)
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=4, is_cid_font=False)
    for gid in (1, 2, 3):
        sid = cs.get_sid_for_gid(gid)
        name = cs.get_name_for_gid(gid)
        assert name == cffStandardStrings[sid]
        assert cs.get_gid_for_sid(sid) == gid
        assert cs.get_sid(name) == sid


def test_cid_charset_sid_is_cid_not_glyph_name() -> None:
    parser = CFFParser()
    # For a CID font, the format-0 Card16 values are CIDs; there is no
    # glyph-name table. get_cid_for_gid surfaces the CID directly.
    payload = _u16(7) + _u16(42)
    inp = DataInputByteArray(payload)
    cs = parser.read_format0_charset(inp, n_glyphs=3, is_cid_font=True)
    assert cs.is_cid_font()
    assert cs.get_cid_for_gid(1) == 7
    assert cs.get_cid_for_gid(2) == 42
    # Reverse: CID 42 → GID 2.
    assert cs.get_gid_for_cid(42) == 2
