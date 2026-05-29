"""Live Apache PDFBox differential parity for POLYGON / POLYLINE annotation
appearance generation — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDPolygonAppearanceHandler.generate_normal_appearance`` and
``PDPolylineAppearanceHandler.generate_normal_appearance`` invoked via
``annotation.construct_appearances()``. Unlike
``test_annotation_appearance_gen_oracle`` (which compares only operator NAMES
plus an integer-rounded BBox), this probe captures the FULL token stream —
every operand number/name canonicalised to 3 decimals — so a mis-placed vertex
(``m``/``l``), a wrong ``/C`` stroke colour (``RG``), a wrong ``/IC`` interior
fill (``rg``), a wrong ``/BS`` border width (``w``), or a wrong PolyLine
``/LE`` line-ending sub-path (``q``/``cm``/.../``Q``) is caught byte-for-byte.

The Java probe ``PolyAppearanceProbe`` runs in two modes:

* ``write out.pdf`` — builds a Polygon (3 vertices, stroke black, interior
  light-grey, border width 3) and a PolyLine (3 vertices, stroke magenta,
  interior cyan, OpenArrow start / Diamond end endings, border width 2), calls
  ``constructAppearances(doc)`` and saves.
* ``read out.pdf`` — emits per annotation ``RECT`` / ``BBOX`` (canonical
  floats) and one ``TOK`` line per content-stream token (operator keyword,
  canonical number, or ``/Name``).

Parity contract
---------------
Polygon and PolyLine both produce a pure path geometry with deterministic
float coordinates (no ``java.awt`` flattening), so the rewritten ``/Rect``,
``/BBox`` AND the full operand-level token sequence are byte-exact against
Apache PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLine,
    PDAnnotationPolygon,
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "PolyAppearanceProbe"


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors PolyAppearanceProbe.canon* (Java)
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


def _canon_token(tok) -> str:
    if isinstance(tok, Operator):
        return tok.get_name()
    if isinstance(tok, COSNumber):
        return _canon(tok.float_value())
    if isinstance(tok, COSName):
        return "/" + tok.name
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
        "toks": _tokens(stream),
    }


def _parse_java(text: str) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    subtype: str | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            subtype = raw[len("ANNOT ") :]
            current = {"toks": []}
        elif raw.startswith("RECT "):
            current["rect"] = raw[len("RECT ") :]  # type: ignore[index]
        elif raw.startswith("BBOX "):
            current["bbox"] = raw[len("BBOX ") :]  # type: ignore[index]
        elif raw == "NOAP":
            current["bbox"] = "NOAP"  # type: ignore[index]
        elif raw.startswith("TOK "):
            current["toks"].append(raw[len("TOK ") :])  # type: ignore[union-attr,index]
        elif raw == "END":
            assert subtype is not None and current is not None
            records[subtype] = current
            current = None
            subtype = None
    return records


def _build_polygon() -> PDAnnotationPolygon:
    polygon = PDAnnotationPolygon()
    # Java probe uses PDRectangle(x=50, y=500, w=200, h=200); pypdfbox's 4-arg
    # ctor is (llx, lly, urx, ury), so translate to (50, 500, 250, 700).
    polygon.set_rectangle(PDRectangle(50, 500, 250, 700))
    polygon.set_vertices([60, 510, 240, 520, 150, 680])
    polygon.set_color([0, 0, 0])
    polygon.set_interior_color([0.8, 0.8, 0.8])
    bs = PDBorderStyleDictionary()
    bs.set_width(3)
    polygon.set_border_style(bs)
    return polygon


def _build_polyline() -> PDAnnotationPolyline:
    polyline = PDAnnotationPolyline()
    # Java probe uses PDRectangle(x=300, y=500, w=200, h=200); translate to
    # (300, 500, 500, 700).
    polyline.set_rectangle(PDRectangle(300, 500, 500, 700))
    polyline.set_vertices([310, 510, 490, 560, 360, 680])
    polyline.set_color([1, 0, 1])
    polyline.set_interior_color([0, 1, 1])
    polyline.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    polyline.set_end_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    bs = PDBorderStyleDictionary()
    bs.set_width(2)
    polyline.set_border_style(bs)
    return polyline


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "poly.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_polygon_appearance_matches_pdfbox_exactly() -> None:
    """The Polygon /AP /N path is pure deterministic geometry: rewritten
    /Rect, /BBox and the full operand-level token stream are byte-exact against
    Apache PDFBox."""
    java = _java_records()["Polygon"]
    py = _py_fingerprint(_build_polygon())

    assert py["bbox"] != "NOAP", "pypdfbox produced no polygon /AP /N"
    assert py["rect"] == java["rect"], (
        f"Polygon /Rect: {py['rect']!r} != PDFBox {java['rect']!r}"
    )
    assert py["bbox"] == java["bbox"], (
        f"Polygon /BBox: {py['bbox']!r} != PDFBox {java['bbox']!r}"
    )
    assert py["toks"] == java["toks"], (
        f"Polygon token stream diverges\n"
        f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
        f"  PDFBox   ({len(java['toks'])}): {java['toks']}"  # type: ignore[arg-type]
    )


@requires_oracle
def test_polyline_appearance_matches_pdfbox_exactly() -> None:
    """The PolyLine /AP /N path — including the /LE OpenArrow (start) and
    Diamond (end) line-ending sub-paths drawn with q/cm/.../Q — is pure
    deterministic geometry: rewritten /Rect, /BBox and the full operand-level
    token stream are byte-exact against Apache PDFBox."""
    java = _java_records()["PolyLine"]
    py = _py_fingerprint(_build_polyline())

    assert py["bbox"] != "NOAP", "pypdfbox produced no polyline /AP /N"
    assert py["rect"] == java["rect"], (
        f"PolyLine /Rect: {py['rect']!r} != PDFBox {java['rect']!r}"
    )
    assert py["bbox"] == java["bbox"], (
        f"PolyLine /BBox: {py['bbox']!r} != PDFBox {java['bbox']!r}"
    )
    assert py["toks"] == java["toks"], (
        f"PolyLine token stream diverges\n"
        f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
        f"  PDFBox   ({len(java['toks'])}): {java['toks']}"  # type: ignore[arg-type]
    )
