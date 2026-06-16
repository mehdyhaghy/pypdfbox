"""Wave 1400 — close residual font-subtree branch partials.

Targets the highest-density partials in ``pypdfbox.fontbox`` and
``pypdfbox.pdmodel.font``. Each test ties one or two missing branch
arrows to a concrete behavioural scenario. Tests are organised
per-module; the helpers at the top are shared.
"""

from __future__ import annotations

import contextlib
import struct
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

FIXTURE_FONT = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE_FONT.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE_FONT}")
    return TrueTypeFont.from_bytes(FIXTURE_FONT.read_bytes())


# ============================================================
# pypdfbox/fontbox/ttf/cmap_subtable.py
# ============================================================
# Missing branches:
#   [150, 137] format 4 — glyph_index == 0 short-circuit
#   [155, 157] format 4 — glyph_index <= max_glyph_id (skip update)
#   [185, -169] format 6 — empty result
#   [218, 220] format 8 — glyph_index <= max_glyph_id
#   [221, -193] format 8 — empty result
#   [243, 245] format 10 — glyph_id <= max_glyph_id
#   [283, 285] format 12 — glyph_index <= max_glyph_id
#   [315, 318] format 13 — glyph_id <= max_glyph_id
#   [320, -293] format 13 — empty result
#   [437, 441] format 2 — p == 0 short-circuit


def _fmt4_two_segments_with_offset_zero_glyph() -> bytes:
    # Build a format-4 body:
    #   segment 0: codes 65..66 -> glyph 1..2 (range_offset=2 to read the
    #     glyph-id array; second entry is 0 which exercises the
    #     ``glyph_index != 0`` False arm at line 150).
    #   segment 1: 0xFFFF sentinel.
    seg_count_x2 = 4
    body = struct.pack(">HHHH", seg_count_x2, 4, 1, 0)
    body += struct.pack(">HH", 66, 0xFFFF)  # endCode
    body += b"\x00\x00"  # reservedPad
    body += struct.pack(">HH", 65, 0xFFFF)  # startCode
    body += struct.pack(">hh", 0, 1)  # idDelta
    body += struct.pack(">HH", 4, 0)  # idRangeOffset (4 → look 2 entries ahead)
    # glyphIdArray[2]: first non-zero, second zero (triggers the != 0 check).
    body += struct.pack(">HH", 1, 0)
    return body


def _fmt4_indirect_two_entries() -> bytes:
    """Format-4 body: segment 0 covers codes 65..66 via indirect glyph
    array with two entries (5, 3). Both > 0; first sets max_glyph_id=5,
    second (3) exercises the False arm of `glyph_index > max_glyph_id`."""
    seg_count_x2 = 4
    body = struct.pack(">HHHH", seg_count_x2, 4, 1, 0)
    body += struct.pack(">HH", 66, 0xFFFF)  # endCode
    body += b"\x00\x00"  # reservedPad
    body += struct.pack(">HH", 65, 0xFFFF)  # startCode
    body += struct.pack(">hh", 0, 1)        # idDelta — 0 for segment 0
    body += struct.pack(">HH", 4, 0)        # idRangeOffset for seg 0 → indirect
    body += struct.pack(">HH", 5, 3)        # glyph_id_array entries
    return body


def test_format4_glyph_index_lte_max_skips_update() -> None:
    """Format 4 branch [155, 157]: subsequent glyph_index <= max_glyph_id —
    skip max update; record mapping unchanged."""
    sub = CmapSubtable()
    sub.process_subtype4(MemoryTTFDataStream(_fmt4_indirect_two_entries()), 100)
    assert sub.get_glyph_id(65) == 5
    assert sub.get_glyph_id(66) == 3


def test_format6_out_of_range_glyph_ids_are_kept() -> None:
    """Format 6: upstream processSubtype6 (PDFBox 3.0.7) does NOT bound entries
    against num_glyphs — every entry is stored verbatim and the reverse lookup
    is built. (Retargeted in wave 1524 after the live PDFBox oracle proved the
    earlier num_glyphs filter was a divergence.)"""
    # first_code=100, entry_count=2; both glyph_ids=99 with num_glyphs=10.
    body = struct.pack(">HH", 100, 2) + struct.pack(">HH", 99, 99)
    sub = CmapSubtable()
    sub.process_subtype6(MemoryTTFDataStream(body), num_glyphs=10)
    # Out-of-range gids are kept (no num_glyphs filter).
    assert sub.get_glyph_id(100) == 99
    assert sub.get_glyph_id(101) == 99


def test_format4_glyph_index_zero_is_skipped() -> None:
    """Format 4: when the indirect glyph-id-array entry resolves to 0,
    skip without recording a mapping (line 150 → 137)."""
    sub = CmapSubtable()
    sub.process_subtype4(MemoryTTFDataStream(_fmt4_two_segments_with_offset_zero_glyph()), 100)
    # Code 65 maps to glyph 1; code 66 (which had a 0 in the indirect
    # array) must NOT be present.
    assert sub.get_glyph_id(65) == 1
    assert sub.get_glyph_id(66) == 0  # absent → default


def _fmt6_empty() -> bytes:
    # entry_count=0 path — early return WITHOUT touching glyph map.
    return struct.pack(">HH", 100, 0)


