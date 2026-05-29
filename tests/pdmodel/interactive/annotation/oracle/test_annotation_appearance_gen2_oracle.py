"""Live Apache PDFBox differential parity for the REMAINING non-widget
annotation appearance GENERATION handlers.

This file complements ``test_annotation_appearance_gen_oracle.py`` (wave 1414,
which covered Line / Square / Circle / Polygon / PolyLine / Ink / Highlight).
Here we cover the markup types that wave left untouched:

* ``Text`` (note-icon stamp), ``Caret``, ``FileAttachment`` (push-pin icon),
  ``StrikeOut``, ``Underline``, ``Squiggly``, ``FreeText`` — types with a
  built-in appearance handler.
* ``Popup`` and ``RubberStamp`` (Stamp) — types that have **no** built-in
  appearance handler upstream, so ``constructAppearances`` is a deliberate
  no-op (no ``/AP`` produced). NOAP-on-both-sides is itself the parity fact.

How it works
------------
The Java probe ``AnnotAppear2Probe`` runs in two modes:

* ``write out.pdf`` — builds a page with one of each type (rect, colour,
  ``/Contents``, ``/QuadPoints`` for the text-markup trio, icon ``/Name`` for
  Text + FileAttachment), then calls ``annotation.constructAppearances(doc)``
  on each and saves.
* ``read out.pdf`` — re-opens and emits, per annotation, a coordinate-
  independent fingerprint of its ``/AP /N`` appearance stream:
  ``ANNOT <subtype>`` / ``BBOX <canonical floats>`` (or ``NOAP``) / one
  ``OP:<name>`` per operator token / ``END``.

pypdfbox builds the identical annotations and emits the same fingerprint.
The operator KEYWORD sequence plus the canonical-float ``/BBox`` are compared
exactly, with documented lite-surface divergences normalised (see below).

WAVE-1414 BUG, ALSO PRESENT HERE — FIXED
-----------------------------------------
``construct_appearances()`` on Text / Caret / FileAttachment / StrikeOut /
Underline / Squiggly / FreeText was a no-op on the default (no-custom-handler)
path: the subclass only invoked a *custom* handler and otherwise fell through
to the base no-op, never instantiating the built-in handler that already
exists in ``handlers/``. Upstream's ``constructAppearances(PDDocument)`` always
instantiates the default handler when ``customAppearanceHandler == null``.
Fixed in each ``PDAnnotation*`` subclass to wire the matching handler (the
handlers themselves were already ported — only the wiring was missing). With
the fix every type produces an ``/AP /N`` stream whose bbox matches Apache
PDFBox exactly.

Popup / Stamp legitimately stay NOAP (no upstream handler) and are asserted as
such on both sides.

Documented (NOT fixed — legitimate lite-surface differences)
------------------------------------------------------------
* **Colour-set operator** (Caret, StrikeOut, Underline): upstream calls
  ``cs.setStrokingColor(PDColor)`` / ``setNonStrokingColor(PDColor)`` which,
  for a DeviceRGB colour, emits the colour-space pair ``CS SC`` / ``cs sc``.
  pypdfbox's lite annotation colour surface has no typed ``PDColor`` carrying
  an explicit colour space (deferred to rendering — see ``CHANGES.md``), so
  ``set_stroking_color([r, g, b])`` emits the device shorthand ``RG`` / ``rg``.
  Identical colour, identical path-drawing operators; only the colour-set
  operator spelling differs. This is the same divergence wave 1414 normalised
  for Ink.
* **Squiggly tiling pattern**: upstream paints the zig-zag via a tiling
  pattern wrapped in a form XObject (outer stream ``cm Do``). ``PDFormXObject``
  / pattern emission isn't ported, so the lite handler draws the zig-zag
  polyline inline (``m l l ... S``). ``/BBox`` matches exactly; the draw form
  differs (documented in the handler + ``CHANGES.md``).
* **FileAttachment icon**: upstream draws the icon from a filled
  ``GeneralPath`` glyph (dozens of ``m``/``l``/``c`` ops). The lite handler
  draws a stylized recognisable icon with a small fixed operator set.
  ``/BBox`` matches (18x18); the glyph path differs (documented in the
  handler).
* **FreeText text layout**: upstream word-wraps ``/Contents`` into multiple
  ``Td Tj`` runs; the lite handler lays the text differently. ``/BBox`` and
  the surrounding rectangle/clip/text-object operator skeleton match; the
  number of ``Tj`` runs differs (a content-layout difference, not a drawing
  bug).

Every ``/BBox`` is asserted exact against Apache PDFBox; for the geometric
handlers the full drawing-operator sequence is asserted exact after
normalising the colour-set operator.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCaret,
    PDAnnotationFileAttachment,
    PDAnnotationFreeText,
    PDAnnotationPopup,
    PDAnnotationSquiggly,
    PDAnnotationStrikeout,
    PDAnnotationText,
    PDAnnotationUnderline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "AnnotAppear2Probe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors AnnotAppear2Probe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _bbox_line(stream) -> str:
    bbox = stream.get_bbox()
    if bbox is None:
        return "BBOX none"
    return "BBOX " + ",".join(
        _canon_float(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
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


def _py_fingerprint(ann, subtype: str) -> dict[str, object]:
    """Build the same per-annotation fingerprint pypdfbox would emit."""
    ann.construct_appearances()
    stream = ann.get_normal_appearance_stream()
    if stream is None:
        return {"subtype": subtype, "bbox": "NOAP", "ops": []}
    return {
        "subtype": subtype,
        "bbox": _bbox_line(stream),
        "ops": _operators(stream),
    }


def _parse_java(text: str) -> list[dict[str, object]]:
    """Parse the probe's read-mode output into per-annotation records."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :], "bbox": None, "ops": []}
        elif raw.startswith("BBOX "):
            assert current is not None
            current["bbox"] = raw
        elif raw == "NOAP":
            assert current is not None
            current["bbox"] = "NOAP"
        elif raw.startswith("OP:"):
            assert current is not None
            current["ops"].append(raw[len("OP:") :])  # type: ignore[union-attr]
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
    return records


