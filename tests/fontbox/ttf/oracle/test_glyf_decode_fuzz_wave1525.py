"""Differential ``glyf`` GLYPH-DECODE fuzz vs Apache FontBox 3.0.7 (wave 1525).

Where ``test_composite_glyph_oracle`` fingerprints a WELL-FORMED composite
outline, this wave fuzzes the DECODE of HOSTILE ``glyf`` byte streams. For the
permissively-licensed bundled ``DejaVuSans.ttf`` we take one glyph (a simple
glyph — ``exclam``, gid 4 — or a composite — ``onequarter``, gid 126), overwrite
its on-disk ``glyf`` bytes IN PLACE (padded / truncated to the original length so
the ``loca`` offsets and every downstream table stay valid), and decode it on
both engines.

The Java side is ``oracle/probes/GlyfDecodeFuzzProbe.java`` (raw
``TTFParser().parse`` → ``getGlyph(gid).getDescription().resolve()``). Each glyph
projects one line::

    GLYPH \t gid \t true  \t numberOfContours \t contourCount \t pointCount \t bbox
    GLYPH \t gid \t false \t ERR \t ERR \t ERR \t ERR          # decode threw
    GLYPH \t gid \t null                                       # no GlyphData
    GLYPH \t gid \t get_err                                    # getGlyph threw
    PARSE \t false                                             # parse threw

``_py_dump`` reproduces this fingerprint on the pypdfbox side.

TWO arms.

* ``_AGREE`` — mutations where the fontTools-backed pypdfbox decode and
  FontBox's hand-rolled ``GlyfSimpleDescript`` / ``GlyfCompositeDescript`` agree
  on the FULL projection. These are asserted as exact-match parity. They cover
  the empty glyph (``numberOfContours == 0``), all-zero glyf bytes, a glyph
  truncated to just its 2-byte ``numberOfContours`` header, a non-monotonic
  ``endPtsOfContours``, and — on the composite side — a clean composite, a
  ``MORE_COMPONENTS`` flag set with no following component, a component that
  references itself (NOT a true decode cycle — it borrows the half-built
  outline), an out-of-range component glyph index, and all-zero composite bytes.

* ``_LIBRARY_GAP`` — mutations where the two engines DIVERGE because pypdfbox
  decodes the ``glyf`` payload through fontTools (library-first per CLAUDE.md)
  while FontBox hand-rolls a deliberately lenient reader. These are NOT bugs in
  ``glyph_data.py``: matching them would mean bypassing fontTools' glyf decoder
  and reimplementing ``GlyfSimpleDescript`` / ``GlyfCompositeDescript`` /
  ``GlyfCompositeComp`` byte-for-byte — out of scope and against the
  library-first rule (the same CCITT/libtiff precedent pinned in wave 1505 and
  the lazy-vs-eager TTF-parse gap pinned in wave 1506). The divergence axes:

    1. *Negative ``numberOfContours`` other than -1.* FontBox treats EVERY
       ``numberOfContours < 0`` as a composite (it dispatches on ``>= 0`` vs
       ``< 0``), so ``-2`` / ``-3`` decode the trailing bytes as a composite and
       resolve to an outline. fontTools accepts only ``-1`` for composites and
       raises on any other negative count.
    2. *Truncated coordinate / component data.* FontBox's reader zero-pads (or
       stops short) when the flag / delta / component stream ends early, so a
       half-truncated simple glyph or a composite cut mid-component still
       resolves to a partial outline. fontTools raises (``not enough data`` /
       ``too few coordinates``) on the short read.
    3. *Cyclic composite.* A composite component that references its own glyph
       with no further base is detected by FontBox (it returns a zero-point
       outline) but drives fontTools into a decode error.
    4. *Huge / ``Integer.MAX`` contour count.* Both engines fail, but at
       different stages and with different surface text (FontBox throws inside
       ``getGlyph``; fontTools throws on point decode), so even the ``ok``
       boolean line text differs.

  These are pinned BOTH-SIDES (the live Java projection is captured and the
  pypdfbox projection is asserted to DIFFER from it) so a future fontTools
  upgrade that closes one of the gaps trips this test and we revisit the pin.

Both engines TERMINATE on every mutant here (no hang, no process crash) — the
self-reference and ``MORE_COMPONENTS``-overrun cases were specifically chosen to
confirm neither backend infinite-loops on malformed composite chains.
"""

from __future__ import annotations

import contextlib
import os
import struct
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FONT = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)
_BASE = bytes(_FONT.read_bytes()) if _FONT.is_file() else b""

# Target glyphs in DejaVuSans: gid 4 = ``exclam`` (a 2-contour simple glyph,
# 100 glyf bytes); gid 126 = ``onequarter`` (a composite, 32 glyf bytes).
_GID_SIMPLE = 4
_GID_COMPOSITE = 126