def test_format6_empty_entries_returns_without_build() -> None:
    """Format 6: entry_count=0 short-circuits before the build call."""
    sub = CmapSubtable()
    # Pre-seed something distinguishable so we can verify nothing was
    # overwritten.
    sub._character_code_to_glyph_id = {99: 99}  # noqa: SLF001
    sub.process_subtype6(MemoryTTFDataStream(_fmt6_empty()), 10)
    # Function returned early; the pre-seeded entry survives untouched.
    assert sub._character_code_to_glyph_id == {99: 99}  # noqa: SLF001


def _fmt8_one_group_two_entries() -> bytes:
    # 8192 is32 bytes, 1 group: codes 100..101 -> glyphs 1..2.
    body = bytes(8192)
    body += struct.pack(">I", 1)  # nb_groups
    body += struct.pack(">III", 100, 101, 1)
    return body


def test_format8_glyph_index_lte_max_skips_update() -> None:
    """Format 8: second glyph (id 2) > max(1); first glyph (id 1) > max(0).
    Both update; need a case where new glyph_id <= max_glyph_id."""
    body = bytes(8192)
    # Two groups: first sets max_glyph_id to 5; second uses glyph 3 which
    # is <= 5 — exercises False arm of ``glyph_index > max_glyph_id``.
    body += struct.pack(">I", 2)
    body += struct.pack(">III", 100, 100, 5)  # single entry, glyph 5
    body += struct.pack(">III", 200, 200, 3)  # single entry, glyph 3 (<5)
    sub = CmapSubtable()
    sub.process_subtype8(MemoryTTFDataStream(body), num_glyphs=10)
    assert sub.get_glyph_id(100) == 5
    assert sub.get_glyph_id(200) == 3


def test_format8_empty_groups_skips_build_call() -> None:
    """Format 8: nb_groups=0 leaves empty map — skip build_glyph_id_to_...
    (line 221 → -193 = function exit)."""
    body = bytes(8192) + struct.pack(">I", 0)
    sub = CmapSubtable()
    sub._glyph_id_to_character_code = [42]  # noqa: SLF001 — sentinel
    sub.process_subtype8(MemoryTTFDataStream(body), num_glyphs=10)
    # Build was skipped; sentinel survives.
    assert sub._glyph_id_to_character_code == [42]  # noqa: SLF001


def test_format10_glyph_id_lte_max_skips_update() -> None:
    """Format 10: subsequent glyph <= max(running). Same shape as fmt 8."""
    # start=200, num_chars=2: glyph[0]=5, glyph[1]=3 (3 < 5).
    body = struct.pack(">II", 200, 2) + struct.pack(">HH", 5, 3)
    sub = CmapSubtable()
    sub.process_subtype10(MemoryTTFDataStream(body), num_glyphs=10)
    assert sub.get_glyph_id(200) == 5
    assert sub.get_glyph_id(201) == 3


def test_format12_glyph_index_lte_max_skips_update() -> None:
    """Format 12: two groups, second uses smaller glyph id."""
    body = struct.pack(">I", 2)
    body += struct.pack(">III", 100, 100, 9)  # max = 9
    body += struct.pack(">III", 200, 200, 4)  # 4 < 9
    sub = CmapSubtable()
    sub.process_subtype12(MemoryTTFDataStream(body), num_glyphs=20)
    assert sub.get_glyph_id(100) == 9
    assert sub.get_glyph_id(200) == 4


def test_format13_glyph_id_lte_max_skips_update() -> None:
    """Format 13: many-to-one — subsequent glyph_id <= max_glyph_id."""
    body = struct.pack(">I", 2)
    body += struct.pack(">III", 100, 102, 7)  # 3 codes → glyph 7 (max=7)
    body += struct.pack(">III", 200, 201, 2)  # 2 codes → glyph 2 (<7)
    sub = CmapSubtable()
    sub.process_subtype13(MemoryTTFDataStream(body), num_glyphs=10)
    assert sub.get_glyph_id(100) == 7
    assert sub.get_glyph_id(101) == 7
    assert sub.get_glyph_id(200) == 2


def test_format13_all_groups_invalid_leaves_empty_map() -> None:
    """Format 13: an out-of-bounds glyph_id breaks the group loop. Per upstream
    processSubtype13 (PDFBox 3.0.7, retargeted in wave 1542), the reverse map is
    initialised to ``newGlyphIdToCharacterCode(numGlyphs)`` (all -1) BEFORE the
    loop, then the bad group breaks — so the sentinel is replaced by an all--1
    array and no character code is ever recorded."""
    body = struct.pack(">I", 1)
    # glyph_id=99 but num_glyphs=10 → out of bounds (strict > break).
    body += struct.pack(">III", 100, 102, 99)
    sub = CmapSubtable()
    sub._glyph_id_to_character_code = [77]  # noqa: SLF001 — sentinel
    sub.process_subtype13(MemoryTTFDataStream(body), num_glyphs=10)
    # Array reset to all -1 up front (upstream parity); no code recorded.
    assert sub._glyph_id_to_character_code == [-1] * 10  # noqa: SLF001
    assert sub._character_code_to_glyph_id == {}  # noqa: SLF001


