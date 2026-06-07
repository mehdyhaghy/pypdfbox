"""Differential TTF/OTF parse fuzz vs Apache FontBox 3.0.7 (wave 1506).

A follow-on to the wave-1503 parser mutation-fuzz, wave-1504 content-stream
fuzz, and wave-1505 stream-filter fuzz, applying the same deterministic-corpus
method to the *lenient SFNT (TrueType/OpenType) parse contract* — the path
``TTFParser().parse(...)`` drives when it is handed a (possibly malformed) font
program.

For a small bundled base TTF (``DejaVuSansMono.ttf``, permissive) we apply a
fixed set of byte-level mutations that exercise the SFNT directory + table
parsers: header corruption, table-directory corruption (bad tag bytes,
offset/length past EOF, checksum corruption), truncations, ``head`` corruption
(bad magic, unitsPerEm 0), ``cmap`` sub-table corruption, ``maxp`` numGlyphs
mismatch, ``OS/2`` corruption, and random byte flips. Both engines parse the
*identical* bytes and are compared on a stable projection:

    ok=true
    numGlyphs=<int>
    unitsPerEm=<int>
    tables=<comma-joined sorted table tags>
    adv0=<advance width of gid 0>
    advN=<advance width of a fixed probe gid (3)>
    cmapA=<gid for U+0041, or -1 when no usable cmap>

or the sole line ``ok=false`` on any parse-time throw. The Java side is
``oracle/probes/TtfParserFuzzProbe.java`` (parses via
``new TTFParser(embedded).parse(new RandomAccessReadBuffer(bytes))``);
``_py_dump`` reproduces the same fingerprint on the pypdfbox side.

LENIENCY ARM. The pypdfbox default ``TTFParser()`` maps to upstream's
non-embedded arm (``isEmbedded=False``) — the strict required-table check
(``head``/``hhea``/``maxp``/``hmtx``/``post``/``name``/``cmap`` all mandatory).
We fuzz that arm. (The embedded arm is more lenient but a clean differential
table-removal there is impossible without shifting every downstream table
offset — deleting a 16-byte directory entry slides all real table data, which
PDFBox's PDFBOX-5285 past-EOF guard then silently drops, so the mutation stops
being a clean "drop one table" — see DOCUMENTED LIBRARY-GAP below.)

DOCUMENTED LIBRARY-GAP DIVERGENCES (deliberately NOT pinned here — the
CCITT/libtiff precedent of wave 1505). pypdfbox parses TTF/OTF through
fontTools (library-first per CLAUDE.md), which differs from PDFBox's
hand-rolled directory walker on two structural axes:

  1. *Eager vs lazy table decode.* Upstream ``TTFParser.parse`` →
     ``parseTables`` force-loads **every** table at parse time, so a malformed
     ``glyf`` / ``loca`` / ``hmtx`` / ``name`` / ``maxp.numGlyphs`` (e.g. a
     glyf offset past EOF, a zero-length hmtx, numGlyphs far larger than the
     loca/hmtx arrays support) makes ``parse`` itself throw (ok=false).
     pypdfbox wraps ``fontTools.ttLib.TTFont(lazy=True)`` — table decode is
     deferred until the table is *accessed*, so ``parse`` succeeds (ok=true)
     and the same fontTools error (``TTLibError`` / ``AssertionError``)
     surfaces only when that broken table is touched. Forcing eager decode in
     ``parse`` would defeat lazy loading (a hard behavioural-compat rule) and
     re-raise fontTools' exception types rather than PDFBox's ``IOException``.

  1b. *Past-EOF directory-entry guard.* A corollary of (1): when a
     *non-required* table's directory entry is made to point past EOF (offset
     or length), PDFBox's PDFBOX-5285 guard drops that entry from the table
     map (it "goes past the file size"), so the ``tables=`` projection loses
     the tag; fontTools keeps the entry (it does not range-check the directory
     against the file size up front). Same root cause — eager geometry
     validation vs lazy tolerance — so not pinned.

  2. *Unknown sfnt scaler type.* FontBox never validates the 32-bit scaler
     magic — it reads it as ``version`` and walks the directory regardless, so
     a garbage sfnt version still parses (ok=true). fontTools hard-rejects an
     unknown sfntVersion (``TTLibError: bad sfntVersion``) before reading any
     table, which pypdfbox surfaces as a parse failure (ok=false). Matching
     PDFBox would mean bypassing fontTools' sfnt-version gate, i.e.
     reimplementing the directory walk — out of scope and against the
     library-first rule.

The corpus below pins only the mutations where the two engines AGREE on the
full projection (or, where noted, the ok boolean). The lazy-vs-eager and
bad-sfnt cases are characterised here and in CHANGES.md / DEFERRED.md but not
asserted, exactly as the CCITT truncated-strip cases were in wave 1505.

Deterministic generator, fixed PRNG seed ``random.Random(1506)``.
"""

