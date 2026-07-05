"""Wave 1598 (Agent B) — fuzz the TrueType ``name`` table decode for
behavioral parity with Apache PDFBox 3.0.7
(``org.apache.fontbox.ttf.NamingTable`` / ``NameRecord``).

Focus areas (every one oracle-verified against the live 3.0.7 jar via
``NamingTableFuzzProbe``):

  * the string-storage base: upstream computes it as ``6 + 12*numRecords``
    past the table start (``NamingTable.java`` line 99) and IGNORES the
    header's declared storage offset;
  * the PDFBOX-2608 guard: only ``stringOffset > tableLength`` skips the
    read (record kept, string ``None``) — a string that starts inside the
    table but crosses the declared table end is read from the following
    file bytes, and a read past EOF fails the whole parse (``OSError``,
    mirroring the ``IOException`` out of ``TTFParser.parse``);
  * per-record charset selection: Windows encodings 0/1 and the whole
    Unicode platform decode as Java ``StandardCharsets.UTF_16`` (BOM-aware,
    default BIG-endian), Windows encoding 10 (UCS-4) is NOT special-cased
    and falls to Latin-1, ISO enc 0 → US-ASCII, ISO enc 1 → strict UTF-16BE
    (BOM retained as U+FEFF/U+FFFE), Macintosh + everything else → Latin-1;
  * PostScript-name resolution (Mac Roman English first, then Windows BMP
    en-US) with ``String.trim()`` semantics — chars <= U+0020 stripped from
    both ends, Unicode whitespace like U+00A0 kept;
  * English-name resolution priority (Unicode encodings 4→0, Windows BMP
    en-US, Mac Roman English) and the getName lookup map (duplicate
    records: last one wins, mirroring ``HashMap.put``).

The synthetic fonts are complete minimal TTFs (head/hhea/maxp/hmtx/loca/
glyf/cmap/post/name, 2 glyphs to clear the PDFBOX-5794 no-glyphs check) so
both sides run the full public ``TTFParser.parse`` path.
"""

from __future__ import annotations

import random
import struct

import pytest

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders, TTFParser

# --------------------------------------------------------------------------
# minimal complete TTF builder
# --------------------------------------------------------------------------

WIN = NameRecord.PLATFORM_WINDOWS
MAC = NameRecord.PLATFORM_MACINTOSH
UNI = NameRecord.PLATFORM_UNICODE
ISO = NameRecord.PLATFORM_ISO
BMP = NameRecord.ENCODING_WINDOWS_UNICODE_BMP
EN_US = NameRecord.LANGUAGE_WINDOWS_EN_US

_FAMILY = NameRecord.NAME_FONT_FAMILY_NAME
_SUBFAMILY = NameRecord.NAME_FONT_SUB_FAMILY_NAME
_PSNAME = NameRecord.NAME_POSTSCRIPT_NAME
_FULL = NameRecord.NAME_FULL_FONT_NAME


def _build_head() -> bytes:
    return struct.pack(
        ">IIII H H 8s 8s hhhh HH hhh",
        0x00010000, 0x00010000, 0, 0x5F0F3CF5,
        0, 1000, b"\x00" * 8, b"\x00" * 8,
        0, 0, 100, 100, 0, 8, 2, 0, 0,
    )


def _build_hhea() -> bytes:
    return struct.pack(
        ">I hhh H hhh hhh hhhh h H",
        0x00010000, 800, -200, 90, 500, 0, 0, 500,
        1, 0, 0, 0, 0, 0, 0, 0, 1,
    )


def _build_maxp() -> bytes:
    # numGlyphs=2: a single all-zero-loca glyph trips upstream's
    # PDFBOX-5794 "The font has no glyphs" rejection.
    return struct.pack(">IH", 0x00010000, 2) + b"\x00" * 26


def _build_post() -> bytes:
    return struct.pack(">IIhhIIIII", 0x00030000, 0, 0, 0, 0, 0, 0, 0, 0)


def _build_cmap() -> bytes:
    sub = struct.pack(">HHH", 0, 262, 0) + bytes(256)
    return struct.pack(">HH", 0, 1) + struct.pack(">HHI", 1, 0, 12) + sub


