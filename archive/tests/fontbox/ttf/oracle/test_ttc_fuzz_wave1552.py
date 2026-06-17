"""Differential TrueTypeCollection (.ttc) per-font fuzz vs FontBox 3.0.7.

Wave 1552, Agent A. Complements the wave-1530 TTC header fuzz
(``test_true_type_collection_fuzz_wave1530.py``, which fingerprints only the
collection-header parse plus the name enumeration of a *single*-font container)
by drilling into the PER-FONT projection wave 1530 left out:

  * the GLYPH COUNT of each enumerated font (``maxp.numGlyphs``), so a
    table-sharing / mis-sliced font shows up rather than passing on name alone;
  * MULTI-font collections (Liberation + DejaVu), which wave 1530 never built —
    only multi-font input exposes per-font failure isolation;
  * ``getFontByName`` for a name we KNOW is present (vs. wave 1530's
    missing-name only), proving the by-name path returns a fully-parsed font;
  * out-of-range / negative ``get_font_at_index`` (a pure-pypdfbox guard;
    upstream's ``getFontAtIndex`` is private so this half has no oracle leg).

Both engines parse the *identical* bytes and are compared on a stable
projection produced by ``oracle/probes/TtcFuzzProbe.java``:

    ok=true
    numFonts=<count visited by processAllFonts, or "error" if it threw>
    visited=<name>:<numGlyphs> per font, comma-joined ("null"/"err" guards)
    byName[<probe>]=<numGlyphs of match, "null" if absent, "error" on throw>

or the sole line ``ok=false`` on any throw from the constructor.
``_py_dump`` reproduces the same fingerprint on the pypdfbox side.

REAL BUG FIXED THIS WAVE (now pinned as agreement cases ``second_off_zero`` /
``second_off_eof`` / ``second_off_into_first``): upstream FontBox parses each
font lazily and independently (``TrueTypeCollection.getFontAtIndex`` seeks one
offset and walks only that directory), so a LATER font with a corrupt offset
does not poison access to an EARLIER well-formed font — ``processAllFonts``
visits font 0 successfully and only throws when it reaches the bad slot
(``visited=LiberationSans:2620``, ``numFonts=error``). pypdfbox re-sliced the
container via fontTools' ``TTCollection`` constructor, which eagerly reads
EVERY font's directory up front, so one bad offset made even
``get_font_at_index(0)`` raise (``visited=`` empty). Fix:
``TrueTypeCollection._extract_font_bytes`` now slices through
``TTFont(BytesIO, fontNumber=idx)`` — a single-directory read — restoring
FontBox's per-font failure isolation.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import struct
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXDIR = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "fontbox" / "ttf"
)
_LIBERATION = _FIXDIR / "LiberationSans-Regular.ttf"
_DEJAVU = _FIXDIR / "DejaVuSansMono.ttf"

# Known PostScript names + glyph counts of the bundled fixtures (used only for
# the no-oracle regression guards; the differential tests read them live).
_LIB_NAME = "LiberationSans"
_DEJAVU_NAME = "DejaVuSansMono"


# ---------------------------------------------------------------------------
# Build a valid TWO-font base TTC once from the bundled, permissively licensed
# TTFs. fontTools is already a pypdfbox dependency (library-first font decode),
# so this adds no new dep. Multi-font input is what exposes the per-font
# failure-isolation behaviour wave 1530's single-font corpus could not reach.
# ---------------------------------------------------------------------------
def _build_base_ttc() -> bytes:
    if not (_LIBERATION.is_file() and _DEJAVU.is_file()):
        return b""
    from fontTools.ttLib import TTCollection, TTFont  # noqa: PLC0415

    collection = TTCollection()
    collection.fonts.append(TTFont(str(_LIBERATION)))
    collection.fonts.append(TTFont(str(_DEJAVU)))
    sink = io.BytesIO()
    collection.save(sink)
    return sink.getvalue()


_BASE = _build_base_ttc()


def _offsets(data: bytes) -> list[int]:
    """The per-font offset array recorded in a TTC header."""
    num = struct.unpack(">I", data[8:12])[0]
    return [struct.unpack(">I", data[12 + 4 * i : 16 + 4 * i])[0] for i in range(num)]


def _patch_offset(data: bytes, idx: int, value: int) -> bytes:
    pos = 12 + 4 * idx
    return data[:pos] + struct.pack(">I", value) + data[pos + 4 :]


# ---------------------------------------------------------------------------
# deterministic mutation corpus. Each entry: (name, ttc_bytes, probe_name).
# probe_name drives the getFontByName(present) leg of the projection.
# ---------------------------------------------------------------------------
def _generate_corpus() -> list[tuple[str, bytes, str]]:
    if not _BASE:
        return []
    offs = _offsets(_BASE)
    out: list[tuple[str, bytes, str]] = [
        # -- clean multi-font baselines ----------------------------------
        ("two_valid_missing", _BASE, "__nope__"),
        ("two_valid_byname_first", _BASE, _LIB_NAME),
        ("two_valid_byname_second", _BASE, _DEJAVU_NAME),
        # -- wrong magic / truncations -----------------------------------
        ("wrong_magic", b"OTTO" + _BASE[4:], "__nope__"),
        ("empty", b"", "__nope__"),
        ("trunc_no_numfonts", b"ttcf" + struct.pack(">I", 0x10000), "__nope__"),
        # -- numFonts bounds ---------------------------------------------
        (
            "numfonts_0",
            b"ttcf" + struct.pack(">I", 0x10000) + struct.pack(">I", 0),
            "__nope__",
        ),
        (
            "numfonts_huge",
            b"ttcf"
            + struct.pack(">I", 0x10000)
            + struct.pack(">I", 0x7FFFFFFF)
            + _BASE[12:],
            "__nope__",
        ),
        (
            "numfonts_3_only_2_offsets",
            b"ttcf"
            + struct.pack(">I", 0x10000)
            + struct.pack(">I", 3)
            + struct.pack(">I", offs[0])
            + struct.pack(">I", offs[1])
            + _BASE[20:],
            "__nope__",
        ),
        # -- per-font failure isolation (THE wave-1552 fix) --------------
        # A LATER font's offset is corrupt; the EARLIER font must still be
        # visited before processAllFonts throws on the bad slot.
        ("second_off_zero", _patch_offset(_BASE, 1, 0), _DEJAVU_NAME),
        ("second_off_eof", _patch_offset(_BASE, 1, 0xFFFFFFF0), _DEJAVU_NAME),
        ("second_off_into_first", _patch_offset(_BASE, 1, offs[0] + 4), _DEJAVU_NAME),
        ("second_off_into_header", _patch_offset(_BASE, 1, 4), _DEJAVU_NAME),
        # The FIRST font's offset is corrupt → both engines throw before any
        # visit (numFonts=error, visited empty on both sides).
        ("first_off_zero", _patch_offset(_BASE, 0, 0), _LIB_NAME),
        ("first_off_eof", _patch_offset(_BASE, 0, 0xFFFFFFF0), _LIB_NAME),
        # -- offset reorderings (still well-formed slices) ---------------
        (
            "swapped_offsets",
            _patch_offset(_patch_offset(_BASE, 0, offs[1]), 1, offs[0]),
            _LIB_NAME,
        ),
        (
            "duplicate_offset_first",
            _patch_offset(_BASE, 1, offs[0]),
            _LIB_NAME,
        ),
        # -- version handling (FontBox does not gate on the version DWORD) -
        ("version0", b"ttcf" + struct.pack(">I", 0) + _BASE[8:], _DEJAVU_NAME),
        (
            "version_huge",
            b"ttcf" + struct.pack(">I", 0xFFFFFFFF) + _BASE[8:],
            _DEJAVU_NAME,
        ),
        (
            "version3",
            b"ttcf" + struct.pack(">I", 0x30000) + _BASE[8:],
            _DEJAVU_NAME,
        ),
    ]
    return out


_CORPUS = _generate_corpus()
_CORPUS_IDS = [m[0] for m in _CORPUS]


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce TtcFuzzProbe's projection exactly.
# ---------------------------------------------------------------------------
def _describe(font: object) -> str:
    try:
        name = font.get_name()  # type: ignore[attr-defined]
        name = "null" if name is None else name
    except Exception:
        name = "nameerr"
    try:
        glyphs = str(font.get_number_of_glyphs())  # type: ignore[attr-defined]
    except Exception:
        glyphs = "glyphserr"
    return f"{name}:{glyphs}"


def _py_dump(data: bytes, probe: str) -> str:
    try:
        ttc = TrueTypeCollection(data)
    except Exception:
        return "ok=false\n"
    try:
        visited: list[str] = []
        try:
            ttc.process_all_fonts(lambda f: visited.append(_describe(f)))
            count = str(len(visited))
        except Exception:
            count = "error"
        try:
            match = ttc.get_font_by_name(probe)
            by_name = "null" if match is None else str(match.get_number_of_glyphs())
        except Exception:
            by_name = "error"
        lines = [
            "ok=true",
            f"numFonts={count}",
            f"visited={','.join(visited)}",
            f"byName[{probe}]={by_name}",
        ]
        return "\n".join(lines) + "\n"
    finally:
        with contextlib.suppress(Exception):
            ttc.close()


def _java_dump(data: bytes, probe: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".ttc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return run_probe_text("TtcFuzzProbe", tmp, probe)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Differential parity: every pinned mutant produces the identical projection.
# fontTools logs malformed-table warnings while re-reading corrupt containers;
# silence them so the test output stays readable (assertions use the projection
# string only, not stderr).
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.skipif(not _CORPUS, reason="base TTF fixtures missing")
@pytest.mark.parametrize(("name", "mutated", "probe"), _CORPUS, ids=_CORPUS_IDS)
def test_ttc_per_font_fuzz_parity(name: str, mutated: bytes, probe: str) -> None:
    logging.disable(logging.WARNING)
    try:
        java = _java_dump(mutated, probe)
        py = _py_dump(mutated, probe)
    finally:
        logging.disable(logging.NOTSET)
    assert py == java, (
        f"divergence on TTC per-font mutant {name!r}:\n"
        f" java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Regression guard for the wave-1552 per-font-isolation fix (no oracle needed):
# a corrupt SECOND offset must still let the FIRST font be visited.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BASE, reason="base TTF fixtures missing")
@pytest.mark.parametrize("bad_value", [0, 0xFFFFFFF0])
def test_later_bad_offset_does_not_poison_earlier_font(bad_value: int) -> None:
    data = _patch_offset(_BASE, 1, bad_value)
    logging.disable(logging.WARNING)
    try:
        dump = _py_dump(data, _DEJAVU_NAME)
    finally:
        logging.disable(logging.NOTSET)
    # Font 0 is visited (its slice is intact); processAllFonts then throws on
    # the corrupt second slot → numFonts=error, byName(second)=error.
    assert dump == (
        f"ok=true\nnumFonts=error\nvisited={_LIB_NAME}:2620\n"
        f"byName[{_DEJAVU_NAME}]=error\n"
    )


# ---------------------------------------------------------------------------
# Sanity: the clean two-font base parses to a non-trivial projection on
# pypdfbox, so a corpus-build regression can't silently make every mutant pass.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BASE, reason="base TTF fixtures missing")
def test_clean_two_font_projection_non_trivial() -> None:
    logging.disable(logging.WARNING)
    try:
        dump = _py_dump(_BASE, _DEJAVU_NAME)
    finally:
        logging.disable(logging.NOTSET)
    assert dump == (
        f"ok=true\nnumFonts=2\nvisited={_LIB_NAME}:2620,{_DEJAVU_NAME}:3115\n"
        f"byName[{_DEJAVU_NAME}]=3115\n"
    )


# ---------------------------------------------------------------------------
# get_font_at_index range guard (pure pypdfbox — upstream getFontAtIndex is
# private, so this half has no oracle leg). Valid indices yield each font;
# out-of-range / negative raise IndexError.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BASE, reason="base TTF fixtures missing")
def test_get_font_at_index_bounds() -> None:
    logging.disable(logging.WARNING)
    try:
        ttc = TrueTypeCollection(_BASE)
        try:
            assert ttc.get_font_at_index(0).get_name() == _LIB_NAME
            assert ttc.get_font_at_index(1).get_name() == _DEJAVU_NAME
            for bad in (2, 99, -1):
                with pytest.raises(IndexError):
                    ttc.get_font_at_index(bad)
        finally:
            ttc.close()
    finally:
        logging.disable(logging.NOTSET)
