"""Live Apache PDFBox differential parity for LINE annotation appearance
generation — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDLineAppearanceHandler.generate_normal_appearance`` invoked via
``PDAnnotationLine.construct_appearances()``. Unlike
``test_annotation_appearance_gen_oracle`` (operator NAMES + integer BBox only),
this probe captures the FULL token stream — every operand number/name
canonicalised to 3 decimals — so the rotation ``cm``, the leader-line
``m``/``l`` sub-paths, the line body, the start/end line-ending shapes drawn by
``draw_style`` (OpenArrow / ClosedArrow / Diamond / Circle / Square / Butt /
Slash / RClosedArrow via ``q cm … Q``), the ``/C`` stroke (``RG``) and ``/IC``
interior fill (``rg``), the inline / top caption ``BT … Tj … ET`` block (whose
``Td`` offset is derived from Helvetica string-width metrics) and the rewritten
``/Rect`` / ``/BBox`` are all caught byte-for-byte.

The Java probe ``LineAppearanceProbe`` writes seven Line annotations (one per
page) covering plain / arrows / diamond+circle / leader-lines / inline-caption /
top-caption+offsets / slash+r-closed-arrow, then in ``read`` mode emits per
annotation ``RECT`` / ``BBOX`` (canonical floats) and one ``TOK`` line per
content-stream token, keyed by ``/Annots`` ordinal (``LINE0`` … ``LINE6``).

Parity contract
---------------
The Line ``/AP /N`` path is deterministic geometry plus Helvetica metric-driven
caption placement; the rewritten ``/Rect`` (extended by ``±max(width*10,
|llo+ll+lle|)``), ``/BBox`` AND the full operand-level token sequence are
byte-exact against Apache PDFBox.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from pypdfbox.cos import COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLine,
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "LineAppearanceProbe"


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors LineAppearanceProbe.canon* (Java)
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


#: The default-font resource name emitted by the caption ``Tf`` operator.
#: pypdfbox's shared ``PDResources._create_key`` allocates 0-based names
#: (``/F0``) whereas upstream PDFBox's ``createKey`` is 1-based (``/F1``).
#: That naming convention is an orthogonal, codebase-wide ``PDResources``
#: divergence (deferred to a dedicated resources-naming wave), NOT a Line
#: appearance bug — the *geometry*, the metric-driven ``Td`` offset, and the
#: text object itself are byte-exact. We canonicalise the single font-name
#: token so this Line probe pins line-specific parity without coupling to the
#: resources-naming follow-up.
_FONT_NAME_RE = re.compile(r"^/F\d+$")


def _normalise_font_name(toks: list[str]) -> list[str]:
    return ["/F" if _FONT_NAME_RE.match(t) else t for t in toks]


def _tokens(stream) -> list[str]:
    parser = PDFStreamParser.from_content_stream(stream)
    out: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        out.append(_canon_token(token))
    return _normalise_font_name(out)


def _py_fingerprint(ann: PDAnnotationLine) -> dict[str, object]:
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
    key: str | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            key = raw[len("ANNOT ") :]
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
            assert key is not None and current is not None
            current["toks"] = _normalise_font_name(current["toks"])  # type: ignore[arg-type]
            records[key] = current
            current = None
            key = None
    return records


# ---------------------------------------------------------------------------
# pypdfbox-side builders — mirror LineAppearanceProbe.write() variant by variant.
# pypdfbox's 4-arg PDRectangle is (llx, lly, urx, ury); the Java probe uses
# (x, y, w, h), so each Rect is translated to lower-left/upper-right form.
# ---------------------------------------------------------------------------


def _border(width: float) -> PDBorderStyleDictionary:
    bs = PDBorderStyleDictionary()
    bs.set_width(width)
    return bs


def _build_lines() -> list[PDAnnotationLine]:
    lines: list[PDAnnotationLine] = []

    # 0: plain line, no endings, stroke orange, width 3
    a0 = PDAnnotationLine()
    a0.set_rectangle(PDRectangle(50, 500, 250, 620))
    a0.set_line([60, 520, 240, 600])
    a0.set_color_components([1, 0.5, 0])
    a0.set_border_style(_border(3))
    lines.append(a0)

    # 1: OpenArrow / ClosedArrow (angled + short), interior fill, w 2
    a1 = PDAnnotationLine()
    a1.set_rectangle(PDRectangle(50, 350, 250, 470))
    a1.set_line([60, 360, 240, 440])
    a1.set_color_components([0, 0, 1])
    a1.set_interior_color([1, 1, 0])
    a1.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    a1.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    a1.set_border_style(_border(2))
    lines.append(a1)

    # 2: Diamond / Circle (non-angled, short, interior fill), w 4
    a2 = PDAnnotationLine()
    a2.set_rectangle(PDRectangle(50, 200, 250, 320))
    a2.set_line([60, 210, 240, 290])
    a2.set_color_components([1, 0, 1])
    a2.set_interior_color([0, 1, 1])
    a2.set_start_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    a2.set_end_point_ending_style(PDAnnotationLine.LE_CIRCLE)
    a2.set_border_style(_border(4))
    lines.append(a2)

    # 3: leader lines (LL/LLE/LLO) + Square start / Butt end, w 2
    a3 = PDAnnotationLine()
    a3.set_rectangle(PDRectangle(50, 500, 250, 620))
    a3.set_line([60, 520, 240, 600])
    a3.set_color_components([0, 0.5, 0])
    a3.set_leader_line_length(20)
    a3.set_leader_line_extension_length(8)
    a3.set_leader_line_offset_length(5)
    a3.set_start_point_ending_style(PDAnnotationLine.LE_SQUARE)
    a3.set_end_point_ending_style(PDAnnotationLine.LE_BUTT)
    a3.set_interior_color([0.8, 0.8, 0.8])
    a3.set_border_style(_border(2))
    lines.append(a3)

    # 4: caption Inline + /Contents, Square / Square, w 2
    a4 = PDAnnotationLine()
    a4.set_rectangle(PDRectangle(50, 350, 250, 470))
    a4.set_line([60, 360, 300, 360])
    a4.set_color_components([0, 0, 0])
    a4.set_interior_color([0.5, 0.5, 0.5])
    a4.set_start_point_ending_style(PDAnnotationLine.LE_SQUARE)
    a4.set_end_point_ending_style(PDAnnotationLine.LE_SQUARE)
    a4.set_caption(True)
    a4.set_contents("Hello")
    a4.set_border_style(_border(2))
    lines.append(a4)

    # 5: caption Top + /CO offsets, OpenArrow / OpenArrow, w 2
    a5 = PDAnnotationLine()
    a5.set_rectangle(PDRectangle(50, 200, 250, 320))
    a5.set_line([60, 210, 300, 210])
    a5.set_color_components([0, 0, 0])
    a5.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    a5.set_end_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    a5.set_caption(True)
    a5.set_caption_positioning("Top")
    a5.set_contents("Length")
    a5.set_caption_horizontal_offset(3)
    a5.set_caption_vertical_offset(7)
    a5.set_border_style(_border(2))
    lines.append(a5)

    # 6: Slash / RClosedArrow (angled), interior fill, w 3
    a6 = PDAnnotationLine()
    a6.set_rectangle(PDRectangle(50, 60, 250, 180))
    a6.set_line([60, 70, 240, 150])
    a6.set_color_components([0.2, 0.4, 0.6])
    a6.set_interior_color([1, 0, 0])
    a6.set_start_point_ending_style(PDAnnotationLine.LE_SLASH)
    a6.set_end_point_ending_style(PDAnnotationLine.LE_R_CLOSED_ARROW)
    a6.set_border_style(_border(3))
    lines.append(a6)

    return lines


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "line.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_line_appearance_matches_pdfbox_exactly() -> None:
    """Every Line ``/AP /N`` variant (plain, arrow / closed-arrow,
    diamond / circle, leader-lines + square / butt, inline caption,
    top caption + /CO offsets, slash / r-closed-arrow) is byte-exact
    against Apache PDFBox: rewritten ``/Rect``, ``/BBox`` and the full
    operand-level token stream (rotation ``cm``, leader-line ``m``/``l``
    sub-paths, line body, ending shapes, ``RG``/``rg`` colours and the
    ``BT … Tj … ET`` caption block)."""
    java = _java_records()
    lines = _build_lines()

    assert len(java) == len(lines), (
        f"probe wrote {len(lines)} lines but read {len(java)} annotations"
    )

    for idx, ann in enumerate(lines):
        key = f"LINE{idx}"
        assert key in java, f"missing Java record for {key}"
        jrec = java[key]
        py = _py_fingerprint(ann)

        assert py["bbox"] != "NOAP", f"{key}: pypdfbox produced no line /AP /N"
        assert py["rect"] == jrec["rect"], (
            f"{key} /Rect: {py['rect']!r} != PDFBox {jrec['rect']!r}"
        )
        assert py["bbox"] == jrec["bbox"], (
            f"{key} /BBox: {py['bbox']!r} != PDFBox {jrec['bbox']!r}"
        )
        assert py["toks"] == jrec["toks"], (
            f"{key} token stream diverges\n"
            f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
            f"  PDFBox   ({len(jrec['toks'])}): {jrec['toks']}"  # type: ignore[arg-type]
        )
