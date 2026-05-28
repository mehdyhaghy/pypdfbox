"""Live Apache PDFBox differential parity for the CLOUDY-BORDER appearance
generation surface (PDF 32000 §12.5.4 ``/BE /S C`` — the "cloudy" border
effect on Square / Circle markup annotations).

Surface under test
------------------
``PDSquareAppearanceHandler`` / ``PDCircleAppearanceHandler`` invoked via
``annotation.construct_appearances(document)`` when the annotation carries a
cloudy ``/BE`` border effect. Unlike the SOLID-border path exercised by
``test_annotation_appearance_gen_oracle`` (a plain ``re`` rectangle / four
Bezier ellipse), the cloudy path runs ``CloudyBorder.create_cloudy_rectangle``
/ ``create_cloudy_ellipse``, which:

* emits a curl-Bezier (``m`` + many ``c``) token stream, and
* REWRITES the annotation ``/Rect``, the form-XObject ``/BBox`` + ``/Matrix``,
  and the ``/RD`` rect-difference from the computed cloud geometry.

The Java probe ``CloudyBorderProbe`` runs in two modes:

* ``write out.pdf`` — builds a cloudy Square and cloudy Circle (stroke colour,
  interior colour, border width, intensity), calls ``constructAppearances`` and
  saves.
* ``read out.pdf`` — emits per annotation: ``RECT`` / ``BBOX`` / ``MTX`` /
  ``RD`` (canonical floats) + one ``OP:`` per operator token + ``OPCOUNT``.

Parity contract
---------------
* **Square** — the cloudy *rectangle* is a pure polygon-curl path (no
  ``java.awt`` ``Ellipse2D`` dependency), so its rewritten ``/Rect``,
  ``/BBox``, ``/Matrix``, ``/RD`` AND its full operator sequence are
  byte-exact across implementations.
* **Circle** — the cloudy *ellipse* flattens via ``java.awt.geom.Ellipse2D``
  upstream vs an equal-angle emulation in the lite port (a documented
  divergence — see ``CloudyBorder.flatten_ellipse`` / ``CHANGES.md``), so the
  exact curl count is not guaranteed. The test asserts the geometry CONTRACT
  instead: the cloudy effect really enlarged the ``/Rect``/``/BBox`` beyond the
  original rectangle, the ``/Matrix`` is the identity-translate that maps the
  bbox lower-left to the origin, an ``/RD`` is present, and the stream is a
  non-trivial closed curl path (``m`` + many ``c`` + ``h`` + ``B``).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "CloudyBorderProbe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors CloudyBorderProbe.canon (Java)
# ---------------------------------------------------------------------------


def _canon(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _canon_rect(r) -> str:
    if r is None:
        return "none"
    return ",".join(
        _canon(v)
        for v in (
            r.get_lower_left_x(),
            r.get_lower_left_y(),
            r.get_upper_right_x(),
            r.get_upper_right_y(),
        )
    )


def _canon_rd(rd) -> str:
    """/RD is rendered as left,top,right,bottom (the spec order)."""
    if rd is None:
        return "none"
    return ",".join(
        _canon(v)
        for v in (
            rd.get_lower_left_x(),
            rd.get_upper_right_y(),
            rd.get_upper_right_x(),
            rd.get_lower_left_y(),
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


def _py_fingerprint(ann) -> dict[str, object]:
    ann.construct_appearances()
    stream = ann.get_normal_appearance_stream()
    if stream is None:
        return {"rect": _canon_rect(ann.get_rectangle()), "bbox": "NOAP"}
    return {
        "rect": _canon_rect(ann.get_rectangle()),
        "bbox": _canon_rect(stream.get_bbox()),
        "mtx": ",".join(_canon(v) for v in stream.get_matrix()),
        "rd": _canon_rd(ann.get_rect_difference()),
        "ops": _operators(stream),
    }


def _parse_java(text: str) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    subtype: str | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            subtype = raw[len("ANNOT ") :]
            current = {"ops": []}
        elif raw.startswith("RECT "):
            current["rect"] = raw[len("RECT ") :]  # type: ignore[index]
        elif raw.startswith("BBOX "):
            current["bbox"] = raw[len("BBOX ") :]  # type: ignore[index]
        elif raw.startswith("MTX "):
            current["mtx"] = raw[len("MTX ") :]  # type: ignore[index]
        elif raw.startswith("RD "):
            current["rd"] = raw[len("RD ") :]  # type: ignore[index]
        elif raw == "NOAP":
            current["bbox"] = "NOAP"  # type: ignore[index]
        elif raw.startswith("OP:"):
            current["ops"].append(raw[len("OP:") :])  # type: ignore[union-attr,index]
        elif raw == "END":
            assert subtype is not None and current is not None
            records[subtype] = current
            current = None
            subtype = None
    return records


def _build_square() -> PDAnnotationSquare:
    square = PDAnnotationSquare()
    # Java probe uses PDRectangle(x=100, y=100, w=200, h=150); pypdfbox's
    # 4-arg ctor is (llx, lly, urx, ury), so translate to (100, 100, 300, 250).
    square.set_rectangle(PDRectangle(100, 100, 300, 250))
    square.set_color([0, 0, 1])
    square.set_interior_color([1, 1, 0])
    bs = PDBorderStyleDictionary()
    bs.set_width(2)
    square.set_border_style(bs)
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1)
    square.set_border_effect(be)
    return square


def _build_circle() -> PDAnnotationCircle:
    circle = PDAnnotationCircle()
    # Java probe uses PDRectangle(x=120, y=400, w=220, h=160); translate the
    # 4-arg ctor (llx, lly, urx, ury) to (120, 400, 340, 560).
    circle.set_rectangle(PDRectangle(120, 400, 340, 560))
    circle.set_color([0, 0.5, 0])
    circle.set_interior_color([1, 0.7, 0.8])
    bs = PDBorderStyleDictionary()
    bs.set_width(2)
    circle.set_border_style(bs)
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(2)
    circle.set_border_effect(be)
    return circle


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "cloudy.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_cloudy_square_matches_pdfbox_exactly() -> None:
    """The cloudy SQUARE path is a pure polygon-curl geometry: rewritten
    /Rect, /BBox, /Matrix, /RD and the full operator sequence are byte-exact
    against Apache PDFBox."""
    java = _java_records()["Square"]
    py = _py_fingerprint(_build_square())

    assert py["bbox"] != "NOAP", "pypdfbox produced no cloudy-square /AP /N"
    assert py["rect"] == java["rect"], (
        f"Square /Rect: {py['rect']!r} != PDFBox {java['rect']!r}"
    )
    assert py["bbox"] == java["bbox"], (
        f"Square /BBox: {py['bbox']!r} != PDFBox {java['bbox']!r}"
    )
    assert py["mtx"] == java["mtx"], (
        f"Square /Matrix: {py['mtx']!r} != PDFBox {java['mtx']!r}"
    )
    assert py["rd"] == java["rd"], (
        f"Square /RD: {py['rd']!r} != PDFBox {java['rd']!r}"
    )
    assert py["ops"] == java["ops"], (
        f"Square cloudy operator sequence diverges\n"
        f"  pypdfbox ({len(py['ops'])}): {py['ops']}\n"  # type: ignore[arg-type]
        f"  PDFBox   ({len(java['ops'])}): {java['ops']}"  # type: ignore[arg-type]
    )


@requires_oracle
def test_cloudy_circle_geometry_contract() -> None:
    """The cloudy CIRCLE path flattens via java.awt Ellipse2D upstream vs an
    equal-angle emulation in the lite port (documented divergence), so the
    exact curl count isn't guaranteed. Assert the geometry CONTRACT: the cloud
    really enlarged /Rect and /BBox, the /Matrix is the identity-translate that
    maps the bbox lower-left to the origin, an /RD is present, and the stream
    is a non-trivial closed curl path."""
    java = _java_records()["Circle"]
    py = _py_fingerprint(_build_circle())
    assert py["bbox"] != "NOAP", "pypdfbox produced no cloudy-circle /AP /N"

    # Original rect was (120, 400) .. (340, 560). The cloud enlarges it.
    bbox_vals = [float(v) for v in py["bbox"].split(",")]  # type: ignore[union-attr]
    assert bbox_vals[0] < 120 and bbox_vals[1] < 400
    assert bbox_vals[2] > 340 and bbox_vals[3] > 560

    # /Rect must equal the /BBox (cloudy handler sets annot.rect = bbox).
    assert py["rect"] == py["bbox"]

    # /Matrix is identity-translate by -bbox_lower_left.
    mtx = [float(v) for v in py["mtx"].split(",")]  # type: ignore[union-attr]
    assert mtx[:4] == [1.0, 0.0, 0.0, 1.0]
    assert _canon(mtx[4]) == _canon(-bbox_vals[0])
    assert _canon(mtx[5]) == _canon(-bbox_vals[1])

    # /RD present and four positive sides.
    assert py["rd"] != "none"
    assert all(float(v) > 0 for v in py["rd"].split(","))  # type: ignore[union-attr]

    # Non-trivial closed curl path: colour ops, width/join, a move, many
    # curves, close + fill-stroke. Same operator VOCABULARY as Java even when
    # the curl COUNT differs.
    ops = py["ops"]
    java_ops = java["ops"]
    assert set(ops) == set(java_ops), (  # type: ignore[arg-type]
        f"Circle operator vocabulary diverges: {sorted(set(ops))}"  # type: ignore[arg-type]
        f" vs {sorted(set(java_ops))}"  # type: ignore[arg-type]
    )
    assert ops[:4] == ["RG", "rg", "w", "j"]  # type: ignore[index]
    assert ops[-2:] == ["h", "B"]  # type: ignore[index]
    assert ops.count("c") > 50  # type: ignore[union-attr]
    assert ops.count("m") == 1  # type: ignore[union-attr]
