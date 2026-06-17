"""Live Apache PDFBox differential parity for the STRUCTURAL form-XObject
shape of a markup annotation's freshly-generated ``/AP /N`` appearance.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation`` handlers
invoked through ``annotation.construct_appearances()`` for the geometric /
markup types whose ``/AP /N`` is built from scratch — Line (line endings +
caption), Square + Circle (interior colour, border width), Polygon, Polyline,
Ink.

Why this is a NON-colliding surface
------------------------------------
Two prior probes already fingerprinted the *content stream* of these
appearances: ``AnnotAppearGenProbe`` (Line / Square / Circle / Polygon /
PolyLine / Ink / Highlight) and ``AnnotAppear2Probe`` (the text-markup trio,
FreeText, etc.). Both compared the operator KEYWORD sequence + the ``/BBox``.

This probe (``AnnotApAppearanceProbe``) verifies the facts those did NOT
capture — the form-XObject *container* around that content stream:

* ``/Type`` is ``XObject`` and ``/Subtype`` is ``Form`` (a valid form XObject),
* ``/FormType`` is ``1``,
* ``/Matrix`` is the deterministic translation that moves the annotation
  rectangle's lower-left corner to the origin (``[1,0,0,1,-llx,-lly]``),
* ``/Resources`` is present (an empty dictionary on a fresh build).

The ``/Matrix`` and ``/BBox`` are coordinate-dependent but DETERMINISTIC, so
they are compared as canonical floats (mirroring the probe's ``canonFloat``).
Operands *inside* the content stream are not deterministic (sub-pixel AA-style
precision differs), so only the operator keyword sequence is compared there.

Result
------
Every structural fact matches Apache PDFBox 3.0.7 exactly — including the
Square's post-``handleBorderBox`` ``/Rect`` enlargement that shifts both the
``/BBox`` and ``/Matrix`` by half the line width (PDFBox ``BBOX
48.5,298.5,201.5,451.5`` / ``MATRIX 1,0,0,1,-48.5,-298.5``; pypdfbox identical).
No structural divergence was found, so nothing in the handler package needed a
fix this wave. The only operator-spelling divergence is the previously
documented Ink ``CS SC`` (PDFBox typed ``PDColor``) vs ``RG`` (pypdfbox lite
colour surface) — normalised below, not a bug.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
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

_PROBE = "AnnotApAppearanceProbe"

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_RESOURCES = COSName.get_pdf_name("Resources")


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors AnnotApAppearanceProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


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


def _name_or_none(value) -> str:
    if isinstance(value, COSName):
        return value.get_name()
    return "none"


def _py_fingerprint(ann, subtype: str) -> dict[str, object]:
    """Build the same per-annotation structural fingerprint the probe emits."""
    ann.construct_appearances()
    stream = ann.get_normal_appearance_stream()
    if stream is None:
        return {"subtype": subtype, "noap": True}
    cos = stream.get_cos_object()

    bbox = stream.get_bbox()
    bbox_line = (
        "none"
        if bbox is None
        else ",".join(
            _canon_float(v)
            for v in (
                bbox.get_lower_left_x(),
                bbox.get_lower_left_y(),
                bbox.get_upper_right_x(),
                bbox.get_upper_right_y(),
            )
        )
    )

    matrix = stream.get_matrix()
    matrix_line = ",".join(_canon_float(v) for v in matrix)

    res = cos.get_dictionary_object(_RESOURCES)
    if res is not None and hasattr(res, "key_set"):
        res_keys = sorted(k.get_name() for k in res.key_set())
        res_repr = "RES " + " ".join(res_keys)
    elif res is not None:
        res_repr = "RES "  # present but non-dict (shouldn't happen on a build)
    else:
        res_repr = "RES_NONE"

    return {
        "subtype": subtype,
        "noap": False,
        "type": _name_or_none(cos.get_dictionary_object(_TYPE)),
        "stype": _name_or_none(cos.get_dictionary_object(_SUBTYPE)),
        "formtype": stream.get_form_type(),
        "bbox": bbox_line,
        "matrix": matrix_line,
        "res": res_repr,
        "ops": _operators(stream),
    }


def _parse_java(text: str) -> dict[str, dict[str, object]]:
    """Parse AnnotApAppearanceProbe read-mode output into per-subtype records."""
    records: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :], "noap": False, "ops": []}
        elif raw == "NOAP":
            assert current is not None
            current["noap"] = True
        elif raw.startswith("TYPE "):
            assert current is not None
            current["type"] = raw[len("TYPE ") :]
        elif raw.startswith("SUBTYPE "):
            assert current is not None
            current["stype"] = raw[len("SUBTYPE ") :]
        elif raw.startswith("FORMTYPE "):
            assert current is not None
            current["formtype"] = int(raw[len("FORMTYPE ") :])
        elif raw.startswith("BBOX "):
            assert current is not None
            current["bbox"] = raw[len("BBOX ") :]
        elif raw.startswith("MATRIX "):
            assert current is not None
            current["matrix"] = raw[len("MATRIX ") :]
        elif raw.startswith("RES "):
            assert current is not None
            # canonicalise to "RES <space-joined sorted keys>" (RES alone -> "RES ")
            current["res"] = "RES " + raw[len("RES ") :].strip()
        elif raw == "RES_NONE":
            assert current is not None
            current["res"] = "RES_NONE"
        elif raw.startswith("OP:"):
            assert current is not None
            current["ops"].append(raw[len("OP:") :])  # type: ignore[union-attr]
        elif raw == "END":
            assert current is not None
            records[current["subtype"]] = current  # type: ignore[index]
            current = None
    return records


def _build_battery() -> list[tuple[str, object]]:
    """Build the same annotation battery as AnnotApAppearanceProbe.write."""

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

    return [
        ("Line", line),
        ("Square", square),
        ("Circle", circle),
        ("Polygon", polygon),
        ("PolyLine", polyline),
        ("Ink", ink),
    ]


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "annot_ap.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_appearance_xobject_structure_matches_pdfbox() -> None:
    """Every freshly-generated ``/AP /N`` is a valid form XObject whose
    ``/Type`` / ``/Subtype`` / ``/FormType`` / ``/Matrix`` / ``/Resources``
    presence is structurally identical to Apache PDFBox 3.0.7."""
    java = _java_records()
    assert set(java) == {
        "Line",
        "Square",
        "Circle",
        "Polygon",
        "PolyLine",
        "Ink",
    }, f"unexpected probe subtypes: {sorted(java)}"

    for subtype, ann in _build_battery():
        py = _py_fingerprint(ann, subtype)
        jr = java[subtype]

        assert not py["noap"], f"{subtype}: pypdfbox produced no /AP /N stream"
        assert not jr["noap"], f"{subtype}: PDFBox produced no /AP /N stream"

        # Form-XObject container tags: identical.
        assert py["type"] == jr["type"] == "XObject", (
            f"{subtype}: /Type {py['type']!r} vs PDFBox {jr['type']!r}"
        )
        assert py["stype"] == jr["stype"] == "Form", (
            f"{subtype}: /Subtype {py['stype']!r} vs PDFBox {jr['stype']!r}"
        )
        assert py["formtype"] == jr["formtype"] == 1, (
            f"{subtype}: /FormType {py['formtype']!r} vs PDFBox {jr['formtype']!r}"
        )

        # Deterministic geometry: /BBox + /Matrix match to canonical floats.
        assert py["bbox"] == jr["bbox"], (
            f"{subtype}: /BBox {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )
        assert py["matrix"] == jr["matrix"], (
            f"{subtype}: /Matrix {py['matrix']!r} != PDFBox {jr['matrix']!r}"
        )

        # /Resources present on both (empty dict on a fresh build).
        assert py["res"] == jr["res"], (
            f"{subtype}: /Resources {py['res']!r} != PDFBox {jr['res']!r}"
        )
        assert py["res"] != "RES_NONE", (
            f"{subtype}: pypdfbox emitted no /Resources dictionary"
        )


@requires_oracle
def test_matrix_is_rect_to_origin_translation() -> None:
    """The /Matrix is the canonical translation moving the annotation's
    rectangle lower-left corner to the origin — for Square this is the
    post-handleBorderBox enlarged rect, exactly as PDFBox computes it."""
    java = _java_records()
    for subtype, ann in _build_battery():
        py = _py_fingerprint(ann, subtype)
        jr = java[subtype]
        # Matrix == [1,0,0,1,-bbox_llx,-bbox_lly]; the bbox is the same.
        bbox_parts = jr["bbox"].split(",")  # type: ignore[union-attr]
        expected = (
            "1,0,0,1,"
            + _canon_float(-float(bbox_parts[0]))
            + ","
            + _canon_float(-float(bbox_parts[1]))
        )
        assert jr["matrix"] == expected, (
            f"{subtype}: PDFBox matrix {jr['matrix']!r} != derived {expected!r}"
        )
        assert py["matrix"] == jr["matrix"], (
            f"{subtype}: pypdfbox matrix {py['matrix']!r} != PDFBox {jr['matrix']!r}"
        )


@requires_oracle
def test_operator_sequence_matches_pdfbox() -> None:
    """Sanity cross-check that the content stream WITHIN the structurally
    matched form XObject draws the same operator sequence. As of wave 1463
    the Ink colour-set divergence is resolved — Ink now emits the typed
    ``CS``/``SC`` pair byte-for-byte like PDFBox, so no normalisation is
    needed."""
    java = _java_records()
    for subtype, ann in _build_battery():
        py = _py_fingerprint(ann, subtype)
        jr = java[subtype]
        py_ops = list(py["ops"])  # type: ignore[arg-type]
        jr_ops = list(jr["ops"])  # type: ignore[arg-type]
        assert py_ops == jr_ops, (
            f"{subtype}: operator sequence diverges\n"
            f"  pypdfbox: {py_ops}\n  PDFBox:   {jr_ops}"
            )
