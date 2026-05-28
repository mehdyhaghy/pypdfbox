"""Live PDFBox differential parity for the **rendered** glyph positions
under the text-state spacing parameters (PDF 32000-1 §9.3 / §9.4.4):

============  ===========================================================
parameter     effect on the painted glyphs
============  ===========================================================
``Tc``        character spacing — extra advance after every glyph, so the
              glyphs spread apart along the baseline.
``Tw``        word spacing — extra advance after a single-byte code 32
              (space), so words separate further.
``Tz``        horizontal scaling (percent) — scales the glyph outline
              horizontally *and* the advance, so a ``Tz 50`` row is half
              as wide and the glyphs themselves are squeezed.
``Ts``        text rise — shifts each glyph off the baseline (positive =
              up, superscript), without changing the advance.
``TJ``        a numeric array entry adjusts the text matrix tx by
              ``-num/1000 * font_size * Tz`` — a large negative number
              opens an extra gap between the surrounding strings.
============  ===========================================================

Wave 1430 covered these same parameters in *extraction* (the text-stripper
``getText`` positions). This file is the orthogonal half: the **rendered
pixel** positions of the painted glyphs under each parameter must match
Apache PDFBox's renderer.

Comparison reuses ``oracle/probes/RenderProbe.java`` (exact rendered
dimensions + a 16x16 average-luminance grid). Pixel-exact parity is
impossible across Java2D vs skia/Pillow (anti-aliasing, sub-pixel
coverage), so the same MAD<6 / MAXDIFF<60 tolerance the other render
oracles calibrated against PDFBox 3.0.7 at 72 DPI applies here.

The glyph source is the embedded ``DemoType1.pfb`` fixture (tiny box
outlines in a 1000-unit em) shown large, exercising the real Type 1
outline draw path through ``_show_string`` / ``_draw_glyph``.

Beyond the per-case MAD gate, extra guards prove each parameter actually
moves the painted glyphs (not just the extraction-side bookkeeping):

* **Tc / Tw / Tz / Ts each differ from a no-spacing baseline** — if the
  parameter were ignored in the glyph-positioning path the render would be
  identical to the baseline and the guard fails.
* **Tz compresses the painted glyph width** — the rightmost dark pixel of
  a ``Tz 50`` row sits well left of the baseline row, proving ``Tz`` scales
  the glyph outline horizontally and not merely the advance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate the other render oracles calibrated for whole-page parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"

# Page sized so the row of large box-outline glyphs fills a good fraction
# of the canvas (keeps the coarse 16x16 grid discriminating).
_PW, _PH, _FS = 220.0, 40.0, 28

# A no-spacing baseline plus one variant per text-state spacing parameter.
# Each variant is built to be clearly distinct from its baseline render.
_CONTENT: dict[str, bytes] = {
    # No spacing — the reference the Tc/Tz/Ts/TJ guards compare against.
    "baseline": b"BT\n/F1 %d Tf\n4 12 Td\n(ABCAB) Tj\nET\n" % (_FS,),
    # Large char spacing — glyphs spread apart along the baseline.
    "tc": b"BT\n/F1 %d Tf\n8 Tc\n4 12 Td\n(ABCAB) Tj\nET\n" % (_FS,),
    # Word-spacing baseline — same string with explicit spaces, no Tw.
    "tw_baseline": b"BT\n/F1 %d Tf\n4 12 Td\n(A B C A) Tj\nET\n" % (_FS,),
    # Large word spacing — the single-byte spaces widen, words separate.
    "tw": b"BT\n/F1 %d Tf\n25 Tw\n4 12 Td\n(A B C A) Tj\nET\n" % (_FS,),
    # Horizontal scaling 50% — glyph outlines + advance squeezed to half.
    "tz": b"BT\n/F1 %d Tf\n50 Tz\n4 12 Td\n(ABCAB) Tj\nET\n" % (_FS,),
    # Text rise +8 — glyphs lifted off the baseline (superscript).
    "ts": b"BT\n/F1 %d Tf\n8 Ts\n4 12 Td\n(ABCAB) Tj\nET\n" % (_FS,),
    # TJ with a large negative adjustment — opens an extra gap between the
    # two "ABC" runs (tx += -(-2000)/1000 * font_size = +2 em widths).
    "tj": b"BT\n/F1 %d Tf\n4 12 Td\n[(ABC) -2000 (AB)] TJ\nET\n" % (_FS,),
}


def _build(out: Path, content: bytes) -> Path:
    """Embed ``DemoType1.pfb`` via pypdfbox, write an explicit
    ``StandardEncoding`` (so the renderer resolves code -> glyph name for
    the embedded Type 1), and lay down ``content`` as the page stream."""
    pfb = (_FIXTURES / "DemoType1.pfb").read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PW, _PH))
        doc.add_page(page)

        font = PDType1Font.load(doc, pfb)
        font._dict.set_item(  # noqa: SLF001
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("StandardEncoding"),
        )

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = COSStream()
        cs.set_data(content)
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror RenderProbe.java's cell mapping exactly
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _py_render(fixture: Path) -> Image.Image:
    with PDDocument.load(fixture) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


def _py_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    img = _py_render(fixture)
    return img.size, _grid_from_image(img)


def _rightmost_dark_x(img: Image.Image, threshold: int = 128) -> int:
    """X coordinate of the rightmost pixel darker than ``threshold`` — a
    proxy for how far the painted glyph run extends horizontally."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    rightmost = 0
    for x in range(width):
        for y in range(height):
            if pixels[x, y] < threshold:
                rightmost = x
                break
    return rightmost


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------

