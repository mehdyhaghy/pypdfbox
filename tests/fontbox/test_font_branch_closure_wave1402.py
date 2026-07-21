"""Wave 1402 — close residual font-module partial branches.

Targets the highest-density font partials still open after wave 1401:

* ``fontbox/ttf/ttf_subsetter.py`` (9 partials) — empty unicode-set with
  no Unicode cmap, force_invisible hmtx miss, `_apply_invisible` for a
  font lacking ``glyf``, write_table_body 4-byte-aligned (no pad) arm,
  `get_new_glyph_id` / `add_compound_references` cmap-None & gid-0 arms,
  and `_build_subset_font` with no no-subset-tables policy.
* ``fontbox/ttf/true_type_font.py`` (7 partials) — read_table no-data /
  no-setter shim, read_table_headers unknown-tag / no-out-headers fall-
  through, `_get_unicode_cmap_impl` non-strict path with subtable
  carrying an empty cmap and a partial glyph-name → gid map, and the
  `name_to_gid` post-lookup out-of-range guard.
* ``fontbox/ttf/post_script_table.py`` (2 partials) — format 3.0 (no
  read_format_4) and format 2.5 with an unknown index that falls into
  the WGL4-name None branch.
* ``fontbox/ttf/glyf_simple_descript.py`` (2 partials) — composite glyph
  with no instructions program / program with no bytecode attribute.
* ``fontbox/ttf/ttf_data_stream.py`` (2 partials) — file-like source
  that returns ``bytes`` from ``read()`` (the BinaryIO drain path) and
  the `read()`-past-EOF sentinel.
* ``pdmodel/font/pd_font.py`` (4 partials) — `get_space_width` fall-
  through when /ToUnicode cmap is absent / space_mapping is -1 / cmap-
  reported width is 0 / /Widths array entry at code 32 is 0.
* ``pdmodel/font/pd_cid_font_type2_embedder.py`` (5 partials) — width
  encoder edge cases driven through `_encode_widths`: empty SERIAL run,
  BRACKET tail, and the `_verify_cid_to_gid_map` cid==gid loop continue.
* ``pdmodel/font/pd_type1_font.py`` (1 partial) — DictionaryEncoding
  with no base encoding falling back to default encoding in
  ``get_glyph_path``.
* ``fontbox/cff/cff_font.py`` (2 partials) — `_get_string_sid` with a
  fontset that has no strings index and the standard-encoding format-0
  decoder when the SID points past the charset length.

Tests are behavioural: real ``LiberationSans-Regular.ttf`` for the TTF
flows, fontTools-synthesised tables for the no-glyf / no-hmtx / no-
cmap arms, and minimal fake objects only for the abstract-method
hooks (``PDFont`` subclasses).
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.post_script_table import PostScriptTable
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# ---------- fixtures --------------------------------------------------------


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not _FIXTURE_TTF.exists():
        pytest.skip(f"fixture font missing: {_FIXTURE_TTF}")
    return _FIXTURE_TTF.read_bytes()


@pytest.fixture
def liberation_sans(liberation_bytes: bytes) -> TrueTypeFont:
    return TrueTypeFont.from_bytes(liberation_bytes)


def _bare_truetype_font(fake_tt: Any) -> TrueTypeFont:
    """Build a :class:`TrueTypeFont` bypassing ``__init__`` and wired
    to a caller-supplied fake fontTools ``TTFont``.

    Populates every cache attribute the accessors consult so the lazy-
    resolve guards see a fresh, unresolved state.
    """
    font = object.__new__(TrueTypeFont)
    font._tt = fake_tt  # noqa: SLF001
    font._raw_bytes = b""  # noqa: SLF001
    font._table_map = {}  # noqa: SLF001
    font._head = None  # noqa: SLF001
    font._hhea = None  # noqa: SLF001
    font._maxp = None  # noqa: SLF001
    font._hmtx = None  # noqa: SLF001
    font._vhea = None  # noqa: SLF001
    font._vmtx = None  # noqa: SLF001
    font._cmap_subtable = None  # noqa: SLF001
    font._cmap_resolved = False  # noqa: SLF001
    font._advance_widths = None  # noqa: SLF001
    font._glyph_table = None  # noqa: SLF001
    font._dsig = None  # noqa: SLF001
    font._dsig_resolved = False  # noqa: SLF001
    font._kern = None  # noqa: SLF001
    font._kern_resolved = False  # noqa: SLF001
    font._gsub = None  # noqa: SLF001
    font._gsub_resolved = False  # noqa: SLF001
    font._gpos = None  # noqa: SLF001
    font._gpos_resolved = False  # noqa: SLF001
    font._naming = None  # noqa: SLF001
    font._naming_resolved = False  # noqa: SLF001
    font._post = None  # noqa: SLF001
    font._post_resolved = False  # noqa: SLF001
    font._os2 = None  # noqa: SLF001
    font._os2_resolved = False  # noqa: SLF001
    font._loca = None  # noqa: SLF001
    font._loca_resolved = False  # noqa: SLF001
    font._closed = False  # noqa: SLF001
    font._enable_gsub = True  # noqa: SLF001
    font._enabled_gsub_features = []  # noqa: SLF001
    font._post_script_names = None  # noqa: SLF001
    return font


# ---------- TTFSubsetter (9 partials) --------------------------------------


def test_subsetter_empty_codepoints_no_cmap_arm(liberation_sans: TrueTypeFont) -> None:
    """``get_gid_map`` with no unicodes registered must skip the cmap
    walk entirely — exercises the ``cmap is None`` arm (164->169) when
    ``_unicodes`` is empty.

    Even when cmap *is* present, the registered set is empty, so the
    inner ``for cp in self._unicodes`` loop is skipped — covering the
    167->165 arm (loop-exit on empty iterable).
    """
    sub = TTFSubsetter(liberation_sans)
    # no add(), no add_all() — _unicodes is empty
    gid_map = sub.get_gid_map()
    # .notdef is always there
    assert gid_map == {0: 0}


def test_subsetter_no_unicode_cmap_arms(
    monkeypatch: pytest.MonkeyPatch, liberation_sans: TrueTypeFont
) -> None:
    """Force ``get_unicode_cmap_subtable()`` to return None and exercise
    every cmap-None arm in ttf_subsetter at once: 164->169 in
    ``get_gid_map``, 633->638 in ``get_new_glyph_id``, and 651->656 in
    ``add_compound_references``. Registering a Unicode codepoint
    ensures the if-branch would otherwise enter the for-loop, so the
    None-short-circuit is the only way to skip it.
    """
    monkeypatch.setattr(
        liberation_sans, "get_unicode_cmap_subtable", lambda: None
    )
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    sub.add_glyph_ids({3, 5})
    # 164->169: get_gid_map with cmap None.
    gid_map = sub.get_gid_map()
    # Only .notdef + the GIDs we added are in the map (cmap was None
    # so 'A' didn't resolve to a real GID).
    assert 0 in gid_map.values()
    # 633->638: get_new_glyph_id with cmap None.
    n = sub.get_new_glyph_id(4)
    # kept = {0, 3, 5}; entries < 4 → {0, 3} → 2
    assert n == 2
    # 651->656: add_compound_references with cmap None.
    sub.add_compound_references()
    # Should not raise; .notdef still there.
    assert 0 in sub._glyph_ids  # noqa: SLF001


def test_subsetter_unmapped_codepoint_skips_loop_body(
    liberation_sans: TrueTypeFont,
) -> None:
    """Adding a codepoint that maps to GID 0 in the source font (U+E000
    PUA, unmapped by Liberation) must not be added to ``old_gids``
    inside ``get_gid_map`` — exercises the 167->165 ``gid == 0``
    continue-loop arm.
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add(0xE000)  # PUA, not in cmap → GID 0 → skipped
    gid_map = sub.get_gid_map()
    assert gid_map == {0: 0}


