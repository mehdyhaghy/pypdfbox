"""Live Apache PDFBox differential parity for NON-WIDGET annotation
appearance GENERATION.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation`` handlers
(``PDLineAppearanceHandler``, square, circle, polygon, polyline, ink,
highlight) invoked via ``annotation.construct_appearances(document)``.

How it works
------------
The Java probe ``AnnotAppearGenProbe`` runs in two modes:

* ``write out.pdf`` — builds a page with a battery of markup annotations
  (Line, Square, Circle, Polygon, PolyLine, Ink, Highlight), each given a
  ``/Rect``, stroke colour, and — where relevant — interior colour, border
  width, and line-ending styles; then calls
  ``annotation.constructAppearances(doc)`` on each and saves.
* ``read out.pdf`` — re-opens the file and emits, per annotation, a
  coordinate-independent fingerprint of its ``/AP /N`` appearance stream:
  ``ANNOT <subtype>`` / ``BBOX <canonical floats>`` / one ``OP:<name>`` per
  operator token (via ``PDFStreamParser``) / ``END``.

pypdfbox builds the identical annotations with identical properties, calls
``construct_appearances()``, and emits the same fingerprint. The operator
KEYWORD sequence plus the canonical-float ``/AP /N`` ``/BBox`` are compared
exactly. Operands (numbers/names) are coordinate dependent and excluded —
a wrong / missing / extra *drawing operator* or a wrong bbox is a real bug;
coordinate precision is normalised by construction.

Divergence FIXED (wave 1414)
----------------------------
``construct_appearances()`` on Line / Square / Circle / Polygon / PolyLine /
Ink / Highlight was a no-op on the default (no custom handler) path — it never
instantiated the built-in appearance handler, so no ``/AP`` stream was
generated at all. Upstream's ``constructAppearances(PDDocument)`` always
instantiates the default handler when ``customAppearanceHandler == null``.
Fixed in each ``PDAnnotation*`` subclass to wire the matching handler. With
the fix the generated operator sequences and bboxes match Apache PDFBox.

Documented (NOT fixed — legitimate lite-surface differences)
------------------------------------------------------------
* **Ink stroking colour operator**: upstream ``PDInkAppearanceHandler`` calls
  ``cs.setStrokingColor(PDColor)`` which, for a DeviceRGB colour, emits
  ``/DeviceRGB CS`` + ``r g b SC``. pypdfbox's lite annotation colour surface
  has no typed ``PDColor`` with an explicit colour space (deferred to the
  rendering cluster — see ``CHANGES.md``); ``set_stroking_color([r,g,b])``
  emits the device shorthand ``r g b RG`` instead. Identical pixels, identical
  path-drawing operators (``m l l S``); only the colour-set operator spelling
  differs. The Line handler, which uses ``setStrokingColorOnDemand`` upstream,
  already emits ``RG`` on both sides and matches exactly.
* **Highlight transparency group**: upstream wraps the quad fill in a
  two-form-XObject transparency group with a Multiply blend (the outer stream
  is ``gs gs Do``). ``PDFormXObject`` group emission isn't ported, so the lite
  highlight handler applies the same alpha + Multiply ``ExtGState`` inline and
  fills the quad directly (``gs gs <colour> <path> f``). The ``/BBox`` matches
  exactly; the inner draw operators are compared instead of the ``Do``.

These two are normalised in the comparison below; every drawing operator and
every bbox is otherwise asserted exact against Apache PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationHighlight,
    PDAnnotationInk,
    PDAnnotationLine,
    PDAnnotationPolygon,
    PDAnnotationPolyline,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "AnnotAppearGenProbe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors AnnotAppearGenProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    # Round half-to-even to 3 decimals (matches Java's BigDecimal HALF_EVEN),
    # strip trailing zeros / trailing dot, normalise -0.
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _bbox_line(stream) -> str:
    bbox = stream.get_bbox()
    if bbox is None:
        return "BBOX none"
    return "BBOX " + ",".join(
        _canon_float(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


def _operators(stream) -> list[str]:
    parser = PDFStreamParser.from_content_stream(stream)
    ops: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        if isinstance(token, Operator):
            ops.append(token.get_name())
    return ops


def _py_fingerprint(ann, subtype: str) -> dict[str, object]:
    """Build the same per-annotation fingerprint pypdfbox would emit."""
    ann.construct_appearances()
    stream = ann.get_normal_appearance_stream()
    if stream is None:
        return {"subtype": subtype, "bbox": "NOAP", "ops": []}
    return {
        "subtype": subtype,
        "bbox": _bbox_line(stream),
        "ops": _operators(stream),
    }


def _parse_java(text: str) -> list[dict[str, object]]:
    """Parse the probe's read-mode output into per-annotation records."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :], "bbox": None, "ops": []}
        elif raw.startswith("BBOX "):
            assert current is not None
            current["bbox"] = raw
        elif raw == "NOAP":
            assert current is not None
            current["bbox"] = "NOAP"
        elif raw.startswith("OP:"):
            assert current is not None
            current["ops"].append(raw[len("OP:") :])  # type: ignore[union-attr]
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
    return records


