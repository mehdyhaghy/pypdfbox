"""Live PDFBox differential parity for glyph OUTLINES (the glyph path) read
straight from the embedded FONT PROGRAM (FontBox), not from any rendered raster.

Companion to ``test_glyph_advance_oracle.py`` (wave 1414, glyph *advance*): this
wave (1415) covers the glyph *path*. The path drives rendering fidelity, so a
divergence here is a real outline bug.

  * TrueType (``PDTrueTypeFont`` / ``PDCIDFontType2``) ->
    ``ttf.get_glyph(gid).get_path()`` (a fontTools ``RecordingPen``).
  * CFF (``PDType1CFont`` / ``PDCIDFontType0``) ->
    ``cff.get_type2_char_string(gid).get_path()`` (a list of draw-command
    tuples ``("moveto"/"lineto"/"curveto"/"closepath", ...)``).

The oracle output is produced by ``oracle/probes/GlyphPathProbe.java``, which
fingerprints Apache PDFBox's ``java.awt.geom.GeneralPath`` from the same
embedded program. The fingerprint is **coordinate-tolerant but
structurally-strict** — see ``GlyphPathProbe``'s class comment:

  * the control-point bounding box (4 ints: minX minY maxX maxY),
  * the number of path segments,
  * the segment-type sequence (M/L/Q/C/Z).

Why a fingerprint and not exact coordinates: AWT's ``GeneralPath`` and the
Python path libraries can differ by sub-unit rounding on control points, and —
more importantly — they use *different but equivalent* representations of the
same TrueType contour. fontTools' ``RecordingPen`` packs a run of N off-curve
TrueType points (with their implied on-curve midpoints) into a *single*
``qCurveTo`` call, whereas Apache PDFBox's ``GlyphRenderer`` emits N separate
``quadTo`` segments (one per off-curve point, materialising the implied
midpoints). Both describe the identical curve. The Python helper below
NORMALISES the fontTools representation down to the same per-quad sequence the
Java ``PathIterator`` yields, so the segment-type sequence and segment count
match exactly.

Bbox: the box is the *tight curve* bounding box. Java ``Path2D.getBounds2D()``
does NOT union the off-curve control points — for quad/cubic segments it
evaluates the actual Bezier arc and bounds that, so a control point lying
outside the rendered curve never widens the box. The Python helper mirrors this
exactly (it solves each segment's coordinate derivative for the in-range
critical parameter and evaluates the curve there). Both sides start from the
same integer font-unit coordinates, so the boxes are normally bit-identical;
we allow an epsilon of **1 font unit** per edge purely to absorb the round-half
difference between ``Math.round`` (Java, half-up) and Python ``round`` (banker's
rounding) at an exact ``.5`` boundary.

Only *embedded* fonts are in scope: a non-embedded font resolves to a
platform/bundled substitute whose outline isn't deterministic across machines
(the probe skips those via ``isEmbedded()``; the Python side mirrors the skip).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Embedded-program coverage — same fixtures as the advance-width oracle so the
# two waves cover the identical embedded TrueType + CFF programs:
#   - embedded Type1C / CFF (Century-Book/Bold) -> CFF charstring -> path
#   - embedded TrueType subsets (Liberation, Calibri, Verdana, Symbol)
#   - Type0 / CIDFontType2 (TrueType) + Type1C simple (Courier)
_FIXTURES_REL = [
    "multipdf/PDFBOX-5811-362972.pdf",  # embedded Type1C CFF (Century)
    "pdmodel/with_outline.pdf",  # embedded TrueType (Liberation subset)
    "multipdf/PDFA3A.pdf",  # embedded TrueType (Calibri subset)
    "multipdf/PDFBOX-4417-054080.pdf",  # CIDFontType2 (Symbol) + Type1C (Courier)
    "text/input/eu-001.pdf",  # embedded TrueType (Verdana/Symbol subsets)
]

# Mirror the Java probe's bounds.
_GID_CAP = 256
_OOB_GIDS = [60000, 65535]

# Per-edge bbox epsilon (font units). See module docstring — inputs are integer
# font-unit coordinates, so boxes are normally bit-identical; this only absorbs
# a Math.round (half-up) vs Python round (half-even) split at an exact .5.
_BBOX_EPS = 1


def _gids(num_glyphs: int) -> list[int]:
    """Leading GIDs ``[0, min(num_glyphs, CAP))`` + synthetic out-of-range GIDs.

    Matches ``GlyphPathProbe.gids`` (de-duplicated, insertion order).
    """
    seen: dict[int, None] = {}
    upper = min(num_glyphs, _GID_CAP) if num_glyphs > 0 else 0
    for g in range(upper):
        seen[g] = None
    for g in _OOB_GIDS:
        seen[g] = None
    return list(seen.keys())


# ---------------------------------------------------------------------------
# Fingerprint helpers — normalise pypdfbox's path representation to the same
# (bbox, nseg, type-sequence) the Java PathIterator yields.
#
# Java ``Path2D.getBounds2D()`` returns TIGHT curve bounds: for quad/cubic
# segments it evaluates the Bezier and unions the actual arc extent, so an
# off-curve control point lying outside the rendered arc does not widen the
# box. The helpers below reproduce that — they return the in-range critical
# parameter(s) where a coordinate's derivative is zero, and evaluate the curve
# there.
# ---------------------------------------------------------------------------


def _quad_extremum_t(p0: float, p1: float, p2: float) -> float | None:
    """Parameter ``t`` in (0, 1) of a quadratic Bezier's coordinate extremum,
    or ``None`` if the extremum is at an endpoint / outside the segment.

    B(t) = (1-t)^2 p0 + 2(1-t)t p1 + t^2 p2; B'(t)=0 at t=(p0-p1)/(p0-2p1+p2).
    """
    denom = p0 - 2.0 * p1 + p2
    if denom == 0:
        return None
    t = (p0 - p1) / denom
    return t if 0.0 < t < 1.0 else None


def _quad_eval(p0: float, p1: float, p2: float, t: float) -> float:
    mt = 1.0 - t
    return mt * mt * p0 + 2.0 * mt * t * p1 + t * t * p2


def _cubic_extrema_t(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """Parameters ``t`` in (0, 1) of a cubic Bezier coordinate's extrema.

    B'(t) is a quadratic ``a t^2 + b t + c``; return its in-range roots.
    """
    a = -p0 + 3.0 * p1 - 3.0 * p2 + p3
    b = 2.0 * (p0 - 2.0 * p1 + p2)
    c = p1 - p0
    roots: list[float] = []
    if a == 0:
        if b != 0:
            roots.append(-c / b)
    else:
        disc = b * b - 4.0 * a * c
        if disc >= 0:
            sq = disc**0.5
            roots.append((-b + sq) / (2.0 * a))
            roots.append((-b - sq) / (2.0 * a))
    return [t for t in roots if 0.0 < t < 1.0]


def _cubic_eval(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    mt = 1.0 - t
    return mt**3 * p0 + 3.0 * mt**2 * t * p1 + 3.0 * mt * t**2 * p2 + t**3 * p3


class _Fingerprint:
    """Mutable accumulator for a glyph-path fingerprint."""

    def __init__(self) -> None:
        self.types: list[str] = []
        self.min_x: float | None = None
        self.min_y: float | None = None
        self.max_x: float | None = None
        self.max_y: float | None = None
        # Track current / sub-path-start so curve segments can compute TIGHT
        # bounds. Java ``Path2D.getBounds2D()`` returns the bounds of the actual
        # curve (it evaluates the Bezier extrema), NOT the loose control-point
        # union — so a quad/cubic whose control point lies outside the rendered
        # arc does not widen the box. We must mirror that to compare bbox.
        self._cur: tuple[float, float] | None = None
        self._start: tuple[float, float] | None = None

    def _point(self, x: float, y: float) -> None:
        if self.min_x is None:
            self.min_x = self.max_x = x
            self.min_y = self.max_y = y
            return
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)

    def move(self, x: float, y: float) -> None:
        self.types.append("M")
        self._point(x, y)
        self._cur = (x, y)
        self._start = (x, y)

    def line(self, x: float, y: float) -> None:
        self.types.append("L")
        self._point(x, y)
        self._cur = (x, y)

    def quad(self, cx: float, cy: float, x: float, y: float) -> None:
        self.types.append("Q")
        p0 = self._cur if self._cur is not None else (x, y)
        # Endpoint always counts; the control point only counts at the curve's
        # critical parameter if that falls inside (0, 1).
        self._point(x, y)
        for axis in (0, 1):
            t = _quad_extremum_t(p0[axis], cx if axis == 0 else cy, x if axis == 0 else y)
            if t is not None:
                ex = _quad_eval(p0[0], cx, x, t)
                ey = _quad_eval(p0[1], cy, y, t)
                self._point(ex, ey)
        self._cur = (x, y)

    def cubic(
        self, c1x: float, c1y: float, c2x: float, c2y: float, x: float, y: float
    ) -> None:
        self.types.append("C")
        p0 = self._cur if self._cur is not None else (x, y)
        self._point(x, y)
        for axis in (0, 1):
            a0 = p0[axis]
            a1 = (c1x, c1y)[axis]
            a2 = (c2x, c2y)[axis]
            a3 = (x, y)[axis]
            for t in _cubic_extrema_t(a0, a1, a2, a3):
                ex = _cubic_eval(p0[0], c1x, c2x, x, t)
                ey = _cubic_eval(p0[1], c1y, c2y, y, t)
                self._point(ex, ey)
        self._cur = (x, y)

    def close(self) -> None:
        self.types.append("Z")
        if self._start is not None:
            self._cur = self._start

    def as_line(self) -> str:
        nseg = len(self.types)
        if nseg == 0:
            return "0\t0\t0\t0\t0\t"
        assert self.min_x is not None
        assert self.min_y is not None
        assert self.max_x is not None
        assert self.max_y is not None
        return (
            f"{round(self.min_x)}\t{round(self.min_y)}\t"
            f"{round(self.max_x)}\t{round(self.max_y)}\t"
            f"{nseg}\t{''.join(self.types)}"
        )


def _ttf_fingerprint(pen: Any) -> _Fingerprint:
    """Fingerprint a TrueType glyph path produced by pypdfbox's own ported
    ``GlyphRenderer`` (``pypdfbox.fontbox.ttf.glyph_renderer``).

    We deliberately drive the fingerprint through pypdfbox's *ported* renderer
    rather than fontTools' built-in ``Glyph.draw`` pen. Both describe the same
    outline, but they use different — equivalent — representations:

      * fontTools' ``RecordingPen`` packs a run of N off-curve TrueType points
        (with their implied on-curve midpoints) into a *single* ``qCurveTo``;
      * Apache PDFBox's ``GlyphRenderer`` emits one ``quadTo`` per off-curve
        point, materialising each implied midpoint, and closes an on-curve-start
        contour with an explicit ``lineTo`` back to the start.

    pypdfbox's ``GlyphRenderer`` is a faithful line-by-line port of PDFBox's
    Java renderer, so its emitted op stream is already one segment per quad and
    matches the Java ``PathIterator`` exactly — no normalisation needed. This
    also means the test exercises the *real* glyph-path code on our surface
    (``glyph_renderer.py``), which is the point of the wave: a bug there shows
    up here as a divergence. Each ``qCurveTo`` from this renderer carries
    exactly one control point + one endpoint = one Q segment.
    """
    fp = _Fingerprint()
    for op, args in pen.value:
        if op == "moveTo":
            fp.move(float(args[0][0]), float(args[0][1]))
        elif op == "lineTo":
            fp.line(float(args[0][0]), float(args[0][1]))
        elif op == "qCurveTo":
            # The ported renderer always emits a single-control-point quad.
            ctrl, end = args[0], args[1]
            fp.quad(float(ctrl[0]), float(ctrl[1]), float(end[0]), float(end[1]))
        elif op == "curveTo":
            # Cubic — not produced by the TrueType renderer, but handle for
            # completeness so an unexpected cubic doesn't silently vanish.
            pts = [(float(p[0]), float(p[1])) for p in args]
            for i in range(0, len(pts) - 2, 3):
                fp.cubic(*pts[i], *pts[i + 1], *pts[i + 2])
        elif op == "closePath":
            fp.close()
    return fp


def _cff_fingerprint(commands: list[tuple[Any, ...]]) -> _Fingerprint:
    """Normalise pypdfbox's CFF draw-command list to the path fingerprint.

    The command list uses ``("moveto", x, y)`` / ``("lineto", x, y)`` /
    ``("curveto", x1, y1, x2, y2, x3, y3)`` / ``("closepath",)``.

    Two representational adjustments bring it onto the Java ``PathIterator``
    sequence (DOCUMENTED divergences, not bugs — see module docstring):

      1. **Trailing moveTo after each close.** Apache PDFBox builds the CFF
         outline through ``Type1CharString`` whose ``closeCharString1Path``
         appends ``GeneralPath.moveTo(currentPoint)`` *after* every
         ``closePath()`` (to prime the next sub-path). pypdfbox's
         ``Type2CharString.get_path()`` delegates to fontTools' charstring
         ``draw``, which omits that no-op trailing moveTo. We re-insert a
         ``moveto`` after each ``closepath`` to mirror PDFBox.
      2. **Consecutive-moveTo coalescing.** A ``GeneralPath`` collapses two
         back-to-back ``moveTo`` calls into a single ``SEG_MOVETO`` (the second
         overwrites the first sub-path origin). So PDFBox's
         "close -> moveTo, then next contour's rmoveto -> moveTo" pair shows up
         as ONE ``M`` between contours, with only the final close's moveTo
         surviving as a trailing ``M``. We coalesce the same way.

    The reconstructed-moveTo coordinate is the current point at the close, which
    PDFBox also uses; since the next op (if any) is itself a moveTo that
    overwrites it, the only surviving reconstructed moveTo is the trailing one,
    whose coordinate equals the last drawn point — already inside the bbox, so
    it never widens it.
    """
    # Build the PDFBox-equivalent op list, then coalesce consecutive moveTos.
    ops: list[tuple[str, tuple[float, ...]]] = []
    current: tuple[float, float] = (0.0, 0.0)
    for cmd in commands:
        tag = cmd[0]
        if tag == "moveto":
            current = (float(cmd[1]), float(cmd[2]))
            ops.append(("M", current))
        elif tag == "lineto":
            current = (float(cmd[1]), float(cmd[2]))
            ops.append(("L", current))
        elif tag == "curveto":
            ops.append(
                (
                    "C",
                    (
                        float(cmd[1]),
                        float(cmd[2]),
                        float(cmd[3]),
                        float(cmd[4]),
                        float(cmd[5]),
                        float(cmd[6]),
                    ),
                )
            )
            current = (float(cmd[5]), float(cmd[6]))
        elif tag == "closepath":
            ops.append(("Z", ()))
            # PDFBox's closeCharString1Path: moveTo(current) after the close.
            ops.append(("M", current))

    fp = _Fingerprint()
    for i, (kind, args) in enumerate(ops):
        if kind == "M":
            # Coalesce with an immediately following moveTo (GeneralPath keeps
            # only the last of a run of consecutive moveTos).
            if i + 1 < len(ops) and ops[i + 1][0] == "M":
                continue
            fp.move(args[0], args[1])
        elif kind == "L":
            fp.line(args[0], args[1])
        elif kind == "C":
            fp.cubic(*args)
        elif kind == "Z":
            fp.close()
    return fp


# ---------------------------------------------------------------------------
# Emit a probe-shaped line block from pypdfbox.
# ---------------------------------------------------------------------------


def _emit_ttf(lines: list[str], page_index: int, key: str, base_font: str, ttf: Any) -> None:
    if ttf is None:
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(null-ttf)\t{base_font}")
        return
    num_glyphs = ttf.get_number_of_glyphs()
    lines.append(f"FONT\t{page_index}\t{key}\tTTF\t{base_font}")
    for gid in _gids(num_glyphs):
        try:
            glyph = ttf.get_glyph(gid)
            if glyph is None:
                fp = _Fingerprint()
            else:
                # Drive pypdfbox's *ported* GlyphRenderer (our surface) so the
                # op stream is one-segment-per-quad, matching Java exactly.
                pen = GlyphRenderer(glyph.get_description()).get_path()
                fp = _ttf_fingerprint(pen)
            lines.append(f"PATH\t{gid}\t{fp.as_line()}")
        except Exception:
            lines.append(f"PATH\t{gid}\tERR\tERR\tERR\tERR\tERR\tERR")


def _emit_cff(lines: list[str], page_index: int, key: str, base_font: str, cff: Any) -> None:
    if cff is None:
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(null-cff)\t{base_font}")
        return
    num_glyphs = cff.get_num_char_strings()
    name = cff.get_name()
    lines.append(f"FONT\t{page_index}\t{key}\tCFF\t{name}")
    for gid in _gids(num_glyphs):
        try:
            cs = cff.get_type2_char_string(gid)
            fp = _Fingerprint() if cs is None else _cff_fingerprint(cs.get_path())
            lines.append(f"PATH\t{gid}\t{fp.as_line()}")
        except Exception:
            lines.append(f"PATH\t{gid}\tERR\tERR\tERR\tERR\tERR\tERR")


def _emit_font(lines: list[str], page_index: int, key: str, font: object) -> None:
    if isinstance(font, PDTrueTypeFont):
        ttf = font.get_true_type_font()
        _emit_ttf(lines, page_index, key, str(font.get_name()), ttf)
        return
    if isinstance(font, PDType1CFont):
        cff = font.get_cff_type1_font()
        _emit_cff(lines, page_index, key, str(font.get_name()), cff)
        return
    if isinstance(font, PDType0Font):
        descendant = font.get_descendant_font()
        if isinstance(descendant, PDCIDFontType2):
            ttf = descendant.get_true_type_font()
            _emit_ttf(lines, page_index, key, str(font.get_name()), ttf)
            return
        if isinstance(descendant, PDCIDFontType0):
            cff = descendant.get_cff_font()
            _emit_cff(lines, page_index, key, str(font.get_name()), cff)
            return
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(no-descendant)\t{font.get_name()}")
        return
    lines.append(f"FONT\t{page_index}\t{key}\tSKIP(not-program-font)\t{font.get_name()}")


def _py_glyph_path(pdf_path: Path) -> str:
    """Reconstruct GlyphPathProbe output from pypdfbox (line-for-line)."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                key = name.name if hasattr(name, "name") else str(name)
                try:
                    font = res.get_font(name)
                except Exception:
                    continue
                if font is None:
                    continue
                try:
                    embedded = font.is_embedded()
                except Exception:
                    embedded = False
                if not embedded:
                    continue
                _emit_font(lines, page_index, key, font)
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