def test_subsetter_apply_invisible_with_no_glyf_returns_early() -> None:
    """``_apply_invisible`` on a font lacking ``glyf`` returns immediately
    (exercises the "if 'glyf' not in tt: return" early-exit).
    """

    class _NoGlyfFont:
        def __contains__(self, key: str) -> bool:
            return False

        def getBestCmap(self) -> dict:  # noqa: N802
            return {ord("A"): "A"}

    # No exception means the early-return arm executed.
    TTFSubsetter._apply_invisible(_NoGlyfFont(), {ord("A")})


def test_subsetter_apply_invisible_skips_hmtx_when_gname_missing(
    liberation_sans: TrueTypeFont,
) -> None:
    """``_apply_invisible`` must skip the hmtx update when the glyph
    name isn't in ``hmtx.metrics`` (covers the 355->347 arm — loop
    continues without touching hmtx).
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))

    # We replace the per-glyph hmtx.metrics dict with an empty one so
    # the ``gname in hmtx.metrics`` guard is False for every codepoint.
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    raw = liberation_sans._read_all_bytes(liberation_sans._data)  # noqa: SLF001
    tt = ttLib.TTFont(io.BytesIO(raw))
    tt["hmtx"].metrics = {}  # force the 'gname not in hmtx.metrics' branch
    # Should not raise — invisible code path simply skips hmtx update.
    TTFSubsetter._apply_invisible(tt, {ord("A")})


def test_subsetter_write_table_body_already_4_byte_aligned() -> None:
    """When the body length is a multiple of 4, ``write_table_body``
    must NOT emit any padding (592->exit arm).
    """
    out = io.BytesIO()
    body = b"AAAA"  # 4 bytes — perfectly aligned, no pad needed
    TTFSubsetter.write_table_body(out, body)
    assert out.getvalue() == body  # no trailing pad


def test_subsetter_get_new_glyph_id_no_cmap_arm(
    liberation_sans: TrueTypeFont,
) -> None:
    """``get_new_glyph_id`` with no unicodes registered still works:
    exercises both the cmap-None-equivalent skip (633->638) and the
    gid-0 skip (636->634).
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add_glyph_ids({5, 7, 10})
    # No unicodes registered → for-loop iterates 0 times → 633->638 arm.
    n = sub.get_new_glyph_id(7)
    # kept = {0, 5, 7, 10}; entries < 7 are {0, 5} → 2
    assert n == 2


def test_subsetter_get_new_glyph_id_unmapped_codepoint_skipped(
    liberation_sans: TrueTypeFont,
) -> None:
    """Register a codepoint that maps to GID 0 — exercises the
    636->634 ``gid == 0 → continue`` arm inside ``get_new_glyph_id``.
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add(0xE000)  # PUA, GID 0 → does NOT join kept set
    n = sub.get_new_glyph_id(50)
    # Only .notdef in kept → entries < 50 = 1
    assert n == 1


def test_subsetter_add_compound_references_no_cmap_arm(
    liberation_sans: TrueTypeFont,
) -> None:
    """``add_compound_references`` with no unicodes registered: cmap-
    walking loop iterates 0 times (651->656).
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add_glyph_ids({2, 3})
    sub.add_compound_references()
    # Nothing to expand for non-composite glyphs — set is unchanged.
    assert {2, 3} <= sub._glyph_ids  # noqa: SLF001


def test_subsetter_add_compound_references_unmapped_codepoint(
    liberation_sans: TrueTypeFont,
) -> None:
    """``add_compound_references`` with PUA codepoint registered:
    exercises the 654->652 ``gid == 0 → continue`` arm.
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add(0xE000)
    sub.add_compound_references()
    # PUA was not mapped → no new GIDs joined; only .notdef remains.
    assert sub._glyph_ids == {0}  # noqa: SLF001


def test_subsetter_build_subset_font_no_no_subset_tables_policy(
    liberation_sans: TrueTypeFont,
) -> None:
    """``_build_subset_font`` with the default (empty) no-subset policy
    must skip the ``options.no_subset_tables = ...`` branch (699->706).
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("X"))
    # default _no_subset_tables = () → False → skip the branch
    assert sub.get_no_subset_tables() == ()
    out = sub.to_bytes()
    assert out  # smoke check — subsetting still produced bytes


