"""Differential TrueType METRIC / NAME table-``read()`` fuzz vs Apache FontBox 3.0.7 (wave 1553).

Where the existing ``test_post_table_oracle`` / ``test_name_table_oracle`` /
``test_os2_metrics_oracle`` / ``test_hmtx_lsb_oracle`` / ``test_head_maxp_oracle``
parse a REAL, well-formed SFNT and read the accessors, THIS wave drives the
package-private ``read(TrueTypeFont, TTFDataStream)`` of each metric/name table
DIRECTLY over hand-crafted, often MALFORMED, table bytes. That is exactly the
surface pypdfbox ports in:

* ``post_script_table.py`` — format 1 / 2 / 2.5 / 3 glyph-name decode, the
  format-2 custom-name Pascal-string array (incl. the PDFBOX-808 32768..65535
  reserved-index handling, the PDFBOX-4851 EOF-padding split, and the
  "custom index past the names array" case).
* ``naming_table.py`` — name-record decode + the 4-arg ``(nid, plat, enc, lang)``
  lookup, the PDFBOX-2608 out-of-range string-offset handling, the unknown
  platform → Latin-1 fallback, and the record-count overrun.
* ``os2_windows_metrics_table.py`` — version 0 / 1 / 2 field reads and the
  truncation-driven version downgrade (v2→v1, v1→v0, legacy→EOF).
* ``horizontal_metrics_table.py`` + ``horizontal_header_table.py`` — the
  trailing-LSB compression, ``numberOfHMetrics > numGlyphs`` hardening, the
  missing-trailing-LSB short table, and ``numberOfHMetrics == 0``.
* ``header_table.py`` — ``unitsPerEm`` (incl. zero), ``indexToLocFormat``,
  ``macStyle``, and truncation.

The Java side is ``oracle/probes/TtfMetricTableFuzzProbe.java``. It declares
``package org.apache.fontbox.ttf;`` so it can call the package-private
``TTFTable.read(...)`` and the table setters; for the post-2.5 / hmtx cases it
pre-reads synthetic ``maxp`` (numGlyphs) and ``hhea`` (numberOfHMetrics) tables
and adds them to a bare ``TrueTypeFont`` so ``getNumberOfGlyphs()`` /
``getHorizontalHeader()`` resolve without a font directory.

TWO arms.

* ``_AGREE`` — table blobs (well-formed AND malformed) that BOTH the ported
  Python parser and FontBox decode to the IDENTICAL projection. Malformed
  blobs that BOTH engines reject are normalised to the single ``err`` outcome
  bucket: the Java and Python exception *classes* differ by the documented
  CLAUDE.md mapping (``IOException`` → ``OSError``, ``EOFException`` →
  ``EOFError``), so the parity criterion is "this blob does not decode", not the
  exact exception type.

* ``_DIVERGE`` — blobs where the two engines DELIBERATELY differ, pinned
  BOTH-SIDES with an honest comment so a future change to either side trips the
  test. The single case is the ``name`` table over-long string record (string
  length runs past the storage area): upstream FontBox 3.0.7 checks only
  ``stringOffset > tableLength`` and then ``readString`` past EOF → throws
  ``IOException``, whereas the pypdfbox port carries the additional PDFBOX-2608
  ``string_end > length`` / ``absolute + length > originalDataSize`` guards and
  therefore SKIPS the record (decodes ``ok`` with the name set to ``None``). The
  port is intentionally more defensive; both engines TERMINATE.

REAL BUG FIXED THIS WAVE (``post_script_table.py``): the format-2 custom-name
loop wrapped BOTH ``read_unsigned_byte`` (the Pascal-string length) and
``read_string`` in the PDFBOX-4851 try/except. Upstream wraps ONLY
``readString`` (verified against the FontBox 3.0.7 bytecode exception table), so
an EOF reading the LENGTH byte must propagate, not pad with ``.notdef``. The port
now reads the length byte outside the guard, matching upstream's throw-vs-pad
split exactly (case ``POST_EOF_LEN`` below pins the corrected behaviour).
"""

from __future__ import annotations

import os
import struct
import subprocess
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.header_table import HeaderTable
from pypdfbox.fontbox.ttf.horizontal_header_table import HorizontalHeaderTable
from pypdfbox.fontbox.ttf.horizontal_metrics_table import HorizontalMetricsTable
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.os2_windows_metrics_table import OS2WindowsMetricsTable
from pypdfbox.fontbox.ttf.post_script_table import PostScriptTable
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream
from tests.oracle.harness import requires_oracle

