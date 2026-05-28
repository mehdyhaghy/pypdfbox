"""Live Apache PDFBox differential parity for the HIGHLIGHT annotation's
blend-mode + alpha graphics state.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight``
appearance generation via ``PDHighlightAppearanceHandler`` — specifically the
ExtGState dictionaries the generated ``/AP /N`` stream applies via ``gs``. A
highlight must visually MULTIPLY over the underlying text (PDF 32000-1 §11.3.5,
§11.6.4.4): the handler sets one ExtGState carrying the alpha constants
(``/CA`` + ``/ca`` = the annotation's constant opacity, ``/AIS false``) and a
second carrying ``/BM /Multiply``.

This complements ``test_text_markup_oracle.py`` (wave 1442/1455). That file
fingerprints the highlight ``/AP /N`` operator KEYWORD sequence and asserts two
``gs`` operators are present — but never inspects what those two ExtGStates
actually contain. A highlight whose ExtGState carried ``/BM /Normal`` (or no
blend mode), or the wrong alpha constant, would pass the operator-sequence test
yet render as an opaque solid block over the text instead of a translucent
multiply wash. This file closes that gap: it resolves each ``gs`` operand to its
ExtGState resource (recursing into any form XObject ``Do``-invoked, so the
PDFBox transparency-group form and the pypdfbox inline emission surface the same
facts) and asserts the ``/BM``, ``/CA``, ``/ca``, ``/AIS`` values match Apache
PDFBox exactly.

The Java probe ``HighlightBlendProbe`` runs in two modes:

* ``write out.pdf`` — three highlights (default-opacity yellow, ``/CA 0.5``
  half-opacity red, ``/CA 1`` cyan), ``constructAppearances(doc)`` then save.
  PDFBox-AUTHORED reference.
* ``read out.pdf`` — re-opens ANY highlight PDF and emits, per annotation:
  ``ANNOT <subtype>`` / ``CA <float|none>`` / one ``GS <name> BM=.. CA=.. ca=..
  AIS=..`` line per ExtGState reachable from a ``gs`` operator / ``END``.

pypdfbox builds the IDENTICAL battery, saves once, then the parity assertions
compare the COLLECTIVE blend facts (set of blend modes, set of alpha constants)
reachable from the ``/AP /N`` stream — independent of whether the ExtGStates
live inline (pypdfbox lite handler) or split across a transparency-group form
XObject (upstream). Both must apply a Multiply blend and the matching constant
opacity.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel.interactive.annotation import PDAnnotationHighlight
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "HighlightBlendProbe"

# Identical battery on the Java (HighlightBlendProbe.write) and Python sides.
# (subtype-label, rect, quad, color, constant_opacity-or-None)
_CASES = [
    ("default", (50, 295, 250, 320), [50, 315, 250, 315, 50, 300, 250, 300], [1.0, 1.0, 0.0], None),
    ("half", (50, 245, 250, 270), [50, 265, 250, 265, 50, 250, 250, 250], [1.0, 0.0, 0.0], 0.5),
    ("opaque", (50, 195, 250, 220), [50, 215, 250, 215, 50, 200, 250, 200], [0.0, 1.0, 1.0], 1.0),
]


def _build_pypdfbox(path: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 300, 400))
        doc.add_page(page)
        annotations = []
        for _label, rect, quad, color, opacity in _CASES:
            ann = PDAnnotationHighlight()
            ann.set_rectangle(PDRectangle(*rect))
            ann.set_quad_points(quad)
            ann.set_color(color)
            if opacity is not None:
                ann.set_constant_opacity(opacity)
            ann.construct_appearances(doc)
            annotations.append(ann)
        page.set_annotations(annotations)
        doc.save(str(path))
    finally:
        doc.close()


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _parse_records(text: str) -> list[dict[str, object]]:
    """Parse HighlightBlendProbe read-mode output into ordered per-annotation
    records: {subtype, ca, gs: [{name, BM, CA, ca, AIS}]}."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :], "ca": None, "gs": []}
        elif raw.startswith("CA "):
            assert current is not None
            current["ca"] = raw[len("CA ") :]
        elif raw.startswith("GS "):
            assert current is not None
            fields = raw[len("GS ") :].split()
            entry: dict[str, str] = {"name": fields[0]}
            for f in fields[1:]:
                k, _, v = f.partition("=")
                entry[k] = v
            current["gs"].append(entry)  # type: ignore[union-attr]
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
    return records


def _blend_modes(rec: dict[str, object]) -> set[str]:
    return {gs["BM"] for gs in rec["gs"] if gs["BM"] != "none"}  # type: ignore[index,union-attr]


def _alpha_constants(rec: dict[str, object]) -> set[str]:
    """The non-'none' /CA + /ca constants applied across all ExtGStates."""
    out: set[str] = set()
    for gs in rec["gs"]:  # type: ignore[union-attr]
        for key in ("CA", "ca"):
            if gs[key] != "none":  # type: ignore[index]
                out.add(gs[key])  # type: ignore[index]
    return out