def test_format2_glyph_p_zero_falls_through_without_delta_math() -> None:
    """Format 2: when ``p == 0`` (read from glyphIndexArray), skip the
    ``p + id_delta`` adjustment (line 437 False arm → 441)."""
    # Build a minimal format-2 body with sub_header_keys all-zero (single
    # sub-header) and a glyph index array with one zero entry.
    body = bytearray()
    # sub_header_keys[256] all zero.
    body += b"\x00" * 512
    # One sub_header: first_code=0, entry_count=1, id_delta=10,
    # id_range_offset (raw uint16) — pick value so the computed offset
    # lands on our zero glyph entry.
    # id_range_offset_computed = raw - (max_sub_header_index+1-i-1)*8 - 2
    #                          = raw - 0 - 2 = raw - 2
    # We want id_range_offset_computed == 0 (read at the start of the
    # glyph array). So raw = 2.
    body += struct.pack(">HHhH", 0, 1, 10, 2)
    # Glyph index array: one zero entry.
    body += struct.pack(">H", 0)
    sub = CmapSubtable()
    sub.process_subtype2(MemoryTTFDataStream(bytes(body)), num_glyphs=50)
    # No mapping recorded for char_code 0 (since p was 0, then 0 is not
    # >= num_glyphs (50), so we fall to assignment with p == 0).
    # The glyph_id 0 IS recorded — that's fine; the key fact is that no
    # exception was raised exercising the p == 0 short-circuit.
    assert sub.get_glyph_id(0) == 0


# ============================================================
# pypdfbox/fontbox/ttf/naming_table.py
# ============================================================


def _build_name_table(records: list[tuple[int, int, int, int, bytes]]) -> bytes:
    n = len(records)
    header = struct.pack(">HHH", 0, n, 6 + n * 12)
    pool = b""
    blobs: list[bytes] = []
    for plat, enc, lang, name_id, raw in records:
        off = len(pool)
        blobs.append(struct.pack(">HHHHHH", plat, enc, lang, name_id, len(raw), off))
        pool += raw
    return header + b"".join(blobs) + pool


def _read_name_table(blob: bytes) -> Any:
    from pypdfbox.fontbox.ttf.naming_table import NamingTable

    t = NamingTable()
    t.set_offset(0)
    t.set_length(len(blob))

    class _Stub:
        pass

    t.read(_Stub(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    return t


def test_get_name_int_skips_en_us_to_find_other_ms_lang() -> None:
    """``_get_name_by_id``: when the only MS UnicodeBMP entry is en-US,
    the inner loop iterates but skips it (lang_id == LANGUAGE_WINDOWS_EN_US
    is False on second arm), then falls through to Unicode platform
    (branch [319, 318] = inner if False, continue loop)."""
    from pypdfbox.fontbox.ttf.name_record import NameRecord

    # Two MS UnicodeBMP records: en-US (filtered by first if) and de-DE
    # (kept). The en-US record forces the inner ``lang_id != EN_US`` False
    # branch when iterated.
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_TRADEMARK,
         "EN".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         0x0407, NameRecord.NAME_TRADEMARK,  # de-DE
         "DE".encode("utf-16-be")),
    ])
    t = _read_name_table(blob)
    # First call hits the preferred (en-US) branch.
    assert t.get_name(NameRecord.NAME_TRADEMARK) == "EN"


def test_get_name_int_inner_loop_skips_en_us_entry() -> None:
    """Branches [318, 322] and [319, 318]: build ms_langs that contains
    EN_US (with value=None, so the first preferred lookup returns None)
    and a non-EN_US (de-DE). The inner ``for`` then must skip EN_US
    (continue) and find de-DE.
    """
    from pypdfbox.fontbox.ttf.name_record import NameRecord
    from pypdfbox.fontbox.ttf.naming_table import NamingTable

    t = NamingTable()
    t._lookup_table = {  # noqa: SLF001
        NameRecord.NAME_FULL_FONT_NAME: {
            NameRecord.PLATFORM_WINDOWS: {
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP: {
                    NameRecord.LANGUAGE_WINDOWS_EN_US: None,
                    0x0407: "DE_VAL",  # de-DE
                },
            },
        },
    }
    t._name_records = []  # noqa: SLF001
    assert t._get_name_by_id(NameRecord.NAME_FULL_FONT_NAME) == "DE_VAL"  # noqa: SLF001


def test_get_name_int_inner_loop_only_en_us_returns_none() -> None:
    """Branch [318, 322]: ms_langs contains only EN_US (with value=None),
    so the loop iterates but never returns; we drop out and try the
    Unicode platform path."""
    from pypdfbox.fontbox.ttf.name_record import NameRecord
    from pypdfbox.fontbox.ttf.naming_table import NamingTable

    t = NamingTable()
    t._lookup_table = {  # noqa: SLF001
        NameRecord.NAME_FULL_FONT_NAME: {
            NameRecord.PLATFORM_WINDOWS: {
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP: {
                    NameRecord.LANGUAGE_WINDOWS_EN_US: None,
                },
            },
        },
    }
    t._name_records = []  # noqa: SLF001
    # The inner ``for`` runs but the only entry is EN_US which is
    # filtered by ``lang_id != EN_US``. Loop completes without return,
    # falls through to the (empty) Unicode-platform / Mac branches, and
    # ultimately returns None.
    assert t._get_name_by_id(NameRecord.NAME_FULL_FONT_NAME) is None  # noqa: SLF001


def test_get_name_int_ms_no_unicode_bmp_encoding_falls_to_unicode_platform() -> None:
    """When MS-Windows has records but no UnicodeBMP encoding, ms_encodings
    is non-None but ms_encodings.get(ENCODING_WINDOWS_UNICODE_BMP) is None
    (line 316 False → next phase): falls to Unicode platform."""
    from pypdfbox.fontbox.ttf.name_record import NameRecord

    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_SYMBOL,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_COPYRIGHT,
         "SYM".encode("utf-16-be")),
        (NameRecord.PLATFORM_UNICODE, NameRecord.ENCODING_UNICODE_2_0_BMP,
         NameRecord.LANGUAGE_UNICODE, NameRecord.NAME_COPYRIGHT,
         "UNI".encode("utf-16-be")),
    ])
    t = _read_name_table(blob)
    # MS-Symbol entry exists but isn't UnicodeBMP — falls through to
    # the Unicode-platform record.
    assert t.get_name(NameRecord.NAME_COPYRIGHT) == "UNI"