# Package-scoped probe (declared ``package org.apache.fontbox.ttf;``): the shared
# harness keys its compiled class on the bare probe name and runs it without a
# package, so — like the glyf-table probe — this test ships its own compile+run
# helper that invokes the probe by fully-qualified name.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ORACLE = _REPO_ROOT / "oracle"
_JARS_DIR = _ORACLE / "jars"
_PROBES = _ORACLE / "probes"
_BUILD = _ORACLE / "build"
_PROBE_FQN = "org.apache.fontbox.ttf.TtfMetricTableFuzzProbe"


def _classpath() -> str:
    jars = sorted(str(p) for p in _JARS_DIR.glob("*.jar"))
    return os.pathsep.join([*jars, str(_BUILD)])


def _run_probe(*args: str) -> str:
    src = _PROBES / "TtfMetricTableFuzzProbe.java"
    cls = _BUILD / "org/apache/fontbox/ttf/TtfMetricTableFuzzProbe.class"
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
# Blob builders — identical bytes the Java probe receives as hex.
# ---------------------------------------------------------------------------
def _post_header(whole: int, frac: int = 0) -> bytes:
    # 4-byte 16.16 fixed formatType + 28 bytes of the remaining fixed header.
    return struct.pack(">hH", whole, frac) + b"\x00" * 28


def _post_fmt2(num_glyphs: int, indices: list[int], names: list[str]) -> bytes:
    b = _post_header(2, 0) + struct.pack(">H", num_glyphs)
    for i in indices:
        b += struct.pack(">H", i)
    for n in names:
        nb = n.encode("latin-1")
        b += bytes([len(nb)]) + nb
    return b


def _name_record(plat: int, enc: int, lang: int, nid: int, length: int, off: int) -> bytes:
    return struct.pack(">HHHHHH", plat, enc, lang, nid, length, off)


def _name_table(records: list[bytes], storage: bytes) -> bytes:
    n = len(records)
    return struct.pack(">HHH", 0, n, 6 + 12 * n) + b"".join(records) + storage


def _os2_v0() -> bytes:
    b = struct.pack(">H", 0)  # version
    b += struct.pack(">h", 0)  # avgCharWidth
    b += struct.pack(">H", 400)  # weightClass
    b += struct.pack(">H", 5)  # widthClass
    b += struct.pack(">h", 8)  # fsType
    b += struct.pack(">h", 0) * 10  # subscript / superscript / strikeout
    b += struct.pack(">h", 0)  # familyClass
    b += b"\x00" * 10  # panose
    b += struct.pack(">I", 0) * 4  # unicode ranges
    b += b"ABCD"  # achVendID
    b += struct.pack(">H", 0)  # fsSelection
    b += struct.pack(">H", 0)  # firstChar
    b += struct.pack(">H", 0)  # lastChar
    b += struct.pack(">h", 700)  # typoAscender
    b += struct.pack(">h", -200)  # typoDescender
    b += struct.pack(">h", 0)  # typoLineGap
    b += struct.pack(">H", 800)  # winAscent
    b += struct.pack(">H", 200)  # winDescent
    return b


def _os2_version(v: int) -> bytes:
    return struct.pack(">H", v) + _os2_v0()[2:]


def _hmtx(pairs: list[tuple[int, int]], extra_lsb: list[int]) -> bytes:
    b = b""
    for adv, lsb in pairs:
        b += struct.pack(">Hh", adv, lsb)
    for lsb in extra_lsb:
        b += struct.pack(">h", lsb)
    return b


def _head(units: int, indexloc: int, macstyle: int = 0, magic: int = 0x5F0F3CF5) -> bytes:
    b = struct.pack(">i", 0x00010000)  # version 1.0
    b += struct.pack(">i", 0)  # fontRevision
    b += struct.pack(">I", 0)  # checkSumAdjustment
    b += struct.pack(">I", magic)  # magicNumber
    b += struct.pack(">H", 0)  # flags
    b += struct.pack(">H", units)  # unitsPerEm
    b += struct.pack(">q", 0)  # created
    b += struct.pack(">q", 0)  # modified
    b += struct.pack(">hhhh", 0, 0, 0, 0)  # bbox
    b += struct.pack(">H", macstyle)  # macStyle
    b += struct.pack(">H", 8)  # lowestRecPPEM
    b += struct.pack(">h", 2)  # fontDirectionHint
    b += struct.pack(">h", indexloc)  # indexToLocFormat
    b += struct.pack(">h", 0)  # glyphDataFormat
    return b


