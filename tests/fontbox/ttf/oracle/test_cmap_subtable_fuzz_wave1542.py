"""Live PDFBox differential parity for the TrueType cmap subtable REVERSE
lookup surface (``oracle/probes/CmapSubtableFuzzProbe.java``, wave 1542).

Where ``test_cmap_subtable_format_fuzz_wave1524.py`` pins the FORWARD
:meth:`CmapSubtable.get_glyph_id` projection across malformed subtable bodies,
this module drives the inverse direction — :meth:`CmapSubtable.get_char_codes`
— plus the formats and edge cases that wave 1524 did NOT exercise:

* format 13 (many-to-one): every code in a group maps to one gid, so the
  reverse map for that gid must list ALL the codes (the multi-mapping path
  through the ``-2_147_483_648`` sentinel + ``_glyph_id_to_character_code_multiple``);
* format 0 / 4 / 6 / 12 reverse maps, including the multi-mapping sentinel case
  where several distinct character codes collide on one gid (``idDelta`` chosen
  so two codes resolve to the same glyph);
* the "no mapping" reverse case (a gid past the end of the reverse array) which
  must return ``None`` — not throw, not an empty list;
* a format-14 (UVS) subtable, which is inert through the single-codepoint
  ``get_glyph_id`` API and carries no reverse map either (both projections
  empty) — confirming its presence does not corrupt neighbours.

The base font is the bundled DejaVuSans (re-serialised through fontTools so the
table directory is canonical); only the ``cmap`` bytes are hostile. The same
spliced font file is fed to both the Java probe and the pypdfbox reproducer (the
reproducer drives the native :class:`CmapTable` byte parser over the WHOLE-FONT
stream exactly as FontBox does), so any divergence surfaces as a single
differing line.

The splice / cmap-wrapper plumbing is shared verbatim with the wave-1524 module;
this module only contributes a fresh, reverse-lookup-focused case battery.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from tests.fontbox.ttf.oracle.test_cmap_subtable_format_fuzz_wave1524 import (
    _base_font,
    _cmap,
    _cmap_offset,
    _f0,
    _f4,
    _f6,
    _f12,
    _num_glyphs,
    _splice_cmap,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# Mirror the probe's CODEPOINTS exactly (forward lookup).
_CODEPOINTS = [
    0x00, 0x20, 0x41, 0x42, 0x43, 0x44, 0x45, 0x61, 0xFF,
    0x100, 0x4E00, 0xFFFF, 0x10000, 0x1F600, 0x10FFFF, 0x110000,
]

# Mirror the probe's GIDS exactly (reverse lookup).
_GIDS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 20, 21, 22, 100, 65535, 70000]


# --------------------------------------------------------------------------- #
# Format-13 body builder (many-to-one) — not provided by the wave-1524 module.
# --------------------------------------------------------------------------- #
def _f13(groups: list[tuple[int, int, int]]) -> bytes:
    """Build a format-13 subtable body (each group maps a code range to ONE gid)."""
    body = struct.pack(">I", len(groups))
    for start_code, end_code, glyph in groups:
        body += struct.pack(">III", start_code, end_code, glyph)
    # format(uint16) reserved(uint16) length(uint32) language(uint32)
    return struct.pack(">HHII", 13, 0, 16 + len(body), 0) + body


def _f14(records: list[tuple[int, list[tuple[int, int]]]]) -> bytes:
    """Build a minimal format-14 (UVS) subtable body with non-default mappings.

    ``records`` is a list of ``(var_selector, [(unicode_value, glyph_id), ...])``.
    Only the non-default-UVS table is emitted (default-UVS offset = 0); this is
    enough to confirm the subtable is inert through ``get_glyph_id`` / has no
    reverse map on both sides.
    """
    num_records = len(records)
    # Record array: each record is uint24 selector + uint32 default + uint32
    # non-default = 11 bytes. The subtable starts at the format word, so offsets
    # are measured from there: format(2) + length(4) + numRecords(4) = 10 bytes
    # header, then 11 bytes per record.
    header_len = 2 + 4 + 4
    record_array_len = 11 * num_records
    non_default_base = header_len + record_array_len

    record_blob = b""
    table_blob = b""
    cursor = non_default_base
    for selector, mappings in records:
        non_default_offset = cursor
        record_blob += (
            struct.pack(">B", (selector >> 16) & 0xFF)
            + struct.pack(">B", (selector >> 8) & 0xFF)
            + struct.pack(">B", selector & 0xFF)
            + struct.pack(">I", 0)  # default UVS offset (absent)
            + struct.pack(">I", non_default_offset)
        )
        tbl = struct.pack(">I", len(mappings))
        for unicode_value, glyph_id in mappings:
            tbl += (
                struct.pack(">B", (unicode_value >> 16) & 0xFF)
                + struct.pack(">B", (unicode_value >> 8) & 0xFF)
                + struct.pack(">B", unicode_value & 0xFF)
                + struct.pack(">H", glyph_id)
            )
        table_blob += tbl
        cursor += len(tbl)

    body = struct.pack(">I", num_records) + record_blob + table_blob
    length = 2 + 4 + len(body)
    return struct.pack(">HI", 14, length) + body


# idDelta that makes char code 0x41 -> gid 5 (matches wave 1524's convention).
_DELTA_C = (5 - 0x41) & 0xFFFF
# idDelta that makes char code 0x42 ALSO resolve to gid 5 (collision -> multi map).
_DELTA_COLLIDE = (5 - 0x42) & 0xFFFF


_CASES: dict[str, bytes] = {
    # format 0: reverse lookup. Byte 0x41 -> gid 5, 0x42 -> gid 6, etc.
    "f0_reverse": _f0(
        bytes(
            (5 if i == 0x41 else 6 if i == 0x42 else 7 if i == 0x43 else 0)
            for i in range(256)
        )
    ),
    # format 0 with a glyph-id collision: codes 0x41 and 0x61 both -> gid 5.
    "f0_reverse_collision": _f0(
        bytes((5 if i in (0x41, 0x61) else 0) for i in range(256))
    ),
    # format 4: straightforward reverse (0x41..0x43 -> gid 5..7).
    "f4_reverse": _f4(
        4, [0x43, 0xFFFF], [0x41, 0xFFFF], [_DELTA_C, 1], [0, 0]
    ),
    # format 4: two single-code segments collide on gid 5 (0x41 and 0x42).
    "f4_reverse_collision": _f4(
        6,
        [0x41, 0x42, 0xFFFF],
        [0x41, 0x42, 0xFFFF],
        [_DELTA_C, _DELTA_COLLIDE, 1],
        [0, 0, 0],
    ),
    # format 6: reverse over a trimmed array.
    "f6_reverse": _f6(0x41, 4, [5, 6, 7, 8]),
    # format 6: a repeated glyph id -> multi-mapping reverse.
    "f6_reverse_collision": _f6(0x41, 4, [5, 5, 7, 8]),
    # format 12: reverse over a single group.
    "f12_reverse": _f12([(0x41, 0x44, 5)]),
    # format 12: two groups whose glyphs overlap -> later code wins forward,
    # both contribute to reverse (multi-mapping on the shared gids).
    "f12_reverse_overlap": _f12([(0x41, 0x43, 5), (0x4E00, 0x4E02, 5)]),
    # format 13: many-to-one. Codes 0x41..0x45 ALL -> gid 5 (reverse lists all).
    "f13_many_to_one": _f13([(0x41, 0x45, 5)]),
    # format 13: two groups -> two distinct multi-mapped gids.
    "f13_two_groups": _f13([(0x41, 0x43, 5), (0x100, 0x102, 6)]),
    # format 13: single code per "group" (degenerate -> singleton reverse).
    "f13_singletons": _f13([(0x41, 0x41, 5), (0x42, 0x42, 6)]),
    # format 14 (UVS): inert through get_glyph_id, empty reverse map.
    "f14_uvs": _f14([(0xFE00, [(0x4E00, 5), (0x6F22, 6)])]),
}


# --------------------------------------------------------------------------- #
# pypdfbox reproducer — drive the native cmap byte parser over the WHOLE font,
# rendering BOTH the forward and reverse projections the probe emits.
# --------------------------------------------------------------------------- #
def _render_codes(codes: list[int] | None) -> str:
    if codes is None:
        return "null"
    return ",".join(str(c) for c in codes)


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
            for g in _GIDS:
                try:
                    rendered = _render_codes(sub.get_char_codes(g))
                except Exception:  # noqa: BLE001 — match probe's broad catch
                    rendered = "throw"
                lines.append(f"CC{i}\t{g}\t{rendered}")
    except Exception:  # noqa: BLE001 — match probe's ok=false fingerprint
        return "ok=false\n"
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_cmap_subtable_reverse_matches_pdfbox(case: str, tmp_path: Path) -> None:
    """A real font whose ``cmap`` carries a hostile/edge subtable body must
    parse to the same per-subtable forward (``get_glyph_id``) AND reverse
    (``get_char_codes``) projection as Apache PDFBox 3.0.7's native
    ``CmapTable`` / ``CmapSubtable`` byte parser.
    """
    font = _splice_cmap(_base_font(), _cmap(_CASES[case]))
    font_path = tmp_path / "FuzzCmapRev.ttf"
    font_path.write_bytes(font)

    java = run_probe_text("CmapSubtableFuzzProbe", str(font_path))
    py = _py_lines(font, _num_glyphs(font))

    j = java.splitlines()
    p = py.splitlines()
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(j, p, strict=False))
        if a != b
    ]
    assert len(j) == len(p) and not diffs, (
        f"cmap reverse-lookup parity broken for {case!r}: "
        f"java_lines={len(j)} py_lines={len(p)}\n" + "\n".join(diffs[:30])
    )