def _rect(x: float, y: float, w: float, h: float) -> PDRectangle:
    """Mirror Java's ``new PDRectangle(x, y, width, height)``.

    pypdfbox's ``PDRectangle(llx, lly, urx, ury)`` takes corner coordinates,
    so the ``(x, y, w, h)`` Java overload maps to ``from_xywh`` — matching the
    convention wave 1414's battery used.
    """
    return PDRectangle.from_xywh(x, y, w, h)


def _build_battery() -> list[tuple[object, str]]:
    """Build the same annotation battery as AnnotAppear2Probe.write."""

    def rgb(r: float, g: float, b: float) -> list[float]:
        return [r, g, b]

    text = PDAnnotationText()
    text.set_rectangle(_rect(50, 750, 20, 20))
    text.set_name(PDAnnotationText.NAME_NOTE)
    text.set_color(rgb(1, 1, 0))
    text.set_contents("a note")

    caret = PDAnnotationCaret()
    caret.set_rectangle(_rect(100, 700, 30, 30))
    caret.set_color(rgb(1, 0, 1))

    file_attachment = PDAnnotationFileAttachment()
    file_attachment.set_rectangle(_rect(150, 700, 30, 30))
    file_attachment.set_attachment_name(
        PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN
    )
    file_attachment.set_color(rgb(0, 0, 0))

    strike = PDAnnotationStrikeout()
    strike.set_rectangle(_rect(50, 600, 250, 20))
    strike.set_quad_points([50, 616, 300, 616, 50, 604, 300, 604])
    strike.set_color(rgb(1, 0, 0))

    underline = PDAnnotationUnderline()
    underline.set_rectangle(_rect(50, 560, 250, 20))
    underline.set_quad_points([50, 576, 300, 576, 50, 564, 300, 564])
    underline.set_color(rgb(0, 0, 1))

    squiggly = PDAnnotationSquiggly()
    squiggly.set_rectangle(_rect(50, 520, 250, 20))
    squiggly.set_quad_points([50, 536, 300, 536, 50, 524, 300, 524])
    squiggly.set_color(rgb(0, 1, 0))

    free_text = PDAnnotationFreeText()
    free_text.set_rectangle(_rect(50, 350, 200, 100))
    free_text.set_contents("Free text content")
    free_text.set_color(rgb(0, 0, 0))
    free_text.set_default_appearance("/Helv 12 Tf 0 g")

    popup = PDAnnotationPopup()
    popup.set_rectangle(_rect(300, 350, 150, 100))

    stamp = PDAnnotationRubberStamp()
    stamp.set_rectangle(_rect(300, 200, 150, 100))
    stamp.set_name(PDAnnotationRubberStamp.NAME_TOP_SECRET)

    return [
        (text, "Text"),
        (caret, "Caret"),
        (file_attachment, "FileAttachment"),
        (strike, "StrikeOut"),
        (underline, "Underline"),
        (squiggly, "Squiggly"),
        (free_text, "FreeText"),
        (popup, "Popup"),
        (stamp, "Stamp"),
    ]


# ---------------------------------------------------------------------------
# documented, normalised colour-set divergence (see module docstring)
#
# Upstream emits the colour-space operator pair per colour-set (CS/SC stroking,
# cs/sc non-stroking); the lite surface emits the device shorthand RG/rg.
# Normalising means collapsing each {CS,SC,cs,sc} into the {RG,rg} the lite
# stream produces so the path-drawing operators line up.
# ---------------------------------------------------------------------------

_JAVA_COLOR_OPS = {"CS", "SC", "cs", "sc"}
# Handlers that mirror an upstream ``setStrokingColor(getColor())`` (e.g. Caret)
# now emit the verbose ``/DeviceRGB CS … SC`` form byte-for-byte; the remaining
# lite-surface handlers still emit the device shorthand ``RG``/``rg``. Strip
# both spellings so this test isolates the *path-drawing* operator sequence.
_PY_COLOR_OPS = {"RG", "rg", "G", "g", "CS", "SC", "cs", "sc"}