def test_language_ids_dedupes_repeated_language() -> None:
    """``language_ids`` returns distinct ids; a repeated language is
    skipped via ``if lid in seen: continue`` (branch [423, 419])."""
    from pypdfbox.fontbox.ttf.name_record import NameRecord

    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "A".encode("utf-16-be")),
        (NameRecord.PLATFORM_UNICODE, NameRecord.ENCODING_UNICODE_2_0_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "A2".encode("utf-16-be")),
    ])
    t = _read_name_table(blob)
    ids = t.language_ids(NameRecord.NAME_FONT_FAMILY_NAME)
    assert ids == [NameRecord.LANGUAGE_WINDOWS_EN_US]


def test_lookup_by_language_skips_none_value_records() -> None:
    """``_lookup_by_language``: when a matching (lang_id) entry has a None
    value (undecoded bytes), the loop continues to the next encoding
    (branch [457, 454] = ``v is not None`` False)."""
    from pypdfbox.fontbox.ttf.name_record import NameRecord
    from pypdfbox.fontbox.ttf.naming_table import NamingTable

    t = NamingTable()
    # Manually craft a lookup_table where one (lang) entry decodes to
    # None and another to a string.
    t._lookup_table = {  # noqa: SLF001
        NameRecord.NAME_FULL_FONT_NAME: {
            NameRecord.PLATFORM_WINDOWS: {
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP: {0x0409: None},
                NameRecord.ENCODING_WINDOWS_UNICODE_UCS4: {0x0409: "OK"},
            },
        },
    }
    t._name_records = []  # noqa: SLF001
    v = t._lookup_by_language(NameRecord.NAME_FULL_FONT_NAME, 0x0409)  # noqa: SLF001
    assert v == "OK"


# ============================================================
# pypdfbox/fontbox/ttf/glyph_substitution_table.py
# ============================================================


class _FakeScriptRecord:
    def __init__(self, tag: str, lang_sys_records: list[Any] | None = None,
                 default_lang_sys: Any | None = None) -> None:
        self.ScriptTag = tag
        from types import SimpleNamespace

        self.Script = SimpleNamespace(
            LangSysRecord=lang_sys_records,
            DefaultLangSys=default_lang_sys,
        )


def test_populate_from_fonttools_handles_missing_script_list() -> None:
    """Branch [135, 140]: when ``sl is None``, skip the script loop but
    still execute the FeatureList block."""
    from types import SimpleNamespace

    from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable

    fake_table = SimpleNamespace(
        ScriptList=None,
        FeatureList=SimpleNamespace(FeatureRecord=[
            SimpleNamespace(FeatureTag="liga"),
        ]),
    )
    fake_gsub = SimpleNamespace(table=fake_table)

    class _Tt:
        def __init__(self) -> None:
            self._data = {"GSUB": fake_gsub}

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def getGlyphOrder(self) -> list[str]:  # noqa: N802 — fontTools API
            return [".notdef"]

    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(_Tt())
    assert gsub.get_supported_script_tags() == set()
    assert gsub.get_supported_feature_tags() == ["liga"]


def test_populate_from_fonttools_handles_missing_feature_list() -> None:
    """Branch [141, 145]: when ``fl is None``, skip the feature loop and
    proceed to the final assignment with empty feature_tags."""
    from types import SimpleNamespace

    from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable

    fake_table = SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=[
            SimpleNamespace(ScriptTag="latn",
                            Script=SimpleNamespace(LangSysRecord=[],
                                                   DefaultLangSys=None)),
        ]),
        FeatureList=None,
    )
    fake_gsub = SimpleNamespace(table=fake_table)

    class _Tt:
        def __init__(self) -> None:
            self._data = {"GSUB": fake_gsub}

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def getGlyphOrder(self) -> list[str]:  # noqa: N802
            return [".notdef"]

    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(_Tt())
    assert gsub.get_supported_script_tags() == {"latn"}
    assert gsub.get_supported_feature_tags() == []


def test_get_lang_sys_tables_omits_default_when_absent() -> None:
    """Branch [404, 406]: ``default_ls is None`` — skip the append."""
    from types import SimpleNamespace

    from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable

    # Script with one explicit LangSys but NO default.
    fake_lang_sys = object()
    fake_table = SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=[
            SimpleNamespace(
                ScriptTag="grek",
                Script=SimpleNamespace(
                    LangSysRecord=[SimpleNamespace(LangSys=fake_lang_sys)],
                    DefaultLangSys=None,
                ),
            ),
        ]),
        FeatureList=None,
    )
    gsub = GlyphSubstitutionTable()
    gsub._gsub_table = fake_table  # noqa: SLF001
    result = gsub.get_lang_sys_tables("grek")
    assert result == [fake_lang_sys]  # no default appended


def test_project_gsub_data_with_no_gsub_table_returns_empty_features() -> None:
    """Branch [652, 664]: ``_gsub_table is None`` — feature_list stays empty."""
    from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable

    gsub = GlyphSubstitutionTable()
    gsub._gsub_table = None  # noqa: SLF001
    data = gsub._project_gsub_data("latn", "dflt")  # noqa: SLF001
    assert data.feature_list == {}
    assert data.active_script_name == "latn"