# ---------------------------------------------------------------------------
# Stub TrueTypeFont — supplies only what the table reads touch.
# ---------------------------------------------------------------------------
class _StubTTF:
    def __init__(self, num_glyphs: int = 0, hhea: HorizontalHeaderTable | None = None) -> None:
        self._n = num_glyphs
        self._hhea = hhea

    def get_name(self) -> str:
        return "stub"

    def get_number_of_glyphs(self) -> int:
        return self._n

    def get_horizontal_header(self) -> HorizontalHeaderTable | None:
        return self._hhea


# ---------------------------------------------------------------------------
# Python projections — mirror the probe's per-mode output lines exactly.
# ---------------------------------------------------------------------------
def _py_post(num_glyphs: int, blob: bytes, gids: list[int]) -> str:
    post = PostScriptTable()
    post.set_offset(0)
    post.set_length(len(blob))
    try:
        post.read(_StubTTF(num_glyphs), RandomAccessReadDataStream(blob))
    except (OSError, EOFError):
        return "err"
    lines = [f"ok\t{post.get_format_type()}"]
    for g in gids:
        n = post.get_name(g)
        lines.append(f"NAME\t{g}\t{'NULL' if n is None else n}")
    return "\n".join(lines)


def _py_name(blob: bytes, lookups: list[tuple[int, int, int, int]]) -> str:
    t = NamingTable()
    t.set_offset(0)
    t.set_length(len(blob))
    try:
        t.read(_StubTTF(), RandomAccessReadDataStream(blob))
    except (OSError, EOFError):
        return "err"
    lines = [f"ok\t{len(t.get_name_records())}"]
    lines.append(f"FAMILY\t{t.get_font_family() or 'NULL'}")
    lines.append(f"SUBFAMILY\t{t.get_font_sub_family() or 'NULL'}")
    lines.append(f"PSNAME\t{t.get_post_script_name() or 'NULL'}")
    for nid, plat, enc, lang in lookups:
        v = t.get_name(nid, plat, enc, lang)
        lines.append(f"LOOKUP\t{nid},{plat},{enc},{lang}\t{'NULL' if v is None else v}")
    return "\n".join(lines)


def _py_os2(blob: bytes) -> str:
    os2 = OS2WindowsMetricsTable()
    os2.set_offset(0)
    os2.set_length(len(blob))
    try:
        os2.read(_StubTTF(), RandomAccessReadDataStream(blob))
    except (OSError, EOFError):
        return "err"
    return "\n".join(
        [
            f"ok\t{os2.get_version()}",
            f"WEIGHT\t{os2.get_weight_class()}",
            f"FSTYPE\t{os2.get_fs_type()}",
            f"TYPOASC\t{os2.get_typo_ascender()}",
            f"WINASC\t{os2.get_win_ascent()}",
            f"CODEPAGE1\t{os2.get_code_page_range1()}",
            f"CAPHEIGHT\t{os2.get_cap_height()}",
        ]
    )


def _py_hmtx(num_glyphs: int, num_h_metrics: int, blob: bytes, gids: list[int]) -> str:
    hhea = HorizontalHeaderTable()
    hhea.set_number_of_h_metrics(num_h_metrics)
    hmtx = HorizontalMetricsTable()
    hmtx.set_offset(0)
    hmtx.set_length(len(blob))
    try:
        hmtx.read(_StubTTF(num_glyphs, hhea), RandomAccessReadDataStream(blob))
    except (OSError, EOFError):
        return "err"
    lines = [f"ok\t{num_glyphs}\t{num_h_metrics}"]
    for g in gids:
        try:
            adv = str(hmtx.get_advance_width(g))
        except (IndexError, OSError):
            adv = "ERR"
        try:
            lsb = str(hmtx.get_left_side_bearing(g))
        except (IndexError, OSError):
            lsb = "ERR"
        lines.append(f"HM\t{g}\t{adv}\t{lsb}")
    return "\n".join(lines)


def _py_head(blob: bytes) -> str:
    head = HeaderTable()
    head.set_offset(0)
    head.set_length(len(blob))
    try:
        head.read(_StubTTF(), RandomAccessReadDataStream(blob))
    except (OSError, EOFError):
        return "err"
    return "\n".join(
        [
            f"ok\t{head.get_units_per_em()}",
            f"INDEXTOLOC\t{head.get_index_to_loc_format()}",
            f"MACSTYLE\t{head.get_mac_style()}",
            f"MAGIC\t{head.get_magic_number()}",
            f"FLAGS\t{head.get_flags()}",
        ]
    )