def _strip_color_ops(ops: list[str], color_ops: set[str]) -> list[str]:
    """Drop colour-set operators so the drawing-operator sequence can be
    compared regardless of the colour-set spelling."""
    return [op for op in ops if op not in color_ops]


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "annot_appear2.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return {rec["subtype"]: rec for rec in _parse_java(text)}


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_all_remaining_types_bbox_matches_pdfbox() -> None:
    """Every remaining markup type's ``/AP /N`` ``/BBox`` matches Apache
    PDFBox exactly (the wave-1414 default-path-no-op bug, present on these
    types too, is fixed), and Popup / Stamp stay NOAP on both sides."""
    java = _java_records()
    for ann, subtype in _build_battery():
        py = _py_fingerprint(ann, subtype)
        jr = java[subtype]
        assert py["bbox"] == jr["bbox"], (
            f"{subtype}: bbox {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )


@requires_oracle
def test_popup_and_stamp_have_no_appearance() -> None:
    """Popup and RubberStamp have no built-in appearance handler upstream, so
    ``constructAppearances`` produces no ``/AP /N`` — NOAP on both sides."""
    java = _java_records()
    battery = {sub: ann for ann, sub in _build_battery()}
    for subtype in ("Popup", "Stamp"):
        py = _py_fingerprint(battery[subtype], subtype)
        assert py["bbox"] == "NOAP", f"{subtype}: pypdfbox unexpectedly produced /AP"
        assert java[subtype]["bbox"] == "NOAP", f"{subtype}: PDFBox produced /AP"


@requires_oracle
def test_geometric_handlers_operator_sequence_exact() -> None:
    """Text, Caret, StrikeOut, Underline are geometric (path-drawing) handlers:
    after normalising the documented colour-set operator divergence, the full
    drawing-operator sequence matches Apache PDFBox exactly."""
    java = _java_records()
    battery = {sub: ann for ann, sub in _build_battery()}
    for subtype in ("Text", "Caret", "StrikeOut", "Underline"):
        py = _py_fingerprint(battery[subtype], subtype)
        jr = java[subtype]
        assert py["bbox"] != "NOAP", f"{subtype}: pypdfbox produced no /AP /N"
        py_ops = _strip_color_ops(list(py["ops"]), _PY_COLOR_OPS)  # type: ignore[arg-type]
        jr_ops = _strip_color_ops(list(jr["ops"]), _JAVA_COLOR_OPS)  # type: ignore[arg-type]
        assert py_ops == jr_ops, (
            f"{subtype}: drawing-operator sequence diverges\n"
            f"  pypdfbox: {py_ops}\n  PDFBox:   {jr_ops}"
        )


@requires_oracle
def test_squiggly_filewattach_freetext_bbox_and_draw_present() -> None:
    """Squiggly (tiling-pattern vs inline zig-zag), FileAttachment (glyph vs
    stylized icon) and FreeText (text layout) are documented draw-form
    divergences. Assert the contract that survives: an ``/AP /N`` stream with
    the exact bbox and a non-empty drawing-operator sequence on both sides."""
    java = _java_records()
    battery = {sub: ann for ann, sub in _build_battery()}
    for subtype in ("Squiggly", "FileAttachment", "FreeText"):
        py = _py_fingerprint(battery[subtype], subtype)
        jr = java[subtype]
        assert py["bbox"] != "NOAP", f"{subtype}: pypdfbox produced no /AP /N"
        assert jr["bbox"] != "NOAP", f"{subtype}: PDFBox produced no /AP /N"
        assert py["bbox"] == jr["bbox"], (
            f"{subtype}: bbox {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )
        assert py["ops"], f"{subtype}: pypdfbox emitted no operators"
        assert jr["ops"], f"{subtype}: PDFBox emitted no operators"


@requires_oracle
def test_squiggly_draws_a_path_freetext_lays_text() -> None:
    """Sharper assertions on the two richest documented divergences: the lite
    Squiggly stroke actually strokes a polyline; the lite FreeText emits a
    text object that shows the contents."""
    java = _java_records()
    battery = {sub: ann for ann, sub in _build_battery()}

    squiggly = _py_fingerprint(battery["Squiggly"], "Squiggly")
    sq_ops = list(squiggly["ops"])  # type: ignore[arg-type]
    # Lite handler strokes an inline zig-zag (m + many l + S); upstream uses
    # a tiling pattern (cm Do).
    assert "S" in sq_ops and sq_ops.count("l") >= 1, sq_ops
    assert java["Squiggly"]["ops"][-1:] == ["Do"], java["Squiggly"]["ops"]

    free_text = _py_fingerprint(battery["FreeText"], "FreeText")
    ft_ops = list(free_text["ops"])  # type: ignore[arg-type]
    # Both wrap the text in a BT ... ET object with at least one Tj show.
    assert "BT" in ft_ops and "ET" in ft_ops and "Tj" in ft_ops, ft_ops
    assert "BT" in java["FreeText"]["ops"] and "Tj" in java["FreeText"]["ops"]
