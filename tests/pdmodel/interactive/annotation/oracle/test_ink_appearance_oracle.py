"""Live Apache PDFBox differential parity for INK annotation appearance
generation — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDInkAppearanceHandler.generate_normal_appearance`` invoked via
``PDAnnotationInk.construct_appearances()``. Unlike
``test_annotation_appearance_gen_oracle`` (which compares only operator NAMES
plus an integer-rounded BBox), this probe captures the FULL token stream —
every operand number/name canonicalised to 3 decimals — so a mis-placed stroke
vertex (``m``/``l``), a wrong ``/C`` stroke colour (``RG``), a wrong ``/BS``
border width (``w``), a missing per-path ``S`` (stroke), or a wrongly-rewritten
``/Rect`` / ``/BBox`` is caught byte-for-byte.

The Java probe ``InkAppearanceProbe`` runs in two modes:

* ``write out.pdf`` — builds an Ink annotation whose ``/InkList`` holds TWO
  stroked paths (path 0 = 3 points, path 1 = 2 points), stroke colour orange,
  border width 4 — then calls ``constructAppearances(doc)`` and saves.
* ``read out.pdf`` — emits per annotation ``RECT`` / ``BBOX`` (canonical
  floats) and one ``TOK`` line per content-stream token (operator keyword,
  canonical number, or ``/Name``).

Parity contract
---------------
The Ink ``/AP /N`` path is pure deterministic geometry — each ``/InkList`` path
becomes ``m`` then ``l`` per subsequent point, followed by a per-path ``S`` —
so the rewritten ``/Rect`` (extended by ``±width*2`` around the ink extents),
``/BBox`` AND the full operand-level token sequence are byte-exact against
Apache PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationInk,
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "InkAppearanceProbe"


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors InkAppearanceProbe.canon* (Java)
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


def _build_ink() -> PDAnnotationInk:
    ink = PDAnnotationInk()
    # Java probe uses PDRectangle(x=50, y=500, w=200, h=200); pypdfbox's 4-arg
    # ctor is (llx, lly, urx, ury), so translate to (50, 500, 250, 700).
    ink.set_rectangle(PDRectangle(50, 500, 250, 700))
    ink.set_ink_paths(
        [
            [60, 510, 120, 640, 230, 560],
            [80, 520, 240, 690],
        ]
    )
    ink.set_color([1, 0.5, 0])
    bs = PDBorderStyleDictionary()
    bs.set_width(4)
    ink.set_border_style(bs)
    return ink


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "ink.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_ink_appearance_matches_pdfbox_exactly() -> None:
    """The Ink /AP /N path is pure deterministic geometry: rewritten /Rect
    (extended by ±width*2 around the ink extents), /BBox and the full
    operand-level token stream (two m/l/.../S sub-paths) are byte-exact
    against Apache PDFBox."""
    java = _java_records()["Ink"]
    py = _py_fingerprint(_build_ink())

    assert py["bbox"] != "NOAP", "pypdfbox produced no ink /AP /N"
    assert py["rect"] == java["rect"], (
        f"Ink /Rect: {py['rect']!r} != PDFBox {java['rect']!r}"
    )
    assert py["bbox"] == java["bbox"], (
        f"Ink /BBox: {py['bbox']!r} != PDFBox {java['bbox']!r}"
    )
    assert py["toks"] == java["toks"], (
        f"Ink token stream diverges\n"
        f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
        f"  PDFBox   ({len(java['toks'])}): {java['toks']}"  # type: ignore[arg-type]
    )
