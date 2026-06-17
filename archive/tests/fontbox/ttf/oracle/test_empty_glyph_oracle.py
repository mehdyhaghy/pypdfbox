"""Live PDFBox differential parity for the ``glyf`` EMPTY / ZERO-CONTOUR glyph.

A whitespace glyph (e.g. ``space``) carries ``numberOfContours == 0`` and a
ZERO-LENGTH ``loca`` entry (``loca[gid] == loca[gid+1]``, i.e. no glyf bytes at
all). FontBox must still return a non-``None`` :class:`GlyphData` for such a GID
-- see PDFBOX-5135, where composite-glyph resolution could not tolerate a
``None`` here -- with an EMPTY outline (no path segments), a degenerate
``(0, 0, 0, 0)`` bounding box, a resolved contour count of 0, a point count of
0, and the glyph's real ADVANCE WIDTH from ``hmtx``. It must NOT throw.

This is the surface ``oracle/probes/EmptyGlyphProbe.java`` fingerprints: it
loads a RAW bundled TrueType font directly through ``TTFParser`` (not via a
PDF) and, for a curated set of empty GIDs, emits -- from
``ttf.getGlyph().getGlyph(gid)``:

  * the resolved contour count + total point count;
  * the advance width (``ttf.getAdvanceWidth(gid)``);
  * the glyph bbox (degenerate ``0 0 0 0`` for empties);
  * the path fingerprint (segment count + M/L/Q/C/Z type sequence) of
    ``gd.getPath()`` -- empty for a no-outline glyph;
  * a ``NULL`` / ``OK`` flag for whether ``getGlyph(gid)`` returned ``None``.

Everything is integer / exact, so this is an EXACT-match parity test (no
epsilon).

The fixture is the permissively-licensed bundled ``DejaVuSans.ttf`` (Bitstream
Vera / public-domain-equivalent). Its GIDs 1 (``.null``), 2
(``nonmarkingreturn``), 3 (``space``) and 98 (``nonbreakingspace``) are all
zero-contour, zero-length-``loca`` whitespace glyphs. GID 0 (``.notdef``) is a
real outline, included as a contrast control so the test would notice if empty
detection wrongly swallowed a real glyph.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer
from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FONT = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# Curated GIDs in DejaVuSans:
#   - 1 .null / 2 nonmarkingreturn / 3 space / 98 nonbreakingspace: zero-contour
#     + zero-length-loca whitespace glyphs (the empty-glyph surface).
#   - 0 .notdef: a real outline, included as a contrast control.
_GIDS = [1, 2, 3, 98, 0]


def _fingerprint(pen: object) -> str:
    """Reproduce the Java ``GeneralPath`` PathIterator fingerprint: "nseg\ttypeSeq".

    pypdfbox's ported :class:`GlyphRenderer` emits one segment per quad, exactly
    matching the Java ``PathIterator`` op stream. For an empty glyph the pen has
    no ops, so this is ``"0\t"``.
    """
    types: list[str] = []
    for op, _args in pen.value:  # type: ignore[attr-defined]
        if op == "moveTo":
            types.append("M")
        elif op == "lineTo":
            types.append("L")
        elif op == "qCurveTo":
            types.append("Q")
        elif op == "curveTo":
            types.append("C")
        elif op == "closePath":
            types.append("Z")
    return f"{len(types)}\t{''.join(types)}"


def _py_lines(font_path: Path, gids: list[int]) -> list[str]:
    """Reconstruct ``EmptyGlyphProbe`` output from pypdfbox, line-for-line."""
    ttf = TTFParser().parse(font_path)
    try:
        glyf = ttf.get_glyph_table()
        assert glyf is not None
        lines: list[str] = []
        for gid in gids:
            advance_width = ttf.get_advance_width(gid)
            gd = glyf.get_glyph(gid)
            if gd is None:
                lines.append(f"GLYPH\t{gid}\tNULL\tNULL\t{advance_width}\tNULL\t0\t\tNULL")
                continue
            desc = gd.get_description()
            desc.resolve()
            contours = desc.get_contour_count()
            points = desc.get_point_count()
            bbox = gd.get_bounding_box()
            pen = GlyphRenderer(desc).get_path()
            lines.append(
                f"GLYPH\t{gid}\t{contours}\t{points}\t{advance_width}\t"
                f"{int(bbox.get_lower_left_x())} {int(bbox.get_lower_left_y())} "
                f"{int(bbox.get_upper_right_x())} {int(bbox.get_upper_right_y())}\t"
                f"{_fingerprint(pen)}\tOK"
            )
        return lines
    finally:
        ttf.close()


@requires_oracle
def test_empty_glyph_outline_matches_pdfbox() -> None:
    """An empty / zero-contour whitespace glyph (``space`` et al., with a
    zero-length ``loca`` entry) read from the bundled DejaVuSans must match
    Apache PDFBox 3.0.7 exactly: a non-null GlyphData with 0 contours, 0 points,
    a degenerate ``0 0 0 0`` bbox, an empty path, and the glyph's real advance
    width -- and it must NOT throw. A real outline (``.notdef``) is included as a
    contrast control.

    Every emitted field is an integer / exact string, so the match is exact (no
    tolerance).
    """
    gid_arg = ",".join(str(g) for g in _GIDS)
    java = run_probe_text("EmptyGlyphProbe", str(_FONT), gid_arg).splitlines()
    py = _py_lines(_FONT, _GIDS)

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:4]}\nfirst py:   {py[:4]}"
    )

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "empty-glyph parity broken:\n" + "\n".join(diffs[:40])
