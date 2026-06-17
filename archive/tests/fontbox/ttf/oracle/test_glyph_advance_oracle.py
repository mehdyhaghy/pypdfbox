"""Live PDFBox differential parity for glyph advance widths read straight from
the embedded FONT PROGRAM (FontBox), not from the PDF ``/Widths`` array.

Wave 1408's ``FontMetricsProbe`` compared ``PDFont.getWidth(code)`` — the
``/Widths``-array path. This wave compares the *program-native* advance:

  * TrueType (``PDTrueTypeFont`` / ``PDCIDFontType2``) ->
    ``TrueTypeFont.get_advance_width(gid)`` in font design units, plus
    ``get_units_per_em()``.
  * CFF (``PDType1CFont`` / ``PDCIDFontType0``) -> the charstring width via
    ``CFFFont.get_type2_char_string(gid).get_width()``, plus unitsPerEm derived
    from the CFF FontMatrix x-scale.

pypdfbox delegates font-program parsing to fontTools; this test verifies the
delegation surfaces the *same advance widths* Apache PDFBox 3.0.7 reads from the
same embedded program. The oracle output is produced by
``oracle/probes/GlyphAdvanceProbe.java``; the Python helper here reconstructs
the identical line format so a divergence shows up as a single differing line.

Only *embedded* fonts are in scope: a non-embedded font resolves to a
platform/bundled substitute whose metrics aren't deterministic across machines
(the probe skips those via ``isEmbedded()``; the Python side mirrors the skip).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Embedded-program coverage (subset of the wave 1408 embedded-font fixtures):
#   - embedded Type1C / CFF (Century-Book/Bold) -> CFF charstring widths
#   - embedded TrueType subsets (Arial/Times, Liberation, Calibri, Verdana)
#   - Type0 / CIDFontType2 (TrueType program) + Type1C simple (Courier)
_FIXTURES_REL = [
    "multipdf/PDFBOX-5811-362972.pdf",  # embedded Type1C CFF (Century)
    "pdmodel/with_outline.pdf",  # embedded TrueType (Liberation subset)
    "multipdf/PDFA3A.pdf",  # embedded TrueType (Calibri subset)
    "multipdf/PDFBOX-4417-054080.pdf",  # CIDFontType2 (Symbol) + Type1C (Courier)
    "text/input/eu-001.pdf",  # embedded TrueType (Verdana/Symbol subsets)
]

# Mirror the Java probe's bounds.
_GID_CAP = 256
_OOB_GIDS = [60000, 65535]


def _gids(num_glyphs: int) -> list[int]:
    """Leading GIDs ``[0, min(num_glyphs, CAP))`` + synthetic out-of-range GIDs.

    Matches ``GlyphAdvanceProbe.gids`` (de-duplicated, insertion order).
    """
    seen: dict[int, None] = {}
    upper = min(num_glyphs, _GID_CAP) if num_glyphs > 0 else 0
    for g in range(upper):
        seen[g] = None
    for g in _OOB_GIDS:
        seen[g] = None
    return list(seen.keys())


def _cff_units_per_em(cff: object) -> int:
    """unitsPerEm from the CFF FontMatrix x-scale: ``round(1 / matrix[0])``.

    Mirrors ``GlyphAdvanceProbe.cffUnitsPerEm``. pypdfbox exposes the same
    derivation through ``CFFFont.units_per_em`` (a cached property), but we
    recompute from ``font_matrix`` here to assert the underlying matrix, not
    just the cached integer.
    """
    try:
        matrix = cff.font_matrix  # type: ignore[attr-defined]
    except Exception:
        return 1000
    if not matrix:
        return 1000
    scale = float(matrix[0])
    return round(1.0 / scale) if scale != 0.0 else 1000


def _emit_ttf(lines: list[str], page_index: int, key: str, base_font: str, ttf: object) -> None:
    if ttf is None:
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(null-ttf)\t{base_font}\t0")
        return
    upem = ttf.get_units_per_em()  # type: ignore[attr-defined]
    num_glyphs = ttf.get_number_of_glyphs()  # type: ignore[attr-defined]
    lines.append(f"FONT\t{page_index}\t{key}\tTTF\t{base_font}\t{upem}")
    for gid in _gids(num_glyphs):
        try:
            adv = str(ttf.get_advance_width(gid))  # type: ignore[attr-defined]
        except Exception:
            adv = "ERR"
        lines.append(f"ADV\t{gid}\t{adv}")


def _emit_cff(lines: list[str], page_index: int, key: str, cff: object) -> None:
    if cff is None:
        lines.append(f"FONT\t{page_index}\t{key}\tSKIP(null-cff)\t\t0")
        return
    upem = _cff_units_per_em(cff)
    num_glyphs = cff.get_num_char_strings()  # type: ignore[attr-defined]
    name = cff.get_name()  # type: ignore[attr-defined]
    lines.append(f"FONT\t{page_index}\t{key}\tCFF\t{name}\t{upem}")
    for gid in _gids(num_glyphs):
        try:
            cs = cff.get_type2_char_string(gid)  # type: ignore[attr-defined]
            # Java's Type1CharString.getWidth() returns an int; pypdfbox's
            # get_width() returns a float carrying the same integral advance.
            adv = str(int(cs.get_width()))
        except Exception:
            adv = "ERR"
        lines.append(f"ADV\t{gid}\t{adv}")


def _emit_font(lines: list[str], page_index: int, key: str, font: object) -> None:
    if isinstance(font, PDTrueTypeFont):
        ttf = font.get_true_type_font()
        _emit_ttf(lines, page_index, key, str(font.get_name()), ttf)
        return
    if isinstance(font, PDType1CFont):
        cff = font.get_cff_type1_font()
        _emit_cff(lines, page_index, key, cff)
        return
    if isinstance(font, PDType0Font):
        descendant = font.get_descendant_font()
        if isinstance(descendant, PDCIDFontType2):
            ttf = descendant.get_true_type_font()
            _emit_ttf(lines, page_index, key, str(font.get_name()), ttf)
            return
        if isinstance(descendant, PDCIDFontType0):
            cff = descendant.get_cff_font()
            _emit_cff(lines, page_index, key, cff)
            return
        lines.append(
            f"FONT\t{page_index}\t{key}\tSKIP(no-descendant)\t{font.get_name()}\t0"
        )
        return
    lines.append(
        f"FONT\t{page_index}\t{key}\tSKIP(not-program-font)\t{font.get_name()}\t0"
    )


def _py_glyph_advance(pdf_path: Path) -> str:
    """Reconstruct the GlyphAdvanceProbe output from pypdfbox.

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
    # Probe uses printf with %n (newline) after each record incl. the last.
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_glyph_advance_matches_pdfbox(fixture_rel: str) -> None:
    """Per-GID advance width (font design units) read from the embedded program
    and unitsPerEm must match Apache PDFBox 3.0.7 exactly across embedded
    TrueType and CFF fonts.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("GlyphAdvanceProbe", str(pdf_path)).splitlines()
    py = _py_glyph_advance(pdf_path).splitlines()

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
        f"glyph-advance parity broken for {fixture_rel}:\n" + "\n".join(diffs[:40])
    )