# ---------------------------------------------------------------------------
# Differential comparison.
# ---------------------------------------------------------------------------


def _parse_path_line(line: str) -> tuple[str, tuple[int, int, int, int] | None, str, str]:
    """Split a ``PATH`` line into (gid, bbox-or-None, nseg, typeseq).

    Returns bbox=None for the ERR sentinel.
    """
    parts = line.split("\t")
    # PATH \t gid \t minX \t minY \t maxX \t maxY \t nseg \t typeSeq
    gid = parts[1]
    if parts[2] == "ERR":
        return gid, None, "ERR", "ERR"
    bbox = (int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5]))
    nseg = parts[6]
    typeseq = parts[7] if len(parts) > 7 else ""
    return gid, bbox, nseg, typeseq


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_glyph_path_matches_pdfbox(fixture_rel: str) -> None:
    """Per-GID glyph-path fingerprint (control-point bbox + segment count +
    M/L/Q/C/Z type sequence) read from the embedded program must match Apache
    PDFBox 3.0.7 across embedded TrueType and CFF fonts.

    Segment count and type sequence must match exactly (after normalising
    fontTools' packed ``qCurveTo`` to PDFBox's per-quad emission). The bbox may
    differ by at most ``_BBOX_EPS`` per edge (rounding only — see module
    docstring).
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("GlyphPathProbe", str(pdf_path)).splitlines()
    py = _py_glyph_path(pdf_path).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch for {fixture_rel}: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )

    diffs: list[str] = []
    for i, (j, p) in enumerate(zip(java, py, strict=True)):
        if j.startswith("FONT"):
            if j != p:
                diffs.append(f"  line {i} (FONT): java={j!r} py={p!r}")
            continue
        # PATH line — structurally strict, bbox tolerant.
        jg, jb, jn, jt = _parse_path_line(j)
        pg, pb, pn, pt = _parse_path_line(p)
        if jg != pg or jn != pn or jt != pt:
            diffs.append(f"  line {i} (PATH gid={jg}): java={j!r} py={p!r}")
            continue
        if jb is None or pb is None:
            if jb is not pb:
                diffs.append(f"  line {i} (PATH gid={jg}): java={j!r} py={p!r}")
            continue
        if any(abs(a - b) > _BBOX_EPS for a, b in zip(jb, pb, strict=True)):
            diffs.append(
                f"  line {i} (PATH gid={jg}) bbox>{_BBOX_EPS}: java={jb} py={pb}"
            )

    assert not diffs, (
        f"glyph-path parity broken for {fixture_rel}:\n" + "\n".join(diffs[:40])
    )