def build_name(
    records: list[tuple[int, int, int, int, int, int]],
    storage: bytes,
    *,
    format_selector: int = 0,
    declared_storage_offset: int | None = None,
) -> bytes:
    """records: (platform, encoding, language, name_id, length, offset)."""
    n = len(records)
    decl = 6 + 12 * n if declared_storage_offset is None else declared_storage_offset
    blob = struct.pack(">HHH", format_selector, n, decl)
    for rec in records:
        blob += struct.pack(">HHHHHH", *rec)
    return blob + storage


def build_name_pool(
    records: list[tuple[int, int, int, int, bytes]],
    **kwargs: object,
) -> bytes:
    """records: (platform, encoding, language, name_id, raw_bytes) — offsets
    are laid out sequentially in a string pool."""
    pool = b""
    fixed: list[tuple[int, int, int, int, int, int]] = []
    for plat, enc, lang, nid, raw in records:
        fixed.append((plat, enc, lang, nid, len(raw), len(pool)))
        pool += raw
    return build_name(fixed, pool, **kwargs)  # type: ignore[arg-type]


def build_font(
    name_table: bytes,
    *,
    name_last: bool = True,
    name_declared_length: int | None = None,
    trailing_junk: bytes = b"",
) -> bytes:
    tables = [
        ("head", _build_head(), None),
        ("hhea", _build_hhea(), None),
        ("maxp", _build_maxp(), None),
        ("hmtx", struct.pack(">Hhh", 500, 0, 0), None),
        ("loca", bytes(6), None),
        ("glyf", bytes(4), None),
        ("cmap", _build_cmap(), None),
    ]
    if name_last:
        tables.append(("post", _build_post(), None))
        tables.append(("name", name_table, name_declared_length))
    else:
        tables.append(("name", name_table, name_declared_length))
        tables.append(("post", _build_post(), None))
    num = len(tables)
    entry_selector = num.bit_length() - 1
    search_range = (1 << entry_selector) * 16
    header = struct.pack(
        ">IHHHH", 0x00010000, num, search_range, entry_selector,
        num * 16 - search_range,
    )
    offset = 12 + 16 * num
    offsets: dict[str, int] = {}
    body = b""
    for tag, data, _decl in tables:
        offsets[tag] = offset
        body += data
        offset += len(data)
    entries = b""
    for tag, data, decl in sorted(tables, key=lambda t: t[0]):
        ln = len(data) if decl is None else decl
        entries += struct.pack(">4sIII", tag.encode("ascii"), 0, offsets[tag], ln)
    return header + entries + body + trailing_junk


# --------------------------------------------------------------------------
# canonical dump (same wire format as NamingTableFuzzProbe)
# --------------------------------------------------------------------------


def _esc(s: str | None) -> str:
    if s is None:
        return "NULL"
    out = "S:"
    for ch in s:
        cp = ord(ch)
        if 0x20 <= cp <= 0x7E and ch != "\\":
            out += ch
        elif cp > 0xFFFF:
            # match Java's UTF-16 string model: astral chars print as a
            # surrogate pair
            cp -= 0x10000
            out += f"\\u{0xD800 + (cp >> 10):04x}\\u{0xDC00 + (cp & 0x3FF):04x}"
        else:
            out += f"\\u{cp:04x}"
    return out


def py_dump(font: bytes) -> str:
    """Parse with pypdfbox and dump the naming surface canonically.

    Parse failures collapse to ``"ERROR"`` — upstream fails with an
    IOException whose Python mapping is OSError (or EOFError for the
    short-read primitives), and the probe reports the class name only.
    """
    try:
        ttf = TTFParser().parse(font)
    except (OSError, EOFError):
        return "ERROR"
    try:
        name = ttf.get_naming()
        if name is None:
            return "NAME\tabsent"
        lines = ["NAME\tpresent"]
        records = name.get_name_records()
        lines.append(f"COUNT\t{len(records)}")
        for i, nr in enumerate(records):
            lines.append(
                f"REC\t{i}\t{nr.get_platform_id()}\t{nr.get_platform_encoding_id()}"
                f"\t{nr.get_language_id()}\t{nr.get_name_id()}\t{_esc(nr.get_string())}"
            )
        lines.append(f"FAMILY\t{_esc(name.get_font_family())}")
        lines.append(f"SUBFAMILY\t{_esc(name.get_font_sub_family())}")
        lines.append(f"PSNAME\t{_esc(name.get_post_script_name())}")
        return "\n".join(lines)
    finally:
        ttf.close()