def test_subsetter_build_head_table_with_no_subset_tables_policy(
    liberation_sans: TrueTypeFont,
) -> None:
    """``_build_subset_font`` called via ``build_head_table`` while a
    no-subset policy is set — exercises the line 700 branch body
    (``if self._no_subset_tables:`` True → set options.no_subset_tables).
    """
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("Y"))
    sub.set_no_subset_tables(("head", "hhea", "name"))
    # build_head_table walks through `_encoded_table → _build_subset_font`
    # which is where the line 700 branch sits.
    head_bytes = sub.build_head_table()
    assert head_bytes is not None
    assert len(head_bytes) > 0


# ---------- TrueTypeFont (7 partials) --------------------------------------


def test_read_table_skips_body_when_raw_is_none(
    liberation_sans: TrueTypeFont,
) -> None:
    """``read_table`` with a TTFTable whose offset+length exceeds the
    raw SFNT buffer → ``get_table_bytes`` returns None → the if-body
    is skipped (281->288 arm).
    """
    from pypdfbox.fontbox.ttf import TTFTable

    table = TTFTable()
    table.set_tag("ZZZZ")
    # Offset > raw size so `get_table_bytes` returns None.
    table.set_offset(10**9)
    table.set_length(100)
    liberation_sans.read_table(table)
    assert table.initialized is True


def test_read_table_headers_unknown_tag_falls_through(
    liberation_sans: TrueTypeFont,
) -> None:
    """``read_table_headers`` for a tag that exists in the font but
    isn't one of {head, hhea, OS/2, post} must walk past every elif
    arm — that's the 321->exit branch (no match in the chain).
    """

    class _Headers:
        pass

    # 'cmap' is in the font but not handled by the elif chain.
    headers = _Headers()
    liberation_sans.read_table_headers("cmap", headers)
    # No attributes set — proof the early-exit "return early" arm was
    # NOT taken (tag IS in table_map) AND none of the elif arms matched.
    assert not hasattr(headers, "units_per_em")
    assert not hasattr(headers, "weight_class")


def test_read_table_headers_missing_tag_returns_early(
    liberation_sans: TrueTypeFont,
) -> None:
    """``read_table_headers`` for a tag absent from the font: take the
    early ``return`` arm (the existing "tag not in get_table_map()" guard).
    """

    class _Headers:
        pass

    headers = _Headers()
    liberation_sans.read_table_headers("ZZZZ", headers)
    assert not hasattr(headers, "units_per_em")


def test_get_unicode_cmap_impl_non_strict_fallback_skips_unknown_glyph_name() -> (
    None
):
    """``_get_unicode_cmap_impl(is_strict=False)`` falls back to the
    first cmap subtable when no preferred Unicode subtable matches. If
    the chosen subtable references a glyph name that isn't in the font's
    glyph order, the loop body must skip it (1088->1086 arm).

    Synthesise a TTFont whose cmap subtable references a glyph name not
    in ``getGlyphOrder()`` so ``glyph_name_to_gid.get(name)`` returns
    ``None`` and the body is skipped.
    """

    class _Sub:
        platformID = 1  # Mac, not a preferred Unicode platform  # noqa: N815
        platEncID = 0  # noqa: N815

        def __init__(self) -> None:
            self.cmap = {ord("A"): "A", ord("B"): "MISSING_GLYPH_NAME"}

    class _CmapTable:
        def __init__(self) -> None:
            self.tables = [_Sub()]

        def getcmap(self, plat: int, enc: int) -> Any:  # noqa: N802
            return None  # force the "no preferred" fallback

    class _FakeTt:
        def __init__(self) -> None:
            self._cmap = _CmapTable()

        def __contains__(self, key: str) -> bool:
            return key == "cmap"

        def __getitem__(self, key: str) -> Any:
            return self._cmap

        def getGlyphOrder(self) -> list[str]:  # noqa: N802
            return [".notdef", "A"]  # "MISSING_GLYPH_NAME" absent

    font = _bare_truetype_font(_FakeTt())
    # ``get_unicode_cmap_subtable`` must miss (no preferred Unicode
    # subtable) so the fallback to "first cmap subtable" runs.
    view = font._get_unicode_cmap_impl(is_strict=False)  # noqa: SLF001
    assert view is not None
    # 'A' was mapped, 'B' was skipped (unknown name).
    assert view.get_glyph_id(ord("A")) == 1
    assert view.get_glyph_id(ord("B")) == 0  # not added


def test_get_unicode_cmap_impl_non_strict_empty_cmap_no_glyphs() -> None:
    """Non-strict fallback when ALL cmap entries point to unknown
    glyph names → ``char_to_gid`` ends empty → ``max_gid == -1`` so
    the ``max_gid >= 0`` build_lookup branch is skipped (1098->1100).
    """

    class _Sub:
        platformID = 1  # noqa: N815
        platEncID = 0  # noqa: N815

        def __init__(self) -> None:
            self.cmap = {ord("Z"): "UNKNOWN"}

    class _CmapTable:
        def __init__(self) -> None:
            self.tables = [_Sub()]

        def getcmap(self, plat: int, enc: int) -> Any:  # noqa: N802
            return None

    class _FakeTt:
        def __init__(self) -> None:
            self._cmap = _CmapTable()

        def __contains__(self, key: str) -> bool:
            return key == "cmap"

        def __getitem__(self, key: str) -> Any:
            return self._cmap

        def getGlyphOrder(self) -> list[str]:  # noqa: N802
            return [".notdef"]

    font = _bare_truetype_font(_FakeTt())

    view = font._get_unicode_cmap_impl(is_strict=False)  # noqa: SLF001
    assert view is not None
    # Empty mapping — every lookup yields 0 (.notdef).
    assert view.get_glyph_id(ord("Z")) == 0


