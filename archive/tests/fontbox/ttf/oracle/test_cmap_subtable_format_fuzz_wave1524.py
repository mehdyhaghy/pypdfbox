"""Live PDFBox differential parity for the byte-level PARSING of individual
TrueType cmap subtable FORMAT bodies
(``oracle/probes/CmapSubtableFormatFuzzProbe.java``, wave 1524).

Where ``test_cmap_subtable_select_oracle.py`` pins platform/encoding SELECTION
across a multi-subtable font, this module drives the per-format body reader
(:meth:`CmapSubtable.process_subtype0` / ``2`` / ``4`` / ``6`` / ``12`` and the
format dispatch in :meth:`CmapSubtable.init_subtable`) against a real, valid
SFNT whose ``cmap`` table has been surgically replaced with a deliberately
MALFORMED subtable body:

* format 0 — short / wrong-length glyph array;
* format 4 — odd / zero ``segCountX2``, ``endCode`` not ending 0xFFFF,
  ``startCode > endCode``, ``idRangeOffset`` pointing out of bounds, and a
  direct/indirect glyph id that exceeds ``numGlyphs`` (the wave-1524 fix:
  upstream stores it verbatim, it is NOT filtered);
* format 6 — huge ``entryCount``, out-of-range glyph id;
* format 12 — ``nGroups`` overflow, overlapping groups,
  ``startCharCode > endCharCode``, surrogate range;
* format 2 — malformed ``subHeaderKeys``;
* unknown format number, truncated body, zero-length body.

The base font is the bundled DejaVuSans (re-serialised through fontTools so the
table directory is canonical); only the ``cmap`` bytes are hostile. The same
spliced font file is fed to both the Java probe and the pypdfbox reproducer (the
reproducer drives the native :class:`CmapTable` byte parser over the WHOLE-FONT
stream exactly as FontBox does, so out-of-bounds subtable reads continue into
adjacent font bytes identically on both sides), so any divergence surfaces as a
single differing line.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

# Mirror the probe's CODEPOINTS exactly.
_CODEPOINTS = [
    0x00, 0x20, 0x41, 0x42, 0x43, 0x61, 0x80, 0xFF,
    0x100, 0x1000, 0x4000, 0x4001, 0x4002, 0xABCD,
    0xFFFF, 0x10000, 0x10FFFF, 0x110000,
]


# --------------------------------------------------------------------------- #
# SFNT splicing — replace the cmap table bytes with a hostile body.
# --------------------------------------------------------------------------- #
def _base_font() -> bytes:
    """Re-serialise DejaVuSans through fontTools to get a canonical SFNT."""
    from fontTools.ttLib import TTFont  # noqa: PLC0415

    tt = TTFont(io.BytesIO((_TTF_DIR / "DejaVuSans.ttf").read_bytes()))
    try:
        buf = io.BytesIO()
        tt.save(buf)
        return buf.getvalue()
    finally:
        tt.close()


def _table_checksum(data: bytes) -> int:
    if len(data) % 4:
        data = data + b"\x00" * (4 - len(data) % 4)
    total = 0
    for i in range(0, len(data), 4):
        total = (total + struct.unpack(">I", data[i : i + 4])[0]) & 0xFFFFFFFF
    return total


def _splice_cmap(font: bytes, cmap_body: bytes) -> bytes:
    """Replace the ``cmap`` table bytes with ``cmap_body``; rewrite directory."""
    sfnt, num_tables = struct.unpack(">4sH", font[:6])
    bodies: dict[bytes, bytes] = {}
    off = 12
    for _ in range(num_tables):
        tag, _csum, toff, tlen = struct.unpack(">4sIII", font[off : off + 16])
        bodies[tag] = font[toff : toff + tlen]
        off += 16
    bodies[b"cmap"] = cmap_body

    tags = sorted(bodies)
    n = len(tags)
    high_bit = max(1, 2 ** (n.bit_length() - 1))
    header = struct.pack(
        ">4sHHHH", sfnt, n, high_bit * 16, n.bit_length() - 1,
        n * 16 - high_bit * 16,
    )

    cur = 12 + n * 16
    placed: dict[bytes, tuple[int, int]] = {}
    blob = bytearray()
    for tag in tags:
        body = bodies[tag]
        placed[tag] = (cur, len(body))
        blob += body
        pad = (-len(body)) % 4
        blob += b"\x00" * pad
        cur += len(body) + pad

    directory = bytearray()
    for tag in tags:
        toff, tlen = placed[tag]
        directory += struct.pack(
            ">4sIII", tag, _table_checksum(bodies[tag]), toff, tlen
        )
    return bytes(header) + bytes(directory) + bytes(blob)


def _cmap(subtable_body: bytes, platform: int = 3, encoding: int = 1) -> bytes:
    """Wrap one subtable body in a cmap table: version, count=1, one dir entry."""
    sub_offset = 4 + 8  # table header (version + count) + one directory record
    head = struct.pack(">HH", 0, 1) + struct.pack(
        ">HHI", platform, encoding, sub_offset
    )
    return head + subtable_body


def _cmap_offset(font: bytes) -> int:
    num_tables = struct.unpack(">H", font[4:6])[0]
    off = 12
    for _ in range(num_tables):
        tag, _csum, toff, _tlen = struct.unpack(">4sIII", font[off : off + 16])
        if tag == b"cmap":
            return toff
        off += 16
    raise AssertionError("spliced font has no cmap table")


# --------------------------------------------------------------------------- #
# Malformed subtable body builders.
# --------------------------------------------------------------------------- #
def _f0(glyph_array: bytes) -> bytes:
    return struct.pack(">HHH", 0, 6 + len(glyph_array), 0) + glyph_array


def _f4(
    seg_x2: int,
    end_count: list[int],
    start_count: list[int],
    id_delta: list[int],
    id_range_offset: list[int],
) -> bytes:
    body = struct.pack(">HHHH", seg_x2, 0, 0, 0)
    body += struct.pack(f">{len(end_count)}H", *end_count)
    body += struct.pack(">H", 0)  # reservedPad
    body += struct.pack(f">{len(start_count)}H", *start_count)
    body += struct.pack(
        f">{len(id_delta)}h",
        *[(d if d < 0x8000 else d - 0x10000) for d in id_delta],
    )
    body += struct.pack(f">{len(id_range_offset)}H", *id_range_offset)
    return struct.pack(">HHH", 4, 6 + len(body), 0) + body


def _f6(first_code: int, entry_count: int, glyphs: list[int]) -> bytes:
    body = struct.pack(">HH", first_code, entry_count)
    body += struct.pack(f">{len(glyphs)}H", *glyphs)
    return struct.pack(">HHH", 6, 6 + len(body), 0) + body


def _f12(groups: list[tuple[int, int, int]]) -> bytes:
    body = struct.pack(">I", len(groups))
    for fc, ec, sg in groups:
        body += struct.pack(">III", fc, ec, sg)
    return struct.pack(">HHII", 12, 0, 16 + len(body), 0) + body


def _f12_ngroups_overflow() -> bytes:
    body = struct.pack(">I", 1000) + struct.pack(">III", 0x41, 0x43, 5)
    return struct.pack(">HHII", 12, 0, 16 + len(body), 0) + body


def _f2_simple() -> bytes:
    keys = struct.pack(">256H", *([0] * 256))
    sub_header = struct.pack(">HHhH", 0x41, 3, 0, 2)
    glyphs = struct.pack(">3H", 5, 6, 7)
    body = keys + sub_header + glyphs
    return struct.pack(">HHH", 2, 6 + len(body), 0) + body


def _f2_bad_subheaders() -> bytes:
    keys_list = [0] * 256
    keys_list[0x81] = 8000  # /8 -> a huge maxSubHeaderIndex
    keys = struct.pack(">256H", *keys_list)
    body = keys + struct.pack(">HHhH", 0x41, 3, 0, 2) + struct.pack(">3H", 5, 6, 7)
    return struct.pack(">HHH", 2, 6 + len(body), 0) + body


_DELTA_C = (5 - 0x41) & 0xFFFF

_CASES: dict[str, bytes] = {
    "f0_full": _f0(bytes(i % 256 for i in range(256))),
    "f0_short": _f0(bytes(range(100))),
    "f0_wronglen": struct.pack(">HHH", 0, 10, 0)
    + bytes(i % 256 for i in range(256)),
    "f4_odd_segx2": _f4(5, [0x43, 0xFFFF], [0x41, 0xFFFF], [_DELTA_C, 1], [0, 0]),
    "f4_zero_segx2": _f4(0, [], [], [], []),
    "f4_no_ffff": _f4(2, [0x43, 0x50], [0x41, 0x44], [_DELTA_C, 1], [0, 0]),
    "f4_start_gt_end": _f4(2, [0x43, 0xFFFF], [0x50, 0xFFFF], [_DELTA_C, 1], [0, 0]),
    "f4_idrange_oob": _f4(2, [0x43, 0xFFFF], [0x41, 0xFFFF], [0, 1], [0xF000, 0]),
    "f6_valid": _f6(0x41, 3, [5, 6, 7]),
    "f6_huge_entry": _f6(0x41, 5000, [5, 6, 7]),
    "f12_valid": _f12([(0x41, 0x43, 5)]),
    "f12_ngroups_of": _f12_ngroups_overflow(),
    "f12_start_gt_end": _f12([(0x50, 0x41, 5)]),
    "f12_overlap": _f12([(0x41, 0x45, 5), (0x43, 0x47, 20)]),
    "f12_surrogate": _f12([(0xD800, 0xD810, 5)]),
    "f2_simple": _f2_simple(),
    "f2_bad_subheaders": _f2_bad_subheaders(),
    "unknown_fmt": struct.pack(">HHH", 99, 16, 0) + b"\x00" * 10,
    "truncated": struct.pack(">HHH", 0, 600, 0) + b"\x00" * 10,
    "zero_length": struct.pack(">HHH", 0, 0, 0),
}


# --------------------------------------------------------------------------- #
# pypdfbox reproducer — drive the native cmap byte parser over the WHOLE font.
# --------------------------------------------------------------------------- #
def _py_lines(font: bytes, num_glyphs: int) -> str:
    lines: list[str] = []

    class _Font:
        def get_number_of_glyphs(self) -> int:
            return num_glyphs

    try:
        offset = _cmap_offset(font)
        stream = MemoryTTFDataStream(font)
        stream.seek(offset)
        cmap = CmapTable()
        cmap.set_offset(offset)
        cmap.read(_Font(), stream)
        subs = cmap.get_cmaps()
        lines.append("ok=true")
        lines.append(f"nsub={len(subs)}")
        for i, sub in enumerate(subs):
            for cp in _CODEPOINTS:
                try:
                    gid = sub.get_glyph_id(cp)
                except Exception:  # noqa: BLE001 — match probe's broad catch
                    gid = -1
                lines.append(f"GID{i}\t{cp}\t{gid}")
    except Exception:  # noqa: BLE001 — match probe's ok=false fingerprint
        return "ok=false\n"
    return "\n".join(lines) + "\n"


def _num_glyphs(font: bytes) -> int:
    ttf = TrueTypeFont.from_bytes(font)
    try:
        return ttf.get_number_of_glyphs()
    finally:
        ttf.close()


@requires_oracle
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_cmap_subtable_format_body_matches_pdfbox(case: str, tmp_path: Path) -> None:
    """A real font whose ``cmap`` carries a malformed subtable body of each
    format must parse to the same per-subtable ``get_glyph_id`` projection (or
    the same ``ok=false`` parse failure) as Apache PDFBox 3.0.7's native
    ``CmapTable`` / ``CmapSubtable`` byte parser.
    """
    font = _splice_cmap(_base_font(), _cmap(_CASES[case]))
    font_path = tmp_path / "FuzzCmap.ttf"
    font_path.write_bytes(font)

    java = run_probe_text("CmapSubtableFormatFuzzProbe", str(font_path))
    py = _py_lines(font, _num_glyphs(font))

    j = java.splitlines()
    p = py.splitlines()
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(j, p, strict=False))
        if a != b
    ]
    assert len(j) == len(p) and not diffs, (
        f"cmap format-body parity broken for {case!r}: "
        f"java_lines={len(j)} py_lines={len(p)}\n" + "\n".join(diffs[:30])
    )