# ---------------------------------------------------------------------------
# SFNT splice helpers: locate a glyph's glyf byte range via the (long) loca
# table and overwrite it in place, padding/truncating to the original length so
# no downstream offset shifts (a clean per-glyph mutation, not cascade rot).
# ---------------------------------------------------------------------------
def _directory(data: bytes) -> dict[str, tuple[int, int, int]]:
    out: dict[str, tuple[int, int, int]] = {}
    if len(data) < 12:
        return out
    num = struct.unpack(">H", data[4:6])[0]
    pos = 12
    for _ in range(num):
        if pos + 16 > len(data):
            break
        tag = data[pos : pos + 4].decode("latin1")
        _cs, off, length = struct.unpack(">III", data[pos + 4 : pos + 16])
        out[tag] = (pos, off, length)
        pos += 16
    return out


_DIR = _directory(_BASE)


def _loca_offsets() -> tuple[int, list[int]]:
    """Return ``(glyf_table_offset, [loca offsets])`` (long loca format)."""
    glyf_off = _DIR["glyf"][1]
    loca_off, loca_len = _DIR["loca"][1], _DIR["loca"][2]
    n = loca_len // 4
    offsets = list(struct.unpack(f">{n}L", _BASE[loca_off : loca_off + 4 * n]))
    return glyf_off, offsets


def _glyph_range(gid: int) -> tuple[int, int]:
    glyf_off, offsets = _loca_offsets()
    return glyf_off + offsets[gid], glyf_off + offsets[gid + 1]


def _glyph_bytes(gid: int) -> bytes:
    start, end = _glyph_range(gid)
    return _BASE[start:end]


def _splice(gid: int, new_bytes: bytes) -> bytes:
    """Overwrite ``gid``'s glyf bytes, padded/truncated to the original length."""
    start, end = _glyph_range(gid)
    length = end - start
    body = bytearray(new_bytes)
    if len(body) < length:
        body += b"\x00" * (length - len(body))
    else:
        body = body[:length]
    out = bytearray(_BASE)
    out[start : start + length] = body
    return bytes(out)