# --------------------------------------------------------------------------
# fuzz corpus
# --------------------------------------------------------------------------

def _u16(s: str) -> bytes:
    return s.encode("utf-16-be")


def _corpus() -> dict[str, bytes]:
    cases: dict[str, bytes] = {}

    def add(label: str, name_table: bytes, **kwargs: object) -> None:
        cases[label] = build_font(name_table, **kwargs)  # type: ignore[arg-type]

    # -- storage base / offset guard ------------------------------------
    raw = _u16("Offset Sans")
    add("declared_offset_padding_ignored", build_name(
        [(WIN, BMP, EN_US, _FAMILY, len(raw), 0)], b"xxxx" + raw,
        declared_storage_offset=6 + 12 + 4))
    add("declared_offset_lies_low", build_name(
        [(WIN, BMP, EN_US, _FAMILY, len(raw), 0)], raw,
        declared_storage_offset=2))
    add("string_at_computed_base", build_name(
        [(WIN, BMP, EN_US, _FAMILY, len(raw), 0)], raw,
        declared_storage_offset=6 + 12 + 4))
    add("offset_beyond_table_length_null_string", build_name(
        [(WIN, BMP, EN_US, _FAMILY, 4, 500)], b"\x00A\x00B"))
    add("offset_at_exact_table_length_reads_on", build_name(
        # stringOffset == tableLength is NOT > tableLength: upstream reads.
        [(WIN, BMP, EN_US, _FAMILY, 2, 34)],
        b"\x00A\x00B" + bytes(30) + b"\x00Z"))
    add("overflow_into_next_table", build_name(
        [(WIN, BMP, EN_US, _FAMILY, 20, 0)], b"\x00A\x00B"),
        name_last=False)
    add("overflow_past_eof_error", build_name(
        [(WIN, BMP, EN_US, _FAMILY, 40, 0)], b"\x00A\x00B"))
    add("second_record_bad_offset_first_ok", build_name(
        [(WIN, BMP, EN_US, _FAMILY, 4, 0),
         (WIN, BMP, EN_US, _SUBFAMILY, 2, 999)],
        b"\x00O\x00K"))

    # -- charset selection ------------------------------------------------
    add("win_symbol_utf16", build_name_pool(
        [(WIN, NameRecord.ENCODING_WINDOWS_SYMBOL, EN_US, _FAMILY,
          _u16("Sym"))]))
    add("win_bmp_utf16", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, _u16("Family"))]))
    add("win_ucs4_is_latin1", build_name_pool(
        [(WIN, NameRecord.ENCODING_WINDOWS_UNICODE_UCS4, EN_US, _FAMILY,
          _u16("Hi"))]))
    add("win_shiftjis_enc2_latin1", build_name_pool(
        [(WIN, 2, 0x0411, _FAMILY, bytes([0x82, 0xA0, 0x41]))]))
    add("unicode_platform_enc3", build_name_pool(
        [(UNI, 3, 0, _FAMILY, _u16("Uni"))]))
    add("unicode_platform_enc7_still_utf16", build_name_pool(
        [(UNI, 7, 0, _FAMILY, _u16("U7"))]))
    add("mac_roman_high_bytes_latin1", build_name_pool(
        [(MAC, 0, 0, _FAMILY, bytes([0x41, 0xAA, 0xC0]))]))
    add("mac_script99_latin1", build_name_pool(
        [(MAC, 99, 0, _FAMILY, bytes([0xC0, 0xC1]))]))
    add("iso_ascii_high_bytes_replaced", build_name_pool(
        [(ISO, 0, 0, _FAMILY, b"A\x80B\xffC")]))
    add("iso_utf16be_plain", build_name_pool(
        [(ISO, 1, 0, _FAMILY, _u16("Iso"))]))
    add("iso_enc2_default_latin1", build_name_pool(
        [(ISO, 2, 0, _FAMILY, b"\xe9\xea")]))
    add("platform7_unknown_latin1", build_name_pool(
        [(7, 4, 2, _FAMILY, b"\x00Q\xfe")]))

    # -- BOM handling -----------------------------------------------------
    add("win_bmp_be_bom_consumed", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xfe\xff" + _u16("Be"))]))
    add("win_bmp_le_bom_consumed_le_decode", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xff\xfe" + "Le".encode("utf-16-le"))]))
    add("win_bmp_no_bom_big_endian", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, _u16("Nb"))]))
    add("unicode_le_bom", build_name_pool(
        [(UNI, 3, 0, _FAMILY, b"\xff\xfe" + "Ul".encode("utf-16-le"))]))
    add("iso_utf16be_be_bom_retained", build_name_pool(
        [(ISO, 1, 0, _FAMILY, b"\xfe\xff" + _u16("Iso"))]))
    add("iso_utf16be_le_bom_retained_be_decode", build_name_pool(
        [(ISO, 1, 0, _FAMILY, b"\xff\xfe" + _u16("Iso"))]))
    add("bom_only_string", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xfe\xff")]))

    # -- malformed UTF-16 payloads -----------------------------------------
    add("odd_length_utf16", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, _u16("Odd") + b"\x00")]))
    add("lone_high_surrogate", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xd8\x00\x00A")]))
    add("lone_low_surrogate", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xdc\x00\x00B")]))
    add("astral_surrogate_pair", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, "A\U0001d400B".encode("utf-16-be"))]))
    add("high_surrogate_then_odd_tail", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xd8\x00\x41")]))
    add("high_surrogate_at_end", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, "A".encode("utf-16-be") + b"\xd8\x00")]))
    add("two_high_surrogates_then_char", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"\xd8\x00\xd8\x00\x00A")]))
    add("iso_utf16be_lone_high_surrogate", build_name_pool(
        [(ISO, 1, 0, _FAMILY, b"\xd8\x00\x00A")]))
    add("empty_string_record", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, b"")]))

    # -- psName trim + priority --------------------------------------------
    add("psname_java_trim_controls", build_name_pool(
        [(WIN, BMP, EN_US, _PSNAME, _u16("\x00\x01 PSName \x00"))]))
    add("psname_nbsp_not_trimmed", build_name_pool(
        [(WIN, BMP, EN_US, _PSNAME, _u16(" PS "))]))
    add("psname_all_whitespace", build_name_pool(
        [(WIN, BMP, EN_US, _PSNAME, _u16("  \t "))]))
    add("psname_mac_beats_windows", build_name_pool(
        [(WIN, BMP, EN_US, _PSNAME, _u16("WinPS")),
         (MAC, 0, 0, _PSNAME, b"MacPS")]))
    add("psname_windows_fallback", build_name_pool(
        [(WIN, BMP, EN_US, _PSNAME, _u16("WinPS")),
         (MAC, 0, 6, _PSNAME, b"MacFrenchPS")]))  # lang 6 != Mac English

    # -- english-name resolution priority -----------------------------------
    add("family_unicode_enc4_beats_enc0_and_win", build_name_pool(
        [(UNI, 0, 0, _FAMILY, _u16("U0")),
         (UNI, 4, 0, _FAMILY, _u16("U4")),
         (WIN, BMP, EN_US, _FAMILY, _u16("Win"))]))
    add("family_win_beats_mac", build_name_pool(
        [(MAC, 0, 0, _FAMILY, b"MacFam"),
         (WIN, BMP, EN_US, _FAMILY, _u16("WinFam"))]))
    add("family_mac_only", build_name_pool(
        [(MAC, 0, 0, _FAMILY, b"MacFam")]))
    add("family_win_wrong_lang_ignored", build_name_pool(
        [(WIN, BMP, 0x0407, _FAMILY, _u16("DeFam"))]))
    add("duplicate_records_last_wins", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, _u16("First")),
         (WIN, BMP, EN_US, _FAMILY, _u16("Second"))]))
    add("null_string_record_family_falls_through", build_name(
        # family record has an invalid offset (null string); the Mac record
        # still resolves — upstream getName returns null for the Windows
        # slot and getEnglishName falls through.
        [(WIN, BMP, EN_US, _FAMILY, 4, 900),
         (MAC, 0, 0, _FAMILY, 6, 0)],
        b"MacFam"))

    # -- header / structure edges -------------------------------------------
    add("zero_records", build_name([], b""))
    add("format_selector_1_same_layout", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, _u16("Fmt1"))], format_selector=1))
    add("typographic_family_nid16_stored_not_family", build_name_pool(
        [(WIN, BMP, EN_US, 16, _u16("TypoFam"))]))
    add("record_count_overruns_table_error", build_name(
        [(WIN, BMP, EN_US, _FAMILY, 2, 0)], b"\x00A")[:12])
    add("subfamily_and_full_name", build_name_pool(
        [(WIN, BMP, EN_US, _FAMILY, _u16("Fam")),
         (WIN, BMP, EN_US, _SUBFAMILY, _u16("Bold")),
         (WIN, BMP, EN_US, _FULL, _u16("Fam Bold"))]))

    # -- seeded random structured fuzz ---------------------------------------
    rng = random.Random(1598)
    platforms = [0, 1, 2, 3, 3, 3, 4, 7]
    encodings = [0, 1, 2, 3, 4, 10, 99]
    languages = [0, 6, 0x0409, 0x0407, 0xFFFF]
    name_ids = [0, 1, 2, 4, 5, 6, 7, 16, 25]
    for i in range(10):
        n_records = rng.randint(1, 5)
        records = []
        pool_len = rng.randint(0, 40)
        for _ in range(n_records):
            records.append((
                rng.choice(platforms),
                rng.choice(encodings),
                rng.choice(languages),
                rng.choice(name_ids),
                rng.randint(0, 24),
                rng.randint(0, 60),
            ))
        pool = bytes(rng.randrange(256) for _ in range(pool_len))
        add(f"random_{i}", build_name(records, pool), trailing_junk=bytes(64))

    return cases


