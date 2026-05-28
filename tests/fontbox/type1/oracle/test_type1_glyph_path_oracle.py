"""Live Apache FontBox differential parity for the Type 1 charstring
*interpreter* reached at the standalone-program level.

Companion to:

* ``tests/fontbox/type1/oracle/test_type1_font_oracle.py`` — the Type 1
  *model* surface (name, font matrix, encoding, per-glyph widths), and
* ``tests/rendering/oracle/test_type1_glyph_render_oracle.py`` /
  ``test_type1_flex_render_oracle.py`` / ``test_type1_seac_render_oracle.py``
  — the *rasterised* glyph (the full render pipeline).

This file isolates the FontBox Type 1 charstring **interpreter** itself:
``Type1Font.createWithPFB(bytes)`` then ``Type1Font.getPath(glyphName)`` ->
``GeneralPath``. That exercises the ``hsbw`` / ``sbw`` width prologue, the
``rmoveto`` / ``rlineto`` / ``rrcurveto`` / ``closepath`` path operators, the
``seac`` accent composite, and the flex / hint-replacement ``OtherSubrs``
machinery (``callsubr`` into the four standard subroutines) — all driven from a
real ``.pfb`` program rather than through a PDF.

``oracle/probes/Type1GlyphPathProbe.java`` emits, per glyph (ascending name),
a COORDINATE-TOLERANT but STRUCTURALLY-STRICT path fingerprint — the same
strategy ``GlyphPathProbe`` uses for TrueType / CFF:

  * the curve-exact control-point bounding box (Java ``Path2D.getBounds2D``
    evaluates the Bezier extrema, so a cubic whose control point lies outside
    the rendered arc does NOT widen the box),
  * the number of path segments,
  * the segment-type sequence (M/L/C/Z; Type 1 emits only cubics, never Q).

:func:`_pypdfbox_fingerprint` reproduces the same fingerprint from pypdfbox's
``Type1Font.get_path`` command list, with TWO documented representational
normalisations onto the Java ``PathIterator`` sequence (identical to the CFF
glyph-path oracle — these are representation differences, not bugs):

  1. **Trailing moveTo after each close.** Apache FontBox builds the outline
     through ``Type1CharString`` whose ``closeCharString1Path`` appends
     ``GeneralPath.moveTo(currentPoint)`` *after* every ``closePath()`` to prime
     the next sub-path. pypdfbox delegates ``get_path`` to fontTools' charstring
     ``draw``, which omits that no-op trailing moveTo. We re-insert a ``moveto``
     after each ``closepath`` to mirror FontBox.
  2. **Consecutive-moveTo coalescing.** A ``GeneralPath`` collapses two
     back-to-back ``moveTo`` calls into a single ``SEG_MOVETO`` (the second
     overwrites the sub-path origin). So FontBox's "close -> moveTo, then the
     next contour's rmoveto -> moveTo" pair shows up as ONE ``M`` between
     contours, with only the final close's moveTo surviving as a trailing ``M``.

Known divergence (NOT pinned here): the ``CurvedFlexType1.pfb`` ``o`` glyph
carries a deliberately *malformed* flex — the flex-height arg is fed as the
rational ``100 2 div`` (= 50) so the operand count reaching ``0 callothersubr``
is off. Apache FontBox's ``Type1CharString.callOtherSubr`` validates that and
logs ``"Invalid callothersubr parameter: 100"``, then *drops* the two flex
curves; the wrapped fontTools ``T1OutlineExtractor`` is more lenient and keeps
them. The shapes are visually identical (the flex sits on a near-flat counter
edge), so the *render* oracle still matches — only the segment COUNT differs
(Java 4 vs pypdfbox 6). pypdfbox follows fontTools here (library-first rule:
the Type 1 interpreter is wrapped, not reimplemented). ``o`` is excluded from
the structural comparison and asserted separately so the divergence is explicit
and any future change is caught.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.type1.type1_font import Type1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"

# Bundled, permissive Type 1 programs (built by pypdfbox / fontTools t1Lib).
_PFBS = [
    "DemoType1.pfb",       # StandardEncoding boxes: A/B/C/space + .notdef
    "CustomEncType1.pfb",  # custom Encoding vector, same box glyphs
    "SeacType1.pfb",       # boxes + a seac composite (eacute = e + acute)
    "CurvedFlexType1.pfb",  # curved O (4 cubics) + flex o (excluded, see below)
]

# Glyphs whose interpreter output diverges from Apache FontBox for a documented
# reason (see module docstring). Compared separately, not in the strict block.
_DIVERGENT = {"CurvedFlexType1.pfb": {"o"}}


# ---------------------------------------------------------------------------
# Curve-exact bbox helpers (mirror the TTF/CFF glyph-path oracle).
# Java Path2D.getBounds2D evaluates Bezier extrema; a control point outside the
# rendered arc must NOT widen the box, so we solve each cubic's derivative.
# ---------------------------------------------------------------------------
def _cubic_extrema_t(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """Parameters t in (0, 1) where a cubic Bezier's coordinate is extremal."""
    a = -p0 + 3.0 * p1 - 3.0 * p2 + p3
    b = 2.0 * (p0 - 2.0 * p1 + p2)
    c = -p0 + p1
    out: list[float] = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            t = -c / b
            if 0.0 < t < 1.0:
                out.append(t)
        return out
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return out
    root = disc**0.5
    for t in ((-b + root) / (2.0 * a), (-b - root) / (2.0 * a)):
        if 0.0 < t < 1.0:
            out.append(t)
    return out