# ---------------------------------------------------------------------------
# Mutation builders (only built when the fixture is present).
# ---------------------------------------------------------------------------
def _build_corpus() -> tuple[
    list[tuple[str, int, bytes]], list[tuple[str, int, bytes]]
]:
    if not _DIR:
        return [], []
    s_orig = _glyph_bytes(_GID_SIMPLE)
    c_orig = _glyph_bytes(_GID_COMPOSITE)
    gs, gc = _GID_SIMPLE, _GID_COMPOSITE

    # ----- AGREE arm: full-projection parity ------------------------------
    # Each tuple's third field is the per-glyph glyf payload; ``_splice`` below
    # embeds it into the full font (padded/truncated to the original length).
    agree_raw: list[tuple[str, int, bytes]] = [
        # numberOfContours == 0 -> empty glyph, both yield a zero-rect outline.
        ("s_empty_nc0", gs, b"\x00\x00"),
        # all-zero glyf bytes -> empty glyph.
        ("s_all_zero", gs, b"\x00" * len(s_orig)),
        # only the 2-byte numberOfContours + bbox header survives (rest zero):
        # both decode the real contour count with a 1-point degenerate outline.
        ("s_header_only", gs, s_orig[:10]),
        # non-monotonic endPtsOfContours appended after the bbox header.
        ("s_endpts_nonmono", gs, s_orig[:10] + struct.pack(">HH", 5, 1)),
        # truncated to the 2-byte numberOfContours only.
        ("s_trunc_to_nc", gs, s_orig[:2]),
        # a clean composite resolves identically.
        ("c_clean", gc, c_orig),
        # MORE_COMPONENTS (0x0020) set on the last component with no follower:
        # both stop at the partial component (no hang).
        ("c_more_no_follower", gc, c_orig[:2] + struct.pack(">HH", 0x0020, 0xFFFF) + c_orig[6:]),
        # component references itself (borrows the half-built outline, NOT a
        # decode cycle) -> both resolve the same partial outline.
        ("c_comp_self_ref", gc, c_orig[:4] + struct.pack(">H", gc) + c_orig[6:]),
        # component glyph index out of range -> both tolerate (FontBox borrows
        # an empty glyph, fontTools the same), identical projection.
        ("c_comp_oob_index", gc, c_orig[:4] + struct.pack(">H", 60000) + c_orig[6:]),
        # all-zero composite bytes -> empty glyph.
        ("c_all_zero", gc, b"\x00" * len(c_orig)),
    ]

    # ----- LIBRARY_GAP arm: pinned divergences ----------------------------
    # A true cyclic composite: a single component, ARGS_ARE_XY (0x0002), byte
    # args, no MORE_COMPONENTS, referencing its own glyph.
    cyclic = struct.pack(">HH", 0x0002, gc) + struct.pack(">bb", 0, 0)
    gap_raw: list[tuple[str, int, bytes]] = [
        # negative numberOfContours other than -1 -> FontBox decodes as
        # composite; fontTools rejects.
        ("s_nc_neg2", gs, struct.pack(">h", -2) + s_orig[2:]),
        ("s_nc_neg3", gs, struct.pack(">h", -3) + s_orig[2:]),
        # huge / max contour count -> both fail, different surface.
        ("s_nc_huge", gs, struct.pack(">h", 5000) + s_orig[2:]),
        ("s_nc_max", gs, struct.pack(">h", 0x7FFF) + s_orig[2:]),
        # simple glyph truncated mid coordinate stream -> FontBox zero-pads,
        # fontTools raises.
        ("s_trunc_half", gs, s_orig[: len(s_orig) // 2]),
        # composite truncated mid-component -> FontBox tolerates, fontTools raises.
        ("c_trunc_after_nc", gc, c_orig[:2]),
        ("c_trunc_mid", gc, c_orig[:8]),
        # composite bytes reinterpreted as a simple glyph (nc=1) -> both fail,
        # different surface.
        ("c_as_simple", gc, struct.pack(">h", 1) + c_orig[2:]),
        # true cyclic composite -> FontBox returns a zero-point outline,
        # fontTools errors.
        ("c_cyclic_self", gc, struct.pack(">h", -1) + c_orig[2:10] + cyclic),
    ]
    agree = [(name, gid, _splice(gid, body)) for name, gid, body in agree_raw]
    gap = [(name, gid, _splice(gid, body)) for name, gid, body in gap_raw]
    return agree, gap


_AGREE, _LIBRARY_GAP = _build_corpus()
_AGREE_IDS = [m[0] for m in _AGREE]
_GAP_IDS = [m[0] for m in _LIBRARY_GAP]


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce GlyfDecodeFuzzProbe's per-gid projection.
# ---------------------------------------------------------------------------
def _py_dump(mutated: bytes, gid: int) -> str:
    try:
        font = TTFParser().parse(mutated)
    except Exception:
        return "PARSE\tfalse"
    try:
        glyf = font.get_glyph_table()
        if glyf is None:
            return f"GLYPH\t{gid}\tnull"
        try:
            gd = glyf.get_glyph(gid)
        except Exception:
            return f"GLYPH\t{gid}\tget_err"
        if gd is None:
            return f"GLYPH\t{gid}\tnull"
        try:
            noc = gd.get_number_of_contours()
            desc = gd.get_description()
            desc.resolve()
            contours = desc.get_contour_count()
            points = desc.get_point_count()
            bbox = gd.get_bounding_box()
            return (
                f"GLYPH\t{gid}\ttrue\t{noc}\t{contours}\t{points}\t"
                f"{int(bbox.get_lower_left_x())} {int(bbox.get_lower_left_y())} "
                f"{int(bbox.get_upper_right_x())} {int(bbox.get_upper_right_y())}"
            )
        except Exception:
            return f"GLYPH\t{gid}\tfalse\tERR\tERR\tERR\tERR"
    finally:
        with contextlib.suppress(Exception):
            font.close()


def _java_dump(mutated: bytes, gid: int) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".ttf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(mutated)
        return run_probe_text("GlyfDecodeFuzzProbe", tmp, str(gid)).strip()
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# AGREE arm: every pinned mutant produces the identical projection.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.skipif(not _AGREE, reason="base TTF fixture missing")
@pytest.mark.parametrize(("name", "gid", "mutated"), _AGREE, ids=_AGREE_IDS)
def test_glyf_decode_fuzz_parity(name: str, gid: int, mutated: bytes) -> None:
    java = _java_dump(mutated, gid)
    py = _py_dump(mutated, gid)
    assert py == java, (
        f"divergence on glyf decode mutant {name!r}:\n"
        f" java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# LIBRARY_GAP arm: pinned divergence (library-first fontTools decode vs
# FontBox's lenient hand-rolled reader). Both sides still TERMINATE.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.skipif(not _LIBRARY_GAP, reason="base TTF fixture missing")
@pytest.mark.parametrize(("name", "gid", "mutated"), _LIBRARY_GAP, ids=_GAP_IDS)
def test_glyf_decode_library_gap(name: str, gid: int, mutated: bytes) -> None:
    java = _java_dump(mutated, gid)
    py = _py_dump(mutated, gid)
    # Both engines must terminate with a non-empty projection (no hang/crash).
    assert java, f"empty java projection for {name!r}"
    assert py, f"empty py projection for {name!r}"
    # The documented library-gap: the projections differ. If a fontTools
    # upgrade closes the gap (py == java) this assertion trips and we revisit.
    assert py != java, (
        f"glyf decode library-gap {name!r} unexpectedly CONVERGED — "
        f"revisit the pin: java={java!r} py={py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the unmutated composite resolves to a non-trivial outline on pypdfbox,
# so a corpus-build regression can't silently vacate every assertion.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _DIR, reason="base TTF fixture missing")
def test_clean_composite_projection_non_trivial() -> None:
    dump = _py_dump(_BASE, _GID_COMPOSITE)
    assert dump == "GLYPH\t126\ttrue\t-1\t4\t29\t137 -29 1919 1520"