from __future__ import annotations

import contextlib
import os
import random
import struct
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_RNG = random.Random(1506)

_FIXDIR = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "fontbox" / "ttf"
)
_BASE_PATH = _FIXDIR / "DejaVuSansMono.ttf"
_BASE = bytearray(_BASE_PATH.read_bytes()) if _BASE_PATH.is_file() else bytearray()

# Fixed probe gid (must match TtfParserFuzzProbe.PROBE_GID).
_PROBE_GID = 3


# ---------------------------------------------------------------------------
# SFNT directory map of the base font (offsets of each 16-byte entry +
# absolute table offset/length) — used to target individual tables.
# ---------------------------------------------------------------------------
def _directory(data: bytes) -> dict[str, tuple[int, int, int, int]]:
    """Return ``{tag: (dir_entry_offset, checksum, table_offset, length)}``."""
    out: dict[str, tuple[int, int, int, int]] = {}
    if len(data) < 12:
        return out
    num_tables = struct.unpack(">H", data[4:6])[0]
    pos = 12
    for _ in range(num_tables):
        if pos + 16 > len(data):
            break
        tag = data[pos : pos + 4].decode("latin1")
        check_sum, offset, length = struct.unpack(">III", data[pos + 4 : pos + 16])
        out[tag] = (pos, check_sum, offset, length)
        pos += 16
    return out


_DIR = _directory(_BASE)


# ---------------------------------------------------------------------------
# deterministic mutation corpus
#
# Each entry: (name, mutated_bytes). All mutations preserve the byte LAYOUT of
# the base font (they overwrite in place; they never insert/delete bytes that
# would shift downstream table offsets) so a divergence reflects a genuine
# parse-contract difference, not cascade corruption.
# ---------------------------------------------------------------------------
_Mut = tuple[str, bytes]


def _put(base: bytearray, offset: int, fmt: str, value: int) -> bytearray:
    b = bytearray(base)
    struct.pack_into(fmt, b, offset, value)
    return b


