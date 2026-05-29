"""Live PDFBox differential parity for the **embedded simple Type1C** font
surface of :class:`PDType1CFont` (PDF 32000-1 §9.6.2 + Adobe Technote #5176).

Wave 1466. A *simple* Type1C font is a font dictionary with
``/Subtype /Type1`` whose ``/FontDescriptor`` carries a ``/FontFile3`` stream
with ``/Subtype /Type1C`` — an embedded CFF (Compact Font Format) glyph
program with single-byte character codes. For every one-byte code the lookup
chain is:

  1. ``code_to_name(code)`` — resolve the byte through the font's encoding (the
     dictionary ``/Encoding`` with its ``/Differences`` overlay, else the CFF
     program's built-in encoding) to a PostScript glyph name;
  2. ``nameToGID(name)`` — the CFF charset lists glyph names in CharStrings
     order, so the GID is the charset index of the name (``0`` == ``.notdef``);
  3. ``get_width(code)`` — the ``/Widths`` array (offset by ``/FirstChar``),
     falling back to the embedded CFF advance;
  4. ``get_width_from_font(code)`` — the embedded CFF advance directly,
     rescaled to 1/1000 em via the font matrix, bypassing ``/Widths``;
  5. ``has_glyph(code)`` / ``has_glyph(name)`` — whether the CFF program carries
     a glyph for the resolved name.

This complements the CID/Type0 CFF probes (wave 1410+) and the bare-CFF
fontbox probes — it pins the *simple-font* (``PDType1CFont``) wrapper end to
end. Two real upstream fixtures are driven, each exercising a different
encoding source:

  * ``PDFBOX-3044-010197-p5-ligatures.pdf`` — Times-Roman / Times-Bold subsets
    that resolve through the *embedded CFF built-in encoding* (no dictionary
    ``/Encoding``), including the ``fi`` / ``fl`` ligature glyphs;
  * ``PDFBOX-4417-054080.pdf`` — a Courier subset with a dictionary
    ``/WinAnsiEncoding``.

Every ``FONT`` header (base font, encoding, font matrix), every per-code
``ROW`` (name, GID, width, width-from-font, has-glyph), and a fixed
``getStringWidth`` sample are asserted against Apache PDFBox 3.0.7. Result:
pypdfbox already matches PDFBox on the full surface; the only tolerated
divergence is the 4th-decimal float rounding of ``get_width_from_font`` (Java
``float`` vs Python ``double`` in the font-matrix rescale, <1e-3), which the
test compares with a small absolute tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

# (relative fixture path, human label) — each embeds simple Type1C fonts.
_PDFS = [
    ("pdmodel/font/PDFBOX-3044-010197-p5-ligatures.pdf", "times_builtin"),
    ("multipdf/PDFBOX-4417-054080.pdf", "courier_winansi"),
]

# The fixed string the probe measures with ``getStringWidth`` — every Latin
# Times / Courier subset in the fixtures carries these six glyphs.
_STRING_SAMPLE = "ABCabc"

# pypdfbox models the CFF program's built-in encoding with ``BuiltInEncoding``;
# Apache PDFBox surfaces the same thing as ``Type1Encoding`` (the FontBox CFF
# built-in encoding class). They are behaviourally identical — the per-code
# ``code_to_name`` parity below proves the equivalence — so the encoding-class
# name is normalised through this map before comparison.
_ENCODING_NAME_ALIASES = {"BuiltInEncoding": "Type1Encoding"}

# get_width_from_font rescales the CFF advance through the font matrix; Java
# does this in 32-bit float, pypdfbox in 64-bit double, so an integral advance
# can land on e.g. 722.0001 vs 722.0000. Tolerate <1e-3.
_WIDTH_FROM_FONT_TOL = 1e-3


def _fmt(value: float) -> str:
    """Match the probe's ``String.format(Locale.ROOT, "%.4f", v)``."""
    return f"{float(value):.4f}"