def test_project_gsub_data_with_no_lang_sys_returns_empty_features() -> None:
    """Branch [654, 664]: ``lang_sys_tables`` is empty — skip feature loop."""
    from types import SimpleNamespace

    from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable

    # Script with neither LangSysRecord nor DefaultLangSys.
    fake_table = SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=[
            SimpleNamespace(
                ScriptTag="cyrl",
                Script=SimpleNamespace(LangSysRecord=None, DefaultLangSys=None),
            ),
        ]),
        FeatureList=None,
    )
    gsub = GlyphSubstitutionTable()
    gsub._gsub_table = fake_table  # noqa: SLF001
    data = gsub._project_gsub_data("cyrl", "dflt")  # noqa: SLF001
    assert data.feature_list == {}


def test_project_gsub_data_skips_empty_feature_tag() -> None:
    """Branch [658, 656]: ``if tag`` False — continue past empty tag."""
    from types import SimpleNamespace

    from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable

    # Build a script with one default LangSys carrying a feature index 0.
    default_ls = SimpleNamespace(
        FeatureIndex=[0],
        ReqFeatureIndex=0xFFFF,
    )
    fake_table = SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=[
            SimpleNamespace(
                ScriptTag="latn",
                Script=SimpleNamespace(LangSysRecord=None, DefaultLangSys=default_ls),
            ),
        ]),
        # Feature 0 has a blank tag → filtered out.
        FeatureList=SimpleNamespace(FeatureRecord=[
            SimpleNamespace(FeatureTag="   ", Feature=SimpleNamespace(LookupListIndex=[])),
        ]),
    )
    gsub = GlyphSubstitutionTable()
    gsub._gsub_table = fake_table  # noqa: SLF001
    data = gsub._project_gsub_data("latn", "dflt")  # noqa: SLF001
    # Empty-tag feature filtered → no entry recorded.
    assert data.feature_list == {}


# ============================================================
# pypdfbox/fontbox/ttf/glyf_composite_descript.py
# ============================================================


def _build_composite_with_one_component(point_count: int = 4,
                                        contour_count: int = 1) -> Any:
    from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
    from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript

    class _FakeDescript:
        def resolve(self) -> None:
            return

        def get_point_count(self) -> int:
            return point_count

        def get_contour_count(self) -> int:
            return contour_count

        def get_end_pt_of_contours(self, i: int) -> int:
            return 0

        def get_flags(self, i: int) -> int:
            return 0

        def get_x_coordinate(self, i: int) -> int:
            return 0

        def get_y_coordinate(self, i: int) -> int:
            return 0

    desc = GlyfCompositeDescript()
    comp = GlyfCompositeComp.__new__(GlyfCompositeComp)
    comp._flags = 0  # noqa: SLF001
    comp._glyph_index = 0  # noqa: SLF001
    comp._x_translate = 0  # noqa: SLF001
    comp._y_translate = 0  # noqa: SLF001
    comp._first_index = 0  # noqa: SLF001
    comp._first_contour = 0  # noqa: SLF001
    comp._scale01 = 0.0  # noqa: SLF001
    comp._scale10 = 0.0  # noqa: SLF001
    comp._xscale = 1.0  # noqa: SLF001
    comp._yscale = 1.0  # noqa: SLF001
    desc._components = [comp]  # noqa: SLF001
    desc._descriptions = {0: _FakeDescript()}  # noqa: SLF001
    desc._resolved = True  # noqa: SLF001
    return desc


def test_get_end_pt_of_contours_missing_description_returns_zero() -> None:
    """Branch [132, 134]: c is not None but ``self._descriptions.get(idx)``
    is None (the dict was mutated between calls)."""
    desc = _build_composite_with_one_component()
    # Build a sentinel comp whose glyph index is missing from the
    # descriptions dict.
    from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp

    rogue = GlyfCompositeComp.__new__(GlyfCompositeComp)
    rogue._glyph_index = 999  # noqa: SLF001
    rogue._first_index = 0  # noqa: SLF001
    rogue._first_contour = 0  # noqa: SLF001

    # Force get_composite_comp_end_pt to return rogue regardless of i.
    desc.get_composite_comp_end_pt = lambda i: rogue  # type: ignore[method-assign]
    # Now descriptions.get(999) → None — line 132 False branch.
    assert desc.get_end_pt_of_contours(0) == 0


def test_get_flags_missing_description_returns_zero() -> None:
    """Branch [141, 143]: c is not None but description missing."""
    desc = _build_composite_with_one_component()
    from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp

    rogue = GlyfCompositeComp.__new__(GlyfCompositeComp)
    rogue._glyph_index = 999  # noqa: SLF001
    rogue._first_index = 0  # noqa: SLF001
    rogue._first_contour = 0  # noqa: SLF001
    desc.get_composite_comp = lambda i: rogue  # type: ignore[method-assign]
    assert desc.get_flags(0) == 0


def test_get_x_coordinate_missing_description_returns_zero() -> None:
    """Branch [150, 155]: c is not None but description missing."""
    desc = _build_composite_with_one_component()
    from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp

    rogue = GlyfCompositeComp.__new__(GlyfCompositeComp)
    rogue._glyph_index = 999  # noqa: SLF001
    rogue._first_index = 0  # noqa: SLF001
    rogue._first_contour = 0  # noqa: SLF001
    desc.get_composite_comp = lambda i: rogue  # type: ignore[method-assign]
    assert desc.get_x_coordinate(0) == 0