def _norm(out: str) -> str:
    """Normalise a probe / projection string into the err-bucket outcome.

    A blob that does not decode is collapsed to the single ``err`` token on
    BOTH sides (the Java exception simple-name differs from the Python one by
    the documented CLAUDE.md mapping; the parity criterion is "does it
    decode"). Otherwise the full tab-separated projection is compared verbatim.
    """
    stripped = out.strip()
    if stripped.startswith("err"):
        return "err"
    return stripped


# ===========================================================================
# AGREE matrix — (mode-args tuple for the probe, expected normalised projection)
# Expected values are pinned from FontBox 3.0.7; the live oracle (when present)
# re-verifies them and the Python projection must match too.
# ===========================================================================
_FAM = "Ab".encode("utf-16-be")

_AGREE: list[tuple[str, list[str], str, object]] = [
    # ---- POST ----
    (
        "post_fmt2_normal",
        ["POST", "2", _post_fmt2(2, [3, 258], ["foo"]).hex(), "--", "0", "1", "2"],
        "post",
        ("ok\t2.0\nNAME\t0\tspace\nNAME\t1\tfoo\nNAME\t2\tNULL", 2, [0, 1, 2]),
    ),
    (
        "post_fmt2_reserved_index",
        ["POST", "2", _post_fmt2(2, [3, 40000], ["foo"]).hex(), "--", "0", "1"],
        "post",
        ("ok\t2.0\nNAME\t0\tspace\nNAME\t1\t.undefined", 2, [0, 1]),
    ),
    (
        "post_fmt3_no_names",
        ["POST", "2", _post_header(3, 0).hex(), "--", "0", "1"],
        "post",
        ("ok\t3.0\nNAME\t0\tNULL\nNAME\t1\tNULL", 2, [0, 1]),
    ),
    (
        "post_fmt2_5",
        ["POST", "3", (_post_header(2, 0x8000) + bytes([0, 1, 2])).hex(), "--", "0", "1", "2"],
        "post",
        ("ok\t2.5\nNAME\t0\t.null\nNAME\t1\tspace\nNAME\t2\tquotedbl", 3, [0, 1, 2]),
    ),
    (
        "post_fmt1_standard",
        ["POST", "3", (_post_header(1, 0) + b"\x00").hex(), "--", "0", "3", "257", "258"],
        "post",
        (
            "ok\t1.0\nNAME\t0\t.notdef\nNAME\t3\tspace\nNAME\t257\tdcroat\nNAME\t258\tNULL",
            3,
            [0, 3, 257, 258],
        ),
    ),
    (
        "post_fmt2_no_name_data",
        ["POST", "2", _post_header(2, 0).hex(), "--", "0"],
        "post",
        ("ok\t2.0\nNAME\t0\tNULL", 2, [0]),
    ),
    (
        # CORRECTED behaviour (this wave's bug fix): EOF reading the Pascal
        # length byte must throw, NOT pad with .notdef.
        "post_eof_len_byte",
        [
            "POST",
            "1",
            (_post_header(2, 0) + struct.pack(">H", 1) + struct.pack(">H", 258)).hex(),
            "--",
            "0",
        ],
        "post",
        ("err", 1, [0]),
    ),
    # ---- NAME ----
    (
        "name_normal_family",
        ["NAME", _name_table([_name_record(3, 1, 0x409, 1, len(_FAM), 0)], _FAM).hex(),
         "--", "1,3,1,1033"],
        "name",
        (
            "ok\t1\nFAMILY\tAb\nSUBFAMILY\tNULL\nPSNAME\tNULL\nLOOKUP\t1,3,1,1033\tAb",
            [(1, 3, 1, 1033)],
        ),
    ),
    (
        "name_offset_past_storage",
        ["NAME", _name_table([_name_record(3, 1, 0x409, 1, len(_FAM), 9999)], _FAM).hex(),
         "--", "1,3,1,1033"],
        "name",
        (
            "ok\t1\nFAMILY\tNULL\nSUBFAMILY\tNULL\nPSNAME\tNULL\nLOOKUP\t1,3,1,1033\tNULL",
            [(1, 3, 1, 1033)],
        ),
    ),
    (
        "name_unknown_platform_latin1",
        ["NAME", _name_table([_name_record(99, 1, 0x409, 1, len(_FAM), 0)], _FAM).hex(),
         "--", "1,99,1,1033"],
        "name",
        (
            # platform 99 is not a Unicode/UTF-16 platform, so the raw UTF-16BE
            # bytes ``00 41 00 62`` decode as Latin-1 → ``\x00A\x00b`` (the NULs
            # render as blanks in a terminal but are real here).
            "ok\t1\nFAMILY\tNULL\nSUBFAMILY\tNULL\nPSNAME\tNULL\nLOOKUP\t1,99,1,1033\t\x00A\x00b",
            [(1, 99, 1, 1033)],
        ),
    ),
    (
        "name_record_count_overrun",
        ["NAME",
         (struct.pack(">HHH", 0, 3, 18) + _name_record(3, 1, 0x409, 1, len(_FAM), 0) + _FAM).hex(),
         "--", "1,3,1,1033"],
        "name",
        ("err", [(1, 3, 1, 1033)]),
    ),
    # ---- OS/2 ----
    (
        "os2_v0_full",
        ["OS2", _os2_v0().hex()],
        "os2",
        "ok\t0\nWEIGHT\t400\nFSTYPE\t8\nTYPOASC\t700\nWINASC\t800\nCODEPAGE1\t0\nCAPHEIGHT\t0",
    ),
    (
        "os2_v1_truncated_downgrade",
        ["OS2", _os2_version(1).hex()],
        "os2",
        "ok\t0\nWEIGHT\t400\nFSTYPE\t8\nTYPOASC\t700\nWINASC\t800\nCODEPAGE1\t0\nCAPHEIGHT\t0",
    ),
    (
        "os2_v1_full",
        ["OS2", (_os2_version(1) + struct.pack(">I", 0) * 2).hex()],
        "os2",
        "ok\t1\nWEIGHT\t400\nFSTYPE\t8\nTYPOASC\t700\nWINASC\t800\nCODEPAGE1\t0\nCAPHEIGHT\t0",
    ),
    (
        "os2_v2_truncated_downgrade",
        ["OS2", (_os2_version(2) + struct.pack(">I", 0) * 2 + struct.pack(">h", 100)).hex()],
        "os2",
        "ok\t1\nWEIGHT\t400\nFSTYPE\t8\nTYPOASC\t700\nWINASC\t800\nCODEPAGE1\t0\nCAPHEIGHT\t0",
    ),
    (
        "os2_legacy_truncated",
        ["OS2", _os2_v0()[:-12].hex()],
        "os2",
        "err",
    ),
    # ---- HMTX ----
    (
        "hmtx_normal_trailing_lsb",
        ["HMTX", "4", "2", _hmtx([(500, 10), (600, 20)], [30, 40]).hex(),
         "--", "0", "1", "2", "3"],
        "hmtx",
        (
            "ok\t4\t2\nHM\t0\t500\t10\nHM\t1\t600\t20\nHM\t2\t600\t30\nHM\t3\t600\t40",
            4, 2, [0, 1, 2, 3],
        ),
    ),
    (
        "hmtx_num_hmetrics_gt_glyphs",
        ["HMTX", "2", "4", _hmtx([(500, 10), (600, 20), (700, 30), (800, 40)], []).hex(),
         "--", "0", "1", "2", "3"],
        "hmtx",
        (
            "ok\t2\t4\nHM\t0\t500\t10\nHM\t1\t600\t20\nHM\t2\t700\t30\nHM\t3\t800\t40",
            2, 4, [0, 1, 2, 3],
        ),
    ),
    (
        "hmtx_missing_trailing_lsb",
        ["HMTX", "4", "2", _hmtx([(500, 10), (600, 20)], []).hex(),
         "--", "0", "1", "2", "3"],
        "hmtx",
        (
            "ok\t4\t2\nHM\t0\t500\t10\nHM\t1\t600\t20\nHM\t2\t600\t0\nHM\t3\t600\t0",
            4, 2, [0, 1, 2, 3],
        ),
    ),
    (
        "hmtx_num_hmetrics_zero",
        ["HMTX", "3", "0", _hmtx([], []).hex(), "--", "0", "1"],
        "hmtx",
        ("ok\t3\t0\nHM\t0\t250\t0\nHM\t1\t250\t0", 3, 0, [0, 1]),
    ),
    # ---- HEAD ----
    (
        "head_normal",
        ["HEAD", _head(1000, 0).hex()],
        "head",
        "ok\t1000\nINDEXTOLOC\t0\nMACSTYLE\t0\nMAGIC\t1594834165\nFLAGS\t0",
    ),
    (
        "head_units_per_em_zero",
        ["HEAD", _head(0, 1, 2).hex()],
        "head",
        "ok\t0\nINDEXTOLOC\t1\nMACSTYLE\t2\nMAGIC\t1594834165\nFLAGS\t0",
    ),
    (
        "head_truncated",
        ["HEAD", _head(1000, 0)[:30].hex()],
        "head",
        "err",
    ),
]


