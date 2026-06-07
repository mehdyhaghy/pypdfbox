"""Live Apache PDFBox differential parity for FILE-ATTACHMENT annotation
appearance generation — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDFileAttachmentAppearanceHandler.generate_normal_appearance`` invoked via
``PDAnnotationFileAttachment.construct_appearances()``, for each of the four
standard attachment icons: PushPin (default), Paperclip, Graph, Tag.

Earlier waves (``test_annotation_appearance_gen2_oracle.py``) only asserted the
``/BBox`` and treated the icon glyph as a documented "stylized icon vs filled
glyph path" lite-surface divergence — the four draw helpers drew rough,
recognisable approximations rather than the exact SVG-derived paths upstream
emits. This file closes that gap: the handler now ports the exact upstream
``drawPushPin`` / ``drawPaperclip`` / ``drawGraph`` / ``drawTag`` glyph paths
(the same CC0 / Apache SVG sources, scale ``0.022`` and translate matrices),
so the FULL token stream — every operand number/name canonicalised to 3
decimals — matches Apache PDFBox byte-for-byte. A wrong control point, a wrong
scale/translate ``cm`` matrix, a missing ``q``/``Q`` (Tag wraps each of its two
sub-shapes in a save/restore), a wrong icon dispatch, or a wrongly-rewritten
``/Rect`` / ``/BBox`` is caught.

The Java probe ``FileAttachmentIconProbe`` runs in two modes:

* ``write out.pdf`` — builds four FileAttachment annotations (one per icon,
  ``/Rect`` 30x30, no colour) and calls ``constructAppearances(doc)`` and saves.
* ``read out.pdf`` — emits per annotation ``RECT`` / ``BBOX`` (canonical floats)
  and one ``TOK`` line per content-stream token (operator keyword, canonical
  number, or ``/Name``), keyed ``FA0`` … ``FA3`` by ``/Annots`` ordinal.

Parity contract
---------------
All four icons are pure deterministic glyph paths — the rewritten ``/Rect``
(reduced to the 18-pt glyph square anchored at the upper-left of the original
``/Rect``), the ``/BBox`` (``0 0 18 18``) AND the full operand-level token
sequence are byte-exact against Apache PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationFileAttachment
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FileAttachmentIconProbe"

_ICON_NAMES = (
    PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN,
    PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP,
    PDAnnotationFileAttachment.ATTACHMENT_NAME_GRAPH,
    PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG,
)


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors FileAttachmentIconProbe.canon* (Java)
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
        return {"rect": _canon_rect(ann.get_rectangle()), "bbox": "NOAP", "toks": []}
    return {
        "rect": _canon_rect(ann.get_rectangle()),
        "bbox": _canon_rect(stream.get_bbox()),
        "toks": _tokens(stream),
    }


def _parse_java(text: str) -> list[dict[str, object]]:
    """Parse into an ordered list (one record per /Annots ordinal)."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
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
            assert current is not None
            records.append(current)
            current = None
    return records


def _build_battery() -> list[PDAnnotationFileAttachment]:
    """Mirror FileAttachmentIconProbe.write — four icons, /Rect 30x30."""
    battery: list[PDAnnotationFileAttachment] = []
    y = 700
    for name in _ICON_NAMES:
        fa = PDAnnotationFileAttachment()
        # Java probe uses PDRectangle(x=50, y, w=30, h=30) → from_xywh.
        fa.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
        fa.set_attachment_name(name)
        battery.append(fa)
        y -= 50
    return battery


def _java_records() -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "file_attachment.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


@requires_oracle
def test_file_attachment_icons_match_pdfbox_exactly() -> None:
    """All four file-attachment icons (PushPin / Paperclip / Graph / Tag) are
    deterministic SVG-derived glyph paths: the rewritten /Rect, the /BBox
    (0 0 18 18) and the full operand-level token stream are byte-exact against
    Apache PDFBox."""
    java = _java_records()
    battery = _build_battery()
    assert len(java) == len(battery), (
        f"probe wrote {len(java)} annots, battery has {len(battery)}"
    )
    for ann, name, jr in zip(battery, _ICON_NAMES, java, strict=True):
        py = _py_fingerprint(ann)
        assert py["bbox"] != "NOAP", f"{name}: pypdfbox produced no /AP /N"
        assert py["rect"] == jr["rect"], (
            f"{name} /Rect: {py['rect']!r} != PDFBox {jr['rect']!r}"
        )
        assert py["bbox"] == jr["bbox"], (
            f"{name} /BBox: {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )
        assert py["toks"] == jr["toks"], (
            f"{name} token stream diverges\n"
            f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
            f"  PDFBox   ({len(jr['toks'])}): {jr['toks']}"  # type: ignore[arg-type]
        )