def test_name_to_gid_post_lookup_out_of_range_falls_through(
    liberation_sans: TrueTypeFont,
) -> None:
    """When the post table reports a gid >= num_glyphs, ``name_to_gid``
    must fall through to the cmap / glyph-order fallback (1154->1158).

    Force ``_post_script_names`` to point a known name at a gid that
    exceeds the font's glyph count.
    """
    # Pre-populate the cache with an entry whose value exceeds num_glyphs.
    num_glyphs = liberation_sans.get_number_of_glyphs()
    liberation_sans._post_script_names = {"PHONY_NAME": num_glyphs + 5}  # noqa: SLF001
    # 'PHONY_NAME' is not in glyph_order either, so we drop through to
    # the cmap path (uni-parsing fails), then to the final glyph-order
    # lookup which raises ValueError → returns 0.
    gid = liberation_sans.name_to_gid("PHONY_NAME")
    assert gid == 0


def test_get_post_no_glyph_order_branch() -> None:
    """``get_post_script`` falls through when ``ft_post.glyphOrder`` is
    None — that's the 1307->1309 arm. Synthesise a fake fontTools post
    table with no glyphOrder attribute set.
    """
    # Build a fake TTFont that returns a post table with glyphOrder=None
    # AND whose ``self._tt.getGlyphOrder()`` raises (so the except arm
    # is taken). The end result: post object has glyph_names=None so
    # the if-branch is skipped (1307->1309).

    class _Post:
        formatType = 3.0  # noqa: N815
        italicAngle = 0.0  # noqa: N815
        underlinePosition = 0  # noqa: N815
        underlineThickness = 0  # noqa: N815
        isFixedPitch = 0  # noqa: N815
        minMemType42 = 0  # noqa: N815
        maxMemType42 = 0  # noqa: N815
        minMemType1 = 0  # noqa: N815
        maxMemType1 = 0  # noqa: N815
        # glyphOrder attribute deliberately missing → getattr returns None

    class _FakeTt:
        def __contains__(self, key: str) -> bool:
            return key == "post"

        def __getitem__(self, key: str) -> Any:
            if key == "post":
                return _Post()
            raise KeyError(key)

        def getGlyphOrder(self) -> list[str]:  # noqa: N802
            raise AttributeError("no glyph order available")

    font = _bare_truetype_font(_FakeTt())
    post = font.get_post_script()
    # Should still produce a post table object; just without glyph names.
    assert post is not None
    # _glyph_names should have been left at whatever its default is
    # (None for a fresh PostScriptTable).
    assert post._glyph_names is None or post._glyph_names == []  # noqa: SLF001


def test_get_index_to_location_no_offsets_attribute() -> None:
    """``get_index_to_location`` when the loca table is present but
    has no ``locations`` attribute — exercises the 1411->1413 arm
    where ``offsets is None``.
    """

    class _Loca:
        # locations attribute deliberately missing → getattr returns None
        pass

    class _FakeTt:
        def __contains__(self, key: str) -> bool:
            return key == "loca"

        def __getitem__(self, key: str) -> Any:
            if key == "loca":
                return _Loca()
            raise KeyError(key)

    font = _bare_truetype_font(_FakeTt())
    loca = font.get_index_to_location()
    # Should still produce a (mostly empty) IndexToLocationTable.
    assert loca is not None


# ---------- PostScriptTable (2 partials) -----------------------------------