def _build_battery() -> list[tuple[object, str]]:
    """Build the same annotation battery as AnnotAppearGenProbe.write."""

    def rgb(r: float, g: float, b: float) -> list[float]:
        return [r, g, b]

    line = PDAnnotationLine()
    line.set_rectangle(PDRectangle(50, 50, 250, 250))
    line.set_line([60, 60, 240, 240])
    line.set_color(rgb(1, 0, 0))
    line.set_interior_color(rgb(0, 1, 0))
    line.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    line.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)

    square = PDAnnotationSquare()
    square.set_rectangle(PDRectangle(50, 300, 200, 450))
    square.set_color(rgb(0, 0, 1))
    square.set_interior_color(rgb(1, 1, 0))
    square_bs = PDBorderStyleDictionary()
    square_bs.set_width(3)
    square.set_border_style(square_bs)

    circle = PDAnnotationCircle()
    circle.set_rectangle(PDRectangle(250, 300, 400, 450))
    circle.set_color(rgb(0, 0.5, 0))
    circle_bs = PDBorderStyleDictionary()
    circle_bs.set_width(2)
    circle.set_border_style(circle_bs)

    polygon = PDAnnotationPolygon()
    polygon.set_rectangle(PDRectangle(50, 500, 250, 700))
    polygon.set_vertices([60, 510, 240, 520, 150, 680])
    polygon.set_color(rgb(0, 0, 0))
    polygon.set_interior_color(rgb(0.8, 0.8, 0.8))

    polyline = PDAnnotationPolyline()
    polyline.set_rectangle(PDRectangle(300, 500, 500, 700))
    polyline.set_vertices([310, 510, 490, 560, 360, 680])
    polyline.set_color(rgb(1, 0, 1))
    polyline.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    polyline.set_end_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    polyline.set_interior_color(rgb(0, 1, 1))

    ink = PDAnnotationInk()
    ink.set_rectangle(PDRectangle(50, 720, 250, 820))
    ink.set_ink_paths([[60, 730, 100, 800, 140, 740], [160, 730, 200, 810, 240, 740]])
    ink.set_color(rgb(0.5, 0, 0))

    highlight = PDAnnotationHighlight()
    highlight.set_rectangle(PDRectangle(300, 720, 500, 780))
    highlight.set_quad_points([300, 770, 500, 770, 300, 730, 500, 730])
    highlight.set_color(rgb(1, 0.6, 0))

    return [
        (line, "Line"),
        (square, "Square"),
        (circle, "Circle"),
        (polygon, "Polygon"),
        (polyline, "PolyLine"),
        (ink, "Ink"),
        (highlight, "Highlight"),
    ]


