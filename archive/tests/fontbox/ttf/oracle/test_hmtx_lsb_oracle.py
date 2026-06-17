"""Live PDFBox differential parity for the ``hmtx`` table decode read straight
from the embedded TrueType FONT PROGRAM (FontBox).

Wave 1414's ``GlyphAdvanceProbe`` covered only the advance width
(``TrueTypeFont.get_advance_width``). This wave targets the
``HorizontalMetricsTable`` directly and asserts BOTH the advance width and the
LEFT-SIDE BEARING per GID against Apache PDFBox 3.0.7.

The interesting parity surface is the **trailing-LSB compression**: an ``hmtx``
table stores ``numberOfHMetrics`` (advance, LSB) pairs followed by an LSB-only
array for the remaining glyphs (which all share the last advance). So
``get_left_side_bearing(gid)`` for ``gid >= numberOfHMetrics`` must read the
trailing LSB array, while ``get_advance_width`` clamps to the last advance. The
probed GID set straddles ``numberOfHMetrics`` to exercise both branches plus
the out-of-range fallback (advance -> 250 in upstream when the list is empty;
LSB -> 0 when the trailing index is out of range).

Only TrueType programs carry an ``hmtx`` table, so CFF/Type1 fonts are skipped.
Only embedded fonts are in scope (a non-embedded font resolves to a platform
substitute whose metrics aren't deterministic across machines — the probe skips
those via ``isEmbedded()``; the Python side mirrors the skip).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Embedded TrueType programs only (CFF fixtures carry no hmtx and are SKIPped):
#   - embedded TrueType subset (Liberation)
#   - embedded TrueType subset (Calibri)
#   - CIDFontType2 (Symbol) TrueType program
#   - embedded TrueType subsets (Verdana/Symbol)
_FIXTURES_REL = [
    "pdmodel/with_outline.pdf",
    "multipdf/PDFA3A.pdf",
    "multipdf/PDFBOX-4417-054080.pdf",
    "text/input/eu-001.pdf",
]

# Mirror the Java probe's bounds.
_GID_CAP = 256
_OOB_GIDS = [60000, 65535]


def _gids(num_glyphs: int, num_h_metrics: int) -> list[int]:
    """GIDs straddling ``num_h_metrics``; matches ``HmtxLsbProbe.gids`` exactly
    (de-duplicated, insertion order via a ``LinkedHashSet`` equivalent).
    """
    seen: dict[int, None] = {}
    upper = min(num_glyphs, _GID_CAP) if num_glyphs > 0 else 0
    for g in range(upper):
        seen[g] = None
    for b in (num_h_metrics - 1, num_h_metrics, num_h_metrics + 1):
        if 0 <= b < num_glyphs:
            seen[b] = None
    for g in _OOB_GIDS:
        seen[g] = None
    return list(seen.keys())


def _emit_ttf(lines: list[str], page_index: int, key: str, base_font: str, ttf: Any) -> None:
    if ttf is None:
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(null-ttf)\t{base_font}\t0\t0")
        return
    hmtx = ttf.get_horizontal_metrics()
    if hmtx is None:
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(no-hmtx)\t{base_font}\t0\t0")
        return
    num_glyphs = ttf.get_number_of_glyphs()
    num_h_metrics = ttf.get_horizontal_header().get_number_of_h_metrics()
    lines.append(
        f"FONT\t{page_index}\t{key}\tTTF\t{base_font}\t{num_h_metrics}\t{num_glyphs}"
    )
    for gid in _gids(num_glyphs, num_h_metrics):
        try:
            adv = str(hmtx.get_advance_width(gid))
            lsb = str(hmtx.get_left_side_bearing(gid))
        except Exception:
            adv = "ERR"
            lsb = "ERR"
        lines.append(f"HM\t{gid}\t{adv}\t{lsb}")


def _emit_font(lines: list[str], page_index: int, key: str, font: object) -> None:
    if isinstance(font, PDTrueTypeFont):
        ttf = font.get_true_type_font()
        _emit_ttf(lines, page_index, key, str(font.get_name()), ttf)
        return
    if isinstance(font, PDType0Font):
        descendant = font.get_descendant_font()
        if isinstance(descendant, PDCIDFontType2):
            ttf = descendant.get_true_type_font()
            _emit_ttf(lines, page_index, key, str(font.get_name()), ttf)
            return
    lines.append(f"FONT\t{page_index}\t{key}\tSKIP(not-truetype)\t{font.get_name()}\t0\t0")


def _py_hmtx(pdf_path: Path) -> str:
    """Reconstruct HmtxLsbProbe output from pypdfbox (line-for-line)."""
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
                    continue
                if font is None:
                    continue
                try:
                    embedded = font.is_embedded()
                except Exception:
                    embedded = False
                if not embedded:
                    continue
                _emit_font(lines, page_index, key, font)
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_hmtx_lsb_matches_pdfbox(fixture_rel: str) -> None:
    """Per-GID advance width + left-side bearing read from the embedded
    TrueType ``hmtx`` table must match Apache PDFBox 3.0.7, including the
    trailing-LSB-only block for GIDs at or past ``numberOfHMetrics``.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("HmtxLsbProbe", str(pdf_path)).splitlines()
    py = _py_hmtx(pdf_path).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch for {fixture_rel}: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"hmtx parity broken for {fixture_rel}:\n" + "\n".join(diffs[:40])
    )
