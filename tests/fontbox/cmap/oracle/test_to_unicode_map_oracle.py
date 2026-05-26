"""Live PDFBox differential parity for code -> Unicode mapping.

This is the mapping that drives correct text extraction: for every font on every
page, ``font.to_unicode(code)`` must return the same Unicode string Apache
PDFBox returns from ``font.toUnicode(code)``. The mapping comes from the font's
``/ToUnicode`` CMap (parsed by ``pypdfbox.fontbox.cmap.CMapParser`` into a
``CMap``), with subclass fallbacks for simple fonts (encoding + glyph list) and
Type0/CID fonts (encoding CMap bfchar, predefined ``*-UCS2`` CMap, embedded
TrueType cmap).

The oracle output is produced by ``oracle/probes/ToUniMapProbe.java``: one
canonical line per code that maps to a non-empty string, formatted as
``<page> <fontName> <code> -> U+XXXX[ U+YYYY...]``. The Python side here
reconstructs the identical line format so a divergence shows up as a single
differing line.

Fixtures span simple TrueType subsets with embedded ``/ToUnicode`` CMaps and
Type0 composite fonts (``C2_*`` / ``T1_*``) so both the 1-byte and the
composite-code paths are exercised.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Each fixture carries at least one embedded /ToUnicode CMap; the multipdf
# ones additionally carry Type0 composite fonts (C2_* / T1_*).
_FIXTURES_REL = [
    "text/input/eu-001.pdf",  # CIDFontType2 + TrueType subsets w/ ToUnicode
    "multipdf/PDFBOX-4417-001031.pdf",  # Type0 (C2_0) + many TrueType subsets
    "multipdf/PDFBOX-5809-509329.pdf",  # Type0 (C2_0/C2_1) + TrueType subsets
    "multipdf/PDFBOX-4417-054080.pdf",  # Type0 (T1_0) + TrueType + std-14
    "text/BidiSample.pdf",  # TrueType subsets w/ ToUnicode
    "pdmodel/with_outline.pdf",  # embedded TrueType (Liberation subset)
]

# Match the probe default; keeps both walks bounded to the BMP-and-below range
# that every fixture's codespace covers.
_MAX_CODE = 0xFFFF


def _fmt_unicode(s: str) -> str:
    """Render ``s`` as the probe does: space-separated ``U+XXXX`` per code
    point (Python iterates code points natively, so no surrogate handling)."""
    return " ".join(f"U+{ord(ch):04X}" for ch in s)


def _py_to_unicode_map(pdf_path: Path) -> str:
    """Reconstruct the ToUniMapProbe output from pypdfbox.

    Mirrors the probe's control flow line-for-line: page index, resource
    font-name iteration order, ascending code; emit only codes that map to a
    non-empty string. A textual diff then isolates a single divergence.
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
                    # Unloadable font — probe skips on its catch too.
                    continue
                if font is None:
                    continue
                for code in range(_MAX_CODE + 1):
                    try:
                        uni = font.to_unicode(code)
                    except Exception:
                        continue
                    if not uni:
                        continue
                    lines.append(
                        f"{page_index} {key} {code} -> {_fmt_unicode(uni)}"
                    )
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_to_unicode_map_matches_pdfbox(fixture_rel: str) -> None:
    """pypdfbox's full per-font code -> Unicode map must equal Java's exactly.

    Every line (page, font name, code, and the hex code points) must match.
    A missing line means pypdfbox dropped a mapping PDFBox produced; an extra
    line means pypdfbox invented one; a differing right-hand side means the
    CMap / glyph-list resolution diverged.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    jl = run_probe_text(
        "ToUniMapProbe", str(pdf_path), str(_MAX_CODE)
    ).splitlines()
    pl = _py_to_unicode_map(pdf_path).splitlines()

    java_set = set(jl)
    py_set = set(pl)
    missing = [ln for ln in jl if ln not in py_set]  # PDFBox had, pypdfbox lost
    extra = [ln for ln in pl if ln not in java_set]  # pypdfbox invented

    assert not missing and not extra, (
        f"code->unicode parity broken for {fixture_rel}: "
        f"{len(missing)} missing, {len(extra)} extra\n"
        "  MISSING (java has, py lacks):\n"
        + "\n".join(f"    {ln}" for ln in missing[:25])
        + "\n  EXTRA (py has, java lacks):\n"
        + "\n".join(f"    {ln}" for ln in extra[:25])
    )
