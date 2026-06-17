"""Live Apache PDFBox differential parity for the PD-level read surface of a
simple Type 1 font that embeds its program as a classic raw ``/FontFile``
(segmented PFA/PFB with ``/Length1``/``/Length2``/``/Length3``).

This is the *PDFont* read surface — as distinct from
``tests/fontbox/type1/oracle/test_type1_font_oracle.py`` which reaches the
FontBox ``Type1Font`` program directly. Here we exercise exactly the methods
a renderer / text-extractor calls on the :class:`PDType1Font`:

* :meth:`PDType1Font.is_embedded` — true for ``/FontFile``;
* :meth:`PDType1Font.get_encoding` — for a ``/FontFile`` font with no
  ``/Encoding`` dict this comes from the program's *built-in* encoding
  (upstream ``getEncodingFromFont``), surfaced as a ``Type1Encoding``;
* :meth:`PDType1Font.code_to_name` — per-code glyph name;
* :meth:`PDType1Font.get_width` — per-code advance (1/1000 em);
* :meth:`PDType1Font.has_glyph` — per-name glyph presence.

``oracle/probes/Type1FontFileReadProbe.java`` emits these as canonical lines
from Apache PDFBox 3.0.7; :func:`_pypdfbox_lines` reproduces the same lines
from pypdfbox. The two must agree verbatim.

Fixtures (built by Apache PDFBox itself, so the embedded ``/FontFile`` is the
authoritative source — neither carries an ``/Encoding`` dict, so the resolved
encoding is the program's built-in one):

* ``DemoType1Embedded.pdf`` — StandardEncoding Type 1, glyphs A/B/C/space.
* ``CustomEncType1Embedded.pdf`` — custom built-in Encoding (1->A, 2->B,
  3->C), the discriminating code->name case.
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
    """Reproduce the probe's canonical lines from pypdfbox: for each embedded
    ``PDType1Font`` emit FONT / ENC / CODE / HASGLYPH rows in the same
    deterministic order as ``Type1FontFileReadProbe``."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page in doc.get_pages():
            resources = page.get_resources()
            if resources is None:
                continue
            for name in resources.get_font_names():
                font = resources.get_font(name)
                if not isinstance(font, PDType1Font):
                    continue
                embedded = "true" if font.is_embedded() else "false"
                descriptor = font.get_font_descriptor()
                has_font_file = "true" if (
                    descriptor is not None
                    and descriptor.get_font_file() is not None
                ) else "false"
                program = font.get_type1_font()
                program_name = program.get_name() if program is not None else "null"
                lines.append(
                    f"FONT {font.get_name()} {font.get_sub_type()} "
                    f"{embedded} {has_font_file} {program_name}"
                )

                enc = font.get_encoding_typed()
                enc_class = type(enc).__name__ if enc is not None else "null"
                lines.append(f"ENC {enc_class}")

                for code in range(256):
                    glyph = font.code_to_name(code)
                    width = _canon_number(font.get_width(code))
                    lines.append(f"CODE {code} {glyph} {width}")

                if program is not None:
                    for glyph in sorted(program.get_char_strings_dict()):
                        has = "true" if font.has_glyph(glyph) else "false"
                        lines.append(f"HASGLYPH {glyph} {has}")
    finally:
        doc.close()
    return lines


@requires_oracle
@pytest.mark.parametrize("pdf_name", _PDFS)
def test_type1_fontfile_read_matches_pdfbox(pdf_name: str) -> None:
    pdf_path = _FIXTURES / pdf_name
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"

    java = run_probe_text("Type1FontFileReadProbe", str(pdf_path)).splitlines()
    py = _pypdfbox_lines(pdf_path)

    # The probe must have reached an embedded Type 1 font.
    assert any(line.startswith("FONT ") for line in java), (
        f"PDFBox reached no embedded Type1 font for {pdf_name}: {java[:5]}"
    )
    assert py == java


@requires_oracle
def test_custom_builtin_encoding_codes_match_pdfbox() -> None:
    """Focused check on the custom built-in Encoding vector recovered through
    the PDType1Font surface (no /Encoding dict — encoding comes from the
    embedded program): pypdfbox's code->name + per-code width equals PDFBox's
    for the discriminating codes."""
    pdf_path = _FIXTURES / "CustomEncType1Embedded.pdf"
    java = run_probe_text("Type1FontFileReadProbe", str(pdf_path)).splitlines()
    py = _pypdfbox_lines(pdf_path)

    java_code = sorted(line for line in java if line.startswith("CODE "))
    py_code = sorted(line for line in py if line.startswith("CODE "))
    assert py_code == java_code
    # Sanity: the discriminating built-in mapping is actually present.
    assert "CODE 1 A 600" in py_code
    assert "CODE 2 B 700" in py_code
    assert "CODE 3 C 650" in py_code
