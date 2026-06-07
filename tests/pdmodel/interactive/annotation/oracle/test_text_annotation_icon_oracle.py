"""Live Apache PDFBox differential parity for TEXT (sticky-note) annotation
appearance generation — the OPERAND-LEVEL ``/AP /N`` content.

Surface under test
------------------
``PDTextAppearanceHandler.generate_normal_appearance`` invoked via
``PDAnnotationText.construct_appearances()``, for the standard sticky-note icon
names this wave pins byte-for-byte against Apache PDFBox 3.0.7:

* ``Note`` — notebook glyph (already exact in earlier waves; pinned here as a
  negative control plus the colour-set variant).
* ``Comment`` / ``Key`` — Font-Awesome SVG glyph paths (already exact; pinned).
* ``Help`` / ``Paragraph`` / ``NewParagraph`` — these previously emitted
  hand-built approximations because pypdfbox has not ported
  ``Standard14Fonts.getGlyphPath``. Wave 1508 embeds the exact upstream glyph
  outlines (Helvetica-Bold ``question``, Helvetica ``paragraph``,
  Helvetica-Bold ``N`` + ``P``) so the full operand stream matches.
* ``Insert`` — caret triangle (already exact; pinned).
* default/unknown ``/Name`` — Apache PDFBox produces NO appearance stream
  (``NOAP``); pypdfbox's early return matches.
* missing ``/Name`` — ``getName()`` defaults to ``Note``; the full Note stream
  is produced.

Colour is varied on two icons (red ``Note`` / green ``Insert``) to pin the
``setNonStrokingColor(PDColor)`` path: Apache PDFBox emits ``/DeviceRGB cs r g b
sc`` (colour-space + ``cs`` + components + ``sc``), never the device shorthand
``rg``. Wave 1508 wraps the raw ``/C`` components in a ``PDColor`` to match.

Known divergence tolerated
--------------------------
The ext-gstate halo resource key differs by a constant: pypdfbox allocates
0-based (``/gs0``) while Apache PDFBox allocates 1-based (``/gs1``) — a
codebase-wide resource-key numbering divergence documented in
``CHANGES.md`` and already tolerated by the image-extract oracle. The trailing
digit of an auto-allocated ``/gs<n>`` token is normalised on both sides so the
glyph geometry — the substance of this test — is what is compared. The
ext-gstate *contents* (CA / ca = 0.6, a non-null blend mode) are pinned exactly.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from pypdfbox.cos import COSArray, COSFloat, COSName, COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "TextAnnotationIconProbe"

# The 16 standard names, in the order the probe writes them.
_STANDARD_NAMES = (
    PDAnnotationText.NAME_NOTE,
    PDAnnotationText.NAME_COMMENT,
    PDAnnotationText.NAME_KEY,
    PDAnnotationText.NAME_HELP,
    PDAnnotationText.NAME_NEW_PARAGRAPH,
    PDAnnotationText.NAME_PARAGRAPH,
    PDAnnotationText.NAME_INSERT,
    PDAnnotationText.NAME_CIRCLE,
    PDAnnotationText.NAME_CROSS,
    PDAnnotationText.NAME_STAR,
    PDAnnotationText.NAME_CHECK,
    PDAnnotationText.NAME_RIGHT_ARROW,
    PDAnnotationText.NAME_RIGHT_POINTER,
    PDAnnotationText.NAME_UP_ARROW,
    PDAnnotationText.NAME_UP_LEFT_ARROW,
    PDAnnotationText.NAME_CROSS_HAIRS,
)

# Names whose operand stream is pinned byte-exact. As of wave 1509 this is the
# FULL standard icon set — the ZapfDingbats / Symbol glyph icons (Cross / Star /
# Check / RightPointer / CrossHairs) that previously used hand-built
# approximations now embed the exact upstream Standard-14 glyph outlines, so
# every icon's operand stream is asserted here.
_PINNED_NAMES = frozenset(
    {
        PDAnnotationText.NAME_NOTE,
        PDAnnotationText.NAME_COMMENT,
        PDAnnotationText.NAME_KEY,
        PDAnnotationText.NAME_HELP,
        PDAnnotationText.NAME_NEW_PARAGRAPH,
        PDAnnotationText.NAME_PARAGRAPH,
        PDAnnotationText.NAME_INSERT,
        PDAnnotationText.NAME_CIRCLE,
        PDAnnotationText.NAME_CROSS,
        PDAnnotationText.NAME_STAR,
        PDAnnotationText.NAME_CHECK,
        PDAnnotationText.NAME_RIGHT_ARROW,
        PDAnnotationText.NAME_RIGHT_POINTER,
        PDAnnotationText.NAME_UP_ARROW,
        PDAnnotationText.NAME_UP_LEFT_ARROW,
        PDAnnotationText.NAME_CROSS_HAIRS,
    }
)

# (name, rgb) colour variants the probe writes after the 16 standard icons.
_COLOUR_VARIANTS = (
    (PDAnnotationText.NAME_NOTE, (1.0, 0.0, 0.0)),
    (PDAnnotationText.NAME_INSERT, (0.0, 1.0, 0.0)),
)

# Matches an auto-allocated ext-gstate resource slot: /gs0, /gs1, ...
_GS_TOKEN = re.compile(r"^/gs\d+$")


# ---------------------------------------------------------------------------
# canonical token rendering — mirrors TextAnnotationIconProbe.canon* (Java)
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


def _normalise_gs(token: str) -> str:
    """Collapse an auto-allocated ``/gs<n>`` slot to ``/gs#`` so the
    documented 0-based vs 1-based resource-key divergence does not mask the
    glyph-geometry comparison."""
    return "/gs#" if _GS_TOKEN.match(token) else token


def _canon_token(tok) -> str:
    if isinstance(tok, Operator):
        return tok.get_name()
    if isinstance(tok, COSNumber):
        return _canon(tok.float_value())
    if isinstance(tok, COSName):
        return _normalise_gs("/" + tok.name)
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
        return {
            "rect": _canon_rect(ann.get_rectangle()),
            "bbox": "NOAP",
            "toks": [],
            "gs": [],
        }
    res = stream.get_resources()
    gs_pins: list[tuple[str, str]] = []
    if res is not None:
        for name in res.get_ext_g_state_names():
            gs = res.get_ext_g_state(name)
            ca = gs.get_stroking_alpha_constant()
            non = gs.get_non_stroking_alpha_constant()
            bm = gs.get_blend_mode()
            gs_pins.append(
                (
                    "null" if ca is None else _canon(ca),
                    "null" if non is None else _canon(non),
                    "null" if bm is None else "blend",
                )
            )
    return {
        "rect": _canon_rect(ann.get_rectangle()),
        "bbox": _canon_rect(stream.get_bbox()),
        "toks": _tokens(stream),
        "gs": sorted(gs_pins),
    }


def _parse_java(text: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"toks": [], "gs": [], "name": raw[len("ANNOT ") :]}
        elif raw.startswith("RAWNAME "):
            current["rawname"] = raw[len("RAWNAME ") :]  # type: ignore[index]
        elif raw.startswith("RECT "):
            current["rect"] = raw[len("RECT ") :]  # type: ignore[index]
        elif raw.startswith("BBOX "):
            current["bbox"] = raw[len("BBOX ") :]  # type: ignore[index]
        elif raw == "NOAP":
            current["bbox"] = "NOAP"  # type: ignore[index]
        elif raw.startswith("GS "):
            ca, non, bm = raw[len("GS ") :].split(" ")
            current["gs"].append(  # type: ignore[union-attr]
                (ca, non, "null" if bm == "null" else "blend")
            )
        elif raw.startswith("TOK "):
            current["toks"].append(  # type: ignore[union-attr,index]
                _normalise_gs(raw[len("TOK ") :])
            )
        elif raw == "END":
            assert current is not None
            current["gs"] = sorted(current["gs"])  # type: ignore[assignment,arg-type]
            records.append(current)
            current = None
    return records


def _build_battery() -> list[PDAnnotationText]:
    """Mirror TextAnnotationIconProbe.write — 16 icons, then two colour
    variants, then a missing-/Name annot, then an unknown-/Name annot."""
    battery: list[PDAnnotationText] = []
    y = 750
    for name in _STANDARD_NAMES:
        ann = PDAnnotationText()
        ann.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
        ann.set_name(name)
        battery.append(ann)
        y -= 45
    for name, rgb in _COLOUR_VARIANTS:
        ann = PDAnnotationText()
        ann.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
        ann.set_name(name)
        arr = COSArray()
        for comp in rgb:
            arr.add(COSFloat(comp))
        ann.get_cos_object().set_item(COSName.get_pdf_name("C"), arr)
        battery.append(ann)
        y -= 45
    # missing /Name
    missing = PDAnnotationText()
    missing.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
    battery.append(missing)
    y -= 45
    # unknown /Name
    unknown = PDAnnotationText()
    unknown.set_rectangle(PDRectangle.from_xywh(50, y, 30, 30))
    unknown.set_name("DefinitelyNotAStandardIcon")
    battery.append(unknown)
    return battery


def _java_records() -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "text_annotation.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


def _is_pinned(java_record: dict[str, object]) -> bool:
    """A record is operand-pinned when its effective icon name is in the
    byte-exact set. The missing-/Name record reduces to Note; the unknown-name
    record (NOAP) is pinned at the NOAP / RECT level only."""
    if java_record.get("bbox") == "NOAP":
        return True
    return java_record["name"] in _PINNED_NAMES


@requires_oracle
def test_text_annotation_icons_match_pdfbox_exactly() -> None:
    java = _java_records()
    battery = _build_battery()
    assert len(java) == len(battery), (
        f"probe wrote {len(java)} annots, battery has {len(battery)}"
    )
    pinned_seen = 0
    for ann, jr in zip(battery, java, strict=True):
        py = _py_fingerprint(ann)
        label = jr["name"]
        # /Rect (rewritten by adjustRectAndBBox) is pinned for every record.
        assert py["rect"] == jr["rect"], (
            f"{label} /Rect: {py['rect']!r} != PDFBox {jr['rect']!r}"
        )
        if not _is_pinned(jr):  # pragma: no cover - every standard icon is pinned
            continue
        pinned_seen += 1
        assert py["bbox"] == jr["bbox"], (
            f"{label} /BBox: {py['bbox']!r} != PDFBox {jr['bbox']!r}"
        )
        assert py["gs"] == jr["gs"], (
            f"{label} ExtGState halo CA/ca/BM: {py['gs']!r} != PDFBox {jr['gs']!r}"
        )
        assert py["toks"] == jr["toks"], (
            f"{label} token stream diverges\n"
            f"  pypdfbox ({len(py['toks'])}): {py['toks']}\n"  # type: ignore[arg-type]
            f"  PDFBox   ({len(jr['toks'])}): {jr['toks']}"  # type: ignore[arg-type]
        )
    # Sanity: all 16 standard icons, plus the two colour variants, plus the
    # missing-name(Note) record, plus the unknown-name(NOAP) record = 20.
    assert pinned_seen == 20, f"expected 20 pinned records, asserted {pinned_seen}"


@requires_oracle
def test_help_paragraph_newparagraph_use_exact_glyph_paths() -> None:
    """Focused regression: the three Standard-14 glyph-bearing icons that
    previously used hand-built approximations now emit the exact upstream
    glyph outlines. Asserts each contains the signature first glyph operand
    the approximation never produced."""
    java = {r["name"]: r for r in _java_records() if r.get("bbox") != "NOAP"}
    signatures = {
        PDAnnotationText.NAME_HELP: ["778", "544", "m"],
        PDAnnotationText.NAME_PARAGRAPH: ["940", "-363", "m"],
        PDAnnotationText.NAME_NEW_PARAGRAPH: ["1348", "0", "m"],
    }
    for name, sig in signatures.items():
        ann = PDAnnotationText()
        ann.set_rectangle(PDRectangle.from_xywh(50, 700, 30, 30))
        ann.set_name(name)
        py = _py_fingerprint(ann)
        toks = py["toks"]
        joined = " ".join(toks)  # type: ignore[arg-type]
        assert " ".join(sig) in joined, (
            f"{name}: missing exact glyph signature {sig} in {toks}"
        )
        # And the whole stream equals upstream.
        assert toks == java[name]["toks"], (
            f"{name} full stream diverges from PDFBox"
        )


@requires_oracle
def test_zapf_symbol_glyph_icons_use_exact_glyph_paths() -> None:
    """Focused regression: the five ZapfDingbats / Symbol glyph icons closed
    in wave 1509 — Cross / Star / Check / RightPointer (ZapfDingbats) and
    CrossHairs (Symbol) — previously emitted hand-built approximations. They
    now embed the exact upstream Standard-14 glyph outlines, driven through
    ``add_path`` under the fontMatrix-derived scale. Asserts each carries the
    signature first glyph operand the approximation never produced, then that
    the whole operand stream equals Apache PDFBox byte-for-byte."""
    java = {r["name"]: r for r in _java_records() if r.get("bbox") != "NOAP"}
    signatures = {
        PDAnnotationText.NAME_CROSS: ["1493", "344", "m"],
        PDAnnotationText.NAME_STAR: ["1606", "883", "m"],
        PDAnnotationText.NAME_CHECK: ["1663", "1300", "m"],
        PDAnnotationText.NAME_RIGHT_POINTER: ["1806", "709", "m"],
        PDAnnotationText.NAME_CROSS_HAIRS: ["731", "555", "m"],
    }
    for name, sig in signatures.items():
        ann = PDAnnotationText()
        ann.set_rectangle(PDRectangle.from_xywh(50, 700, 30, 30))
        ann.set_name(name)
        py = _py_fingerprint(ann)
        toks = py["toks"]
        joined = " ".join(toks)  # type: ignore[arg-type]
        assert " ".join(sig) in joined, (
            f"{name}: missing exact glyph signature {sig} in {toks}"
        )
        assert toks == java[name]["toks"], (
            f"{name} full stream diverges from PDFBox"
        )
