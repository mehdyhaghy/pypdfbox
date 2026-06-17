"""Live PDFBox differential parity for TrueType cmap subtable SELECTION and
format-4 segment lookup (``oracle/probes/CmapSubtableSelectProbe.java``).

This complements ``test_cmap_lookup_oracle.py`` (which leans on bundled
fontTools-built fonts) by driving the **native byte parser**
(:class:`pypdfbox.fontbox.ttf.cmap_subtable.CmapSubtable`) against a
hand-crafted font that carries MULTIPLE cmap subtables in a deliberately
non-priority directory order — (1,0) Mac-Roman format-6, (3,1) Windows BMP
Unicode format-4, (0,3) Unicode-2.0-BMP format-4 — where the two format-4
subtables contain a deliberate SEGMENT GAP (codes ``0x4002`` and ``0xABCD``
are unmapped between mapped neighbours, so format-4 segment search must return
GID 0 for them).

What it pins against Apache PDFBox 3.0.7:

* the parsed subtable count and directory order;
* ``CmapTable.get_subtable(platform, encoding)`` selection for every canonical
  PDFBox priority pair (incl. the absent (0,4)/(3,10)/(3,0)/(0,1) -> ``None``);
* ``CmapSubtable.get_glyph_id(code)`` for EACH subtable across a codepoint
  battery that includes the format-4 segment-gap codes (-> GID 0), so the
  segment idRangeOffset / idDelta walk is exercised end to end;
* the priority Unicode resolver pick (``get_unicode_cmap_lookup``) — which
  prefers the (0,3) Unicode subtable over the (3,1) Windows one — and its
  per-codepoint GID.

The synthetic font is generated into a tempdir at runtime (deterministic
bytes; nothing committed) and the same file is fed to both the Java probe and
the pypdfbox reproducer, so any divergence surfaces as a single differing line.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

# Mirror the probe's PAIRS / CODEPOINTS exactly.
_PAIRS = [(0, 4), (3, 10), (0, 3), (3, 1), (3, 0), (1, 0), (0, 1)]
_CODEPOINTS = [
    0x00, 0x20, 0x41, 0x42, 0x43, 0x61, 0x7A, 0x80, 0xE9,
    0x4000, 0x4001, 0x4002, 0x4003, 0x4004,
    0xABCD, 0x2122, 0x20AC, 0xF041, 0xFFFF,
]


def _make_multi_cmap_font(djv_bytes: bytes) -> bytes:
    """Rewrite DejaVuSans to carry three cmap subtables with a format-4 gap.

    * (3,1) Windows BMP Unicode, format 4 — maps ``A B C`` and ``0x4000 0x4001
      0x4003 0x4004`` (skipping ``0x4002`` and ``0xABCD`` so format-4 segment
      search must return GID 0 for those).
    * (0,3) Unicode-2.0-BMP, format 4 — identical mapping to (3,1). PDFBox's
      priority resolver prefers this over (3,1).
    * (1,0) Mac-Roman, format 6 — a different ``A B`` mapping so the per-subtable
      ``get_glyph_id`` lines visibly diverge between subtables.

    The subtables are appended in non-priority directory order; fontTools
    serialises them by (platformID, platEncID) so both Java and pypdfbox parse
    the identical byte order.
    """
    from fontTools.ttLib import TTFont  # noqa: PLC0415
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FTSub  # noqa: PLC0415

    tt = TTFont(io.BytesIO(djv_bytes))
    try:
        bmp = tt["cmap"].getcmap(3, 1)
        name_a = bmp.cmap.get(0x41)
        name_b = bmp.cmap.get(0x42)
        name_c = bmp.cmap.get(0x43)
        assert name_a and name_b and name_c, "DejaVuSans must map A/B/C"

        unicode_map = {
            0x41: name_a, 0x42: name_b, 0x43: name_c,
            0x4000: name_a, 0x4001: name_b, 0x4003: name_c, 0x4004: name_a,
        }

        sub_31 = FTSub.getSubtableClass(4)(4)
        sub_31.platformID = 3
        sub_31.platEncID = 1
        sub_31.format = 4
        sub_31.language = 0
        sub_31.cmap = dict(unicode_map)

        sub_03 = FTSub.getSubtableClass(4)(4)
        sub_03.platformID = 0
        sub_03.platEncID = 3
        sub_03.format = 4
        sub_03.language = 0
        sub_03.cmap = dict(unicode_map)

        sub_10 = FTSub.getSubtableClass(6)(6)
        sub_10.platformID = 1
        sub_10.platEncID = 0
        sub_10.format = 6
        sub_10.language = 0
        sub_10.cmap = {0x41: name_c, 0x42: name_b}

        tt["cmap"].tables = [sub_10, sub_31, sub_03]
        buf = io.BytesIO()
        tt.save(buf)
        return buf.getvalue()
    finally:
        tt.close()


def _py_lines(ttf_path: Path) -> str:
    """Reconstruct ``CmapSubtableSelectProbe`` output from pypdfbox."""
    lines: list[str] = []
    ttf = TrueTypeFont.from_bytes(ttf_path.read_bytes())
    try:
        num_glyphs = ttf.get_number_of_glyphs()
        raw = ttf.get_table_bytes("cmap")
        assert raw is not None

        class _Font:
            def get_number_of_glyphs(self) -> int:
                return num_glyphs

        cmap = CmapTable()
        cmap.read(_Font(), MemoryTTFDataStream(raw))
        subs = cmap.get_cmaps()
        lines.append(f"CMAPS\t{len(subs)}")
        for i, sub in enumerate(subs):
            lines.append(
                f"CMAP\t{i}\t{sub.get_platform_id()}\t"
                f"{sub.get_platform_encoding_id()}"
            )
        for plat, enc in _PAIRS:
            sub = cmap.get_subtable(plat, enc)
            if sub is None:
                lines.append(f"GET\t{plat}\t{enc}\tNONE\t-")
            else:
                lines.append(
                    f"GET\t{plat}\t{enc}\t"
                    f"{sub.get_platform_id()}\t{sub.get_platform_encoding_id()}"
                )
        for sub in subs:
            for cp in _CODEPOINTS:
                lines.append(
                    f"GID\t{sub.get_platform_id()}\t"
                    f"{sub.get_platform_encoding_id()}\t{cp}\t{sub.get_glyph_id(cp)}"
                )
        uni = ttf.get_unicode_cmap_subtable()
        if uni is None:
            lines.append("UNICODE\tNONE\t-")
        else:
            lines.append(
                f"UNICODE\t{uni.get_platform_id()}\t{uni.get_platform_encoding_id()}"
            )
            look = ttf.get_unicode_cmap_lookup()
            assert look is not None
            for cp in _CODEPOINTS:
                lines.append(f"UGID\t{cp}\t{look.get_glyph_id(cp)}")
    finally:
        ttf.close()
    return "\n".join(lines) + "\n"


def _assert_parity(java: str, py: str) -> None:
    j = java.splitlines()
    p = py.splitlines()
    assert len(j) == len(p), (
        f"line-count mismatch: java={len(j)} py={len(p)}\n"
        f"first java: {j[:3]}\nfirst py:   {p[:3]}"
    )
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(j, p, strict=True))
        if a != b
    ]
    assert not diffs, "cmap subtable-select parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
def test_multi_cmap_selection_and_format4_gap_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """A multi-subtable font's directory order, ``get_subtable`` selection
    across every priority pair, per-subtable ``get_glyph_id`` (incl. format-4
    segment-gap codes -> GID 0), and the priority Unicode resolver pick must
    all match Apache PDFBox 3.0.7's native ``CmapTable`` / ``CmapSubtable``.
    """
    djv = (_TTF_DIR / "DejaVuSans.ttf").read_bytes()
    font_path = tmp_path / "MultiCmap.ttf"
    font_path.write_bytes(_make_multi_cmap_font(djv))
    java = run_probe_text("CmapSubtableSelectProbe", str(font_path))
    py = _py_lines(font_path)
    _assert_parity(java, py)
