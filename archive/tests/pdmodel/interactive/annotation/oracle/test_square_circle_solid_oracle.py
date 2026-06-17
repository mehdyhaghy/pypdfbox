"""Live Apache PDFBox differential parity for the SOLID-border Square / Circle
appearance generation surface — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDSquareAppearanceHandler`` / ``PDCircleAppearanceHandler`` invoked via
``annotation.construct_appearances()`` on the SOLID-border path (no ``/BE``
cloudy effect):

* the square's plain ``re`` rectangle (``handle_border_box`` → ``add_rect`` →
  ``draw_shape``), and
* the circle's four-Bezier ellipse (Adobe kappa constant ``0.55555417`` —
  ``m`` + four ``c`` + ``h``).

Unlike ``test_annotation_appearance_gen_oracle`` (which pins these two only at
the operator-KEYWORD + ``/BBox`` level) and ``test_cloudy_border_oracle`` (which
operand-pins the cloudy ``/BE`` path), this file pins the FULL operand-level
token stream — every operator AND every numeric/array/name operand
canonicalised to 3 decimals — across a matrix that exercises:

* default border width (1, line-width command suppressed),
* thick width (5, explicit ``5 w``),
* zero width (no stroke even when a colour is set — ``draw_shape`` gating),
* interior colour ``/IC`` present vs absent (fill vs no fill),
* dashed ``/BS /D`` — the ``[...] 0 d`` dash operand,
* the ``/RD`` rect-difference REWRITE arithmetic (``handle_border_box`` seeds
  ``/RD`` = width/2 and enlarges ``/Rect`` when ``/RD`` is unset; a pre-set
  ``/RD`` takes the no-enlarge branch),

plus, per annotation, the rewritten ``/Rect``, the form-XObject ``/BBox`` +
``/Matrix`` and the ``/RD`` rect-difference.

The Java probe ``SquareCircleSolidProbe`` runs in two modes:

* ``write out.pdf`` — builds five Squares and two Circles (the matrix above)
  and calls ``constructAppearances(doc)`` and saves.
* ``read out.pdf`` — emits per annotation ``ANNOT`` / ``RECT`` / ``BBOX`` /
  ``MTX`` / ``RD`` (canonical floats) and one ``TOK`` per content-stream token
  (operator keyword, canonical number, ``/Name`` or ``[...]`` array).

Parity contract
---------------
Every annotation's rewritten ``/Rect``, ``/BBox``, ``/Matrix``, ``/RD`` AND the
full operand-level token sequence are byte-exact against Apache PDFBox 3.0.7.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSArray, COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "SquareCircleSolidProbe"


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors SquareCircleSolidProbe.canon* (Java)
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
    """/RD is rendered as left,top,right,bottom (the probe's spec order)."""
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


def _canon_token(tok) -> str:
    if isinstance(tok, Operator):
        return tok.get_name()
    if isinstance(tok, COSNumber):
        return _canon(tok.float_value())
    if isinstance(tok, COSName):
        return "/" + tok.name
    if isinstance(tok, COSArray):
        parts: list[str] = []
        for element in tok:
            if isinstance(element, COSNumber):
                parts.append(_canon(element.float_value()))
            else:
                parts.append(str(element))
        return "[" + " ".join(parts) + "]"
    return type(tok).__name__


def _tokens(stream) -> list[str]:
    parser = PDFStreamParser.from_content_stream(stream)
    out: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        out.append(_canon_token(token))
    return out


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
        "toks": _tokens(stream),
    }