CASES = _corpus()
CASE_IDS = sorted(CASES)


# --------------------------------------------------------------------------
# pure-Python pins of the oracle-established semantics
# --------------------------------------------------------------------------


def _naming(label: str) -> NamingTable:
    ttf = TTFParser().parse(CASES[label])
    naming = ttf.get_naming()
    assert naming is not None
    return naming


def test_storage_base_is_computed_not_declared() -> None:
    naming = _naming("declared_offset_padding_ignored")
    raw = _u16("Offset Sans")
    expected = (b"xxxx" + raw)[: len(raw)].decode("utf-16-be")
    assert naming.get_name_records()[0].get_string() == expected
    assert naming.get_font_family() == expected


def test_declared_offset_lower_than_records_end_also_ignored() -> None:
    naming = _naming("declared_offset_lies_low")
    assert naming.get_font_family() == "Offset Sans"


def test_offset_beyond_table_length_keeps_record_with_none_string() -> None:
    naming = _naming("offset_beyond_table_length_null_string")
    records = naming.get_name_records()
    assert len(records) == 1
    assert records[0].get_string() is None
    assert naming.get_font_family() is None


def test_offset_equal_to_table_length_is_read() -> None:
    naming = _naming("offset_at_exact_table_length_reads_on")
    assert naming.get_name_records()[0].get_string() == "Z"


