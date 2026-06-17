"""Live Apache PDFBox differential parity for the embedded Type 1 font
program surface (``pypdfbox.fontbox.type1.Type1Font``).

For each ``PDType1Font`` in a PDF whose ``/FontDescriptor`` carries a classic
``/FontFile`` (Type 1 / PFB) program, both implementations reach the FontBox
``Type1Font`` and expose:

* the font name,
* the 6-element font matrix,
* the encoding (code -> glyph name for codes 0..255 that map), and
* ``getWidth(name)`` / ``hasGlyph(name)`` for the font's own charstring names.

``oracle/probes/Type1FontProbe.java`` emits these as canonical lines from
Apache PDFBox; :func:`_pypdfbox_lines` reproduces the same lines from
pypdfbox. The two must agree.

Note on the font matrix: Apache PDFBox stores the matrix entries as Java
``float`` and surfaces e.g. ``0.001`` as ``0.0010000000474974513`` (single
-> double widening). pypdfbox keeps the original decimal. We therefore
compare the matrix numerically (with a small tolerance) rather than as
strings; every other line is compared verbatim.

Fixtures (built by Apache PDFBox itself, so the embedded ``/FontFile`` is
authoritative):

* ``DemoType1Embedded.pdf`` — StandardEncoding Type 1, glyphs A/B/C/space.
* ``CustomEncType1Embedded.pdf`` — custom Encoding vector (1->A, 2->B,
  3->C), the discriminating case for the code->name map.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"

_PDFS = [
    "DemoType1Embedded.pdf",
    "CustomEncType1Embedded.pdf",
]


def _canon_number(value: float) -> str:
    """Render a number the way the Java probe's ``canonNumber`` does:
    integral values as plain integers, otherwise the default repr."""
    if value == int(value):
        return str(int(value))
    return repr(float(value))


def _pypdfbox_lines(pdf_path: Path) -> list[str]:
    """Reproduce the probe's canonical lines from pypdfbox: walk each page's
    embedded ``PDType1Font`` programs and emit FONT / NAME / MATRIX / ENC /
    GLYPH rows in the same deterministic order as ``Type1FontProbe``."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        index = 0
        for page in doc.get_pages():
            resources = page.get_resources()
            if resources is None:
                continue
            for name in resources.get_font_names():
                font = resources.get_font(name)
                if not isinstance(font, PDType1Font):
                    continue
                t1 = font._get_type1_font()
                if t1 is None:
                    continue
                lines.append(f"FONT {index}")
                index += 1
                lines.append(f"NAME {t1.get_name()}")
                matrix = t1.get_font_matrix()
                lines.append(
                    "MATRIX " + " ".join(_canon_number(v) for v in matrix)
                )
                encoding = t1.get_encoding()
                for code in sorted(encoding):
                    glyph = encoding[code]
                    if glyph == ".notdef":
                        continue
                    lines.append(f"ENC {code} {glyph}")
                for glyph in sorted(t1.get_char_strings_dict()):
                    has = "true" if t1.has_glyph(glyph) else "false"
                    width = _canon_number(t1.get_width(glyph))
                    lines.append(f"GLYPH {glyph} {has} {width}")
    finally:
        doc.close()
    return lines


def _split_records(lines: list[str]) -> dict[str, dict[str, object]]:
    """Group canonical lines by FONT index into a structured record so the
    MATRIX line can be compared numerically while everything else stays a
    verbatim string compare."""
    records: dict[str, dict[str, object]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("FONT "):
            current = line.split(" ", 1)[1]
            records[current] = {"matrix": [], "other": []}
        elif line.startswith("MATRIX "):
            assert current is not None
            records[current]["matrix"] = [
                float(tok) for tok in line.split()[1:]
            ]
        else:
            assert current is not None
            records[current]["other"].append(line)  # type: ignore[union-attr]
    return records


@requires_oracle
@pytest.mark.parametrize("pdf_name", _PDFS)
def test_type1_font_matches_pdfbox(pdf_name: str) -> None:
    pdf_path = _FIXTURES / pdf_name
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"

    java = run_probe_text("Type1FontProbe", str(pdf_path)).splitlines()
    py = _pypdfbox_lines(pdf_path)

    java_rec = _split_records(java)
    py_rec = _split_records(py)

    # At least one embedded Type 1 font must have been reached on both sides.
    assert java_rec, "PDFBox reached no embedded Type1 font"
    assert py_rec.keys() == java_rec.keys()

    for key in java_rec:
        # NAME / ENC / GLYPH lines: verbatim.
        assert py_rec[key]["other"] == java_rec[key]["other"]
        # MATRIX: numeric (PDFBox widens float->double).
        jm = java_rec[key]["matrix"]
        pm = py_rec[key]["matrix"]
        assert isinstance(jm, list) and isinstance(pm, list)
        assert len(pm) == len(jm) == 6
        for a, b in zip(pm, jm, strict=True):
            assert a == pytest.approx(b, abs=1e-6)


@requires_oracle
def test_custom_encoding_codes_match_pdfbox() -> None:
    """Focused check on the custom Encoding vector (the discriminating
    code->name case): pypdfbox's parsed code->name map equals PDFBox's."""
    pdf_path = _FIXTURES / "CustomEncType1Embedded.pdf"
    java = run_probe_text("Type1FontProbe", str(pdf_path)).splitlines()
    py = _pypdfbox_lines(pdf_path)

    java_enc = sorted(line for line in java if line.startswith("ENC "))
    py_enc = sorted(line for line in py if line.startswith("ENC "))
    assert py_enc == java_enc
    # Sanity: the discriminating mapping is actually present.
    assert "ENC 1 A" in py_enc
    assert "ENC 2 B" in py_enc
    assert "ENC 3 C" in py_enc
