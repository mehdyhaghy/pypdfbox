"""Live PDFBox differential parity for the ``vhea`` (vertical header) and
``vmtx`` (vertical metrics) TrueType tables read straight from a TrueType FONT
PROGRAM (FontBox).

Recent waves pinned ``hmtx``, ``glyf``, ``kern``, ``cmap`` (0/4/6/12/14),
``OS/2``, and ``head``/``maxp``. This wave targets the vertical writing-mode
metrics tables: ``VerticalHeaderTable`` (ascender/descender/lineGap,
advanceHeightMax, the caret params, numberOfVMetrics) and
``VerticalMetricsTable`` (per-GID advanceHeight + topSideBearing).

The interesting parity surface is the ``vmtx`` **trailing-TSB compression**: the
table stores ``numberOfVMetrics`` (advanceHeight, topSideBearing) pairs followed
by a TSB-only array for the remaining glyphs (which all share the last advance
height). So ``get_top_side_bearing(gid)`` for ``gid >= numberOfVMetrics`` must
read the trailing TSB array, while ``get_advance_height`` clamps to the last
advance height. The probed GID set straddles ``numberOfVMetrics`` to exercise
both branches.

No bundled font carries vhea/vmtx (they are Latin-only), so we **synthesize** a
deterministic TTF by patching a vhea + vmtx onto LiberationSans-Regular via
fontTools and re-serializing. The vmtx advances are crafted with a long run of
equal trailing advances so fontTools compresses them, producing a genuine
``numberOfVMetrics < numGlyphs`` table that exercises the trailing-TSB path. The
exact same bytes are written to a temp file and fed to BOTH Apache FontBox (the
probe) and pypdfbox, so the comparison is byte-for-byte deterministic.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

_GID_CAP = 256


def _synthesize_vhea_vmtx_ttf() -> bytes:
    """Patch a deterministic vhea + vmtx onto LiberationSans and re-serialize.

    Advances are crafted so a long run of identical trailing advance-heights
    lets fontTools compress the on-disk ``vmtx`` to ``numberOfVMetrics <
    numGlyphs``, producing a real trailing-TSB-only block.
    """
    from fontTools.ttLib import TTFont, newTable  # noqa: PLC0415

    font = TTFont(io.BytesIO(_FIXTURE.read_bytes()))

    vhea = newTable("vhea")
    vhea.tableVersion = 0x00011000  # version 1.1 -> 1.0625 as 16.16 fixed
    vhea.ascent = 880
    vhea.descent = -120
    vhea.lineGap = 200
    vhea.advanceHeightMax = 1100
    vhea.minTopSideBearing = -50
    vhea.minBottomSideBearing = -10
    vhea.yMaxExtent = 900
    vhea.caretSlopeRise = 1
    vhea.caretSlopeRun = 0
    vhea.caretOffset = 3
    vhea.reserved1 = 0
    vhea.reserved2 = 0
    vhea.reserved3 = 0
    vhea.reserved4 = 0
    vhea.metricDataFormat = 0
    vhea.numberOfVMetrics = 0  # recomputed on save
    font["vhea"] = vhea

    glyph_order = font.getGlyphOrder()
    n = len(glyph_order)
    # Distinct advances for the first 2/3 of glyphs; an identical-advance run
    # for the trailing 1/3 so fontTools compresses it into the trailing-TSB
    # block. TSB always varies per glyph so the trailing TSB-only array is
    # meaningful.
    head_count = (2 * n) // 3
    vmtx = newTable("vmtx")
    metrics = {}
    for i, name in enumerate(glyph_order):
        advance = 1000 if i >= head_count else 700 + (i % 17) * 13
        tsb = (i % 11) * 7 - 30
        metrics[name] = (advance, tsb)
    vmtx.metrics = metrics
    font["vmtx"] = vmtx

    font.recalcBBoxes = False
    font.recalcTimestamp = False
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def _py_output(raw: bytes) -> str:
    """Reconstruct VheaVmtxProbe output from pypdfbox (line-for-line)."""
    ttf = TrueTypeFont.from_bytes(raw)
    num_glyphs = ttf.get_number_of_glyphs()
    lines: list[str] = []

    vhea = ttf.get_vertical_header()
    if vhea is None:
        lines.append("vhea\tabsent")
    else:
        lines.append("vhea\tpresent")
        lines.append(f"vhea.version\t{_jfloat(vhea.get_version())}")
        lines.append(f"vhea.ascender\t{vhea.get_ascender()}")
        lines.append(f"vhea.descender\t{vhea.get_descender()}")
        lines.append(f"vhea.lineGap\t{vhea.get_line_gap()}")
        lines.append(f"vhea.advanceHeightMax\t{vhea.get_advance_height_max()}")
        lines.append(f"vhea.minTopSideBearing\t{vhea.get_min_top_side_bearing()}")
        lines.append(f"vhea.minBottomSideBearing\t{vhea.get_min_bottom_side_bearing()}")
        lines.append(f"vhea.yMaxExtent\t{vhea.get_y_max_extent()}")
        lines.append(f"vhea.caretSlopeRise\t{vhea.get_caret_slope_rise()}")
        lines.append(f"vhea.caretSlopeRun\t{vhea.get_caret_slope_run()}")
        lines.append(f"vhea.caretOffset\t{vhea.get_caret_offset()}")
        lines.append(f"vhea.reserved1\t{vhea.get_reserved1()}")
        lines.append(f"vhea.reserved2\t{vhea.get_reserved2()}")
        lines.append(f"vhea.reserved3\t{vhea.get_reserved3()}")
        lines.append(f"vhea.reserved4\t{vhea.get_reserved4()}")
        lines.append(f"vhea.metricDataFormat\t{vhea.get_metric_data_format()}")
        lines.append(f"vhea.numberOfVMetrics\t{vhea.get_number_of_v_metrics()}")

    vmtx = ttf.get_vertical_metrics()
    if vmtx is None:
        lines.append("vmtx\tabsent")
    else:
        lines.append("vmtx\tpresent")
        num_v_metrics = vhea.get_number_of_v_metrics() if vhea is not None else 0
        upper = min(num_glyphs, _GID_CAP)
        for gid in _gids(num_glyphs, num_v_metrics, upper):
            try:
                adv = str(vmtx.get_advance_height(gid))
                tsb = str(vmtx.get_top_side_bearing(gid))
            except Exception:
                adv = "ERR"
                tsb = "ERR"
            lines.append(f"VM\t{gid}\t{adv}\t{tsb}")

    return "\n".join(lines) + "\n"


def _gids(num_glyphs: int, num_v_metrics: int, upper: int) -> list[int]:
    """Mirror VheaVmtxProbe.gids exactly (LinkedHashSet insertion order)."""
    seen: dict[int, None] = {}
    for g in range(upper):
        seen[g] = None
    for b in (num_v_metrics - 1, num_v_metrics, num_v_metrics + 1):
        if 0 <= b < num_glyphs:
            seen[b] = None
    return list(seen.keys())


def _jfloat(value: float) -> str:
    """Render a float the way Java's ``PrintStream.println(float)`` would for
    the small fixed-point versions in scope (e.g. ``1.0625``).
    """
    if value == int(value):
        return f"{value:.1f}"
    return repr(value)


@requires_oracle
def test_vhea_vmtx_matches_pdfbox(tmp_path: Path) -> None:
    """vhea field decode + per-GID vmtx advanceHeight/topSideBearing read from a
    synthesized TrueType ``vhea``/``vmtx`` must match Apache PDFBox 3.0.7,
    including the trailing-TSB-only block for GIDs at/past numberOfVMetrics.
    """
    if not _FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_FIXTURE}")
    raw = _synthesize_vhea_vmtx_ttf()
    font_path = tmp_path / "synth-vhea-vmtx.ttf"
    font_path.write_bytes(raw)

    java = run_probe_text("VheaVmtxProbe", str(font_path)).splitlines()
    py = _py_output(raw).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:5]}\nfirst py:   {py[:5]}"
    )

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "vhea/vmtx parity broken:\n" + "\n".join(diffs[:40])