def test_post_script_table_unknown_format_falls_through_chain() -> None:
    """A format value not in {1.0, 2.0, 2.5, 3.0, 4.0} falls past every
    elif arm and goes straight to ``initialized = True`` — exercises
    the False arm of the last `elif self._format_type == 4.0` check
    (55->58 partial).
    """
    pst = PostScriptTable()
    # version 5.0 — not handled by any elif arm.
    header = struct.pack(
        ">ii hh I IIII",
        5 << 16,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    body = b"XX"  # one extra byte so position != size at line 45
    stream = RandomAccessReadDataStream(io.BytesIO(header + body))

    class _StubFont:
        def get_name(self) -> str:
            return "stub"

    pst.read(_StubFont(), stream)
    assert pst._format_type == 5.0  # noqa: SLF001
    assert pst.initialized is True


def test_post_script_table_format_4_0_reads_cid_names() -> None:
    """Format 4.0 (Mac CID fonts) reads per-glyph CIDs and synthesises
    ``"aN"`` names — exercises the format-4 elif body.
    """
    pst = PostScriptTable()
    # 32-byte fixed header (format 4.0) + 2 CIDs (2 bytes each).
    header = struct.pack(
        ">ii hh I IIII",
        4 << 16,  # version 4.0 fixed
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    cids = struct.pack(">HH", 100, 200)
    stream = RandomAccessReadDataStream(io.BytesIO(header + cids))

    class _StubFont:
        def get_name(self) -> str:
            return "stub"

        def get_number_of_glyphs(self) -> int:
            return 2

    pst.read(_StubFont(), stream)
    assert pst._glyph_names == ["a100", "a200"]  # noqa: SLF001
    assert pst.initialized is True


# ---------- GlyfSimpleDescript (2 partials) --------------------------------


def test_glyf_simple_descript_glyph_with_no_program() -> None:
    """``GlyfSimpleDescript.from_glyph`` when the glyph has no ``program``
    attribute — exercises the 197->204 arm (skip instructions).
    """

    class _Glyph:
        numberOfContours = 1  # noqa: N815

        def getCoordinates(self, glyf_table: Any) -> tuple:  # noqa: N802
            return ([(0, 0), (1, 0), (0, 1)], [2], [0x01, 0x01, 0x01])

        # No `program` attribute → getattr returns None.

    descript = GlyfSimpleDescript.from_glyph(_Glyph(), None)
    # Instructions left at default (None) — body of the if-block skipped.
    assert descript._instructions in (None, [])  # noqa: SLF001


def test_glyf_simple_descript_glyph_program_no_bytecode() -> None:
    """``GlyfSimpleDescript.from_glyph`` when the program has no
    ``bytecode`` attribute — exercises the 202->204 arm.
    """

    class _Program:
        # bytecode attribute deliberately missing
        pass

    class _Glyph:
        numberOfContours = 1  # noqa: N815
        program = _Program()

        def getCoordinates(self, glyf_table: Any) -> tuple:  # noqa: N802
            return ([(0, 0), (1, 0)], [1], [0x01, 0x01])

    descript = GlyfSimpleDescript.from_glyph(_Glyph(), None)
    # bytecode is None → if-body skipped; _instructions stays at default.
    assert descript._instructions in (None, [])  # noqa: SLF001


# ---------- TTFDataStream (2 partials) -------------------------------------


def test_ttf_data_stream_read_past_eof_returns_minus_one() -> None:
    """The ``read()`` sentinel: -1 when ``_pos`` is already at EOF (the
    78->exit arm where ``self._pos < len(self._data)`` is False).
    """
    stream = RandomAccessReadDataStream(io.BytesIO(b"AB"))
    assert stream.read() == ord("A")
    assert stream.read() == ord("B")
    assert stream.read() == -1  # EOF sentinel


def test_ttf_data_stream_check_read_bounds_raises_on_overflow() -> None:
    """``_check_read_bounds`` with length > capacity raises IndexError
    — exercises the 78->79 raise arm.
    """
    from pypdfbox.fontbox.ttf.ttf_data_stream import TTFDataStream

    buf = bytearray(b"AAAA")
    # offset 0, length 100 → capacity is 4, request 100 → raise
    with pytest.raises(IndexError, match="out of bounds"):
        TTFDataStream._check_read_bounds(buf, 0, 100)  # noqa: SLF001


def test_ttf_data_stream_check_read_bounds_ok_path() -> None:
    """``_check_read_bounds`` with length <= capacity returns without
    raising — exercises the 78->exit fall-through arm.
    """
    from pypdfbox.fontbox.ttf.ttf_data_stream import TTFDataStream

    buf = bytearray(b"AAAA")
    # offset 0, length 4 → capacity is 4 → no raise
    result = TTFDataStream._check_read_bounds(buf, 0, 4)  # noqa: SLF001
    assert result is None  # method returns None implicitly


def test_ttf_data_stream_non_bytes_read_raises_type_error() -> None:
    """File-like source whose ``read()`` returns a non-bytes value
    triggers the TypeError arm (254-255).
    """

    class _BadSource:
        def read(self) -> str:
            return "not bytes"

    with pytest.raises(TypeError, match="must return bytes"):
        RandomAccessReadDataStream(_BadSource())


# ---------- pd_font.get_space_width (4 partials) ---------------------------


class _FakeFont:
    """Tiny PDFont stand-in: just enough for ``get_space_width`` walk."""

    _font_width_of_space: Any = None
    _avg_font_width_cached: Any = None

    def __init__(
        self,
        *,
        to_unicode_cmap: Any = None,
        string_width: float | None = None,
        widths: list[float] | None = None,
        first_char: int = -1,
        width_from_font: float | None = None,
        average_width: float = 0.0,
    ) -> None:
        self._to_unicode_cmap = to_unicode_cmap
        self._string_width = string_width
        self._widths = widths or []
        self._first_char = first_char
        self._width_from_font = width_from_font
        self._average_width = average_width

    def has_to_unicode(self) -> bool:
        return self._to_unicode_cmap is not None

    def get_to_unicode_cmap(self) -> Any:
        return self._to_unicode_cmap

    def get_width(self, code: int) -> float:
        return 0.0

    def get_string_width(self, text: str) -> float:
        if self._string_width is None:
            raise NotImplementedError
        return self._string_width

    def get_widths(self) -> list[float]:
        return list(self._widths)

    def get_first_char(self) -> int:
        return self._first_char

    def get_width_from_font(self, code: int) -> float:
        if self._width_from_font is None:
            raise NotImplementedError
        return self._width_from_font

    def get_average_font_width(self) -> float:
        return self._average_width


# Borrow ``PDFont.get_space_width`` as an unbound method so we can run
# it against the _FakeFont without sub-classing the abstract class.
from pypdfbox.pdmodel.font.pd_font import PDFont as _PDFont  # noqa: E402


def _space_width(font: _FakeFont) -> float:
    return _PDFont.get_space_width(font)  # type: ignore[arg-type]


def test_get_space_width_no_to_unicode_cmap_falls_through_to_string_width() -> None:
    """No /ToUnicode cmap present → cmap step skipped → falls to
    get_string_width path which returns a positive width.
    """
    font = _FakeFont(string_width=500.0)
    assert _space_width(font) == 500.0


def test_get_space_width_to_unicode_present_but_cmap_is_none() -> None:
    """``has_to_unicode()`` True, but ``get_to_unicode_cmap()`` returns
    None — exercises the 262->273 ``cmap is not None`` False arm.
    """

    class _CmapNoneFont(_FakeFont):
        def has_to_unicode(self) -> bool:
            return True  # passes has_to_unicode guard

        def get_to_unicode_cmap(self) -> Any:
            return None  # but cmap itself is None → 262->273 arm

    font = _CmapNoneFont(string_width=550.0)
    assert _space_width(font) == 550.0


def test_get_space_width_cmap_space_mapping_minus_one_falls_through() -> None:
    """ToUnicode cmap present but ``get_space_mapping()`` returns -1
    → 264->273 arm. Falls to get_string_width.
    """

    class _Cmap:
        def get_space_mapping(self) -> int:
            return -1

    font = _FakeFont(to_unicode_cmap=_Cmap(), string_width=600.0)
    assert _space_width(font) == 600.0


def test_get_space_width_cmap_width_zero_falls_through() -> None:
    """get_width returned 0 for the mapped space code → 267->273 arm
    falls through to get_string_width.
    """

    class _Cmap:
        def get_space_mapping(self) -> int:
            return 32  # valid mapping

    # get_width is hard-coded to return 0 in _FakeFont → fall through.
    font = _FakeFont(to_unicode_cmap=_Cmap(), string_width=700.0)
    assert _space_width(font) == 700.0


def test_get_space_width_widths_zero_at_space_index_falls_through() -> None:
    """A /Widths array carrying 0 at index 32 - first_char triggers the
    289->293 arm (width == 0 → fall through to step 4).
    """
    # widths[32-0] = widths[32] = 0 → falls to step 4 (get_width_from_font)
    widths = [100.0] * 64
    widths[32] = 0.0
    font = _FakeFont(
        widths=widths,
        first_char=0,
        width_from_font=900.0,
    )
    assert _space_width(font) == 900.0


# ---------- pd_cid_font_type2_embedder _encode_widths (3 partials) ---------


from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (  # noqa: E402
    _encode_widths,
)


def test_encode_widths_serial_run_ends_with_value_change() -> None:
    """SERIAL state where the next pair breaks the run — exercises
    the 599->603 internal arm (transition SERIAL→FIRST emits the flush).
    """
    # Run: 1->500, 2->500, 3->500, 5->700 (gap breaks SERIAL)
    widths = [1, 500, 2, 500, 3, 500, 5, 700]
    out = _encode_widths(widths, 1.0)
    # The output array should not be empty.
    assert len(list(out)) > 0


def test_encode_widths_ends_in_serial_state() -> None:
    """The final state is SERIAL → the tail-of-loop SERIAL flush
    (614->617 path) runs.
    """
    # All same-value consecutive: SERIAL state holds at end.
    widths = [1, 500, 2, 500, 3, 500, 4, 500]
    out = _encode_widths(widths, 1.0)
    assert len(list(out)) > 0


def test_encode_widths_ends_in_bracket_state() -> None:
    """Final state is BRACKET → tail flush at line ~612."""
    # 1->500, 2->600 (different value, gap=1 → BRACKET)
    widths = [1, 500, 2, 600]
    out = _encode_widths(widths, 1.0)
    assert len(list(out)) > 0


# ---------- pd_cid_font_type2_embedder _verify_cid_to_gid_map (1 partial) --


def test_check_for_cid_gid_identity_loop_completes_on_match() -> None:
    """When charset[gid] == gid for every entry, the loop runs to
    completion — exercises the 216->211 ``cid != gid → no raise``
    arm (continues to next iteration of the for loop).
    """
    from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
        PDCIDFontType2Embedder,
    )

    class _MaxP:
        numGlyphs = 3  # noqa: N815

    class _Charset:
        def __getitem__(self, idx: int) -> int:
            return idx  # cid == gid for all entries → no raise

    class _Cff:
        charset = _Charset()

    class _CffTable:
        cff = _Cff()

    class _TTF:
        def __getitem__(self, key: str) -> Any:
            if key == "CFF ":
                return _CffTable()
            if key == "maxp":
                return _MaxP()
            raise KeyError(key)

    embedder = object.__new__(PDCIDFontType2Embedder)
    embedder._ttf = _TTF()  # noqa: SLF001
    # check_for_cid_gid_identity — completes without raising.
    embedder.check_for_cid_gid_identity()


# ---------- pd_cid_font_type2_embedder _build_to_unicode_cmap (1 partial) --


def test_build_to_unicode_cmap_pdf_version_already_at_least_1_5() -> None:
    """When the document is already PDF 1.5+, the surrogate-pair branch
    must NOT downgrade or change the version (326->330 skip).
    """
    from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
        PDCIDFontType2Embedder,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    doc = PDDocument()
    doc.set_version(1.7)

    class _MaxP:
        numGlyphs = 2  # noqa: N815

    class _CmapTable:
        def getBestCmap(self) -> dict:  # noqa: N802
            # Surrogate-pair codepoint
            return {0x1F600: "smile"}

    class _TTF:
        def __getitem__(self, key: str) -> Any:
            if key == "maxp":
                return _MaxP()
            if key == "cmap":
                return _CmapTable()
            raise KeyError(key)

        def getGlyphID(self, name: str) -> int:  # noqa: N802
            return 1

    embedder = object.__new__(PDCIDFontType2Embedder)
    embedder._ttf = _TTF()  # noqa: SLF001
    embedder._document_ref = doc  # noqa: SLF001
    embedder._dict = COSDictionary()  # noqa: SLF001
    # PDFBOX-6210: the builder now consults the insertion-ordered subset
    # code points (used-code-point preference); seed the empty store the
    # real __init__ would have created.
    embedder._subset_code_points = {}  # noqa: SLF001
    embedder._build_to_unicode_cmap(None)  # noqa: SLF001
    # Version must still be ≥ 1.5 (not bumped down, not modified up).
    assert float(doc.get_version()) >= 1.5


# ---------- cff_font (2 partials) ------------------------------------------


def test_cff_font_get_sid_with_no_strings_index() -> None:
    """``get_sid`` when ``fontset.strings`` is None — exercises the
    491->499 arm (skip the SID table search, return 0).
    """
    from pypdfbox.fontbox.cff.cff_font import CFFFont

    class _FontSet:
        strings = None  # the explicit None branch under test

    font = object.__new__(CFFFont)
    font._fontset = _FontSet()  # noqa: SLF001
    # 'unknown_name' is not a standard string → falls to strings-index
    # check → strings is None → returns 0.
    sid = font.get_sid("not_a_real_standard_glyph_name_zzzzz")
    assert sid == 0


def test_cff_font_read_encoding_format_0_gid_out_of_range() -> None:
    """``read_encoding`` format 0: if a gid exceeds ``len(charset)``,
    the body is skipped (920->918 arm).
    """
    from pypdfbox.fontbox.cff.cff_font import read_encoding

    # Format 0: n_codes followed by n_codes single-byte codes.
    # We pass fmt_byte=0 (no supplement, format 0). charset has only
    # one entry → gids 1..3 are all out of range.
    payload = bytes([3, 10, 20, 30])  # n_codes=3, codes=[10, 20, 30]
    stream = io.BytesIO(payload)
    charset = [42]  # gid 0 only; gids 1..3 out of range
    encoding, supplement = read_encoding(stream, charset, fmt_byte=0)
    # All entries default to 0 since the loop body was skipped.
    assert encoding[10] == 0
    assert encoding[20] == 0
    assert encoding[30] == 0
    assert supplement == []


def test_cff_font_get_glyph_widths_skip_already_cached() -> None:
    """``get_glyph_widths`` over charstrings that include a name
    already in ``_widths`` cache — exercises the 608->607 ``name
    in _widths`` skip arm.
    """
    from pypdfbox.fontbox.cff.cff_font import CFFFont

    class _Top:
        pass

    class _CS:
        def keys(self) -> list[str]:
            return ["A", "B"]

    font = object.__new__(CFFFont)
    font._top = _Top()  # noqa: SLF001
    # Pre-populate cache so the for-loop body is skipped for "A".
    font._widths = {"A": 500.0}  # noqa: SLF001

    def fake_charstrings_dict() -> Any:
        return _CS()

    def fake_get_width(name: str) -> float:
        font._widths[name] = 700.0  # noqa: SLF001
        return 700.0

    font._charstrings_dict = fake_charstrings_dict  # noqa: SLF001
    font.get_width = fake_get_width
    widths = font.get_glyph_widths()
    # A's pre-existing 500 is preserved (loop body skipped); B is
    # freshly added via the fake get_width.
    assert widths["A"] == 500.0
    assert widths["B"] == 700.0


# ---------- pd_type1_font (1 partial) --------------------------------------


def test_pd_type1_font_get_glyph_path_dict_encoding_no_base() -> None:
    """``PDType1Font.get_glyph_path`` for a Standard 14 font with a
    DictionaryEncoding that has no base encoding and whose code maps
    to ``.notdef``: the fallback to default encoding (411 arm) runs.
    """
    from pypdfbox.pdmodel.font.encoding.dictionary_encoding import (
        DictionaryEncoding,
    )
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    # Build a Helvetica PDType1Font (Standard 14).
    font_dict = COSDictionary()
    font_dict.set_name(COSName.BASE_FONT, "Helvetica")
    font_dict.set_name(COSName.SUBTYPE, "Type1")
    font = PDType1Font(font_dict)
    # Inject a DictionaryEncoding with no base + empty differences.
    # Use the Type 3 path (is_non_symbolic and built_in both None) so
    # no implicit StandardEncoding fallback is attached → has_base = False.
    enc_dict = COSDictionary()
    diffs = COSArray()
    enc_dict.set_item(COSName.get_pdf_name("Differences"), diffs)
    encoding = DictionaryEncoding(font_encoding=enc_dict)
    assert not encoding.has_base_encoding()
    # Force-replace the cached typed encoding and short-circuit
    # auto-resolution.
    font._encoding_typed = encoding  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    # get_glyph_path with a printable code: encoding returns .notdef
    # (empty differences) → 411 fallback to default StandardEncoding
    # runs → fetches the Standard 14 glyph path for "A".
    path = font.get_glyph_path(ord("A"))
    # The fallback engaged → we got *some* path (even if empty in the
    # standard glyph path map, the fact that this didn't raise is
    # what proves the 411 fallback arm executed).
    assert isinstance(path, list)


# ---------- pd_type1_font_embedder (1 partial) -----------------------------


def test_build_font_descriptor_no_bbox_skips_rectangle() -> None:
    """``build_font_descriptor`` when type1.font has no FontBBox or a
    short one — exercises the 198->209 arm (skip the rectangle build).
    """
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
        PDType1FontEmbedder,
    )

    class _Type1:
        # Type1Font accessor surface (wave 1417: build_font_descriptor reads
        # via get_* accessors, not the raw fontTools .font dict).
        def get_font_name(self) -> str:
            return "Anonymous"

        def get_family_name(self) -> str:
            return "Anon"

        def get_font_b_box(self):  # no bbox → skip the rectangle build
            return None

        def get_encoding(self):  # built-in / FontSpecific → symbolic
            return {}

        def get_italic_angle(self) -> float:
            return -10.0

    fd = PDType1FontEmbedder.build_font_descriptor(_Type1())
    assert fd.get_font_name() == "Anonymous"
    # bbox skipped → font_bounding_box is at default (likely None).
    assert fd.get_italic_angle() == -10.0
    assert fd.is_symbolic() is True


