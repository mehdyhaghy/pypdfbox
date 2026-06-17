"""Live Apache PDFBox differential parity for STAMP
(``PDAnnotationRubberStamp``) and CARET (``PDAnnotationCaret``) annotations.

Surfaces under test
--------------------
* ``PDAnnotationRubberStamp`` — the standard-icon ``/Name`` accessor:
  ``get_name`` (default ``Draft`` when ``/Name`` is absent) and ``set_name``.
  Several rubber stamps are written with different ``/Name`` values (and one
  with none, to pin the ``NAME_DRAFT`` default), then read back.
* ``PDAnnotationCaret`` — ``get_rectangle_differences`` /
  ``set_rect_differences*`` AND the operand-level ``/AP /N`` content generated
  by ``PDCaretAppearanceHandler`` via ``construct_appearances``. The no-``/RD``
  path auto-creates ``/RD = min(height/10, 5)`` on all four sides and enlarges
  ``/Rect`` + ``/BBox``; a pre-set ``/RD`` leaves ``/Rect`` untouched and uses
  the rect-sized BBox. The filled-Bezier caret "tooth" token stream, the
  rewritten ``/Rect``, the ``/BBox`` and the resolved ``/RD`` are all asserted
  byte-for-byte against Apache PDFBox 3.0.7.

The Java probe ``StampCaretProbe`` writes the annotations (``write`` mode) and
emits per-annotation records (``read`` mode), keyed ``STAMP0…`` / ``CARET0…``
by ``/Annots`` ordinal.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCaret,
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "StampCaretProbe"


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors StampCaretProbe.canon* (Java)
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


def _canon_rd(rd) -> str:
    if not rd:
        return "empty"
    return ",".join(_canon(v) for v in rd)


# ---------------------------------------------------------------------------
# parse the probe's read-mode output
# ---------------------------------------------------------------------------


def _parse_java(text: str) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    key: str | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            key = raw[len("ANNOT ") :]
            current = {"toks": []}
        elif raw.startswith("NAME "):
            current["name"] = raw[len("NAME ") :]  # type: ignore[index]
        elif raw.startswith("RD "):
            current["rd"] = raw[len("RD ") :]  # type: ignore[index]
        elif raw.startswith("RECT "):
            current["rect"] = raw[len("RECT ") :]  # type: ignore[index]
        elif raw.startswith("BBOX "):
            current["bbox"] = raw[len("BBOX ") :]  # type: ignore[index]
        elif raw.startswith("TOK "):
            current["toks"].append(raw[len("TOK ") :])  # type: ignore[union-attr,index]
        elif raw == "END":
            assert key is not None and current is not None
            records[key] = current
            current = None
            key = None
    return records


# ---------------------------------------------------------------------------
# pypdfbox-side builders — mirror StampCaretProbe.write() variant by variant.
# pypdfbox's 4-arg PDRectangle is (llx, lly, urx, ury); the Java probe uses
# (x, y, w, h), so each Rect is translated to lower-left/upper-right form.
# ---------------------------------------------------------------------------


def _build_stamps() -> list[PDAnnotationRubberStamp]:
    stamps: list[PDAnnotationRubberStamp] = []

    # 0: no /Name set -> get_name() defaults to DRAFT
    s0 = PDAnnotationRubberStamp()
    s0.set_rectangle(PDRectangle(50, 700, 200, 740))
    stamps.append(s0)

    # 1: Approved
    s1 = PDAnnotationRubberStamp()
    s1.set_rectangle(PDRectangle(50, 650, 200, 690))
    s1.set_name(PDAnnotationRubberStamp.NAME_APPROVED)
    stamps.append(s1)

    # 2: Confidential
    s2 = PDAnnotationRubberStamp()
    s2.set_rectangle(PDRectangle(50, 600, 200, 640))
    s2.set_name(PDAnnotationRubberStamp.NAME_CONFIDENTIAL)
    stamps.append(s2)

    # 3: TopSecret
    s3 = PDAnnotationRubberStamp()
    s3.set_rectangle(PDRectangle(50, 550, 200, 590))
    s3.set_name(PDAnnotationRubberStamp.NAME_TOP_SECRET)
    stamps.append(s3)

    # 4: non-standard custom name
    s4 = PDAnnotationRubberStamp()
    s4.set_rectangle(PDRectangle(50, 500, 200, 540))
    s4.set_name("MyCustomStamp")
    stamps.append(s4)

    # 5: explicitly Draft (matches default, present in dict)
    s5 = PDAnnotationRubberStamp()
    s5.set_rectangle(PDRectangle(50, 450, 200, 490))
    s5.set_name(PDAnnotationRubberStamp.NAME_DRAFT)
    stamps.append(s5)

    return stamps


def _build_carets() -> list[PDAnnotationCaret]:
    carets: list[PDAnnotationCaret] = []

    # 0: no /RD -> handler auto-creates /RD + enlarges rect
    c0 = PDAnnotationCaret()
    c0.set_rectangle(PDRectangle(100, 600, 180, 640))
    c0.set_color_components([1, 0, 0])
    carets.append(c0)

    # 1: pre-set uniform /RD -> rect untouched, rect-sized bbox
    c1 = PDAnnotationCaret()
    c1.set_rectangle(PDRectangle(100, 400, 180, 440))
    c1.set_color_components([0, 0, 1])
    c1.set_rect_differences_uniform(3)
    carets.append(c1)

    # 2: pre-set LRTB /RD
    c2 = PDAnnotationCaret()
    c2.set_rectangle(PDRectangle(100, 200, 160, 300))
    c2.set_color_components([0.2, 0.4, 0.6])
    c2.set_rect_differences_lrtb(2, 4, 6, 8)
    carets.append(c2)

    # 3: tall rect, no /RD -> rd capped at 5 (height/10 > 5)
    c3 = PDAnnotationCaret()
    c3.set_rectangle(PDRectangle(100, 100, 150, 220))
    c3.set_color_components([0, 0.5, 0])
    carets.append(c3)

    return carets


def _stamp_fingerprint(ann: PDAnnotationRubberStamp) -> dict[str, object]:
    return {"name": ann.get_name()}


def _caret_fingerprint(ann: PDAnnotationCaret) -> dict[str, object]:
    ann.construct_appearances()
    stream = ann.get_normal_appearance_stream()
    rec: dict[str, object] = {
        "rd": _canon_rd(ann.get_rectangle_differences()),
        "rect": _canon_rect(ann.get_rectangle()),
    }
    if stream is None:
        rec["bbox"] = "NOAP"
        return rec
    rec["bbox"] = _canon_rect(stream.get_bbox())
    rec["toks"] = _tokens(stream)
    return rec


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "stamp_caret.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_rubber_stamp_name_matches_pdfbox_exactly() -> None:
    """Every rubber-stamp ``/Name`` round-trips identically to Apache PDFBox:
    the four standard icons, a custom non-standard name, an explicit ``Draft``,
    and (critically) the ``NAME_DRAFT`` default substituted by ``get_name``
    when ``/Name`` is absent."""
    java = _java_records()
    stamps = _build_stamps()

    for idx, ann in enumerate(stamps):
        key = f"STAMP{idx}"
        assert key in java, f"missing Java record for {key}"
        py = _stamp_fingerprint(ann)
        assert py["name"] == java[key]["name"], (
            f"{key} /Name: {py['name']!r} != PDFBox {java[key]['name']!r}"
        )


@requires_oracle
def test_caret_appearance_matches_pdfbox_exactly() -> None:
    """Every caret ``/AP /N`` variant is byte-exact against Apache PDFBox:
    the auto-created ``/RD`` (``min(height/10, 5)`` on all sides), the
    rewritten ``/Rect`` (no-``/RD`` path enlarges it; pre-set ``/RD`` leaves
    it untouched), the ``/BBox`` and the full filled-Bezier caret token
    stream (``CS``/``cs`` colour space, ``SC``/``sc`` stroke+fill colour,
    the two ``c`` curves, ``h`` close, ``f`` fill)."""
    java = _java_records()
    carets = _build_carets()

    for idx, ann in enumerate(carets):
        key = f"CARET{idx}"
        assert key in java, f"missing Java record for {key}"
        jrec = java[key]
        py = _caret_fingerprint(ann)

        assert py["bbox"] != "NOAP", f"{key}: pypdfbox produced no caret /AP /N"
        assert py["rd"] == jrec["rd"], (
            f"{key} /RD: {py['rd']!r} != PDFBox {jrec['rd']!r}"
        )
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