# Map each AGREE case to its Python projection so the test id stays the friendly
# name (the parametrize passes the probe args + payload through).
def _py_for(kind: str, args: list[str], payload: object) -> str:
    if kind == "post":
        _expected, num_glyphs, gids = payload  # type: ignore[misc]
        blob = bytes.fromhex(args[2])
        return _norm(_py_post(num_glyphs, blob, gids))
    if kind == "name":
        _expected, lookups = payload  # type: ignore[misc]
        blob = bytes.fromhex(args[1])
        return _norm(_py_name(blob, lookups))
    if kind == "os2":
        blob = bytes.fromhex(args[1])
        return _norm(_py_os2(blob))
    if kind == "hmtx":
        _expected, num_glyphs, num_h_metrics, gids = payload  # type: ignore[misc]
        blob = bytes.fromhex(args[3])
        return _norm(_py_hmtx(num_glyphs, num_h_metrics, blob, gids))
    if kind == "head":
        blob = bytes.fromhex(args[1])
        return _norm(_py_head(blob))
    raise AssertionError(kind)


def _expected_for(kind: str, payload: object) -> str:
    if kind in ("post", "hmtx"):
        return _norm(payload[0])  # type: ignore[index]
    if kind == "name":
        return _norm(payload[0])  # type: ignore[index]
    return _norm(payload)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "args", "kind", "payload"),
    [(c[0], c[1], c[2], c[3]) for c in _AGREE],
    ids=[c[0] for c in _AGREE],
)
def test_python_matches_pinned_3_0_7(
    name: str, args: list[str], kind: str, payload: object
) -> None:
    """pypdfbox's table read matches the value pinned from FontBox 3.0.7."""
    assert _py_for(kind, args, payload) == _expected_for(kind, payload)


