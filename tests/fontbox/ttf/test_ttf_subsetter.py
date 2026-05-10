"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.TTFSubsetter`.

Loads the bundled LiberationSans-Regular fixture, asks the subsetter to
keep just the glyphs needed for "Hello", and verifies that the resulting
font is markedly smaller and that its cmap maps only the requested
codepoints. The subsetter wraps ``fontTools.subset`` — these tests treat
that as a black-box, asserting the upstream-compatible behaviour rather
than peeking at internal table layout.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return FIXTURE.read_bytes()


@pytest.fixture
def liberation_sans(liberation_bytes: bytes) -> TrueTypeFont:
    return TrueTypeFont.from_bytes(liberation_bytes)


def _load_fonttools(buf: bytes):
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    return ttLib.TTFont(io.BytesIO(buf))


# ---------- basic shape ---------------------------------------------------


def test_constructor_accepts_truetypefont(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    assert sub is not None


def test_constructor_accepts_table_keep_list(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans, ["head", "hhea", "loca", "maxp", "glyf", "hmtx"])
    assert sub is not None


# ---------- subsetting "Hello" -------------------------------------------


def test_hello_subset_is_much_smaller(
    liberation_sans: TrueTypeFont, liberation_bytes: bytes
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    out = sub.to_bytes()
    # Liberation Sans Regular is ~316 KiB; a 5-character subset must be a
    # small fraction of that. We pick a generous 1/3 ceiling so future
    # fontTools tweaks to default keep tables don't make this brittle.
    assert len(out) < len(liberation_bytes) // 3


def test_hello_subset_cmap_only_keeps_requested_codepoints(
    liberation_sans: TrueTypeFont,
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    tt = _load_fonttools(sub.to_bytes())
    best = tt["cmap"].getBestCmap()
    # "Hello" → unique codepoints {H, e, l, o}.
    expected = {ord(c) for c in set("Hello")}
    assert set(best.keys()) == expected


def test_hello_subset_round_trips_via_truetypefont(
    liberation_sans: TrueTypeFont,
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    sub_bytes = sub.to_bytes()
    # The subset must itself be parseable by our TrueTypeFont wrapper.
    sub_ttf = TrueTypeFont.from_bytes(sub_bytes)
    cmap = sub_ttf.get_unicode_cmap_subtable()
    assert cmap is not None
    assert cmap.get_glyph_id(ord("H")) != 0
    assert cmap.get_glyph_id(ord("e")) != 0
    # A character we did NOT register must map to .notdef in the subset.
    assert cmap.get_glyph_id(ord("Z")) == 0


# ---------- write_to_stream parity ---------------------------------------


def test_write_to_stream_matches_to_bytes(liberation_sans: TrueTypeFont) -> None:
    sub_a = TTFSubsetter(liberation_sans)
    sub_a.add_all(ord(c) for c in "abc")
    direct = sub_a.to_bytes()

    sub_b = TTFSubsetter(liberation_sans)
    sub_b.add_all(ord(c) for c in "abc")
    buf = io.BytesIO()
    sub_b.write_to_stream(buf)
    streamed = buf.getvalue()

    assert direct == streamed


# ---------- prefix tagging -----------------------------------------------


def test_set_prefix_tags_postscript_name(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hi")
    sub.set_prefix("ABCDEF")
    out = sub.to_bytes()
    tt = _load_fonttools(out)
    name_table = tt["name"]
    ps_record = name_table.getName(6, 3, 1, 0x409) or name_table.getName(6, 1, 0, 0)
    assert ps_record is not None
    assert ps_record.toUnicode().startswith("ABCDEF+")


def test_set_prefix_does_not_double_tag(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    sub.set_prefix("ABCDEF")
    first = TrueTypeFont.from_bytes(sub.to_bytes())

    # Re-subset the already-tagged output with the same prefix; the name
    # must stay singly-tagged (no "ABCDEF+ABCDEF+...").
    sub2 = TTFSubsetter(first)
    sub2.add(ord("A"))
    sub2.set_prefix("ABCDEF")
    out = sub2.to_bytes()
    tt = _load_fonttools(out)
    ps_name = tt["name"].getDebugName(6) or ""
    assert ps_name.count("ABCDEF+") == 1


# ---------- explicit GIDs -------------------------------------------------


def test_add_glyph_ids_keeps_requested_gids(liberation_sans: TrueTypeFont) -> None:
    # GID 1 in Liberation Sans is "space" (this is fixture-specific but
    # stable across Liberation 2.x). We don't depend on the *name*; we
    # only assert that the requested GID survives the round-trip.
    sub = TTFSubsetter(liberation_sans)
    sub.add_glyph_ids({1, 2, 3})
    tt = _load_fonttools(sub.to_bytes())
    # numGlyphs = .notdef + the three requested.
    assert tt["maxp"].numGlyphs >= 4


# ---------- empty subset (PDFBOX-2854) -----------------------------------


def test_empty_subset_keeps_only_notdef(liberation_sans: TrueTypeFont) -> None:
    """Mirror upstream's PDFBOX-2854 expectation: a subsetter with no
    ``add()`` calls still emits a valid TTF containing just ``.notdef``."""
    sub = TTFSubsetter(liberation_sans)
    out = sub.to_bytes()
    tt = _load_fonttools(out)
    assert tt["maxp"].numGlyphs == 1
    glyph_order = tt.getGlyphOrder()
    assert glyph_order[0] == ".notdef"


# ---------- get_gid_map (upstream getGIDMap) ------------------------------


def test_get_gid_map_includes_notdef(liberation_sans: TrueTypeFont) -> None:
    """``get_gid_map`` must always carry new GID 0 -> old GID 0
    (.notdef), matching upstream behaviour."""
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "AB")
    gid_map = sub.get_gid_map()
    assert gid_map[0] == 0


def test_get_gid_map_translates_widths(liberation_sans: TrueTypeFont) -> None:
    """Widths queried at ``new_gid`` in the subset font equal widths
    queried at ``old_gid`` in the source font. Mirrors upstream's
    ``testPDFBox3319`` advance-width / lsb assertion using the
    fixture font we actually have in the corpus."""
    sub = TTFSubsetter(liberation_sans)
    for ch in "ABCxyz":
        sub.add(ord(ch))
    gid_map = sub.get_gid_map()
    sub_ttf = TrueTypeFont.from_bytes(sub.to_bytes())
    for new_gid, old_gid in gid_map.items():
        assert sub_ttf.get_advance_width(new_gid) == liberation_sans.get_advance_width(
            old_gid,
        )


def test_get_gid_map_size_matches_subset_glyph_count(
    liberation_sans: TrueTypeFont,
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    gid_map = sub.get_gid_map()
    sub_ttf = TrueTypeFont.from_bytes(sub.to_bytes())
    assert len(gid_map) == sub_ttf.get_number_of_glyphs()


# ---------- force_invisible (upstream forceInvisible) ---------------------


def test_force_invisible_zeroes_advance_width(liberation_sans: TrueTypeFont) -> None:
    """Mirror upstream PDFBOX-5230: when a codepoint is added AND
    flagged invisible, its glyph in the subset has zero advance
    width — but a sibling un-flagged codepoint still has a non-zero
    width."""
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    sub.add(ord("B"))
    sub.force_invisible(ord("B"))
    sub_ttf = TrueTypeFont.from_bytes(sub.to_bytes())
    cmap = sub_ttf.get_unicode_cmap_subtable()
    assert cmap is not None
    gid_a = cmap.get_glyph_id(ord("A"))
    gid_b = cmap.get_glyph_id(ord("B"))
    assert gid_a != 0
    assert gid_b != 0
    assert sub_ttf.get_advance_width(gid_a) > 0
    assert sub_ttf.get_advance_width(gid_b) == 0


def test_force_invisible_without_add_is_noop(liberation_sans: TrueTypeFont) -> None:
    """Upstream contract (PDFBOX-5230 javadoc): the codepoint is NOT
    automatically added to the subset by ``force_invisible``. With
    only ``force_invisible('Z')`` and no ``add``, the subset must
    still contain just ``.notdef``."""
    sub = TTFSubsetter(liberation_sans)
    sub.force_invisible(ord("Z"))
    out = sub.to_bytes()
    tt = _load_fonttools(out)
    assert tt["maxp"].numGlyphs == 1


def test_force_invisible_unmapped_codepoint_silently_skipped(
    liberation_sans: TrueTypeFont,
) -> None:
    """A codepoint that doesn't map to any glyph in the source font
    must be silently ignored (matches upstream, where the GID lookup
    yields 0 and the invisibleGlyphIds set stays empty)."""
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    # U+E000 is in the Private Use Area and not mapped by Liberation Sans.
    sub.force_invisible(0xE000)
    sub_ttf = TrueTypeFont.from_bytes(sub.to_bytes())
    cmap = sub_ttf.get_unicode_cmap_subtable()
    assert cmap is not None
    gid_a = cmap.get_glyph_id(ord("A"))
    # 'A' must still render normally — force_invisible on PUA must not
    # accidentally taint the subset.
    assert sub_ttf.get_advance_width(gid_a) > 0


# ---------- byte-stream helpers (upstream parity surface) -----------------


def test_log2_matches_upstream_formula() -> None:
    # log2 is "highest bit index" — same value as floor(Math.log(n)/log(2)).
    assert TTFSubsetter.log2(1) == 0
    assert TTFSubsetter.log2(2) == 1
    assert TTFSubsetter.log2(8) == 3
    assert TTFSubsetter.log2(15) == 3
    assert TTFSubsetter.log2(16) == 4


def test_to_u_int32_combines_two_uint16() -> None:
    assert TTFSubsetter.to_u_int32(0x1234, 0x5678) == 0x12345678
    assert TTFSubsetter.to_u_int32(0xFFFF, 0xFFFF) == 0xFFFFFFFF


def test_to_u_int32_unpacks_big_endian_bytes() -> None:
    assert TTFSubsetter.to_u_int32(b"\x12\x34\x56\x78") == 0x12345678


def test_write_uint16_writes_two_bytes_big_endian() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_uint16(buf, 0x1234)
    assert buf.getvalue() == b"\x12\x34"


def test_write_uint32_writes_four_bytes_big_endian() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_uint32(buf, 0xDEADBEEF)
    assert buf.getvalue() == b"\xde\xad\xbe\xef"


def test_write_s_int16_handles_negative_values() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_s_int16(buf, -1)
    assert buf.getvalue() == b"\xff\xff"


def test_write_uint8_writes_single_byte() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_uint8(buf, 0xAB)
    assert buf.getvalue() == b"\xab"


def test_write_fixed_packs_16_16() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_fixed(buf, 1.0)
    # 1.0 in 16.16 fixed = 0x00010000.
    assert buf.getvalue() == b"\x00\x01\x00\x00"


def test_write_long_date_time_accepts_seconds_int() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_long_date_time(buf, 0)
    assert buf.getvalue() == b"\x00\x00\x00\x00\x00\x00\x00\x00"


def test_write_table_body_pads_to_4_byte_boundary() -> None:
    buf = io.BytesIO()
    TTFSubsetter.write_table_body(buf, b"abc")
    # 3 bytes + 1 pad byte.
    assert buf.getvalue() == b"abc\x00"


def test_write_file_header_emits_12_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    buf = io.BytesIO()
    sub.write_file_header(buf, 4)
    # SFNT version (4) + numTables (2) + searchRange (2) + entrySelector (2) + rangeShift (2)
    assert len(buf.getvalue()) == 12
    assert buf.getvalue()[:4] == b"\x00\x01\x00\x00"


def test_write_table_header_emits_16_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    buf = io.BytesIO()
    sub.write_table_header(buf, "head", 0x100, b"\x00" * 4)
    # tag (4) + checksum (4) + offset (4) + length (4) = 16.
    assert len(buf.getvalue()) == 16
    assert buf.getvalue()[:4] == b"head"


def test_copy_bytes_round_trips_a_window() -> None:
    src = io.BytesIO(b"0123456789")
    dst = io.BytesIO()
    new_offset = TTFSubsetter.copy_bytes(src, dst, 4, 0, 3)
    assert dst.getvalue() == b"456"
    assert new_offset == 7


# ---------- build_*_table wrappers ---------------------------------------


def test_build_head_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_head_table()
    assert out is not None
    assert isinstance(out, bytes)
    # ``head`` is a fixed 54-byte table.
    assert len(out) == 54


def test_build_hhea_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_hhea_table()
    assert out is not None
    assert len(out) == 36


def test_build_maxp_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_maxp_table()
    assert out is not None
    assert len(out) >= 6


def test_build_glyf_loca_consistency(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hi")
    glyf = sub.build_glyf_table()
    loca = sub.build_loca_table()
    assert glyf is not None
    assert loca is not None
    # ``loca`` entries are uint16 (short format) or uint32 (long format).
    # Either way: at least (numGlyphs + 1) * 2 bytes.
    assert len(loca) >= 4


def test_build_hmtx_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_hmtx_table()
    assert out is not None
    # 4 bytes per HMetric entry, at least one entry.
    assert len(out) >= 4


def test_build_cmap_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_cmap_table()
    assert out is not None


def test_build_name_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_name_table()
    assert out is not None


def test_build_post_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_post_table()
    assert out is not None


def test_build_os2_table_returns_bytes(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    out = sub.build_os2_table()
    assert out is not None


def test_build_table_returns_none_when_excluded(
    liberation_sans: TrueTypeFont,
) -> None:
    """When the constructor's ``tables`` allow-list excludes a tag,
    the corresponding ``build_*_table`` returns ``None`` — matches
    upstream's pattern of returning ``null`` for excluded tags."""
    # Allow-list omits ``post`` deliberately.
    sub = TTFSubsetter(liberation_sans, ["head", "hhea", "maxp", "glyf", "loca", "hmtx"])
    sub.add(ord("A"))
    assert sub.build_post_table() is None


# ---------- add_compound_references / get_new_glyph_id -------------------


def test_add_compound_references_does_not_shrink_glyph_set(
    liberation_sans: TrueTypeFont,
) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add_all(ord(c) for c in "Hello")
    before = set(sub._glyph_ids)  # noqa: SLF001
    sub.add_compound_references()
    after = set(sub._glyph_ids)  # noqa: SLF001
    assert before <= after


def test_get_new_glyph_id_zero_for_notdef(liberation_sans: TrueTypeFont) -> None:
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    # GID 0 (.notdef) is always the lowest old GID, so its new GID is 0.
    assert sub.get_new_glyph_id(0) == 0
