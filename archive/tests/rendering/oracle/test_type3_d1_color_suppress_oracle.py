"""Live PDFBox differential parity for Type 3 ``d1`` colour-operator SUPPRESSION.

Wave 1496. Companion to ``test_type3_font_render_oracle.py``, which pins that a
``d1`` glyph whose charproc sets *no* colour inherits the text-state colour, and
that a ``d0`` glyph keeps its own colour. The orthogonal gap that file does NOT
cover is the active suppression branch: a ``d1`` ("uncoloured-mask") glyph whose
charproc *attempts* to set its own colour. Per PDF 32000-1 §9.6.5.3 those colour
operators MUST be ignored — the glyph paints in the surrounding text-state
non-stroking colour regardless of what the charproc tries to set. Apache PDFBox
implements this via ``PDFStreamEngine.isShouldProcessColorOperators() == false``
for a charproc that begins with ``d1``; pypdfbox mirrors it in the renderer with
``_type3_ignore_color`` + ``_COLOR_OPS`` (``pypdfbox/rendering/pdf_renderer.py``).

A grey-luminance fingerprint can mask a colour bug (red and blue have similar
luminance), so this file samples exact per-channel RGB via
``oracle/probes/PixelSampleProbe.java`` and asserts each channel against the live
Java render. Two glyphs prove the gate cuts both ways:

* ``d1_blue_attempt`` — a ``d1`` box whose charproc runs ``0 0 1 rg`` (blue)
  before its fill, under a RED page text state. Correct render: the box is RED
  (the blue is suppressed). A renderer that fails to suppress paints it BLUE —
  caught by the per-channel R/B assertion.
* ``d0_own_blue`` — a ``d0`` box that runs the SAME ``0 0 1 rg`` before its
  fill, under the same red text state. A ``d0`` glyph is coloured: the blue is
  HONOURED, so the box is BLUE. This is the control proving the suppression is
  ``d1``-specific and not a blanket "ignore colour in every charproc".

Both fixtures are pypdfbox-authored (no Type 3 corpus fixture ships). The
``d1``-vs-``d0`` pair therefore lands on opposite colours from a single shared
charproc body, so a suppression bug in either direction (suppressing ``d0`` too,
or not suppressing ``d1``) flips a sampled pixel and fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

# Per-channel exact-colour tolerance — sRGB rounding / AA at the box centre only.
_CHANNEL_TOL = 12

_PAGE_W = 120.0
_PAGE_H = 120.0
_FONT_MATRIX = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------------------------------------------------------------------------
# /CharProcs glyph streams — both attempt ``0 0 1 rg`` (blue) before the fill.
# ---------------------------------------------------------------------------


def _char_proc_d1_blue() -> COSStream:
    """Code 65: a ``d1`` glyph whose charproc tries to set BLUE before filling a
    900x900 box. The ``0 0 1 rg`` MUST be suppressed (d1 uncoloured-mask), so the
    box paints in the page's RED text-state colour."""
    body = b"900 0 0 0 900 900 d1\n0 0 1 rg\n0 0 900 900 re f\n"
    stream = COSStream()
    stream.set_data(body)
    return stream


def _char_proc_d0_blue() -> COSStream:
    """Code 66: a ``d0`` glyph with the SAME ``0 0 1 rg`` before the fill. A
    ``d0`` glyph is coloured — the blue is HONOURED, so the box paints BLUE."""
    body = b"900 0 d0\n0 0 1 rg\n0 0 900 900 re f\n"
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_type3_font_dict() -> COSDictionary:
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("d1box"), _char_proc_d1_blue())
    char_procs.set_item(COSName.get_pdf_name("d0box"), _char_proc_d0_blue())

    differences = COSArray()
    differences.add(COSInteger.get(65))
    differences.add(COSName.get_pdf_name("d1box"))
    differences.add(COSName.get_pdf_name("d0box"))
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3")
    )
    font_dict.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("T3"))
    font_dict.set_item(
        COSName.get_pdf_name("FontMatrix"),
        COSArray([COSFloat(v) for v in _FONT_MATRIX]),
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontBBox"),
        COSArray([COSInteger.get(v) for v in (0, 0, 900, 900)]),
    )
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, 65)
    font_dict.set_int(COSName.LAST_CHAR, 66)
    font_dict.set_item(
        COSName.get_pdf_name("Widths"), COSArray([COSFloat(900.0), COSFloat(900.0)])
    )
    return font_dict