def test_overflow_into_next_table_reads_following_bytes() -> None:
    naming = _naming("overflow_into_next_table")
    s = naming.get_name_records()[0].get_string()
    assert s is not None
    assert len(s) == 10  # 20 bytes of UTF-16BE
    assert s.startswith("AB")  # the four in-table bytes \x00A\x00B


def test_overflow_past_eof_fails_parse() -> None:
    with pytest.raises((OSError, EOFError)):
        TTFParser().parse(CASES["overflow_past_eof_error"])


def test_record_count_overrunning_table_fails_parse() -> None:
    with pytest.raises((OSError, EOFError)):
        TTFParser().parse(CASES["record_count_overruns_table_error"])


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("win_symbol_utf16", "Sym"),
        ("win_bmp_utf16", "Family"),
        ("win_ucs4_is_latin1", _u16("Hi").decode("latin-1")),
        ("win_shiftjis_enc2_latin1", bytes([0x82, 0xA0, 0x41]).decode("latin-1")),
        ("unicode_platform_enc3", "Uni"),
        ("unicode_platform_enc7_still_utf16", "U7"),
        ("mac_roman_high_bytes_latin1", bytes([0x41, 0xAA, 0xC0]).decode("latin-1")),
        ("mac_script99_latin1", bytes([0xC0, 0xC1]).decode("latin-1")),
        ("iso_ascii_high_bytes_replaced", "A�B�C"),
        ("iso_utf16be_plain", "Iso"),
        ("iso_enc2_default_latin1", "\xe9\xea"),
        ("platform7_unknown_latin1", "\x00Q\xfe"),
    ],
    ids=lambda v: v if isinstance(v, str) and not v.startswith(("\x00", "A�")) else "expected",
)
def test_charset_selection(label: str, expected: str) -> None:
    naming = _naming(label)
    assert naming.get_name_records()[0].get_string() == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("win_bmp_be_bom_consumed", "Be"),
        ("win_bmp_le_bom_consumed_le_decode", "Le"),
        ("win_bmp_no_bom_big_endian", "Nb"),
        ("unicode_le_bom", "Ul"),
        ("iso_utf16be_be_bom_retained", "﻿Iso"),
        ("iso_utf16be_le_bom_retained_be_decode", "￾Iso"),
        ("bom_only_string", ""),
    ],
    ids=[
        "be_bom", "le_bom", "no_bom", "unicode_le_bom",
        "iso_be_bom_kept", "iso_le_bom_kept", "bom_only",
    ],
)
def test_bom_handling(label: str, expected: str) -> None:
    naming = _naming(label)
    assert naming.get_name_records()[0].get_string() == expected


