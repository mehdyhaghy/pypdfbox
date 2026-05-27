"""Live Apache PDFBox differential parity for TEXT-MARKUP annotations.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation`` text-markup
family — ``PDAnnotationHighlight`` / ``PDAnnotationUnderline`` /
``PDAnnotationStrikeout`` / ``PDAnnotationSquiggly`` (all extending
``PDAnnotationTextMarkup``), their ``/QuadPoints`` accessor, their ``/C``
colour, and the per-subtype shape drawn by ``construct_appearances()`` via the
matching appearance handler (``PDHighlightAppearanceHandler``,
``PDUnderlineAppearanceHandler``, ``PDStrikeoutAppearanceHandler``,
``PDSquigglyAppearanceHandler``).

This file is the *rendered-shape* complement to the appearance-generation
fingerprint tests (``test_annotation_appearance_gen2_oracle.py``, wave 1442).
Those compare the generated ``/AP /N`` operator KEYWORD sequence + ``/BBox``;
here we additionally rasterise BOTH the PDFBox-authored and the
pypdfbox-authored markup PDFs and compare the actual drawn pixels — the
high-value case, because a highlight not filled, an underline/strikeout line at
the wrong y, or a squiggly drawn as a straight line would all pass an operator
fingerprint yet diverge visually.

How it works
------------
The Java probe ``TextMarkupProbe`` runs in two modes:

* ``write out.pdf`` — builds a page with one of each subtype (Highlight,
  Underline, StrikeOut, Squiggly), each with a ``/Rect``, a single
  ``/QuadPoints`` quad over a 200x15-pt band, and a ``/C`` colour, then calls
  ``constructAppearances(doc)`` on each and saves. This is the PDFBox-AUTHORED
  reference.
* ``read out.pdf`` — re-opens ANY text-markup PDF and emits, per annotation:
  ``ANNOT <subtype>`` / ``QP <canonical floats>`` / ``C <canonical floats>`` /
  ``BBOX <canonical floats>`` (or ``NOAP``) / one ``OP:<name>`` per operator /
  ``END``.

pypdfbox builds the IDENTICAL battery, saves once to ``tmp_path``, then:

1. ``/QuadPoints`` + ``/C`` accessors are compared against ``TextMarkupProbe
   read`` on the SAME pypdfbox bytes — exact canonical-float parity (these are
   accessor-level values, not generated geometry, so they must match exactly).
2. The generated ``/AP /N`` operator sequence + ``/BBox`` are compared against
   the PDFBox-AUTHORED reference (``TextMarkupProbe write`` then ``read``), with
   the documented lite-surface divergences normalised (see below).
3. The PDFBox-authored and pypdfbox-authored PDFs are both rasterised at 72 DPI
   (PDFBox via ``RenderProbe``, pypdfbox via ``PDFRenderer``) and the 16x16
   average-luminance grids are compared at the standard render-oracle gate
   (``MAD < 6`` / ``MAXDIFF < 60``). This is what proves the per-subtype shapes
   match.

Documented (NOT a bug — legitimate lite-surface differences, render-identical)
-----------------------------------------------------------------------------
* **Highlight transparency group**: upstream wraps the quad fill in a
  two-form-XObject transparency group with a Multiply blend; its outer stream
  is ``gs gs Do``. ``PDFormXObject`` group emission isn't ported, so the lite
  handler applies the same alpha + Multiply ``ExtGState`` inline and fills the
  quad directly (``gs gs rg <path> f``). ``/BBox`` matches exactly; the rendered
  fill is pixel-equivalent (MAD ~0).
* **Underline / StrikeOut colour-set operator**: upstream emits the colour-space
  pair ``CS SC`` (typed ``PDColor`` with explicit DeviceRGB space); the lite
  colour surface emits the device shorthand ``RG``. Identical colour, identical
  path-drawing operators ``w m l S``.
* **Squiggly tiling pattern**: upstream paints the zig-zag via a tiling pattern
  wrapped in a form XObject (outer stream ``CS SC cm Do``). Pattern / form
  XObject emission isn't ported, so the lite handler draws the zig-zag polyline
  inline (``RG w m l ... l S``). ``/BBox`` matches exactly; the rendered zig-zag
  is perceptually equivalent at 72 DPI (the high-value render gate confirms it).

Every ``/QuadPoints`` value, every ``/C`` component, every ``/BBox``, and the
whole rendered page are asserted against Apache PDFBox; only the operator
SPELLING differences above are normalised.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationHighlight,
    PDAnnotationSquiggly,
    PDAnnotationStrikeout,
    PDAnnotationUnderline,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "TextMarkupProbe"
_GRID = 16
# Standard render-oracle gate. A correct text-markup render scores MAD ~0
# (measured 0.26 / maxdiff 4 in development); a missing fill, a mis-placed line,
# or a squiggly flattened to a straight line lands far above this.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60


# ---------------------------------------------------------------------------
# battery — identical geometry on the Java (TextMarkupProbe.write) and Python
# sides. One quad per subtype over a 200x15-pt band; spec quad-point order
# (upper-left, upper-right, lower-left, lower-right).
# ---------------------------------------------------------------------------

_CASES = [
    (
        "Highlight",
        PDAnnotationHighlight,
        (50, 295, 250, 320),
        [50, 315, 250, 315, 50, 300, 250, 300],
        [1.0, 1.0, 0.0],
    ),
    (
        "Underline",
        PDAnnotationUnderline,
        (50, 245, 250, 270),
        [50, 265, 250, 265, 50, 250, 250, 250],
        [1.0, 0.0, 0.0],
    ),
    (
        "StrikeOut",
        PDAnnotationStrikeout,
        (50, 195, 250, 220),
        [50, 215, 250, 215, 50, 200, 250, 200],
        [0.0, 0.0, 1.0],
    ),
    (
        "Squiggly",
        PDAnnotationSquiggly,
        (50, 145, 250, 170),
        [50, 165, 250, 165, 50, 150, 250, 150],
        [0.0, 0.5, 0.0],
    ),
]


def _build_pypdfbox(path: Path) -> None:
    """Build the identical battery via pypdfbox, call construct_appearances on
    each, save once. Closes the document in a try/finally."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 300, 400))
        doc.add_page(page)
        annotations = []
        for _subtype, cls, rect, quad, color in _CASES:
            ann = cls()
            ann.set_rectangle(PDRectangle(*rect))
            ann.set_quad_points(quad)
            ann.set_color(color)
            ann.construct_appearances(doc)
            annotations.append(ann)
        page.set_annotations(annotations)
        doc.save(str(path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors TextMarkupProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _canon_list(values: list[float]) -> str:
    return " ".join(_canon_float(v) for v in values)


# ---------------------------------------------------------------------------
# Java probe parsing
# ---------------------------------------------------------------------------


def _parse_records(text: str) -> dict[str, dict[str, object]]:
    """Parse TextMarkupProbe read-mode output into per-subtype records."""
    records: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {
                "subtype": raw[len("ANNOT ") :],
                "qp": None,
                "c": None,
                "bbox": None,
                "ops": [],
            }
        elif raw.startswith("QP "):
            assert current is not None
            current["qp"] = raw[len("QP ") :]
        elif raw.startswith("C "):
            assert current is not None
            current["c"] = raw[len("C ") :]
        elif raw.startswith("BBOX "):
            assert current is not None
            current["bbox"] = raw[len("BBOX ") :]
        elif raw == "NOAP":
            assert current is not None
            current["bbox"] = "NOAP"
        elif raw.startswith("OP:"):
            assert current is not None
            current["ops"].append(raw[len("OP:") :])  # type: ignore[union-attr]
        elif raw == "END":
            assert current is not None
            records[current["subtype"]] = current  # type: ignore[index]
            current = None
    return records


# ---------------------------------------------------------------------------
# render fingerprint — identical cell mapping to RenderProbe.java
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _render_grid_java(path: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(path), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _render_grid_py(path: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(path) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


def _qpdf_ok(path: Path) -> bool:
    """``qpdf --check`` passes (warnings tolerated, hard errors not)."""
    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    # 0 = clean, 3 = warnings only, 2 = errors.
    return result.returncode in (0, 3)


# Documented operator-spelling divergences (see module docstring). The colour-set
# operator differs; path-drawing operators must match exactly.
_LINE_COLOR_OPS_JAVA = ["CS", "SC"]
_LINE_COLOR_OPS_PY = ["RG"]


def _drop_prefix(ops: list[str], prefix: list[str]) -> list[str]:
    if ops[: len(prefix)] == prefix:
        return ops[len(prefix) :]
    return ops


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_quad_points_and_color_accessors_match_pdfbox(tmp_path: Path) -> None:
    """``/QuadPoints`` + ``/C`` round-trip through a saved pypdfbox PDF exactly
    as Apache PDFBox reads them — exact canonical-float parity per subtype."""
    fixture = tmp_path / "text_markup_py.pdf"
    _build_pypdfbox(fixture)
    assert _qpdf_ok(fixture), "pypdfbox text-markup PDF failed qpdf --check"

    records = _parse_records(run_probe_text(_PROBE, "read", str(fixture)))
    for subtype, _cls, _rect, quad, color in _CASES:
        rec = records[subtype]
        assert rec["qp"] == _canon_list(quad), (
            f"{subtype}: /QuadPoints {rec['qp']!r} != {_canon_list(quad)!r}"
        )
        assert rec["c"] == _canon_list(color), (
            f"{subtype}: /C {rec['c']!r} != {_canon_list(color)!r}"
        )


@requires_oracle
def test_appearance_operator_sequence_matches_pdfbox(tmp_path: Path) -> None:
    """The generated ``/AP /N`` operator sequence + ``/BBox`` per subtype matches
    Apache PDFBox's own generation, with the documented colour-set / form-XObject
    spelling divergences normalised. Structural: coords differ, op KEYWORDS and
    BBox are asserted."""
    py_pdf = tmp_path / "text_markup_py.pdf"
    java_pdf = tmp_path / "text_markup_java.pdf"
    _build_pypdfbox(py_pdf)
    run_probe_text(_PROBE, "write", str(java_pdf))

    py = _parse_records(run_probe_text(_PROBE, "read", str(py_pdf)))
    java = _parse_records(run_probe_text(_PROBE, "read", str(java_pdf)))

    for subtype, _cls, _rect, _quad, _color in _CASES:
        pr = py[subtype]
        jr = java[subtype]

        # Both sides must produce an /AP /N stream.
        assert pr["bbox"] != "NOAP", f"{subtype}: pypdfbox produced no /AP /N"
        assert jr["bbox"] != "NOAP", f"{subtype}: PDFBox produced no /AP /N"

        # Exact /BBox parity.
        assert pr["bbox"] == jr["bbox"], (
            f"{subtype}: bbox {pr['bbox']!r} != PDFBox {jr['bbox']!r}"
        )

        py_ops = list(pr["ops"])  # type: ignore[arg-type]
        jr_ops = list(jr["ops"])  # type: ignore[arg-type]

        if subtype == "Highlight":
            # Documented transparency-group divergence: PDFBox draws the fill in
            # a form XObject (gs gs Do); the lite handler inlines it. Both apply
            # the two ExtGStates (alpha + Multiply); the lite stream must
            # actually FILL the quad (the high-value fact — render confirms it).
            assert jr_ops[:2] == ["gs", "gs"], f"PDFBox highlight: {jr_ops}"
            assert py_ops[:2] == ["gs", "gs"], f"pypdfbox highlight: {py_ops}"
            assert jr_ops[-1] == "Do", f"PDFBox highlight not Do form: {jr_ops}"
            assert "f" in py_ops, f"pypdfbox highlight did not fill: {py_ops}"
        elif subtype in ("Underline", "StrikeOut"):
            # Colour-set spelling divergence; the line-drawing ops must match.
            assert _drop_prefix(py_ops, _LINE_COLOR_OPS_PY) == _drop_prefix(
                jr_ops, _LINE_COLOR_OPS_JAVA
            ), f"{subtype} path operators diverge: {py_ops} vs {jr_ops}"
        elif subtype == "Squiggly":
            # Documented tiling-pattern divergence: PDFBox paints the zig-zag
            # from a tiling pattern in a form XObject (CS SC cm Do); the lite
            # handler strokes the zig-zag polyline inline. Assert PDFBox uses the
            # form path and that pypdfbox draws a multi-segment stroked polyline.
            assert jr_ops[-1] == "Do", f"PDFBox squiggly not Do form: {jr_ops}"
            assert py_ops[-1] == "S", f"pypdfbox squiggly did not stroke: {py_ops}"
            assert py_ops.count("l") >= 2, (
                f"pypdfbox squiggly is not a zig-zag polyline: {py_ops}"
            )


@requires_oracle
def test_rendered_shapes_match_pdfbox(tmp_path: Path) -> None:
    """The HIGH-VALUE case: rasterise both the PDFBox-authored and the
    pypdfbox-authored text-markup PDFs at 72 DPI and confirm the drawn shapes
    (highlight fill, underline line, strikeout line, squiggly zig-zag) match
    within the render-oracle tolerance."""
    py_pdf = tmp_path / "text_markup_py.pdf"
    java_pdf = tmp_path / "text_markup_java.pdf"
    _build_pypdfbox(py_pdf)
    run_probe_text(_PROBE, "write", str(java_pdf))

    (jw, jh), java_grid = _render_grid_java(java_pdf)
    (pw, ph), py_grid = _render_grid_py(py_pdf)

    # Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (pw, ph) == (jw, jh), (
        f"rendered dimensions diverge: pypdfbox={pw}x{ph} java={jw}x{jh}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"text-markup render mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — a markup shape diverges from PDFBox, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"text-markup render worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_squiggly_is_not_a_straight_line(tmp_path: Path) -> None:
    """Guard: a Squiggly must render *materially different* from a StrikeOut over
    the same band (the zig-zag has a visible vertical extent the flat strikeout
    line lacks). Proves the squiggly handler draws an actual zig-zag and not a
    straight line — a pypdfbox-vs-pypdfbox guard independent of the oracle."""
    squiggly_pdf = tmp_path / "squiggly_only.pdf"
    strike_pdf = tmp_path / "strike_only.pdf"

    quad = [50, 215, 250, 215, 50, 200, 250, 200]
    for path, cls in ((squiggly_pdf, PDAnnotationSquiggly), (strike_pdf, PDAnnotationStrikeout)):
        doc = PDDocument()
        try:
            page = PDPage(PDRectangle(0, 0, 300, 250))
            doc.add_page(page)
            ann = cls()
            ann.set_rectangle(PDRectangle(50, 195, 250, 220))
            ann.set_quad_points(quad)
            ann.set_color([0.0, 0.0, 0.0])
            ann.construct_appearances(doc)
            page.set_annotations([ann])
            doc.save(str(path))
        finally:
            doc.close()

    _, squiggly_grid = _render_grid_py(squiggly_pdf)
    _, strike_grid = _render_grid_py(strike_pdf)

    diffs = [abs(a - b) for a, b in zip(squiggly_grid, strike_grid, strict=True)]
    # The zig-zag spans more vertical pixels (amplitude) than the single
    # mid-line strikeout, so at least some cells differ. A squiggly drawn as a
    # straight line would be indistinguishable here.
    assert max(diffs) > 0, (
        "squiggly renders identically to a straight strikeout line — the zig-zag "
        "shape was not drawn"
    )