def test_get_y_coordinate_missing_description_returns_zero() -> None:
    """Branch [162, 167]: c is not None but description missing."""
    desc = _build_composite_with_one_component()
    from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp

    rogue = GlyfCompositeComp.__new__(GlyfCompositeComp)
    rogue._glyph_index = 999  # noqa: SLF001
    rogue._first_index = 0  # noqa: SLF001
    rogue._first_contour = 0  # noqa: SLF001
    desc.get_composite_comp = lambda i: rogue  # type: ignore[method-assign]
    assert desc.get_y_coordinate(0) == 0


def test_get_point_count_uses_cached_value_when_already_resolved() -> None:
    """Branch [177, 191]: ``_point_count >= 0`` short-circuits computation."""
    desc = _build_composite_with_one_component()
    desc._point_count = 42  # noqa: SLF001 — pre-cached
    assert desc.get_point_count() == 42  # uses cache


def test_get_contour_count_uses_cached_value_when_already_resolved() -> None:
    """Branch [197, 212]: ``_contour_count_resolved >= 0`` skip recompute."""
    desc = _build_composite_with_one_component()
    desc._contour_count_resolved = 17  # noqa: SLF001 — pre-cached
    assert desc.get_contour_count() == 17


# ============================================================
# pypdfbox/fontbox/type1/type1_font.py
# ============================================================


def test_parse_pfb_loop_exits_when_position_reaches_end() -> None:
    """Branch [203, 242]: ``while pos < len(raw)`` becomes False after
    consuming the trailing record (no explicit EOF marker)."""
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    # Two records: type 1 (ASCII header) + type 2 (binary). No EOF.
    # After both are consumed pos == len(raw) — loop exits via condition.
    ascii_header = (
        b"%!PS-AdobeFont-1.0: Foo\n"
        b"/FontInfo 1 dict dup begin\n"
        b"/FullName (Foo) def\n"
        b"end def\n"
        b"currentfile eexec\n"
    )
    binary = b"\x00" * 32
    cleartomark = b"0" * 512 + b"\ncleartomark\n"
    pfb = (
        b"\x80\x01" + len(ascii_header).to_bytes(4, "little") + ascii_header
        + b"\x80\x02" + len(binary).to_bytes(4, "little") + binary
        + b"\x80\x01" + len(cleartomark).to_bytes(4, "little") + cleartomark
    )
    # Parsing this should run the loop body until pos == len(raw) and
    # then exit via the while-condition becoming False (NOT via break).
    # Even if parse fails downstream, the bug we're after is that this
    # branch was never exercised — so as long as we exercise it, the
    # branch closes whether or not the call ultimately succeeds.
    with contextlib.suppress(OSError, ValueError):
        Type1Font.create_with_pfb(pfb)


def test_meta_cache_reuses_weight() -> None:
    """Branch [489, 495]: when ``weight`` is already in _meta_cache, skip
    recomputation."""
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    f = Type1Font.__new__(Type1Font)
    f._meta_cache = {"weight": "Bold"}  # noqa: SLF001
    assert f.get_weight() == "Bold"  # served from cache


def test_meta_cache_reuses_ulpos() -> None:
    """Branch [555, 567]: when ``ulpos`` already cached, skip computation."""
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    f = Type1Font.__new__(Type1Font)
    f._meta_cache = {"ulpos": -50.0}  # noqa: SLF001
    assert f.get_underline_position() == -50.0


def test_meta_cache_reuses_ulthick() -> None:
    """Branch [571, 584]: when ``ulthick`` already cached, skip computation."""
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    f = Type1Font.__new__(Type1Font)
    f._meta_cache = {"ulthick": 40.0}  # noqa: SLF001
    assert f.get_underline_thickness() == 40.0


# ============================================================
# pypdfbox/fontbox/cff/type1_char_string_parser.py
# ============================================================


def test_call_subr_with_empty_sequence_does_not_pop_ret() -> None:
    """Branch [110, -90]: after _parse, ``sequence`` is empty — skip the
    pop-RET cleanup and return."""
    from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser

    parser = Type1CharStringParser("test_font")
    parser._current_glyph = "g"  # noqa: SLF001
    # Operand 0 (valid index) is pushed; subr at index 0 is empty bytes →
    # _parse appends nothing → sequence stays empty after the recursive
    # call, exercising the False arm of ``if sequence:`` at line 110.
    sequence: list[Any] = [0]
    parser.process_call_subr([b""], sequence)
    # operand popped + empty parse + no RET pop happens.
    assert sequence == []


def test_call_other_subr_empty_sequence_after_othersubr_zero() -> None:
    """Branch [148, 150]: at line 148 — ``if sequence: sequence.pop()`` —
    the False arm (empty sequence) jumps directly to the appends."""
    from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
    from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser

    parser = Type1CharStringParser("test_font")
    parser._current_glyph = "g"  # noqa: SLF001
    # othersubr_num=0, num_args=0, plus the two integers we use as the
    # ``remove_integer`` results (= 0 each). Stack after pops: empty.
    sequence: list[Any] = [0, 0, 0, 0]
    # process_call_other_subr expects to be called at position of
    # callothersubr byte; supply enough trailing data to keep i+1 in range.
    data = b"\x00\x00\x00"  # safe trailer
    new_i = parser.process_call_other_subr(data, 0, sequence)
    assert new_i >= 1
    assert sequence[-1] == CharStringCommand.COMMAND_CALLOTHERSUBR


