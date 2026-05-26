"""Live PDFBox differential parity for font *descriptor* metrics.

Companion to ``test_font_metrics_oracle.py`` (wave 1408, per-code advance
widths). This wave (1412) verifies the :class:`PDFontDescriptor` metric block —
font name, flags, font bounding box, italic angle, ascent, descent, cap height,
x-height, stem-v, missing-width, font-family and font-weight — matches Apache
PDFBox 3.0.7 exactly for every font on every page of a varied fixture set.

pypdfbox delegates font-program parsing to fontTools and synthesises a
descriptor from the AFM for Standard-14 fonts (mirroring upstream
``PDFont.loadFontDescriptor``); this test confirms the descriptor numbers and
the Standard-14 synthesis match what PDFBox reports.

The oracle output is produced by ``oracle/probes/FontDescProbe.java``; the
Python side here reconstructs the identical line format so a divergence shows up
as a single differing line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Same font-bearing fixtures wave 1408 (font metrics) used:
#   - Standard-14 Type1 (Helvetica/Bold, Times family) -> synthesized from AFM
#   - embedded Type1C / CFF (Century-Book/Bold, Courier) -> /FontDescriptor
#   - embedded TrueType (Arial/Times subsets, Liberation, Calibri)
#   - Type0 / CIDFontType2 (descriptor on the descendant CID font)
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


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _str(s: str | None) -> str:
    """Match the probe's null-as-literal-"null" rendering for string entries."""
    return "null" if s is None else s


def _py_font_descriptors(pdf_path: Path) -> str:
    """Reconstruct the FontDescProbe output from pypdfbox.

    Mirrors the probe's control flow line-for-line so a textual diff isolates a
    single divergence.
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
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t{font.get_sub_type()}"
                )
                fd = font.get_font_descriptor()
                if fd is None:
                    lines.append("NO_DESCRIPTOR")
                    continue
                parts = ["DESC", _str(fd.get_font_name()), str(fd.get_flags())]
                bbox = fd.get_font_bounding_box()
                if bbox is None:
                    parts.append("NO_BBOX")
                else:
                    parts.append(_fmt(bbox.get_lower_left_x()))
                    parts.append(_fmt(bbox.get_lower_left_y()))
                    parts.append(_fmt(bbox.get_upper_right_x()))
                    parts.append(_fmt(bbox.get_upper_right_y()))
                parts.append(_fmt(fd.get_italic_angle()))
                parts.append(_fmt(fd.get_ascent()))
                parts.append(_fmt(fd.get_descent()))
                parts.append(_fmt(fd.get_cap_height()))
                parts.append(_fmt(fd.get_x_height()))
                parts.append(_fmt(fd.get_stem_v()))
                parts.append(_fmt(fd.get_missing_width()))
                parts.append(_str(fd.get_font_family()))
                parts.append(_fmt(fd.get_font_weight()))
                lines.append("\t".join(parts))
    finally:
        doc.close()
    # Probe uses printf with %n (newline) after each record incl. the last.
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_font_descriptor_metrics_match_pdfbox(fixture_rel: str) -> None:
    """Every PDFontDescriptor metric must match Apache PDFBox exactly across
    embedded TrueType / Type1-CFF / Type0-CID fonts and synthesized Standard-14
    descriptors.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    jl = run_probe_text("FontDescProbe", str(pdf_path)).splitlines()
    pl = _py_font_descriptors(pdf_path).splitlines()
    assert len(jl) == len(pl), (
        f"line-count mismatch for {fixture_rel}: java={len(jl)} py={len(pl)}"
    )

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"font descriptor parity broken for {fixture_rel}:\n" + "\n".join(diffs[:40])
    )