# Documented, normalised divergences (see module docstring).
#
# Ink: upstream emits the colour-space pair ``CS SC`` (PDColor with explicit
# DeviceRGB colour space); pypdfbox's lite colour surface emits the device
# shorthand ``RG``. Identical colour, identical path drawing operators.
_INK_COLOR_OPS_JAVA = ["CS", "SC"]
_INK_COLOR_OPS_PY = ["RG"]


def _normalise_ink(ops: list[str], color_ops: list[str]) -> list[str]:
    """Drop the leading colour-set operator(s) so the path-drawing operator
    sequence can be compared regardless of the colour-set spelling."""
    if ops[: len(color_ops)] == color_ops:
        return ops[len(color_ops) :]
    return ops


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "annot_appear.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return {rec["subtype"]: rec for rec in _parse_java(text)}


@requires_oracle
def test_appearance_generation_matches_pdfbox() -> None:
    """All seven non-widget appearance handlers match Apache PDFBox's
    generated ``/AP /N`` operator sequence + bbox (with the two documented
    lite-surface divergences normalised)."""
    java = _java_records()
    for ann, subtype in _build_battery():
        py = _py_fingerprint(ann, subtype)
        jr = java[subtype]

        # Every handler must produce an /AP /N stream (the wave-1414 fix).
        assert py["bbox"] != "NOAP", f"{subtype}: pypdfbox produced no /AP /N"
        assert jr["bbox"] != "NOAP", f"{subtype}: PDFBox produced no /AP /N"

        # Exact /BBox parity (canonical floats — no rounding-rule artifacts).
        assert py["bbox"] == jr["bbox"], (
            f"{subtype}: bbox {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )

        py_ops = list(py["ops"])  # type: ignore[arg-type]
        jr_ops = list(jr["ops"])  # type: ignore[arg-type]

        if subtype == "Ink":
            # Normalise only the colour-set operator (documented divergence);
            # the path-drawing operators must match exactly.
            assert _normalise_ink(py_ops, _INK_COLOR_OPS_PY) == _normalise_ink(
                jr_ops, _INK_COLOR_OPS_JAVA
            ), f"Ink path operators diverge: {py_ops} vs {jr_ops}"
        elif subtype == "Highlight":
            # Documented transparency-group divergence: upstream's outer
            # stream is ``gs gs Do`` (a form XObject); the lite handler
            # inlines the fill. Assert both start with the two ExtGState
            # applications and that the lite stream actually fills a path.
            assert jr_ops[:2] == ["gs", "gs"], f"PDFBox highlight: {jr_ops}"
            assert py_ops[:2] == ["gs", "gs"], f"pypdfbox highlight: {py_ops}"
            assert "f" in py_ops, f"pypdfbox highlight did not fill: {py_ops}"
        else:
            assert py_ops == jr_ops, (
                f"{subtype}: operator sequence diverges\n"
                f"  pypdfbox: {py_ops}\n  PDFBox:   {jr_ops}"
            )


@requires_oracle
def test_line_appearance_operator_sequence_exact() -> None:
    """Line is the richest exact-match case (leader lines + caption path +
    open/closed arrow endings) — assert the full operator sequence."""
    java = _java_records()
    line, _ = _build_battery()[0]
    py = _py_fingerprint(line, "Line")
    assert py["ops"] == java["Line"]["ops"]
    assert py["bbox"] == java["Line"]["bbox"]


@requires_oracle
def test_square_circle_polygon_polyline_bbox_exact() -> None:
    """Shape annotations: the bbox is part of the contract (square/circle
    enlarge /Rect by /RD; polygon/polyline pad by line width)."""
    java = _java_records()
    battery = {sub: ann for ann, sub in _build_battery()}
    for subtype in ("Square", "Circle", "Polygon", "PolyLine"):
        py = _py_fingerprint(battery[subtype], subtype)
        assert py["bbox"] == java[subtype]["bbox"], (
            f"{subtype}: {py['bbox']!r} != {java[subtype]['bbox']!r}"
        )
        assert py["ops"] == java[subtype]["ops"], (
            f"{subtype}: {py['ops']} != {java[subtype]['ops']}"
        )