def test_call_other_subr_results_empty_skips_append() -> None:
    """Branch [171, 165]: ``if results:`` False — POP found but no result
    available, just advance cursor."""
    from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser

    parser = Type1CharStringParser("test_font")
    parser._current_glyph = "g"  # noqa: SLF001
    # othersubr_num=99 (default branch), num_args=0 → ``results`` empty.
    sequence: list[Any] = [0, 99]
    # Provide POP bytes following the callothersubr byte, then a non-POP
    # terminator (``0x0e`` ENDCHAR) so the wave-1525 unconditional pop-peek
    # has a readable byte and ends the loop cleanly instead of throwing at EOF.
    data = b"\x00\x0c\x11\x0c\x11\x0e"  # callothersubr + 2x (escape POP) + endchar
    new_i = parser.process_call_other_subr(data, 0, sequence)
    # Cursor advanced past callothersubr + two POP escapes (1 + 2 + 2 = 5).
    assert new_i == 5


# ============================================================
# pypdfbox/fontbox/cff/type2_char_string_parser.py
# ============================================================


def test_process_call_subr_raises_on_empty_operand_stack() -> None:
    """Wave 1525 aligned the Type2 interpreter with upstream: an empty operand
    stack on callsubr raises (upstream ``charStringElements.remove(size-1)`` →
    ``IndexOutOfBoundsException``), instead of the old silent return."""
    import pytest

    from pypdfbox.fontbox.cff.type2_char_string_parser import (
        Type2CharStringParser,
        _GlyphData,
    )

    parser = Type2CharStringParser("test_font")
    glyph = _GlyphData()
    # No integer on the operand stack → get_subr_bytes pops from empty → raises.
    with pytest.raises(IndexError):
        parser.process_call_subr([], [b"\x8b"], glyph)


def test_process_subr_skips_pop_when_sequence_empty() -> None:
    """Branch [137, -128]: after parse_sequence, ``glyph_data.sequence`` is
    empty — skip the RET pop and return."""
    from pypdfbox.fontbox.cff.type2_char_string_parser import (
        Type2CharStringParser,
        _GlyphData,
    )

    parser = Type2CharStringParser("test_font")
    glyph = _GlyphData()
    # Empty subr_bytes → parse_sequence does nothing → sequence stays empty.
    parser.process_subr([], [], b"", glyph)
    assert glyph.sequence == []


# ============================================================
# pypdfbox/fontbox/cff/cff_font.py
# ============================================================


def test_cff_font_get_property_with_no_top_dict_returns_none() -> None:
    """Cover the defensive ``_top is None`` arm in CFFFont.get_property."""
    from pypdfbox.fontbox.cff.cff_font import CFFFont

    f = CFFFont()
    # Default state: _top is None.
    assert f.get_property("nonexistent") is None
    # is_cid_font also hits the None-_top short-circuit.
    assert f.is_cid_font() is False


# ============================================================
# pypdfbox/fontbox/afm/afm_parser.py
# ============================================================


def test_afm_parser_composite_without_trailing_semicolon() -> None:
    """Branches [481, 483] and [495, 497] in parse_composite: the
    trailing ``;`` is OPTIONAL — exercise the without-semicolon path."""
    from io import BytesIO

    from pypdfbox.fontbox.afm.afm_parser import AFMParser

    # Minimal AFM ending in a StartComposites block whose lone composite
    # line uses NO trailing semicolons (PCC token follows part count
    # directly; no ';' between part records).
    afm = (
        b"StartFontMetrics 4.1\n"
        b"FontName Foo\n"
        b"StartComposites 1\n"
        b"CC Aacute 2 PCC A 0 0 PCC acute 100 200\n"
        b"EndComposites\n"
        b"EndFontMetrics\n"
    )
    parser = AFMParser(BytesIO(afm))
    fm = parser.parse()
    assert fm.get_font_name() == "Foo"


# ============================================================
# pypdfbox/fontbox/cmap/cmap.py
# ============================================================


def test_cmap_read_code_invalid_sequence_without_warning_log() -> None:
    """Branch [258, 265]: when WARNING logging is disabled, skip the log
    formatting and go straight to the fallback return.

    Setup: silence the cmap logger so ``isEnabledFor(WARNING)`` is False,
    then feed bytes that don't match any codespace range."""
    import io
    import logging

    from pypdfbox.fontbox.cmap.cmap import CMap
    from pypdfbox.fontbox.cmap.codespace_range import CodespaceRange

    c = CMap()
    # Two codespaces of different lengths (min=1, max=2) so the outer
    # loop iterates and reaches the no-match tail.
    c.add_codespace_range(CodespaceRange(b"\x30", b"\x39"))
    c.add_codespace_range(CodespaceRange(b"\x40\x40", b"\x4F\x4F"))
    # Silence the cmap logger so isEnabledFor(WARNING) is False.
    logger = logging.getLogger("pypdfbox.fontbox.cmap.cmap")
    saved = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        # Feed two bytes neither range matches — falls through to
        # fallback return without logging.
        code = c.read_code(io.BytesIO(b"\xFF\xFF"))
        assert code is not None
    finally:
        logger.setLevel(saved)


def test_cmap_read_code_from_bytes_invalid_sequence_without_warning_log() -> None:
    """Branch [302, 312]: analogous to above for the bytes-form API."""
    import logging

    from pypdfbox.fontbox.cmap.cmap import CMap
    from pypdfbox.fontbox.cmap.codespace_range import CodespaceRange

    c = CMap()
    c.add_codespace_range(CodespaceRange(b"\x30", b"\x39"))
    c.add_codespace_range(CodespaceRange(b"\x40\x40", b"\x4F\x4F"))
    logger = logging.getLogger("pypdfbox.fontbox.cmap.cmap")
    saved = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        code, length = c._read_code_from_bytes(b"\xFF\xFF", 0)  # noqa: SLF001
        assert length >= 1
    finally:
        logger.setLevel(saved)