def _py_lines(pdf_path: Path) -> list[str]:
    """Reconstruct ``Type1CSimpleFontProbe`` output line for line from
    pypdfbox, for every embedded simple :class:`PDType1CFont`."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(font, PDType1CFont) or not font.is_embedded():
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                enc = font.get_encoding_typed()
                enc_name = type(enc).__name__ if enc is not None else "null"
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t{enc_name}"
                )
                matrix = font.get_font_matrix()
                lines.append("MATRIX\t" + "\t".join(_fmt(v) for v in matrix))
                lines.append("STRWIDTH\t" + _fmt(font.get_string_width(_STRING_SAMPLE)))
                cff = font.get_cff_font()
                charset = cff.get_charset() if cff is not None else []
                for code in range(256):
                    resolved = font.code_to_name(code)
                    glyph_name = resolved if resolved is not None else ".notdef"
                    gid = charset.index(glyph_name) if glyph_name in charset else 0
                    width = _fmt(font.get_width(code))
                    from_font = _fmt(font.get_width_from_font(code))
                    has_code = font.has_glyph_for_code(code)
                    has_name = resolved is not None and font.has_glyph(glyph_name)
                    lines.append(
                        f"ROW\t{code}\t{glyph_name}\t{gid}\t{width}\t{from_font}\t"
                        f"{str(has_code).lower()}\t{str(has_name).lower()}"
                    )
    finally:
        doc.close()
    return lines


def _normalise(line: str) -> str:
    """Apply the encoding-class alias so the FONT line is comparable."""
    if line.startswith("FONT\t"):
        parts = line.split("\t")
        parts[-1] = _ENCODING_NAME_ALIASES.get(parts[-1], parts[-1])
        return "\t".join(parts)
    return line


# ---------------------------------------------------------------------------
# fixture proof (no oracle needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("rel", "label"), _PDFS, ids=[p[1] for p in _PDFS])
def test_fixture_has_embedded_simple_type1c(rel: str, label: str) -> None:
    """Each fixture must carry at least one embedded simple Type1C font, or the
    surface under test would not be exercised."""
    pdf = _FIXTURES / rel
    assert pdf.is_file(), f"missing fixture {pdf}"
    doc = PDDocument.load(pdf)
    try:
        found = False
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:  # noqa: BLE001
                    continue
                if (
                    isinstance(font, PDType1CFont)
                    and font.is_embedded()
                    and font.get_cff_font() is not None
                ):
                    found = True
        assert found, f"{label}: no embedded simple Type1C font in fixture"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential test against the live oracle
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(("rel", "label"), _PDFS, ids=[p[1] for p in _PDFS])
def test_type1c_simple_font_matches_pdfbox(rel: str, label: str) -> None:
    """Every ``FONT`` header, ``MATRIX``, ``STRWIDTH`` and per-code ``ROW``
    (name / GID / width / width-from-font / has-glyph) on every embedded simple
    Type1C font must match Apache PDFBox 3.0.7 — with the only tolerated
    divergence the <1e-3 float rounding of ``get_width_from_font``."""
    pdf = _FIXTURES / rel
    java = run_probe_text("Type1CSimpleFontProbe", str(pdf)).splitlines()
    py = _py_lines(pdf)
    assert len(java) == len(py), (
        f"{label}: line-count mismatch java={len(java)} py={len(py)}"
    )

    diffs: list[str] = []
    for i, (j_raw, p_raw) in enumerate(zip(java, py, strict=True)):
        j = _normalise(j_raw)
        p = _normalise(p_raw)
        if j == p:
            continue
        # Tolerate only the width-from-font 4th-decimal float artefact: a ROW
        # whose sole disagreement is field index 5 (width-from-font) within
        # _WIDTH_FROM_FONT_TOL is parity.
        if j.startswith("ROW\t") and p.startswith("ROW\t"):
            jf = j.split("\t")
            pf = p.split("\t")
            if (
                jf[:5] == pf[:5]
                and jf[6:] == pf[6:]
                and abs(float(jf[5]) - float(pf[5])) <= _WIDTH_FROM_FONT_TOL
            ):
                continue
        diffs.append(f"  line {i}: java={j_raw!r} py={p_raw!r}")

    assert not diffs, (
        f"Type1C simple-font parity broken for {label}:\n" + "\n".join(diffs[:40])
    )