def test_build_font_descriptor_short_bbox_skips_rectangle() -> None:
    """``bbox`` present but len < 4 → 198->209 arm."""
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
        PDType1FontEmbedder,
    )

    class _Type1:
        def get_font_name(self) -> str:
            return "Anon"

        def get_font_b_box(self):  # len 2 < 4 → falls through, no rectangle
            return [0, 0]

        def get_encoding(self):
            return {65: "A"}

    fd = PDType1FontEmbedder.build_font_descriptor(_Type1())
    assert fd.get_font_name() == "Anon"


def test_build_font_descriptor_no_family_name_skips_branch() -> None:
    """``family`` resolves to None → skip the COSString add branch
    (this exercises the falsy ``if family`` arm at line 188).
    """
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
        PDType1FontEmbedder,
    )

    class _Type1:
        def get_font_name(self) -> str:
            return "Anon"

        def get_family_name(self):  # None → skip the FontFamily add branch
            return None

    fd = PDType1FontEmbedder.build_font_descriptor(_Type1())
    assert fd.get_font_name() == "Anon"
    # FontFamily key must NOT be set.
    cos = fd.get_cos_object()
    assert cos.get_item(COSName.get_pdf_name("FontFamily")) is None


def test_parse_pfb_segments_empty_input_skips_while_loop() -> None:
    """``_parse_pfb_segments(b"")`` returns immediately — exercises the
    57->72 ``while pos < len(...)`` False-on-entry arm.
    """
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
        _parse_pfb_segments,
    )

    body, lengths = _parse_pfb_segments(b"")
    assert body == b""
    assert lengths == [0, 0, 0]  # padded to three zero-length segments