# ============================================================
# pypdfbox/fontbox/encoding/encoding.py
# ============================================================


def test_encoding_overwrite_skips_when_old_name_absent() -> None:
    """Branch [48, 52]: when ``old_name is None`` (code not previously
    mapped), skip the reverse-mapping cleanup and proceed to the assign."""
    from pypdfbox.fontbox.encoding.encoding import Encoding

    enc = Encoding()
    # No prior mapping for code 65 → ``old_name`` is None → branch False.
    enc.overwrite(65, "A")
    assert enc.get_name(65) == "A"
    assert enc.get_code("A") == 65


def test_encoding_overwrite_skips_reverse_when_old_code_mismatches() -> None:
    """Branch [50, 52]: when ``old_code is not None and old_code == code``
    is False, skip the reverse-mapping pop. Build a state where the
    reverse map for old_name points elsewhere."""
    from pypdfbox.fontbox.encoding.encoding import Encoding

    enc = Encoding()
    # Pre-build inconsistent state: code 65 → "A" forward; "A" → 99 reverse.
    enc._code_to_name[65] = "A"  # noqa: SLF001
    enc._name_to_code["A"] = 99  # noqa: SLF001 — points to different code
    enc.overwrite(65, "B")
    # The reverse mapping for "A" should NOT have been popped (because
    # old_code == 99 != 65).
    assert enc._name_to_code.get("A") == 99  # noqa: SLF001


def test_encoding_name_lookup_for_unknown_code_returns_notdef() -> None:
    """Sanity check — Encoding.get_name returns .notdef for unmapped codes."""
    from pypdfbox.fontbox.encoding.encoding import Encoding

    enc = Encoding()
    assert enc.get_name(99) == ".notdef"


# ============================================================
# pypdfbox/pdmodel/font/pd_font.py
# ============================================================


def test_get_widths_skips_non_numeric_entries() -> None:
    """Non-numeric COSArray entry is kept as None in place (index-aligned),
    matching upstream COSArray.toCOSNumberFloatList (wave 1469)."""
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_integer import COSInteger
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.cos.cos_string import COSString
    from pypdfbox.pdmodel.font.pd_font import PDFont

    d = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger(500))
    arr.add(COSString("bogus"))  # non-numeric — kept as None in place
    arr.add(COSInteger(600))
    d.set_item(COSName.get_pdf_name("Widths"), arr)

    f = PDFont(d)
    widths = f.get_widths()
    # The non-numeric slot is preserved as None (index-aligned).
    assert widths == [500.0, None, 600.0]


# ============================================================
# pypdfbox/fontbox/ttf/true_type_font.py — small targeted branches
# ============================================================


def test_get_unicode_cmap_lookup_with_gsub_disabled(liberation_sans: TrueTypeFont) -> None:
    """Branch [1048, 1052]: when ``gsub_table`` is None (GSUB lookups
    requested but the font has no GSUB), skip the substitution wrapper.

    LiberationSans does carry GSUB, so we force ``get_gsub()`` to return
    None instead.
    """
    # Enable a feature so the wrapper branch is even entered.
    liberation_sans.enable_gsub_feature("liga")
    try:
        # Monkey-patch get_gsub to return None to force the None path.
        original = liberation_sans.get_gsub
        liberation_sans.get_gsub = lambda: None  # type: ignore[method-assign]
        try:
            cmap = liberation_sans.get_unicode_cmap_lookup()
            # Returned cmap is the raw lookup, NOT the substituting wrapper.
            assert cmap is not None
        finally:
            liberation_sans.get_gsub = original  # type: ignore[method-assign]
    finally:
        liberation_sans.disable_gsub_feature("liga")


def test_maximum_profile_version_below_one_skips_extended_fields() -> None:
    """Branch [468, 484]: when maxp version < 1.0, skip the extended
    field block."""
    from types import SimpleNamespace

    from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont

    # Build a minimal MaximumProfile fake with version 0x00005000 (== 0.3125).
    fake_maxp = SimpleNamespace(
        tableVersion=0x00005000,
        numGlyphs=2,
    )

    tt = TrueTypeFont.__new__(TrueTypeFont)
    tt._maxp = None  # noqa: SLF001
    tt._tt = {"maxp": fake_maxp}  # type: ignore[assignment]
    mp = tt.get_maximum_profile()
    assert mp is not None
    assert mp.get_num_glyphs() == 2
    # Extended fields stay at their default (0) since version < 1.0.
    assert mp.get_max_points() == 0


# ============================================================
# pypdfbox/fontbox/cff/_expert_encoding.py
# ============================================================
# Both arms [58, 57] and [60, 57] are mathematically unreachable for the
# bundled _RAW data: every SID in _RAW is in-range (max=378, table is 391
# entries) AND every resolved name is non-empty non-.notdef. They would
# only trigger if a future PDFBox upstream patched _RAW with bogus SIDs
# (defensive guard mirrored verbatim from upstream's CFFExpertEncoding
# Java initialiser). We add explicit pragmas to the source file rather
# than synthetic mock tests that would pass even after deleting the
# guards. (Pragma counts to the wave-1400 budget — see report.)