def _ais_flags(rec: dict[str, object]) -> set[str]:
    return {gs["AIS"] for gs in rec["gs"]}  # type: ignore[index,union-attr]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_highlight_extgstate_matches_pdfbox(tmp_path: Path) -> None:
    """Per highlight, the COLLECTIVE blend facts the generated ``/AP /N`` stream
    applies — the set of blend modes, the set of alpha constants, the AIS flags —
    match Apache PDFBox's own generation exactly. This is independent of whether
    the ExtGStates live inline (pypdfbox) or in a transparency-group form
    XObject (upstream), since the probe resolves both."""
    py_pdf = tmp_path / "highlight_blend_py.pdf"
    java_pdf = tmp_path / "highlight_blend_java.pdf"
    _build_pypdfbox(py_pdf)
    run_probe_text(_PROBE, "write", str(java_pdf))

    py = _parse_records(run_probe_text(_PROBE, "read", str(py_pdf)))
    java = _parse_records(run_probe_text(_PROBE, "read", str(java_pdf)))

    assert len(py) == len(java) == len(_CASES), (
        f"annotation count mismatch: py={len(py)} java={len(java)}"
    )

    for idx, (label, _rect, _quad, _color, opacity) in enumerate(_CASES):
        pr = py[idx]
        jr = java[idx]
        assert pr["subtype"] == jr["subtype"] == "Highlight"

        # /CA accessor round-trip (None -> annot has no /CA key -> "none").
        expected_ca = "none" if opacity is None else _canon_float(opacity)
        assert pr["ca"] == expected_ca, f"{label}: /CA {pr['ca']!r} != {expected_ca!r}"
        assert jr["ca"] == expected_ca, f"{label}: PDFBox /CA {jr['ca']!r} != {expected_ca!r}"

        # The load-bearing fact: a Multiply blend is applied.
        assert _blend_modes(jr) == {"Multiply"}, f"{label}: PDFBox blend {_blend_modes(jr)}"
        assert _blend_modes(pr) == {"Multiply"}, (
            f"{label}: pypdfbox did not apply a Multiply blend "
            f"(blend modes seen: {_blend_modes(pr)}) — highlight would paint opaque"
        )

        # Alpha constants: the effective constant opacity (default 1.0 when the
        # annotation carries no /CA). Compared as a set so a CA/ca split or an
        # inline-vs-form layout doesn't matter — the VALUE must match PDFBox.
        eff_opacity = {_canon_float(1.0 if opacity is None else opacity)}
        assert _alpha_constants(jr) == eff_opacity, (
            f"{label}: PDFBox alpha {_alpha_constants(jr)} != {eff_opacity}"
        )
        assert _alpha_constants(pr) == eff_opacity, (
            f"{label}: pypdfbox alpha {_alpha_constants(pr)} != {eff_opacity}"
        )

        # /AIS must be the explicit boolean false (alpha is a constant, not a
        # soft-mask shape) on every ExtGState — matching PDFBox.
        assert _ais_flags(jr) == {"false"}, f"{label}: PDFBox AIS {_ais_flags(jr)}"
        assert _ais_flags(pr) == {"false"}, (
            f"{label}: pypdfbox AIS flags {_ais_flags(pr)} != {{'false'}} — "
            f"alpha-is-shape flag must be the explicit boolean false"
        )


@requires_oracle
def test_highlight_blend_count_and_separation(tmp_path: Path) -> None:
    """Structural guard mirroring upstream: the blend mode and the alpha
    constants are carried on the ExtGStates the ``/AP /N`` stream applies, and a
    Multiply-bearing ExtGState carries NO alpha constant of its own (and vice
    versa) — i.e. PDFBox's two-ExtGState separation (alpha on one, Multiply on
    the other) is preserved, not collapsed into a single state that drops one."""
    py_pdf = tmp_path / "highlight_blend_py.pdf"
    _build_pypdfbox(py_pdf)
    py = _parse_records(run_probe_text(_PROBE, "read", str(py_pdf)))

    for rec in py:
        gs_list = rec["gs"]
        assert gs_list, "pypdfbox highlight applied no ExtGState"  # type: ignore[truthy-bool]
        # At least one Multiply-bearing state and at least one alpha-bearing
        # state are reachable.
        assert any(gs["BM"] == "Multiply" for gs in gs_list), rec  # type: ignore[union-attr,index]
        assert any(
            gs["CA"] != "none" or gs["ca"] != "none"  # type: ignore[index]
            for gs in gs_list  # type: ignore[union-attr]
        ), rec
        # The Multiply state does not also set an alpha constant (matches
        # PDFBox's r1 = blend-only ExtGState).
        for gs in gs_list:  # type: ignore[union-attr]
            if gs["BM"] == "Multiply":  # type: ignore[index]
                assert gs["CA"] == "none" and gs["ca"] == "none", (  # type: ignore[index]
                    f"pypdfbox Multiply ExtGState also carries alpha: {gs}"
                )
