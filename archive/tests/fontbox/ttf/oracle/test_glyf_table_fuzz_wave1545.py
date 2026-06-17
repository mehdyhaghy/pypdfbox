"""Differential ``glyf`` GLYPH-RECORD-PARSER fuzz vs Apache FontBox 3.0.7 (wave 1545).

Where ``test_glyf_decode_fuzz_wave1525`` splices a hostile glyph into a real SFNT
and decodes it through the full ``GlyphData`` / ``loca`` pipeline (fontTools on the
pypdfbox side), THIS wave drives FontBox's hand-rolled byte-level record parsers
DIRECTLY — the very classes pypdfbox ports in ``glyf_simple_descript.py`` /
``glyf_composite_descript.py`` / ``glyf_composite_comp.py``:

* ``GlyfSimpleDescript(number_of_contours, stream, x0)`` — endPts read, the
  PDFBOX-2939 ``0xFFFF`` empty-contour sentinel, the flag REPEAT run-length loop
  (including the upstream "repeat count higher than remaining space" throw),
  ``instructionLength``, and the x / y coordinate-delta decode exhausting the
  stream.
* ``GlyfCompositeComp(stream)`` — one component: ARG_1_AND_2_ARE_WORDS vs byte
  args, ARGS_ARE_XY_VALUES translates, WE_HAVE_A_SCALE / WE_HAVE_AN_X_AND_Y_SCALE
  / WE_HAVE_A_TWO_BY_TWO transform reads, truncation mid-transform.
* ``GlyfCompositeDescript(stream, glyph_table, level)`` — the MORE_COMPONENTS
  component chain and its truncation / never-terminating cases.

The Java side is ``oracle/probes/GlyfTableFuzzProbe.java``. It declares
``package org.apache.fontbox.ttf;`` so it can call the package-private record
constructors, wraps the raw glyf bytes in a ``RandomAccessReadDataStream``, and
projects the decoded shape (point/contour counts, endPts, flags, component
indices, translates) or the exception class. Inputs are raw glyf-record bytes
passed as hex — NO ``loca`` table, NO fontTools, NO full font — so this pins the
decode loops in isolation, a genuinely different surface from wave 1525.

THREE arms.

* ``_AGREE`` — well-formed records that BOTH the ported Python parser and
  FontBox's reader decode to the IDENTICAL projection (point count, contour
  count, endPts, flags / component index, flags, translates). Exact-match parity.

* ``_ERR_AGREE`` — malformed records that BOTH engines REJECT. The Java and
  Python exception *classes* differ by the documented CLAUDE.md mapping
  (``IOException`` → ``OSError``, ``EOFException`` → ``EOFError``,
  ``NegativeArraySizeException`` → ``IndexError`` / ``ArrayIndexOutOfBounds`` →
  ``IndexError``), so we normalise both to the single ``err`` outcome bucket and
  assert agreement on "this record does not decode". The raw Java class name is
  captured in the assertion message for forensic value but is NOT the parity
  criterion (matching the exact Java exception type is neither possible nor
  meaningful across the language boundary).

* ``_NULL_TABLE_GAP`` — a composite component CHAIN that decodes cleanly but is
  then handed a ``null`` parent ``GlyphTable``. FontBox's
  ``GlyfCompositeDescript`` constructor unconditionally calls
  ``initDescriptions`` which dereferences the (null) table and throws
  ``NullPointerException``; the ported Python ``init_descriptions`` returns early
  when ``glyph_table is None`` (so ``get_components()`` succeeds). This is a
  probe-harness artifact — real callers always pass a live table — but it is a
  genuine, deliberate divergence in the ported constructor, pinned BOTH-SIDES so
  a future change to either side trips the test.

Both engines TERMINATE on every record here (the MORE_COMPONENTS-overrun case is
chosen specifically to confirm neither backend loops forever on an unterminated
component chain — FontBox's loop reads the next component which hits EOF).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream
from tests.oracle.harness import requires_oracle

# This probe is *package-scoped* (declared ``package org.apache.fontbox.ttf;`` so
# it can reach the package-private ``GlyfSimpleDescript`` / ``GlyfCompositeDescript``
# / ``GlyfCompositeComp`` constructors). The shared harness keys its compiled
# class on the bare probe name and runs it without a package, so — exactly like
# the mesh probes — this test ships its own compile+run helper that invokes the
# probe by fully-qualified name.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ORACLE = _REPO_ROOT / "oracle"
_JARS_DIR = _ORACLE / "jars"
_PROBES = _ORACLE / "probes"
_BUILD = _ORACLE / "build"
_PROBE_FQN = "org.apache.fontbox.ttf.GlyfTableFuzzProbe"


def _classpath() -> str:
    jars = sorted(str(p) for p in _JARS_DIR.glob("*.jar"))
    return os.pathsep.join([*jars, str(_BUILD)])


def _run_probe(*args: str) -> str:
    """Compile (if stale) and run the packaged GlyfTableFuzzProbe by FQN."""
    src = _PROBES / "GlyfTableFuzzProbe.java"
    cls = _BUILD / "org/apache/fontbox/ttf/GlyfTableFuzzProbe.class"
    if not cls.is_file() or cls.stat().st_mtime < src.stat().st_mtime:
        _BUILD.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["javac", "-cp", _classpath(), "-d", str(_BUILD), str(src)],
            check=True,
            capture_output=True,
        )
    result = subprocess.run(
        ["java", "-cp", _classpath(), _PROBE_FQN, *args],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8")


# ---------------------------------------------------------------------------
# pypdfbox projections — mirror GlyfTableFuzzProbe's per-mode output lines.
# ---------------------------------------------------------------------------
def _py_simple(nc: int, payload: bytes) -> str:
    try:
        d = GlyfSimpleDescript(nc, RandomAccessReadDataStream(payload), 0)
        points = d.get_point_count()
        contours = d.get_contour_count()
        end_pts = ",".join(str(d.get_end_pt_of_contours(i)) for i in range(contours))
        flags = ",".join(str(d.get_flags(i) & 0xFF) for i in range(points))
        return f"SIMPLE\tok\t{points}\t{contours}\t{end_pts}\t{flags}"
    except Exception as exc:  # noqa: BLE001 - outcome bucket, class captured below
        return f"SIMPLE\terr\t{type(exc).__name__}"


def _py_comp(payload: bytes) -> str:
    try:
        c = GlyfCompositeComp(RandomAccessReadDataStream(payload))
        return (
            f"COMP\tok\t{c.get_glyph_index()}\t{c.get_flags() & 0xFFFF}\t"
            f"{c.get_argument1()}\t{c.get_argument2()}\t{c.get_x_translate()}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"COMP\terr\t{type(exc).__name__}"


def _py_composite(payload: bytes) -> str:
    try:
        d = GlyfCompositeDescript(RandomAccessReadDataStream(payload), None, 0)
        comps = d.get_components()
        gids = ",".join(str(c.get_glyph_index()) for c in comps)
        flags = ",".join(str(c.get_flags() & 0xFFFF) for c in comps)
        return f"COMP_DESC\tok\t{len(comps)}\t{gids}\t{flags}"
    except Exception as exc:  # noqa: BLE001
        return f"COMP_DESC\terr\t{type(exc).__name__}"


def _py_dump(mode: str, nc: int, payload: bytes) -> str:
    if mode == "SIMPLE":
        line = _py_simple(nc, payload)
    elif mode == "COMP":
        line = _py_comp(payload)
    else:
        line = _py_composite(payload)
    # ``_java_dump`` ``.strip()``s the probe's stdout, which drops the trailing
    # tab the Java ``printf`` emits when the final field (flags / gids) is empty
    # (e.g. the 0xFFFF empty-contour sentinel: zero points -> no flags). Strip
    # the Python projection the same way so both sides compare on content, not on
    # a trailing empty-field separator.
    return line.rstrip("\t")


def _java_dump(mode: str, nc: int, payload: bytes) -> str:
    hex_arg = payload.hex() if payload else "-"
    return _run_probe(mode, str(nc), hex_arg).strip()


# ``ok``-lines must match field-for-field; ``err``-lines are normalised to the
# bare outcome (the Java exception class != the Python one by the documented
# CLAUDE.md mapping, so only "did it reject" is the parity criterion).
def _outcome(line: str) -> str:
    parts = line.split("\t")
    if len(parts) >= 2 and parts[1] == "err":
        return f"{parts[0]}\terr"
    return line


# ---------------------------------------------------------------------------
# Corpus. Each row: (id, mode, numberOfContours, payload-after-header).
# The payload for SIMPLE is the bytes that follow numberOfContours+bbox
# (i.e. endPtsOfContours onward); for COMP/COMPOSITE it is the component chain.
# ---------------------------------------------------------------------------

# --- AGREE: well-formed, identical decoded projection on both engines -------
_AGREE: list[tuple[str, str, int, bytes]] = [
    # one on-curve point at (0,0): endPt=[0], instr=0, flag 0x01, x/y signed
    # shorts 0,0.
    ("s_one_point", "SIMPLE", 1, bytes.fromhex("000000000100000000")),
    # PDFBOX-2939 empty-contour sentinel: nc=1, endPt == 0xFFFF -> 0 points.
    ("s_empty_sentinel", "SIMPLE", 1, bytes.fromhex("FFFF")),
    # three short-vector points, one contour.
    ("s_three_short", "SIMPLE", 1, bytes.fromhex("000200000707070A0B0C010203")),
    # flag REPEAT (0x08) used legitimately: one flag byte fills two points.
    ("s_repeat_ok", "SIMPLE", 1, bytes.fromhex("0001000009010001000200030004")),
    # two contours, three short-vector points.
    ("s_two_contours", "SIMPLE", 2, bytes.fromhex("000000020000070707050505060606")),
    # single component, ARGS_ARE_XY byte args (translate 1,2), gid 5.
    ("c_xy_byte_args", "COMP", 0, bytes.fromhex("000200050102")),
    # ARG_1_AND_2_ARE_WORDS: gid 7, word args 16, 32.
    ("c_word_args", "COMP", 0, bytes.fromhex("0003000700100020")),
    # WE_HAVE_A_SCALE (0x08): uniform scale 0x4000 (==1.0), gid 3.
    ("c_scale", "COMP", 0, bytes.fromhex("000A000300004000")),
    # WE_HAVE_AN_X_AND_Y_SCALE (0x40): gid 3, both scales 1.0.
    ("c_xy_scale", "COMP", 0, bytes.fromhex("00420003000040004000")),
    # WE_HAVE_A_TWO_BY_TWO (0x80): full 2x2, gid 3.
    ("c_two_by_two", "COMP", 0, bytes.fromhex("0082000300004000000000004000")),
    # signed BYTE args: -2, -3 (xy translate), gid 5.
    ("c_neg_byte_args", "COMP", 0, bytes.fromhex("00020005FEFD")),
]

# --- ERR_AGREE: both engines reject (exception class differs by mapping) ----
_ERR_AGREE: list[tuple[str, str, int, bytes]] = [
    # flag REPEAT count runs past the point array -> upstream throws
    # IOException ("repeat count higher than remaining space"); Python OSError.
    ("s_repeat_overrun", "SIMPLE", 1, bytes.fromhex("000200000AC8")),
    # instructionLength huge with no instruction bytes following -> EOF.
    ("s_instr_huge", "SIMPLE", 1, bytes.fromhex("0000FFFF")),
    # endPtsOfContours truncated (nc=2, only one endPt present) -> EOF.
    ("s_endpts_trunc", "SIMPLE", 2, bytes.fromhex("0001")),
    # non-monotonic endPts that also exhaust the coordinate stream -> EOF.
    ("s_endpts_nonmono", "SIMPLE", 2, bytes.fromhex("00050001")),
    # coordinate deltas exhaust the stream (flag wants 1 x-byte, none left).
    ("s_coords_exhaust", "SIMPLE", 1, bytes.fromhex("0000000002")),
    # huge numberOfContours, no endPt data -> EOF reading the endPt array.
    ("s_nc_huge", "SIMPLE", 5000, bytes.fromhex("0000")),
    # Integer max-ish numberOfContours (short) -> EOF.
    ("s_nc_max", "SIMPLE", 32767, bytes.fromhex("0000")),
    # negative numberOfContours fed to the SIMPLE parser -> Java
    # NegativeArraySizeException, Python IndexError. (Real flow never routes a
    # negative count here — GlyphData dispatches composites by sign — but the
    # direct constructor surfaces the same "reject" outcome on both.)
    ("s_nc_negative", "SIMPLE", -2, bytes.fromhex("0000")),
    # component scale read truncated mid-value -> EOF.
    ("c_scale_trunc", "COMP", 0, bytes.fromhex("000A00030000")),
    # WORD args declared but absent -> EOF.
    ("c_args_trunc", "COMP", 0, bytes.fromhex("00030005")),
    # only the flags word present, glyphIndex missing -> EOF.
    ("c_header_trunc", "COMP", 0, b""),
    # composite chain: MORE_COMPONENTS set on a component with nothing after it
    # -> the next-component read hits EOF (NO infinite loop on either engine).
    ("d_more_never_terminates", "COMPOSITE", 0, bytes.fromhex("002200030000")),
    # composite component with a truncated 2x2 transform -> EOF mid-chain.
    ("d_two_by_two_trunc", "COMPOSITE", 0, bytes.fromhex("008200030000400000")),
]

# --- NULL_TABLE_GAP: clean component chain, null parent table ---------------
# FontBox NPEs in initDescriptions(null); the ported Python returns early.
_NULL_TABLE_GAP: list[tuple[str, str, int, bytes]] = [
    # single clean component, gid 9, no MORE_COMPONENTS.
    ("d_single_clean", "COMPOSITE", 0, bytes.fromhex("000200090000")),
    # two clean components chained via MORE_COMPONENTS (0x20), gids 3 and 7.
    (
        "d_two_components",
        "COMPOSITE",
        0,
        bytes.fromhex("002200030000000200070000"),
    ),
    # component referencing an out-of-range glyph index (no table to validate
    # against): the index is just stored.
    ("d_oob_index", "COMPOSITE", 0, bytes.fromhex("0002EA600000")),
    # component referencing glyph index 0 (a "self/cycle"-style reference that,
    # with a null table, never resolves) -> still a clean decode.
    ("d_self_ref_index", "COMPOSITE", 0, bytes.fromhex("000200000000")),
]

_AGREE_IDS = [r[0] for r in _AGREE]
_ERR_IDS = [r[0] for r in _ERR_AGREE]
_GAP_IDS = [r[0] for r in _NULL_TABLE_GAP]


# ---------------------------------------------------------------------------
# AGREE arm — exact-match parity on the decoded projection.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(("name", "mode", "nc", "payload"), _AGREE, ids=_AGREE_IDS)
def test_glyf_record_parse_parity(
    name: str, mode: str, nc: int, payload: bytes
) -> None:
    java = _java_dump(mode, nc, payload)
    py = _py_dump(mode, nc, payload)
    assert py == java, (
        f"glyf record decode divergence on {name!r}:\n  java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# ERR_AGREE arm — both reject; outcome bucket matches (exception class differs
# by the documented Java->Python mapping).
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(
    ("name", "mode", "nc", "payload"), _ERR_AGREE, ids=_ERR_IDS
)
def test_glyf_record_parse_rejected_both(
    name: str, mode: str, nc: int, payload: bytes
) -> None:
    java = _java_dump(mode, nc, payload)
    py = _py_dump(mode, nc, payload)
    assert _outcome(java).endswith("err"), (
        f"{name!r}: expected Java to reject, got {java!r}"
    )
    assert _outcome(py).endswith("err"), (
        f"{name!r}: expected pypdfbox to reject, got {py!r}"
    )
    assert _outcome(py) == _outcome(java), (
        f"glyf record reject-outcome divergence on {name!r}:\n"
        f"  java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# NULL_TABLE_GAP arm — pinned divergence (FontBox NPEs on a null parent table
# in initDescriptions; the ported Python returns early and succeeds).
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(
    ("name", "mode", "nc", "payload"), _NULL_TABLE_GAP, ids=_GAP_IDS
)
def test_glyf_composite_null_table_gap(
    name: str, mode: str, nc: int, payload: bytes
) -> None:
    java = _java_dump(mode, nc, payload)
    py = _py_dump(mode, nc, payload)
    # FontBox throws NPE inside initDescriptions(null).
    assert _outcome(java) == "COMP_DESC\terr", (
        f"{name!r}: expected FontBox NPE on null table, got {java!r}"
    )
    # The ported Python decodes the chain and exposes the components.
    assert py.startswith("COMP_DESC\tok\t"), (
        f"{name!r}: expected pypdfbox to decode the chain, got {py!r}"
    )


# ---------------------------------------------------------------------------
# Self-contained sanity (runs without the oracle): the ported parsers decode the
# canonical AGREE records to their expected shapes, so a corpus-build regression
# can't silently vacate the parity arms.
# ---------------------------------------------------------------------------
def test_ported_parsers_decode_expected_shapes() -> None:
    assert _py_simple(1, bytes.fromhex("000000000100000000")) == (
        "SIMPLE\tok\t1\t1\t0\t1"
    )
    assert _py_simple(1, bytes.fromhex("FFFF")) == "SIMPLE\tok\t0\t1\t65535\t"
    assert _py_simple(1, bytes.fromhex("000200000707070A0B0C010203")) == (
        "SIMPLE\tok\t3\t1\t2\t7,7,7"
    )
    assert _py_comp(bytes.fromhex("000200050102")) == "COMP\tok\t5\t2\t1\t2\t1"
    assert _py_comp(bytes.fromhex("0003000700100020")) == "COMP\tok\t7\t3\t16\t32\t16"


def test_ported_parsers_reject_malformed() -> None:
    # REPEAT overrun -> OSError (upstream IOException).
    assert _py_simple(1, bytes.fromhex("000200000AC8")) == "SIMPLE\terr\tOSError"
    # negative contour count to the simple parser -> IndexError.
    assert _py_simple(-2, bytes.fromhex("0000")) == "SIMPLE\terr\tIndexError"
    # unterminated MORE_COMPONENTS chain -> EOFError (no infinite loop).
    assert _py_composite(bytes.fromhex("002200030000")) == "COMP_DESC\terr\tEOFError"