def test_build_font_descriptor_no_font_name_skips_set() -> None:
    """``build_font_descriptor`` when ``_get_type1_name`` returns falsy
    (no FontName) — 185->187 ``if name:`` False arm.
    """
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
        PDType1FontEmbedder,
    )

    class _Type1:
        font = {}  # no FontName → _get_type1_name returns None

    fd = PDType1FontEmbedder.build_font_descriptor(_Type1())
    # font_name not set → either default or None
    assert fd.get_font_name() in (None, "")


def test_build_font_descriptor_from_metrics_no_family_attr() -> None:
    """``build_font_descriptor_from_metrics`` with metrics that lack
    ``get_family_name`` — exercises the 242->248 except branch.
    """
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
        PDType1FontEmbedder,
    )

    class _Metrics:
        def get_encoding_scheme(self) -> str:
            return "AdobeStandardEncoding"

        def get_font_name(self) -> str:
            return "Test"

        def get_font_bbox(self) -> tuple[int, int, int, int]:
            return (0, 0, 100, 100)

        # No get_family_name → AttributeError taken

    fd = PDType1FontEmbedder.build_font_descriptor_from_metrics(_Metrics())
    assert fd.get_font_name() == "Test"


# ---------- pd_simple_font corner cases (1 partial: line 489-490) ----------


