"""Live PDFBox differential parity for font metrics (advance widths).

Compares pypdfbox's per-code advance widths, string widths, subtype and
embedding flags against Apache PDFBox 3.0.7 for every font on every page of a
varied fixture set. pypdfbox delegates font-program parsing to fontTools; this
test verifies that the delegation yields the *same numbers* PDFBox reports.

The oracle output is produced by ``oracle/probes/FontMetricsProbe.java``; the
Python side here reconstructs the identical line format so a divergence shows up
as a single differing line.

Standard-14 widths come from AFM files and must match exactly. Embedded font
widths come from the ``/Widths`` array (preferred per PDFBOX-427) or, lacking
that, from the embedded program via fontTools.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Varied font coverage:
#   - Standard-14 Type1 (Times family, Helvetica/Bold) -> AFM widths
#   - embedded Type1C / CFF (Century-Book/Bold, Courier) -> /Widths
#   - embedded TrueType (Arial/Times subsets, Liberation, Calibri)
#   - Type0 / CIDFontType2 (+ Type1C descendant)
_FIXTURES_REL = [
    "multipdf/Overlayed-with-rot0.pdf",  # Helvetica + Helvetica-Bold (std-14)
    "multipdf/PDFBOX-5840-410609.pdf",  # Times family (std-14 Type1)
    "multipdf/PDFBOX-5811-362972.pdf",  # embedded Type1C (Century)
    "multipdf/PDFBOX-5762-722238.pdf",  # embedded TrueType (Arial/Times subset)
    "pdmodel/with_outline.pdf",  # embedded TrueType (Liberation subset)
    "multipdf/PDFA3A.pdf",  # embedded TrueType (Calibri subset)
    "multipdf/PDFBOX-4417-054080.pdf",  # Type0 + CIDFontType2 + Type1C
    "text/input/eu-001.pdf",  # CIDFontType2 + TrueType + std-14 Arial
]

_SAMPLE_IDS = ["space", "ABC", "Hello", "digits"]
_SAMPLES = [" ", "ABC", "Hello", "0123456789"]


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _py_font_metrics(pdf_path: Path) -> str:
    """Reconstruct the FontMetricsProbe output from pypdfbox.

    Mirrors the probe's control flow line-for-line so a textual diff isolates
    a single divergence.
    """
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                key = name.name if hasattr(name, "name") else str(name)
                try:
                    font = res.get_font(name)
                except Exception:
                    lines.append(f"FONT\t{page_index}\t{key}\tLOAD_ERR")
                    continue
                if font is None:
                    lines.append(f"FONT\t{page_index}\t{key}\tNULL")
                    continue
                base_font = font.get_name()
                sub_type = font.get_sub_type()
                try:
                    embedded = font.is_embedded()
                except Exception:
                    embedded = False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{base_font}\t{sub_type}\t"
                    f"{'true' if embedded else 'false'}"
                )
                for code in range(32, 127):
                    try:
                        w = _fmt(font.get_width(code))
                    except Exception:
                        w = "ERR"
                    lines.append(f"W\t{code}\t{w}")
                for sid, sample in zip(_SAMPLE_IDS, _SAMPLES, strict=True):
                    try:
                        sw = _fmt(font.get_string_width(sample))
                    except Exception:
                        sw = "ERR"
                    lines.append(f"SW\t{sid}\t{sw}")
    finally:
        doc.close()
    # Probe uses printf with %n (newline) after each record incl. the last.
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_font_metrics_match_pdfbox(fixture_rel: str) -> None:
    """Per-code advance widths, subtype and embedding flags must match Java
    exactly; ``getStringWidth`` must match wherever Java produces a number.

    The one tolerated divergence is the documented encode-leniency
    (``getStringWidth`` over an unencodable glyph): Apache PDFBox raises
    ``IllegalArgumentException`` and the probe emits ``ERR``, while pypdfbox's
    lenient ``encode`` (which substitutes ``?`` for simple fonts / CID 0 for
    Type0, a behaviour pinned by ``test_pd_font_remaining_wave717`` and
    ``test_pd_type1c_font_wave279``) returns a number. That whole-string encode
    contract is a cross-module decision out of scope for a font-metrics wave —
    see CHANGES.md. This test therefore asserts that pypdfbox is *never
    stricter* than Java and *never numerically different* when both succeed.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    jl = run_probe_text("FontMetricsProbe", str(pdf_path)).splitlines()
    pl = _py_font_metrics(pdf_path).splitlines()
    assert len(jl) == len(pl), (
        f"line-count mismatch for {fixture_rel}: java={len(jl)} py={len(pl)}"
    )

    hard_diffs: list[str] = []
    lenient_skips = 0
    for i, (j, p) in enumerate(zip(jl, pl, strict=True)):
        if j == p:
            continue
        jf = j.split("\t")
        pf = p.split("\t")
        kind = jf[0]
        # FONT header (name / subtype / isEmbedded) and per-code W must be exact.
        if kind in ("FONT", "W"):
            hard_diffs.append(f"  line {i}: java={j!r} py={p!r}")
            continue
        # SW: tolerate ONLY java=ERR (PDFBox threw) vs py=<number> (lenient
        # encode). Any other shape — a both-numeric mismatch, or pypdfbox
        # being *stricter* (py=ERR while java succeeded) — is a hard failure.
        if kind == "SW":
            jv, pv = jf[2], pf[2]
            if jv == "ERR" and pv != "ERR":
                lenient_skips += 1
                continue
            hard_diffs.append(f"  line {i}: java={j!r} py={p!r}")
            continue
        hard_diffs.append(f"  line {i}: java={j!r} py={p!r}")

    assert not hard_diffs, (
        f"font metric parity broken for {fixture_rel} "
        f"(tolerated encode-leniency skips: {lenient_skips}):\n"
        + "\n".join(hard_diffs[:40])
    )