def test_odd_length_utf16_trailing_byte_replaced() -> None:
    naming = _naming("odd_length_utf16")
    assert naming.get_name_records()[0].get_string() == "Odd�"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        # Java's UTF-16 decoder treats a high surrogate + the FOLLOWING
        # unit as one 4-byte malformed sequence → a single U+FFFD (the
        # Python codec would keep the following char). Oracle-verified.
        ("lone_high_surrogate", "�"),
        ("lone_low_surrogate", "�B"),
        ("astral_surrogate_pair", "A\U0001d400B"),
        ("high_surrogate_then_odd_tail", "�"),
        ("high_surrogate_at_end", "A�"),
        ("two_high_surrogates_then_char", "�A"),
        ("iso_utf16be_lone_high_surrogate", "�"),
    ],
    ids=[
        "high_plus_char", "low_plus_char", "valid_pair", "high_odd_tail",
        "high_at_end", "two_highs_char", "iso_be_high_plus_char",
    ],
)
def test_surrogate_malformed_java_semantics(label: str, expected: str) -> None:
    naming = _naming(label)
    assert naming.get_name_records()[0].get_string() == expected


def test_empty_string_record_yields_empty_family() -> None:
    naming = _naming("empty_string_record")
    assert naming.get_name_records()[0].get_string() == ""
    assert naming.get_font_family() == ""


def test_psname_java_trim_strips_controls_and_spaces() -> None:
    naming = _naming("psname_java_trim_controls")
    assert naming.get_post_script_name() == "PSName"
    # the record string itself is untrimmed
    assert naming.get_name_records()[0].get_string() == "\x00\x01 PSName \x00"


def test_psname_nbsp_survives_java_trim() -> None:
    naming = _naming("psname_nbsp_not_trimmed")
    assert naming.get_post_script_name() == " PS "


def test_psname_all_whitespace_trims_to_empty() -> None:
    naming = _naming("psname_all_whitespace")
    assert naming.get_post_script_name() == ""


def test_psname_mac_roman_english_beats_windows() -> None:
    naming = _naming("psname_mac_beats_windows")
    assert naming.get_post_script_name() == "MacPS"


