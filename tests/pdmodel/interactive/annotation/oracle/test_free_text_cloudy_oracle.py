"""Live Apache PDFBox differential parity for the FreeText ``/BE`` *cloudy*
border path of ``PDFreeTextAppearanceHandler.generateNormalAppearance``
(the ``borderEffect != null && STYLE_CLOUDY`` branch, java lines 186-204).

Complements ``test_free_text_da_rd_oracle.py`` (plain straight-edged rectangle):
this drives a FreeText whose ``/BE`` carries ``/S /C /I 2`` plus a ``/RD``
rectangle-difference, so the generated ``/AP /N`` op-sequence emits the cloud's
``m``/``c``/``l`` move chain (via :class:`CloudyBorder`) instead of the plain
padded ``re B`` rectangle, and the appearance stream's ``/BBox`` + ``/Matrix``
are re-stamped by ``CloudyBorder``.

Before this wave pypdfbox ignored ``/BE`` on FreeText entirely (always emitted
the plain rectangle — a documented deviation). The cloudy branch is now wired
through ``CloudyBorder`` exactly as the Square/Circle/Polygon handlers do, so
the appearance op-sequence, ``/BBox`` and ``/Matrix`` match Apache PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FreeTextCloudyProbe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors FreeTextCloudyProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _build_free_text() -> PDAnnotationFreeText:
    ft = PDAnnotationFreeText()
    ft.set_rectangle(PDRectangle.from_xywh(100, 500, 240, 120))
    ft.set_contents("cloudy")
    ft.set_color([1, 1, 1])
    ft.set_default_appearance("/Helv 12 Tf 0 0 1 rg")
    ft.set_intent(PDAnnotationFreeText.IT_FREE_TEXT)
    ft.set_rect_differences(5, 7, 9, 11)
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(2.0)
    ft.set_border_effect(be)
    return ft


# ---------------------------------------------------------------------------
# token fingerprint helpers (operator + operands)
# ---------------------------------------------------------------------------


def _operand(token: object) -> str:
    if isinstance(token, COSName):
        return "/" + token.get_name()
    float_value = getattr(token, "float_value", None)
    if callable(float_value):
        return _canon_float(float_value())
    return str(token)


def _tokens(stream) -> list[list[str]]:
    """Return ``[[op, *operands], ...]`` for every operator token in order."""
    parser = PDFStreamParser.from_content_stream(stream)
    rows: list[list[str]] = []
    operands: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        if isinstance(token, Operator):
            rows.append([token.get_name(), *operands])
            operands = []
        else:
            operands.append(_operand(token))
    return rows


def _bbox(stream) -> str:
    bbox = stream.get_bbox()
    if bbox is None:
        return "none"
    return ",".join(
        _canon_float(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


def _matrix(stream) -> str:
    arr = stream.get_cos_object().get_cos_array(COSName.get_pdf_name("Matrix"))
    if arr is None:
        return "none"
    out: list[str] = []
    for i in range(arr.size()):
        element = arr.get_object(i)
        float_value = getattr(element, "float_value", None)
        out.append(_canon_float(float_value()) if callable(float_value) else str(element))
    return ",".join(out)


# ---------------------------------------------------------------------------
# java-side fingerprint parsing
# ---------------------------------------------------------------------------


def _parse_java(text: str) -> dict[str, object]:
    record: dict[str, object] = {"toks": []}
    for raw in text.splitlines():
        if raw.startswith("TOK "):
            record["toks"].append(raw[len("TOK ") :].split(" "))  # type: ignore[union-attr]
        elif raw.startswith("BE "):
            record["BE"] = raw[len("BE ") :]
        elif raw.startswith("RECT "):
            record["RECT"] = raw[len("RECT ") :]
        elif raw.startswith("RD "):
            record["RD"] = raw[len("RD ") :]
        elif raw.startswith("BBOX "):
            record["BBOX"] = raw[len("BBOX ") :]
        elif raw.startswith("MATRIX "):
            record["MATRIX"] = raw[len("MATRIX ") :]
    return record


def _java_record() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "ftcloudy.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_cloudy_border_op_skeleton_matches_pdfbox() -> None:
    """The cloudy /BE FreeText appearance op-sequence (operator names) matches
    Apache PDFBox — the cloud's ``m``/``c``/``l`` move chain replaces the plain
    padded ``re``."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    py_ops = [row[0] for row in _tokens(ft.get_normal_appearance_stream())]
    jr_ops = [row[0] for row in java["toks"]]  # type: ignore[union-attr]
    assert py_ops == jr_ops, (
        f"cloudy FreeText op-sequence diverges\n pypdfbox: {py_ops}\n PDFBox:   {jr_ops}"
    )
    # The cloud emits Bezier curves; pin that the skeleton is NOT the plain path
    # (which would carry a single ``re``).
    assert "c" in py_ops, "cloudy border should emit Bezier curve ops"


@requires_oracle
def test_cloudy_border_bbox_and_matrix_match_pdfbox() -> None:
    """``CloudyBorder`` re-stamps the appearance stream ``/BBox`` and ``/Matrix``;
    both match Apache PDFBox's cloudy FreeText output."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    stream = ft.get_normal_appearance_stream()
    assert stream is not None, "cloudy FreeText produced no /AP /N"
    assert _bbox(stream) == java["BBOX"], (
        f"BBox {_bbox(stream)!r} != PDFBox {java['BBOX']!r}"
    )
    assert _matrix(stream) == java["MATRIX"], (
        f"Matrix {_matrix(stream)!r} != PDFBox {java['MATRIX']!r}"
    )


@requires_oracle
def test_cloudy_border_rect_writeback_matches_pdfbox() -> None:
    """The cloud writes an expanded ``/Rect`` (and a fresh ``/RD``) back onto the
    annotation; both match Apache PDFBox."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    rect = ft.get_rectangle()
    py_rect = ",".join(
        _canon_float(v)
        for v in (
            rect.get_lower_left_x(),
            rect.get_lower_left_y(),
            rect.get_upper_right_x(),
            rect.get_upper_right_y(),
        )
    )
    assert py_rect == java["RECT"], f"Rect {py_rect!r} != PDFBox {java['RECT']!r}"
    rd = ft.get_rect_differences()
    py_rd = ",".join(_canon_float(v) for v in rd) if rd else "null"
    assert py_rd == java["RD"], f"RD {py_rd!r} != PDFBox {java['RD']!r}"