def _build(out: Path, glyph_code: int) -> Path:
    """One-page PDF showing a single glyph (``glyph_code``) at 100pt under a RED
    page text state, lower-left anchored so the 90x90pt box covers the page."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    doc.add_page(page)

    font = PDType3Font(_build_type3_font_dict())
    res = PDResources()
    res.put(COSName.get_pdf_name("F1"), font)
    font.set_resources(PDResources())
    page.set_resources(res)

    content = (
        b"BT\n1 0 0 rg\n/F1 100 Tf\n5 5 Td\n<"
        + f"{glyph_code:02X}".encode("ascii")
        + b"> Tj\nET\n"
    )
    cs = COSStream()
    cs.set_data(content)
    page.set_contents(cs)
    doc.save(str(out))
    doc.close()
    return out


# Centre of the page (and of the 90x90pt box at 72 DPI on a 120x120pt page).
_SAMPLE = (60, 60)

# (glyph_code, expected_centre_rgb). d1 → red (blue suppressed); d0 → blue.
_CASES = {
    "d1_blue_suppressed": (65, (255, 0, 0)),
    "d0_blue_honoured": (66, (0, 0, 255)),
}


def _oracle_pixel(fixture: Path) -> tuple[tuple[int, int], tuple[int, int, int]]:
    lines = run_probe_text(
        "PixelSampleProbe", str(fixture), "0", f"{_SAMPLE[0]},{_SAMPLE[1]}"
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    r, g, b = (int(v) for v in lines[1].split())
    return (width, height), (r, g, b)


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_type3_d1_color_suppression_matches_pdfbox(
    label: str, tmp_path: Path
) -> None:
    """The box centre must render the SAME per-channel RGB as Java PDFBox 3.0.7:
    red for the ``d1`` glyph (its ``0 0 1 rg`` is suppressed), blue for the
    ``d0`` glyph (its ``0 0 1 rg`` is honoured)."""
    glyph_code, _expected = _CASES[label]
    fixture = _build(tmp_path / f"{label}.pdf", glyph_code)

    (java_w, java_h), jrgb = _oracle_pixel(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    py_w, py_h = img.size
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    prgb = img.getpixel(_SAMPLE)
    for ch in range(3):
        assert abs(prgb[ch] - jrgb[ch]) <= _CHANNEL_TOL, (
            f"{label}: box-centre pixel {_SAMPLE} channel {ch} "
            f"pypdfbox={prgb[ch]} java={jrgb[ch]} "
            f"(diff {abs(prgb[ch] - jrgb[ch])} > {_CHANNEL_TOL})"
        )


@requires_oracle
def test_d1_and_d0_render_opposite_colours(tmp_path: Path) -> None:
    """Guard the gate: the d1 and d0 glyphs — built from the SAME ``0 0 1 rg``
    charproc body — must land on materially DIFFERENT colours in the live Java
    render (red vs blue). If they matched, the per-channel assertion above could
    be satisfied by a renderer that ignores colour everywhere (or nowhere); this
    proves the suppression is genuinely d1-specific in PDFBox itself."""
    d1_fixture = _build(tmp_path / "d1.pdf", 65)
    d0_fixture = _build(tmp_path / "d0.pdf", 66)
    (_d1, d1_rgb) = _oracle_pixel(d1_fixture)
    (_d0, d0_rgb) = _oracle_pixel(d0_fixture)
    # d1 centre is red-dominant, d0 centre is blue-dominant.
    assert d1_rgb[0] > d1_rgb[2] + 100, (
        f"d1 glyph centre not red-dominant in Java render: {d1_rgb}"
    )
    assert d0_rgb[2] > d0_rgb[0] + 100, (
        f"d0 glyph centre not blue-dominant in Java render: {d0_rgb}"
    )