def test_psname_windows_fallback_when_mac_lang_not_english() -> None:
    naming = _naming("psname_windows_fallback")
    assert naming.get_post_script_name() == "WinPS"


def test_family_unicode_priority_enc4_first() -> None:
    naming = _naming("family_unicode_enc4_beats_enc0_and_win")
    assert naming.get_font_family() == "U4"


def test_family_windows_beats_mac() -> None:
    naming = _naming("family_win_beats_mac")
    assert naming.get_font_family() == "WinFam"


def test_family_mac_only() -> None:
    naming = _naming("family_mac_only")
    assert naming.get_font_family() == "MacFam"


def test_family_windows_wrong_language_ignored() -> None:
    naming = _naming("family_win_wrong_lang_ignored")
    assert naming.get_font_family() is None
    # but the record itself is present and decoded
    assert naming.get_name_records()[0].get_string() == "DeFam"


def test_duplicate_records_last_wins_in_lookup() -> None:
    naming = _naming("duplicate_records_last_wins")
    assert len(naming.get_name_records()) == 2
    assert naming.get_font_family() == "Second"
    assert naming.get_name(_FAMILY, WIN, BMP, EN_US) == "Second"


def test_null_string_record_falls_through_to_mac() -> None:
    naming = _naming("null_string_record_family_falls_through")
    assert naming.get_name_records()[0].get_string() is None
    assert naming.get_font_family() == "MacFam"


def test_zero_records_table() -> None:
    naming = _naming("zero_records")
    assert naming.get_name_records() == []
    assert naming.get_font_family() is None
    assert naming.get_post_script_name() is None


def test_format_selector_1_parsed_like_format_0() -> None:
    naming = _naming("format_selector_1_same_layout")
    assert naming.get_font_family() == "Fmt1"


def test_typographic_family_nid16_not_used_for_family() -> None:
    naming = _naming("typographic_family_nid16_stored_not_family")
    assert naming.get_font_family() is None
    assert naming.get_name(16, WIN, BMP, EN_US) == "TypoFam"


def test_random_cases_parse_or_fail_cleanly() -> None:
    for label in CASE_IDS:
        if not label.startswith("random_"):
            continue
        try:
            ttf = TTFParser().parse(CASES[label])
        except (OSError, EOFError):
            continue
        naming = ttf.get_naming()
        assert naming is not None
        for nr in naming.get_name_records():
            s = nr.get_string()
            assert s is None or isinstance(s, str)
        ttf.close()


# --------------------------------------------------------------------------
# read_headers (FileSystemFontProvider fast path) parity
# --------------------------------------------------------------------------


def test_read_headers_filters_but_resolves_same_names() -> None:
    font = CASES["subfamily_and_full_name"]
    full = TTFParser().parse(font)
    naming_full = full.get_naming()
    assert naming_full is not None

    headers = TTFParser().parse_table_headers(font)
    assert isinstance(headers, FontHeaders)
    assert headers.get_error() is None
    assert headers.get_font_family() == naming_full.get_font_family() == "Fam"
    assert headers.get_name() == naming_full.get_post_script_name()
    full.close()


# --------------------------------------------------------------------------
# live oracle differential (skipped without the jar / JDK)
# --------------------------------------------------------------------------

try:
    from tests.oracle.harness import oracle_available, run_probe_text
except ImportError:  # pragma: no cover - harness always present in-repo
    oracle_available = None  # type: ignore[assignment]


def _java_dump(font: bytes, path: str) -> str:
    with open(path, "wb") as f:
        f.write(font)
    out = run_probe_text("NamingTableFuzzProbe", path).rstrip("\n")
    if out.startswith("ERROR\t"):
        return "ERROR"
    return out


@pytest.mark.skipif(
    oracle_available is None or not oracle_available(),
    reason="live PDFBox oracle unavailable",
)
@pytest.mark.parametrize("label", CASE_IDS)
def test_name_table_matches_live_oracle(label: str, tmp_path) -> None:
    font = CASES[label]
    java = _java_dump(font, str(tmp_path / f"{label}.ttf"))
    assert py_dump(font) == java
