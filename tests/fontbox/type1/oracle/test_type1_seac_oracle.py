"""Live Apache FontBox differential parity for the Type 1 charstring
*advance width* prologue, including the ``seac`` accent composite.

Companion to ``tests/fontbox/type1/oracle/test_type1_glyph_path_oracle.py``
(which fingerprints the glyph OUTLINE geometry). This file isolates the WIDTH
side of the interpreter — the ``hsbw`` (horizontal side-bearing + width) and
``sbw`` (full side-bearing + width) operators that set each glyph's advance —
reached straight from a standalone ``.pfb`` program via
``Type1Font.createWithPFB(bytes)`` then ``Type1Font.getWidth(glyphName)``.

The discriminating case is the ``seac`` standard-encoding accented character
(``eacute`` = ``e`` base + ``acute`` accent in ``SeacType1.pfb``). The Type 1
spec takes a composite glyph's advance width from the COMPOSITE charstring's
*own* ``hsbw`` width argument, NOT from the base glyph's. ``seac`` itself
supplies an ``asb`` (accent side bearing) used only to position the accent;
the advance stays whatever ``hsbw`` declared at the top of the ``eacute``
program. Here ``eacute`` declares width 700 while its base ``e`` is also 700,
so the value alone isn't load-bearing — what's pinned is that pypdfbox and
FontBox derive the SAME advance for the composite, the accent, and the base.

``oracle/probes/Type1WidthProbe.java`` emits ``WIDTH <glyph> <advance>`` lines
(glyph name ascending) from Apache FontBox; this test reproduces them from
pypdfbox's ``Type1Font.get_width`` and asserts they agree verbatim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.type1.type1_font import Type1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"

# Bundled, permissive Type 1 programs (built by pypdfbox / fontTools t1Lib).
_PFBS = [
    "DemoType1.pfb",       # StandardEncoding boxes: A/B/C/space + .notdef
    "CustomEncType1.pfb",  # custom Encoding vector, same box glyphs
    "SeacType1.pfb",       # boxes + a seac composite (eacute = e + acute)
    "CurvedFlexType1.pfb",  # curved O + flex o
]


def _canon_number(value: float) -> str:
    """Render a number the way the Java probe's ``canonNumber`` does: an
    integral value as a plain integer, otherwise the default float string."""
    if value == int(value):
        return str(int(value))
    return repr(float(value))


def _parse_probe(text: str) -> tuple[str, dict[str, str]]:
    """Parse the probe stdout into (font name, {glyphName: advance string})."""
    name = ""
    widths: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("NAME "):
            name = line[len("NAME ") :]
        elif line.startswith("WIDTH "):
            rest = line[len("WIDTH ") :]
            glyph, _, payload = rest.partition(" ")
            widths[glyph] = payload
    return name, widths


@requires_oracle
@pytest.mark.parametrize("pfb", _PFBS)
def test_type1_width_matches_pdfbox(pfb: str) -> None:
    fixture = _FIXTURES / pfb
    java_name, java_widths = _parse_probe(
        run_probe_text("Type1WidthProbe", str(fixture))
    )

    font = Type1Font.create_with_pfb(fixture.read_bytes())
    assert font.get_name() == java_name

    names = sorted(font.get_char_strings_dict().keys())
    # The probe walks the same TreeSet of charstring names.
    assert set(names) == set(java_widths.keys())

    for glyph in names:
        py_payload = _canon_number(font.get_width(glyph))
        assert py_payload == java_widths[glyph], (
            f"{pfb}:{glyph}: pypdfbox width {py_payload!r} != FontBox "
            f"{java_widths[glyph]!r}"
        )


@requires_oracle
def test_seac_composite_advance_matches_base_and_pdfbox() -> None:
    """Pin the ``seac`` composite advance explicitly: ``eacute`` takes its
    advance from its own ``hsbw`` (700), matching FontBox, and the accent /
    base glyphs it composes also agree."""
    fixture = _FIXTURES / "SeacType1.pfb"
    _, java_widths = _parse_probe(run_probe_text("Type1WidthProbe", str(fixture)))
    font = Type1Font.create_with_pfb(fixture.read_bytes())

    for glyph in ("eacute", "e", "acute"):
        assert glyph in java_widths
        assert _canon_number(font.get_width(glyph)) == java_widths[glyph]

    # The composite's advance comes from its own hsbw prologue.
    assert _canon_number(font.get_width("eacute")) == "700"
