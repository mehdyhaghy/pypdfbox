"""Live Apache PDFBox differential parity for LINK annotation appearance
generation — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDLinkAppearanceHandler.generate_normal_appearance`` invoked via
``PDAnnotationLink.construct_appearances()``. Unlike
``test_annotation_appearance_gen_oracle`` (operator NAMES + integer BBox only),
this probe captures the FULL token stream — every operand number/name/array
canonicalised to 3 decimals — so the padded border-edge quad
(``m``/``l``/``l``/``l``/``h``), the dashed-border dash pattern (``[..] 0 d``),
the ``STYLE_UNDERLINE`` single-edge path (no close), the explicit
``/QuadPoints`` sub-paths, the ``/C`` stroke colour (``RG`` or the default
black ``0 G``) and the ``/BBox`` are all caught byte-for-byte.

Wave 1498 (agent B) fixed ``PDAnnotationLink.construct_appearances`` to wire
the ported ``PDLinkAppearanceHandler`` on the default path (it previously fell
through to the base no-op even though the handler was ported), mirroring
upstream ``PDAnnotationLink.java`` lines 236-247.

The Java probe ``LinkAppearanceProbe`` writes six Link annotations (one per
page) covering plain-solid / red-solid / dashed / underline / explicit
quadpoints / out-of-rect-quadpoints-ignored, then in ``read`` mode emits per
annotation ``RECT`` / ``BBOX`` (canonical floats) and one ``TOK`` line per
content-stream token, keyed by ``/Annots`` ordinal (``LINK0`` … ``LINK5``).

Parity contract
---------------
The Link ``/AP /N`` path is deterministic geometry; the ``/BBox`` AND the full
operand-level token sequence (stroke colour, dash pattern, padded border-edge
quad, underline single-edge, explicit quadpoints, out-of-rect fallback to
``/Rect``) are byte-exact against Apache PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLink,
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "LinkAppearanceProbe"


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors LinkAppearanceProbe.canon* (Java)
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
    if isinstance(tok, COSArray):
        parts = []
        for i in range(tok.size()):
            base = tok.get_object(i)
            if isinstance(base, COSNumber):
                parts.append(_canon(base.float_value()))
            else:
                parts.append(str(base))
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


def _py_fingerprint(ann: PDAnnotationLink) -> dict[str, object]:
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
            records[key] = current
            current = None
            key = None
    return records


# ---------------------------------------------------------------------------
# pypdfbox-side builders — mirror LinkAppearanceProbe.write() variant by
# variant. pypdfbox's 4-arg PDRectangle is (llx, lly, urx, ury); the Java probe
# uses (x, y, w, h), so each Rect is translated to lower-left/upper-right form.
# ---------------------------------------------------------------------------


def _border(width: float, style: str) -> PDBorderStyleDictionary:
    bs = PDBorderStyleDictionary()
    bs.set_width(width)
    bs.set_style(style)
    return bs


def _build_links() -> list[PDAnnotationLink]:
    links: list[PDAnnotationLink] = []

    # 0: plain solid border, no /C (black gray 0), width 1
    a0 = PDAnnotationLink()
    a0.set_rectangle(PDRectangle(50, 500, 250, 540))
    a0.set_border_style(_border(1, PDBorderStyleDictionary.STYLE_SOLID))
    links.append(a0)

    # 1: red /C, solid, width 3
    a1 = PDAnnotationLink()
    a1.set_rectangle(PDRectangle(50, 400, 250, 440))
    a1.set_color_components([1, 0, 0])
    a1.set_border_style(_border(3, PDBorderStyleDictionary.STYLE_SOLID))
    links.append(a1)

    # 2: dashed border [3 2], green /C, width 2
    a2 = PDAnnotationLink()
    a2.set_rectangle(PDRectangle(50, 300, 250, 340))
    a2.set_color_components([0, 1, 0])
    dbs = _border(2, PDBorderStyleDictionary.STYLE_DASHED)
    dash = COSArray()
    dash.add(COSInteger.get(3))
    dash.add(COSInteger.get(2))
    dbs.set_dash_style(dash)
    a2.set_border_style(dbs)
    links.append(a2)

    # 3: underline border style (single edge, no close), blue /C, width 2
    a3 = PDAnnotationLink()
    a3.set_rectangle(PDRectangle(50, 200, 250, 240))
    a3.set_color_components([0, 0, 1])
    a3.set_border_style(_border(2, PDBorderStyleDictionary.STYLE_UNDERLINE))
    links.append(a3)

    # 4: explicit /QuadPoints inside /Rect, magenta /C, width 1
    a4 = PDAnnotationLink()
    a4.set_rectangle(PDRectangle(50, 100, 250, 140))
    a4.set_color_components([1, 0, 1])
    a4.set_quad_points([60, 110, 240, 110, 240, 130, 60, 130])
    a4.set_border_style(_border(1, PDBorderStyleDictionary.STYLE_SOLID))
    links.append(a4)

    # 5: /QuadPoints partly OUTSIDE /Rect (ignored → /Rect), width 2
    a5 = PDAnnotationLink()
    a5.set_rectangle(PDRectangle(50, 60, 250, 90))
    a5.set_color_components([0, 0, 0])
    a5.set_quad_points([60, 70, 9999, 70, 9999, 80, 60, 80])
    a5.set_border_style(_border(2, PDBorderStyleDictionary.STYLE_SOLID))
    links.append(a5)

    return links


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "link.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_link_appearance_matches_pdfbox_exactly() -> None:
    """Every Link ``/AP /N`` variant (plain solid, red solid, dashed,
    underline single-edge, explicit quadpoints, out-of-rect quadpoints
    fallback) is byte-exact against Apache PDFBox: ``/BBox`` and the full
    operand-level token stream (stroke colour ``RG`` / default ``0 G``, dash
    pattern ``[..] 0 d``, padded border-edge quad, underline single edge)."""
    java = _java_records()
    links = _build_links()

    assert len(java) == len(links), (
        f"probe wrote {len(links)} links but read {len(java)} annotations"
    )

    for idx, ann in enumerate(links):
        key = f"LINK{idx}"
        assert key in java, f"missing Java record for {key}"
        jrec = java[key]
        py = _py_fingerprint(ann)

        assert py["bbox"] != "NOAP", f"{key}: pypdfbox produced no link /AP /N"
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