def _parse_java(text: str) -> list[dict[str, object]]:
    """Parse into an ordered list (one record per /Annots ordinal)."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :], "toks": []}
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
        elif raw.startswith("TOK "):
            current["toks"].append(raw[len("TOK ") :])  # type: ignore[union-attr,index]
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
    return records


def _build_battery() -> list[tuple[object, str]]:
    """Mirror SquareCircleSolidProbe.write exactly — five squares, two circles.

    The Java probe uses ``new PDRectangle(x, y, w, h)`` (x, y, width, height);
    pypdfbox's 4-arg ``PDRectangle`` is (llx, lly, urx, ury), so build via
    ``from_xywh`` to get identical geometry.
    """
    battery: list[tuple[object, str]] = []

    # 0: Square, default width (no /BS) — stroke blue, fill yellow.
    s0 = PDAnnotationSquare()
    s0.set_rectangle(PDRectangle.from_xywh(50, 700, 100, 60))
    s0.set_color([0, 0, 1])
    s0.set_interior_color([1, 1, 0])
    battery.append((s0, "Square0"))

    # 1: Square, thick width 5 — stroke red, no fill.
    s1 = PDAnnotationSquare()
    s1.set_rectangle(PDRectangle.from_xywh(50, 600, 100, 60))
    s1.set_color([1, 0, 0])
    bs1 = PDBorderStyleDictionary()
    bs1.set_width(5)
    s1.set_border_style(bs1)
    battery.append((s1, "Square1"))

    # 2: Square, zero width — stroke set but suppressed by draw_shape, fill green.
    s2 = PDAnnotationSquare()
    s2.set_rectangle(PDRectangle.from_xywh(50, 500, 100, 60))
    s2.set_color([0, 0, 1])
    s2.set_interior_color([0, 1, 0])
    bs2 = PDBorderStyleDictionary()
    bs2.set_width(0)
    s2.set_border_style(bs2)
    battery.append((s2, "Square2"))

    # 3: Square, dashed /BS /D — stroke black, width 2.
    s3 = PDAnnotationSquare()
    s3.set_rectangle(PDRectangle.from_xywh(50, 400, 100, 60))
    s3.set_color([0, 0, 0])
    bs3 = PDBorderStyleDictionary()
    bs3.set_width(2)
    bs3.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    bs3.set_dash_style([3, 2])
    s3.set_border_style(bs3)
    battery.append((s3, "Square3"))

    # 4: Square with a pre-set /RD — handle_border_box "RD already set" branch.
    s4 = PDAnnotationSquare()
    s4.set_rectangle(PDRectangle.from_xywh(50, 300, 100, 60))
    s4.set_color([0, 0, 1])
    s4.set_rect_differences(5, 4, 3, 2)
    bs4 = PDBorderStyleDictionary()
    bs4.set_width(2)
    s4.set_border_style(bs4)
    battery.append((s4, "Square4"))

    # 5: Circle, default width — stroke green, fill pink.
    c0 = PDAnnotationCircle()
    c0.set_rectangle(PDRectangle.from_xywh(200, 700, 100, 60))
    c0.set_color([0, 0.5, 0])
    c0.set_interior_color([1, 0.7, 0.8])
    battery.append((c0, "Circle0"))

    # 6: Circle, thick width 5 — stroke blue, no fill.
    c1 = PDAnnotationCircle()
    c1.set_rectangle(PDRectangle.from_xywh(200, 600, 100, 60))
    c1.set_color([0, 0, 1])
    cbs1 = PDBorderStyleDictionary()
    cbs1.set_width(5)
    c1.set_border_style(cbs1)
    battery.append((c1, "Circle1"))

    return battery


def _java_records() -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "square_circle_solid.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_square_circle_solid_match_pdfbox_exactly() -> None:
    """The SOLID-border Square (plain ``re``) and Circle (four-Bezier ellipse)
    appearance paths are pure deterministic geometry: across the full matrix
    (default/thick/zero/dashed widths, /IC present/absent, /RD set/unset) the
    rewritten /Rect, /BBox, /Matrix, /RD AND the full operand-level token
    stream are byte-exact against Apache PDFBox."""
    java = _java_records()
    battery = _build_battery()
    assert len(java) == len(battery), (
        f"probe wrote {len(java)} annots, battery has {len(battery)}"
    )
    for (ann, label), jr in zip(battery, java, strict=True):
        py = _py_fingerprint(ann)
        assert py["bbox"] != "NOAP", f"{label}: pypdfbox produced no /AP /N"
        assert py["rect"] == jr["rect"], (
            f"{label} /Rect: {py['rect']!r} != PDFBox {jr['rect']!r}"
        )
        assert py["bbox"] == jr["bbox"], (
            f"{label} /BBox: {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )
        assert py["mtx"] == jr["mtx"], (
            f"{label} /Matrix: {py['mtx']!r} != PDFBox {jr['mtx']!r}"
        )
        assert py["rd"] == jr["rd"], (
            f"{label} /RD: {py['rd']!r} != PDFBox {jr['rd']!r}"
        )
        assert py["toks"] == jr["toks"], (
            f"{label} token stream diverges\n"
            f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
            f"  PDFBox   ({len(jr['toks'])}): {jr['toks']}"  # type: ignore[arg-type]
        )
