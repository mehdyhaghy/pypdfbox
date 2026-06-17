"""Live Apache PDFBox round-trip parity for pypdfbox's Type 1 embedding.

This is the *inverse* of ``tests/fontbox/type1/oracle/test_type1_font_oracle.py``
(which reads a PDFBox-built fixture). Here pypdfbox itself embeds a classic
Type 1 (``/FontFile``, PFB) font program into a fresh PDF, saves it, and we
assert two things:

* (a) pypdfbox reloads its own output and recovers the per-glyph widths and
  the code -> glyph-name encoding from the embedded program; and
* (b) Apache PDFBox can READ pypdfbox's embedded output — it reaches
  ``PDType1Font.getType1Font()`` and reports the same font name, encoding and
  per-glyph widths (via ``oracle/probes/Type1EmbedProbe.java``).

This guards the wave-1416 ``DEFERRED.md`` bug: pypdfbox's own Type 1 embed
path was broken (``T1Font(BytesIO)`` raised ``TypeError`` — fontTools'
constructor only accepts a file path), plus two further latent bugs the fix
surfaced (the ``/FontFile`` stream was tagged ``FlateDecode`` but stored
uncompressed; widths were read pre-draw and were always 0).

Fixtures are the wave-1416 PFB programs under
``tests/fixtures/fontbox/type1/``:

* ``DemoType1.pfb`` — StandardEncoding Type 1, glyphs A/B/C/space.
* ``CustomEncType1.pfb`` — custom Encoding vector (1->A, 2->B, 3->C).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"

# (fixture, expected program name, {glyph name: width}, {code: glyph name})
_CASES = [
    (
        "DemoType1.pfb",
        "DemoType1",
        {".notdef": 250, "A": 600, "B": 700, "C": 650, "space": 300},
        # StandardEncoding subset that actually maps to a glyph in this font.
        {32: "space", 65: "A", 66: "B", 67: "C"},
    ),
    (
        "CustomEncType1.pfb",
        "CustomEncType1",
        {".notdef": 250, "A": 600, "B": 700, "C": 650},
        {1: "A", 2: "B", 3: "C"},
    ),
]


def _embed_to_pdf(pfb_name: str, out_path: Path) -> None:
    """Build a one-page PDF embedding the named PFB Type 1 font via
    pypdfbox and save it to ``out_path``."""
    pfb_bytes = (_FIXTURES / pfb_name).read_bytes()
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType1Font.load(doc, pfb_bytes)
        resources = PDResources()
        resources.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(resources)
        doc.save(str(out_path))
    finally:
        doc.close()


def _canon_number(value: float) -> str:
    """Render a number the way the Java probe's ``canonNumber`` does."""
    if value == int(value):
        return str(int(value))
    return repr(float(value))


def test_pypdfbox_reads_back_its_own_type1_embed(tmp_path: Path) -> None:
    """(a) pypdfbox embeds a Type 1 font, saves, reloads, and recovers the
    program's glyph widths + encoding from its own ``/FontFile`` output.

    This part does NOT need the oracle — it pins the embed bug fix on its
    own so the suite stays green on machines without Java."""
    for pfb_name, prog_name, widths, codes in _CASES:
        out = tmp_path / f"{Path(pfb_name).stem}.pdf"
        _embed_to_pdf(pfb_name, out)

        doc = PDDocument.load(out)
        try:
            page = next(iter(doc.get_pages()))
            resources = page.get_resources()
            assert resources is not None
            names = list(resources.get_font_names())
            assert names, "no font landed in the reloaded resources"
            font = resources.get_font(names[0])
            assert isinstance(font, PDType1Font)
            assert font.get_name() == prog_name
            assert font.is_embedded()

            program = font._get_type1_font()
            assert program is not None, "embedded /FontFile did not parse back"
            assert program.get_name() == prog_name

            # Per-glyph widths recovered from the embedded program.
            for glyph, expected in widths.items():
                assert program.get_width(glyph) == pytest.approx(expected)

            # Built-in encoding (code -> glyph) recovered from the program.
            program_encoding = program.get_encoding()
            for code, glyph in codes.items():
                assert program_encoding.get(code) == glyph

            # The PDF-level /Widths array pypdfbox wrote agrees with the
            # program advance at each mapped code.
            for code, glyph in codes.items():
                assert font.get_width(code) == pytest.approx(widths[glyph])
        finally:
            doc.close()


@requires_oracle
def test_pdfbox_reads_pypdfbox_type1_embed(tmp_path: Path) -> None:
    """(b) Apache PDFBox reads pypdfbox's embedded Type 1 output: same font
    name, encoding and per-glyph widths via ``PDType1Font.getType1Font()``."""
    for pfb_name, prog_name, widths, codes in _CASES:
        out = tmp_path / f"{Path(pfb_name).stem}.pdf"
        _embed_to_pdf(pfb_name, out)

        lines = run_probe_text("Type1EmbedProbe", str(out)).splitlines()

        # PDFBox must have reached an embedded Type 1 font.
        assert any(line.startswith("FONT ") for line in lines), (
            f"PDFBox reached no embedded Type1 font for {pfb_name}: {lines}"
        )
        assert f"BASEFONT {prog_name}" in lines
        assert f"T1NAME {prog_name}" in lines

        # Encoding (code -> glyph) PDFBox recovered from the program.
        enc_lines = {line for line in lines if line.startswith("ENC ")}
        for code, glyph in codes.items():
            assert f"ENC {code} {glyph}" in enc_lines, (
                f"missing ENC {code} {glyph} for {pfb_name}"
            )

        # Per-glyph widths PDFBox recovered from the program.
        glyph_lines = {line for line in lines if line.startswith("GLYPH ")}
        for glyph, expected in widths.items():
            assert f"GLYPH {glyph} true {_canon_number(expected)}" in glyph_lines, (
                f"missing GLYPH {glyph} {expected} for {pfb_name}"
            )

        # PDF-level /Widths array (PDW lines) at each mapped code.
        pdw_lines = {line for line in lines if line.startswith("PDW ")}
        for code, glyph in codes.items():
            assert f"PDW {code} {_canon_number(widths[glyph])}" in pdw_lines, (
                f"missing PDW {code} for {pfb_name}"
            )