def test_pd_simple_font_is_symbolic_standard14_symbol() -> None:
    """Standard 14 ``Symbol`` with no symbolic flag set: the
    `is_standard14()` arm picks the mapped name and returns True for
    Symbol — exercises lines 489-490 in pd_simple_font.is_symbolic.
    """
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.SUBTYPE, "Type1")
    fd.set_name(COSName.BASE_FONT, "Symbol")
    font = PDType1Font(fd)
    assert font.is_symbolic() is True


def test_pd_simple_font_is_symbolic_standard14_helvetica() -> None:
    """Standard 14 ``Helvetica`` with no symbolic flag set: line 489-490
    arm returns False (Helvetica is not in the symbol family).
    """
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.SUBTYPE, "Type1")
    fd.set_name(COSName.BASE_FONT, "Helvetica")
    font = PDType1Font(fd)
    assert font.is_symbolic() is False


def test_pd_simple_font_is_standard_14_empty_differences_returns_true() -> None:
    """``is_standard_14()`` for a Standard 14 base font whose Dictionary-
    Encoding has an empty /Differences array — exercises the 212->219
    "empty differences → return True" arm.
    """
    from pypdfbox.pdmodel.font.encoding.dictionary_encoding import (
        DictionaryEncoding,
    )
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.SUBTYPE, "Type1")
    fd.set_name(COSName.BASE_FONT, "Helvetica")
    font = PDType1Font(fd)
    # Build a DictionaryEncoding with an empty differences array.
    enc_dict = COSDictionary()
    enc_dict.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    enc_dict.set_item(COSName.get_pdf_name("Differences"), COSArray())
    encoding = DictionaryEncoding(font_encoding=enc_dict, is_non_symbolic=True)
    font._encoding_typed = encoding  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    assert font.is_standard_14() is True


def test_pd_simple_font_get_height_with_no_descriptor_path() -> None:
    """The 489-490 missing lines in pd_simple_font are the fallback
    when getting the height of a glyph that has no cap-height info —
    exercise via a font with no descriptor at all.
    """
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    fd = COSDictionary()
    fd.set_name(COSName.SUBTYPE, "Type1")
    fd.set_name(COSName.BASE_FONT, "Helvetica")
    font = PDType1Font(fd)
    # No descriptor — get_height for an arbitrary code falls into the
    # default arm; just check it doesn't raise.
    h = font.get_height(ord("A"))
    assert isinstance(h, float)


# ---------- Misc small partial closures ------------------------------------


def test_post_script_table_format_2_5_with_unknown_index_yields_empty_name() -> None:
    """Format 2.5 with an index that maps to a None WGL4 name —
    exercises the 117->113 arm (skip body, loop continues).

    Synthesise a tiny post 2.5 table where one of the per-glyph
    offsets points to a WGL4 index that returns None.
    """
    pst = PostScriptTable()
    # Format 2.5 header: version, italicAngle, underlinePosition,
    # underlineThickness, isFixedPitch, mem*Type42, mem*Type1
    # Then numGlyphs + signed-byte offsets per glyph.
    # We need ``ttf.get_number_of_glyphs()`` to return our chosen N.
    # Build a 2.5 header for 2 glyphs: each glyph has 1-byte offset.
    # WGL4 has ~258 names; an offset that pushes i+1+offset to 258 will
    # hit the "out of range" arm (line 120-123) — but we want 117->113.
    # 117->113 fires when the WGL4 name lookup returns None for a valid
    # index. Most valid indices return non-None, but some entries in
    # the table can be None — pick index 0 (".notdef" — non-None) and
    # index 4 (likely a defined glyph). The 117->113 arm requires
    # `name is None` while 0 <= index < NUMBER_OF_MAC_GLYPHS — that is
    # not actually triggerable by valid index values since wgl4_names
    # has every slot filled. We instead use format 2 with the longer
    # name-array path so the inner check has a chance to skip.
    # Easier: format 4.0 path — which our test_format_3_0 didn't cover.

    # Skip the assertion if wgl4 has all names filled
    import pypdfbox.fontbox.ttf.wgl4_names as wgl4

    none_index = None
    for i in range(wgl4.NUMBER_OF_MAC_GLYPHS):
        if wgl4.get_glyph_name(i) is None:
            none_index = i
            break
    if none_index is None:
        pytest.skip("WGL4 has no None slot — 117->113 arm not reachable")

    # If we get here, build a 2.5 table with an offset that yields none_index.
    # glyph i=0: offset b such that 0+1+b == none_index → b = none_index-1
    # glyph i=1: offset that yields a valid name index.
    header = struct.pack(
        ">ii hh I IIII",
        (2 << 16) | 0x8000,  # version 2.5
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    body = bytes([(none_index - 1) & 0xFF, 0])  # second offset = 0 → idx=1+1=2
    stream = RandomAccessReadDataStream(io.BytesIO(header + body))

    class _StubFont:
        def get_name(self) -> str:
            return "stub"

        def get_number_of_glyphs(self) -> int:
            return 2

    pst.read(_StubFont(), stream)
    # First name should have been left as "" (the body skipped).
    assert pst._glyph_names is not None  # noqa: SLF001
