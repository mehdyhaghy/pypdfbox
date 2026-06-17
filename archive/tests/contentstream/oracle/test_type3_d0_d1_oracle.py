"""Live PDFBox differential parity for the Type 3 glyph-procedure metric
operators ``d0`` (SetCharWidth) and ``d1`` (SetCharWidthAndBoundingBox),
focused on the colour-handling distinction PDF 32000-1 §9.6.5.3 mandates.

A Type 3 glyph procedure must begin with one of:

    wx wy                  d0      (coloured glyph)
    wx wy llx lly urx ury  d1      (uncoloured-mask glyph)

``d1`` declares the glyph an *uncoloured mask*: colour-setting operators inside
the charproc (``rg`` / ``g`` / ``k`` / ``sc`` / ``scn`` / ``cs`` ...) are
IGNORED and the glyph paints in the surrounding text-state non-stroking colour.
``d0`` declares a *coloured* glyph that paints with its own colour operators.
Apache PDFBox enforces this via
``PDFStreamEngine.isShouldProcessColorOperators() == false`` while a ``d1``
charproc is processed.

The companion ``tests/rendering/oracle/test_type3_font_render_oracle.py``
already covers a ``d1`` glyph that sets *no* colour of its own (inherits the
text state) and a ``d0`` glyph that sets its own colour. It does NOT cover the
load-bearing case here: a ``d1`` glyph that sets a colour op which CONTRADICTS
the text-state colour — the only way to prove the colour op is genuinely
ignored rather than merely absent. Wave 1454 found pypdfbox honoured that
internal colour op (painting the glyph in the charproc's colour) where PDFBox
ignores it; this test pins the fix.

Because a luminance grid cannot tell red from green (near-equal luma), the
probe emits a coarse per-cell **RGB** grid. Each fixture is rendered at 72 DPI
through Apache PDFBox (``oracle/probes/Type3D0D1Probe.java``) and through
pypdfbox; the grids are compared per-channel with a tolerance that survives
anti-aliasing (Java2D vs Pillow/aggdraw) but catches a wrong d0/d1 colour
decision (a 255-level channel flip).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

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

_GRID = 8
# Per-channel mean-absolute-diff / worst-cell tolerance. A wrong d0/d1 colour
# decision flips a whole channel by ~255 in the glyph cells (red<->green), so
# the gate sits comfortably below that while absorbing AA differences between
# Java2D and Pillow/aggdraw.
_MAD_TOLERANCE = 12.0
_MAXDIFF_TOLERANCE = 90

_PAGE_W = 100.0
_PAGE_H = 100.0
_FONT_MATRIX = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def _stream(body: bytes) -> COSStream:
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_type3_font_dict(box_body: bytes, bar_body: bytes) -> COSDictionary:
    """A Type 3 font with two glyphs: code 65 ('box') and 66 ('bar'), each a
    full glyph-cell filled rectangle. The bodies supplied decide whether the
    glyph leads with ``d0`` or ``d1`` and what (if any) colour op it sets."""
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("box"), _stream(box_body))
    char_procs.set_item(COSName.get_pdf_name("bar"), _stream(bar_body))

    differences = COSArray()
    differences.add(COSInteger.get(65))
    differences.add(COSName.get_pdf_name("box"))
    differences.add(COSName.get_pdf_name("bar"))
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
        COSArray([COSInteger.get(v) for v in (0, 0, 1000, 1000)]),
    )
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, 65)
    font_dict.set_int(COSName.LAST_CHAR, 66)
    font_dict.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSFloat(1000.0), COSFloat(1000.0)]),
    )
    return font_dict


def _build(out: Path, content: bytes, box_body: bytes, bar_body: bytes) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    doc.add_page(page)

    font = PDType3Font(_build_type3_font_dict(box_body, bar_body))
    res = PDResources()
    res.put(COSName.get_pdf_name("F1"), font)
    font.set_resources(PDResources())
    page.set_resources(res)

    cs = COSStream()
    cs.set_data(content)
    page.set_contents(cs)
    doc.save(str(out))
    doc.close()
    return out


# d1 glyph that sets its OWN red fill inside the (uncoloured-mask) charproc.
# Page text-state colour is green. Per spec the internal ``1 0 0 rg`` MUST be
# ignored, so the glyph paints green. (Before wave 1454 pypdfbox painted red.)
_BOX_D1_RED = b"1000 0 0 0 1000 1000 d1\n1 0 0 rg\n0 0 1000 1000 re f\n"
# d0 glyph that sets its OWN red fill. ``d0`` is a coloured glyph: the internal
# colour op is honoured, so the glyph paints red on the same green text state.
_BAR_D0_RED = b"1000 0 d0\n1 0 0 rg\n0 0 1000 1000 re f\n"

_BUILDERS: dict[str, tuple[bytes, bytes, bytes]] = {
    # Show code 65 ('box', d1): green expected (internal red rg ignored).
    "d1_ignores_internal_color": (
        b"BT\n0 1 0 rg\n/F1 90 Tf\n5 5 Td\n<41> Tj\nET\n",
        _BOX_D1_RED,
        _BAR_D0_RED,
    ),
    # Show code 66 ('bar', d0): red expected (internal red rg honoured).
    "d0_honors_internal_color": (
        b"BT\n0 1 0 rg\n/F1 90 Tf\n5 5 Td\n<42> Tj\nET\n",
        _BOX_D1_RED,
        _BAR_D0_RED,
    ),
}


def _rgb_grid_from_image(img: Image.Image) -> list[int]:
    """Mean R, G, B per cell over an ``_GRID`` x ``_GRID`` grid — mirrors
    ``Type3D0D1Probe.java``'s cell mapping exactly."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    sum_r = [0] * (_GRID * _GRID)
    sum_g = [0] * (_GRID * _GRID)
    sum_b = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            r, g, b = pixels[x, y]
            sum_r[idx] += r
            sum_g[idx] += g
            sum_b[idx] += b
            count[idx] += 1
    out: list[int] = []
    for i in range(_GRID * _GRID):
        c = count[i] if count[i] else 1
        out.append(round(sum_r[i] / c))
        out.append(round(sum_g[i] / c))
        out.append(round(sum_b[i] / c))
    return out


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("Type3D0D1Probe", str(fixture)).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID * 3
    return (width, height), grid


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_type3_d0_d1_color_matches_pdfbox(label: str, tmp_path: Path) -> None:
    content, box_body, bar_body = _BUILDERS[label]
    fixture = _build(tmp_path / f"{label}.pdf", content, box_body, bar_body)
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _rgb_grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs channel diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — d0/d1 colour decision diverges from PDFBox"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst channel diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a glyph cell colour-flips relative to PDFBox"
    )


@requires_oracle
def test_d1_internal_color_would_flip_a_channel(tmp_path: Path) -> None:
    """Guard the gate: prove the d1 case genuinely discriminates the colour
    op being ignored vs honoured. PDFBox's d1 render is green; a hypothetical
    red render (the pre-fix pypdfbox behaviour) would blow far past the gate.
    """
    content, box_body, bar_body = _BUILDERS["d1_ignores_internal_color"]
    fixture = _build(tmp_path / "d1_guard.pdf", content, box_body, bar_body)
    _dims, java_grid = _oracle_signature(fixture)

    # Synthesise the wrong (honour-internal-red) render by swapping R/G in the
    # green glyph cells: any cell whose green channel dominates becomes red.
    wrong = list(java_grid)
    for i in range(0, len(wrong), 3):
        r, g, b = wrong[i], wrong[i + 1], wrong[i + 2]
        wrong[i], wrong[i + 1], wrong[i + 2] = g, r, b
    diffs = [abs(a - b) for a, b in zip(java_grid, wrong, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose — a red (honour-internal-colour) d1 render would "
        f"pass the MAD gate, so the d1 colour-ignore fix would not be caught "
        f"(swapped MAD {mad:.2f})"
    )