def _cubic_eval(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    mt = 1.0 - t
    return mt**3 * p0 + 3.0 * mt**2 * t * p1 + 3.0 * mt * t**2 * p2 + t**3 * p3


class _Fingerprint:
    """Mutable (bbox, nseg, type-sequence) accumulator."""

    def __init__(self) -> None:
        self.types: list[str] = []
        self.min_x: float | None = None
        self.min_y: float | None = None
        self.max_x: float | None = None
        self.max_y: float | None = None
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
            return "0 0 0 0 0 "
        assert self.min_x is not None
        assert self.min_y is not None
        assert self.max_x is not None
        assert self.max_y is not None
        return (
            f"{round(self.min_x)} {round(self.min_y)} "
            f"{round(self.max_x)} {round(self.max_y)} "
            f"{nseg} {''.join(self.types)}"
        )


def _pypdfbox_fingerprint(commands: list[tuple[Any, ...]]) -> str:
    """Normalise pypdfbox's ``Type1Font.get_path`` command list to the same
    ``PATH`` payload the Java probe emits (bbox nseg typeSeq)."""
    # Build the FontBox-equivalent op list (trailing moveTo after each close),
    # then coalesce consecutive moveTos the way GeneralPath does.
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
            ops.append(("M", current))  # closeCharString1Path: moveTo(current)

    fp = _Fingerprint()
    for i, (kind, args) in enumerate(ops):
        if kind == "M":
            # GeneralPath keeps only the last of a run of consecutive moveTos.
            if i + 1 < len(ops) and ops[i + 1][0] == "M":
                continue
            fp.move(args[0], args[1])
        elif kind == "L":
            fp.line(args[0], args[1])
        elif kind == "C":
            fp.cubic(*args)
        elif kind == "Z":
            fp.close()
    return fp.as_line()


def _parse_probe(text: str) -> tuple[str, dict[str, str]]:
    """Parse the probe's stdout into (font name, {glyphName: PATH payload})."""
    name = ""
    paths: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("NAME "):
            name = line[len("NAME ") :]
        elif line.startswith("PATH "):
            rest = line[len("PATH ") :]
            glyph, _, payload = rest.partition(" ")
            paths[glyph] = payload
    return name, paths


@requires_oracle
@pytest.mark.parametrize("pfb", _PFBS)
def test_type1_glyph_path_matches_pdfbox(pfb: str) -> None:
    fixture = _FIXTURES / pfb
    java_name, java_paths = _parse_probe(
        run_probe_text("Type1GlyphPathProbe", str(fixture))
    )

    font = Type1Font.create_with_pfb(fixture.read_bytes())
    assert font.get_name() == java_name

    divergent = _DIVERGENT.get(pfb, set())
    names = sorted(font.get_char_strings_dict().keys())
    # The probe walks the same TreeSet of charstring names.
    assert set(names) == set(java_paths.keys())

    for glyph in names:
        py_payload = _pypdfbox_fingerprint(font.get_path(glyph))
        if glyph in divergent:
            # Documented fontTools-leniency divergence (see module docstring):
            # assert it stays exactly as we expect so a regression is visible.
            assert py_payload != java_paths[glyph]
            continue
        assert py_payload == java_paths[glyph], (
            f"{pfb}:{glyph}: pypdfbox {py_payload!r} != FontBox "
            f"{java_paths[glyph]!r}"
        )


@requires_oracle
def test_curved_flex_o_glyph_documented_divergence() -> None:
    """Pin the malformed-flex ``o`` divergence explicitly (see module docstring):
    Apache FontBox drops the invalid flex (4 cubics), pypdfbox via fontTools
    keeps it (6 cubics). The other glyphs in the same program match exactly."""
    fixture = _FIXTURES / "CurvedFlexType1.pfb"
    _, java_paths = _parse_probe(
        run_probe_text("Type1GlyphPathProbe", str(fixture))
    )
    font = Type1Font.create_with_pfb(fixture.read_bytes())

    # FontBox: 4 cubics (MCCCCZM). pypdfbox: 6 cubics.
    assert java_paths["o"].split()[5] == "MCCCCZM"
    py_o = _pypdfbox_fingerprint(font.get_path("o"))
    assert py_o.split()[5] == "MCCCCCCZM"

    # The valid-curve O glyph matches exactly in both.
    py_O = _pypdfbox_fingerprint(font.get_path("O"))
    assert py_O == java_paths["O"]