def _generate_corpus() -> list[_Mut]:
    if not _DIR:
        return []
    base = _BASE
    out: list[_Mut] = [("clean", bytes(base))]

    # -- header mutations (12-byte SFNT offset table) -------------------
    out.append(("num_tables_0", bytes(_put(base, 4, ">H", 0))))
    out.append(("search_range_garbage", bytes(_put(base, 6, ">H", 0xFFFF))))
    out.append(("entry_selector_garbage", bytes(_put(base, 8, ">H", 0xFFFF))))
    out.append(("range_shift_garbage", bytes(_put(base, 10, ">H", 0xFFFF))))

    # -- truncations ----------------------------------------------------
    out.append(("trunc_empty", b""))
    out.append(("trunc_1_byte", bytes(base[:1])))
    out.append(("trunc_3_bytes", bytes(base[:3])))
    out.append(("trunc_header_only", bytes(base[:12])))
    out.append(("trunc_mid_directory", bytes(base[: 12 + 16 * 5])))
    out.append(("trunc_after_directory", bytes(base[: 12 + 16 * len(_DIR)])))
    out.append(("trunc_quarter", bytes(base[: len(base) // 4])))
    out.append(("trunc_half", bytes(base[: len(base) // 2])))
    out.append(("trunc_three_quarter", bytes(base[: 3 * len(base) // 4])))
    out.append(("trunc_one_short", bytes(base[:-1])))

    # -- table-directory corruption (in place, no offset shift) ---------
    # NOTE: corrupting a *required* table's directory offset/length so it walks
    # past EOF (e.g. the cmap entry) is a documented LIBRARY-GAP case, NOT
    # pinned: PDFBox force-loads that table in parseTables and throws, while
    # the fontTools-lazy backend tolerates the over-long directory entry and
    # only fails on table access (which our cmap projection does not trigger
    # here). We corrupt a *non-required-for-projection* table's geometry
    # instead (gasp / cvt) so both engines agree.
    gasp_dir = _DIR["gasp"][0]
    out.append(("dir_bad_tag_bytes", bytes(_put(base, gasp_dir, ">I", 0x00010203))))
    head_dir = _DIR["head"][0]
    out.append(("dir_checksum_corrupt", bytes(_put(base, head_dir + 4, ">I", 0xDEADBEEF))))

    # -- head table corruption (table content, in place) ----------------
    # head layout: version(4) fontRevision(4) checkSumAdjustment(4) magic(4)
    #              flags(2) unitsPerEm(2) created(8) modified(8) xMin(2) ...
    head_off = _DIR["head"][2]
    out.append(("head_version_bad", bytes(_put(base, head_off, ">I", 0xFFFFFFFF))))
    out.append(("head_revision_bad", bytes(_put(base, head_off + 4, ">I", 0xABCDEF01))))
    out.append(("head_bad_magic", bytes(_put(base, head_off + 12, ">I", 0x12345678))))
    out.append(("head_flags_garbage", bytes(_put(base, head_off + 16, ">H", 0xFFFF))))
    out.append(("head_units_per_em_0", bytes(_put(base, head_off + 18, ">H", 0))))
    out.append(("head_units_per_em_1", bytes(_put(base, head_off + 18, ">H", 1))))
    out.append(("head_units_per_em_huge", bytes(_put(base, head_off + 18, ">H", 0xFFFF))))
    out.append(("head_mac_style_garbage", bytes(_put(base, head_off + 44, ">H", 0xFFFF))))
    out.append(
        ("head_glyph_data_format_bad", bytes(_put(base, head_off + 52, ">h", 99)))
    )

    # -- cmap sub-table corruption (table content) ----------------------
    # cmap header: version(2) numTables(2) [platformID(2) encodingID(2) off(4)]*
    # cmap_num_sub_0 is pinned (both engines yield a cmap with no usable
    # Unicode subtable → cmapA=-1). cmap_num_sub_huge / cmap_sub_offset_oob
    # are documented LIBRARY-GAP cases (PDFBox force-parses the cmap and
    # throws; fontTools tolerates the bogus subtable count / OOB offset), so
    # they are NOT pinned.
    cmap_off = _DIR["cmap"][2]
    out.append(("cmap_num_sub_0", bytes(_put(base, cmap_off + 2, ">H", 0))))

    # -- maxp numGlyphs mutations (table content) -----------------------
    # maxp layout: version(4) numGlyphs(2) ...
    maxp_off = _DIR["maxp"][2]
    out.append(("maxp_num_glyphs_5", bytes(_put(base, maxp_off + 4, ">H", 5))))
    out.append(("maxp_num_glyphs_1", bytes(_put(base, maxp_off + 4, ">H", 1))))

    # -- OS/2 corruption (non-required for the projection) --------------
    os2_off = _DIR["OS/2"][2]
    out.append(("os2_version_garbage", bytes(_put(base, os2_off, ">H", 99))))
    out.append(("os2_weight_garbage", bytes(_put(base, os2_off + 4, ">H", 0xFFFF))))

    # -- random in-place byte flips (deterministic) ---------------------
    # Flip a single byte in the 12-byte SFNT offset table (version /
    # numTables / searchRange / entrySelector / rangeShift). A flip in the
    # *directory entries* themselves can corrupt a required table's offset and
    # land in the lazy-vs-eager LIBRARY-GAP (PDFBox force-loads + throws while
    # the fontTools backend defers), so flips are confined to the header where
    # both engines interpret the bytes the same way.
    # Flips are confined to bytes 6..12 — the searchRange / entrySelector /
    # rangeShift binary-search HINT fields. Neither engine validates these
    # (the directory walk is driven purely by numTables), so a flip there is
    # interpreted identically by both. Excluded:
    #   * bytes 0..4 (sfnt scaler magic) — bad-sfnt LIBRARY-GAP (fontTools
    #     rejects an unknown sfntVersion; PDFBox parses on).
    #   * bytes 4..6 (numTables) — a flip there makes both engines read
    #     trailing garbage directory entries, but each derives a *different*
    #     garbage tag set (see the num_tables_huge OKSAME case), so the
    #     ``tables=`` projection diverges.
    for i in range(6):
        b = bytearray(base)
        pos = _RNG.randrange(6, 12)
        b[pos] ^= 1 << _RNG.randrange(8)
        out.append((f"hint_rand_flip_{i}", bytes(b)))

    return out


_CORPUS = _generate_corpus()
_CORPUS_IDS = [m[0] for m in _CORPUS]


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce TtfParserFuzzProbe's projection exactly.
# ---------------------------------------------------------------------------
def _advance(font: object, gid: int) -> int:
    try:
        return int(font.get_advance_width(gid))  # type: ignore[attr-defined]
    except Exception:
        return -1


def _cmap_gid(font: object, code_point: int) -> int:
    try:
        cmap = font.get_unicode_cmap_lookup(is_strict=False)  # type: ignore[attr-defined]
        if cmap is None:
            return -1
        return int(cmap.get_glyph_id(code_point))
    except Exception:
        return -1


def _py_dump(mutated: bytes) -> str:
    try:
        font = TTFParser().parse(mutated)
    except Exception:
        return "ok=false\n"
    try:
        tags = ",".join(sorted(font.get_table_map().keys()))
        lines = [
            "ok=true",
            f"numGlyphs={font.get_number_of_glyphs()}",
            f"unitsPerEm={font.get_units_per_em()}",
            f"tables={tags}",
            f"adv0={_advance(font, 0)}",
            f"advN={_advance(font, _PROBE_GID)}",
            f"cmapA={_cmap_gid(font, 0x41)}",
        ]
        return "\n".join(lines) + "\n"
    except Exception:
        # A throw while building the projection (not during parse) means the
        # lazy backend hit a corrupt table on access — collapse to ok=false so
        # the projection cannot half-succeed.
        return "ok=false\n"
    finally:
        with contextlib.suppress(Exception):
            font.close()


def _java_dump(mutated: bytes) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(mutated)
        return run_probe_text("TtfParserFuzzProbe", tmp)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Differential parity: every pinned mutant produces the identical projection.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.skipif(not _CORPUS, reason="base TTF fixture missing")
@pytest.mark.parametrize(("name", "mutated"), _CORPUS, ids=_CORPUS_IDS)
def test_ttf_parse_fuzz_parity(name: str, mutated: bytes) -> None:
    java = _java_dump(mutated)
    py = _py_dump(mutated)
    assert py == java, (
        f"divergence on TTF parse mutant {name!r}:\n"
        f" java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the clean base parses to a non-trivial projection on pypdfbox, so a
# corpus-build regression can't silently turn every mutant into a vacuous pass.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _CORPUS, reason="base TTF fixture missing")
def test_clean_base_projection_non_trivial() -> None:
    dump = _py_dump(bytes(_BASE))
    assert dump.startswith("ok=true\n")
    assert "numGlyphs=3115" in dump
    assert "unitsPerEm=2048" in dump
    assert "cmapA=36" in dump