@requires_oracle
@pytest.mark.parametrize(
    ("name", "args", "kind", "payload"),
    [(c[0], c[1], c[2], c[3]) for c in _AGREE],
    ids=[c[0] for c in _AGREE],
)
def test_python_matches_live_oracle(
    name: str, args: list[str], kind: str, payload: object
) -> None:
    """pypdfbox's table read matches the LIVE FontBox 3.0.7 oracle."""
    java = _norm(_run_probe(*args))
    py = _py_for(kind, args, payload)
    assert py == java, f"{name}: py={py!r} java={java!r}"


# ===========================================================================
# DIVERGE — name over-long string record. Upstream throws (single
# stringOffset>length check + readString past EOF); the port carries the extra
# PDFBOX-2608 string_end / original-data-size guards and SKIPS the record.
# Pinned BOTH-SIDES so a future change to either side trips this test.
# ===========================================================================
_DIVERGE_NAME_ARGS = [
    "NAME",
    _name_table([_name_record(3, 1, 0x409, 1, 9999, 0)], _FAM).hex(),
    "--",
    "1,3,1,1033",
]


def test_name_overlong_record_diverges_python_skips() -> None:
    """pypdfbox SKIPS the over-long name record (decodes ok, name None)."""
    py = _norm(_py_name(bytes.fromhex(_DIVERGE_NAME_ARGS[1]), [(1, 3, 1, 1033)]))
    # Decodes ok with the over-long record's string set to None (NULL lookup).
    assert py.startswith("ok\t1")
    assert "LOOKUP\t1,3,1,1033\tNULL" in py


@requires_oracle
def test_name_overlong_record_diverges_java_throws() -> None:
    """FontBox 3.0.7 THROWS on the same over-long name record."""
    java = _run_probe(*_DIVERGE_NAME_ARGS).strip()
    assert java.startswith("err"), java
    # And the two engines genuinely disagree on this blob.
    py = _norm(_py_name(bytes.fromhex(_DIVERGE_NAME_ARGS[1]), [(1, 3, 1, 1033)]))
    assert py != _norm(java)