_LABELS = ["baseline", "tc", "tw_baseline", "tw", "tz", "ts", "tj"]


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_text_spacing_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each text-state spacing parameter renders the glyphs at identically
    positioned (within the AA tolerance) pixels as Apache PDFBox 3.0.7."""
    fixture = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _py_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance — catches glyphs painted
    #     at the wrong X/Y (Tc not spacing, Tw ignored, Tz not scaling the
    #     outline, Ts not lifting, TJ wrong sign/scale).
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — glyph positions grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize(
    ("label", "base"),
    [
        ("tc", "baseline"),
        ("tz", "baseline"),
        ("ts", "baseline"),
        ("tw", "tw_baseline"),
    ],
    ids=["tc", "tz", "ts", "tw"],
)
def test_parameter_moves_painted_glyphs(
    label: str, base: str, tmp_path: Path
) -> None:
    """Each spacing parameter must materially change the *painted* glyph
    positions versus its no-spacing baseline. A renderer that parses the
    operator but never feeds it into ``_show_string`` / ``_draw_glyph``
    would render identically to the baseline and fail here."""
    variant = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    reference = _build(tmp_path / f"{base}.pdf", _CONTENT[base])

    _vdims, variant_grid = _py_grid(variant)
    _rdims, reference_grid = _py_grid(reference)
    mad, maxdiff = _mad_maxdiff(variant_grid, reference_grid)
    assert maxdiff > 20, (
        f"{label}: painted output is nearly identical to the {base} "
        f"render (mad={mad:.2f} maxdiff={maxdiff}) — the parameter does "
        f"not affect the rendered glyph positions"
    )


@requires_oracle
def test_horizontal_scaling_compresses_glyph_width(tmp_path: Path) -> None:
    """``Tz 50`` must squeeze the *glyph outlines* horizontally, not just
    shorten the advance: the painted run's rightmost dark pixel under
    ``Tz 50`` sits well left of the un-scaled baseline's. A renderer that
    only halves the advance (leaving full-width glyphs) would overlap them
    but keep roughly the same right edge and fail this guard."""
    baseline = _build(tmp_path / "baseline.pdf", _CONTENT["baseline"])
    scaled = _build(tmp_path / "tz.pdf", _CONTENT["tz"])

    base_right = _rightmost_dark_x(_py_render(baseline))
    scaled_right = _rightmost_dark_x(_py_render(scaled))
    # Tz 50 halves both glyph width and advance, so the whole run is ~half
    # as wide; require the scaled right edge to sit clearly left of the
    # baseline's (well beyond AA jitter).
    assert scaled_right < base_right * 0.75, (
        f"Tz 50 did not compress the painted glyph width: "
        f"baseline right edge={base_right}px scaled={scaled_right}px — "
        f"the glyph outline is not being scaled horizontally"
    )

    # Cross-check the compressed render against PDFBox too.
    _jdims, java_scaled = _oracle_signature(scaled)
    _sdims, py_scaled = _py_grid(scaled)
    mad, maxdiff = _mad_maxdiff(java_scaled, py_scaled)
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"Tz 50 diverges from PDFBox: mad={mad:.2f} maxdiff={maxdiff}"
    )
