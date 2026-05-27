"""Live PDFBox differential parity for an explicit zero-width ``/W`` advance.

Wave 1445. A composite (Type0 / CIDFontType2) font's per-glyph advance comes
from the descendant CIDFont's ``/W`` array (with ``/DW`` as the default for
CIDs ``/W`` does not cover). A ``/W`` entry may legally declare a width of
*exactly 0* — common for combining marks, which sit on top of the preceding
glyph and must not advance the text position. Upstream
``PDFStreamEngine.showText`` resolves the advance via
``font.getDisplacement(code).getX()`` = ``getWidth(code) / 1000`` with **no**
fallback to the embedded program's ``hmtx`` table, so PDFBox honours the
declared 0: the next glyph paints directly over the zero-width glyph.

The bug this guards against (fixed in wave 1445): the renderer's TTF glyph
path (``rendering/pdf_renderer.py::_draw_glyph``) did
``if advance_units <= 0.0: advance_units = ttf.get_advance_width(gid)…`` — so
when ``/W`` declared a code's width as exactly 0, pypdfbox *ignored* the 0 and
fell back to the embedded program's ``hmtx`` advance, advancing the text matrix
by the glyph's natural width and shifting every subsequent glyph. The fix
distinguishes "width ABSENT (use the hmtx / ``/DW`` fallback)" from "width
PRESENT and exactly 0 (honour it)" by gating the hmtx fallback on
``has_explicit_width(code)`` — mirroring upstream's
``getDisplacement`` semantics (PDFBOX-563).

Fixture: ``DejaVuSans.ttf`` embedded (subset OFF) as Type0/Identity-H, showing
``HiH`` where the middle ``i``'s CID is given an explicit ``/W`` of **0**.
With the bug, the trailing ``H`` is pushed ~278/1000 em to the right; with the
fix it overlaps the zero-width ``i`` exactly as PDFBox renders it.

Fingerprint (identical to the page / composite-glyph render oracles):

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs aggdraw) but catches the
  glyph-spacing shift the zero-width bug introduces.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 at 72 DPI: with the fix the zero-width page lands at MAD ~0.3 /
MAXDIFF ~15; with the bug it measured MAXDIFF ~115 (far outside the gate). A
*control* page where the same middle glyph keeps a non-zero ``/W`` also matches
PDFBox — and PDFBox's own zero vs control renders differ by MAXDIFF ~119,
proving the explicit 0 genuinely changes layout (so the test exercises the
zero-advance path, not a no-op).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FONT = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# Three glyphs; the *middle* one ("i") is the one we force to width 0 so the
# trailing "H" must overlap it. Flanking "H"s give the page solid ink at both
# ends so a shift of the trailing "H" is plainly visible in the grid.
_TEXT = "HiH"
_PAGE_W = 120.0
_PAGE_H = 40.0
_FONT_SIZE = 24


def _build(out: Path, *, zero_width: bool) -> float:
    """Embed ``DejaVuSans.ttf`` (subset OFF) as Type0/Identity-H, show
    ``HiH``, and override the descendant ``/W`` so the middle ``i`` has either
    an explicit width of 0 (``zero_width=True``) or its natural advance
    (control). Returns the glyph's natural advance (1/1000 em) for assertions.
    """
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
        doc.add_page(page)

        # subset OFF keeps the full embedded program + full hmtx, so the
        # renderer's hmtx fallback has a real (non-zero) advance available —
        # which is exactly what the bug wrongly used in place of the 0.
        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)

        mid_code = int.from_bytes(font.encode(_TEXT[1]), "big")
        cid = font.code_to_cid(mid_code)
        descendant = font.get_descendant_font()
        natural = descendant.get_glyph_width(cid)

        # Build a /W declaring the middle CID's width explicitly: 0 for the
        # zero-width case, its natural rounded advance for the control. Form
        # ``c [w]`` (single-CID list) per PDF 32000-1 §9.7.4.3.
        w = COSArray()
        w.add(COSInteger.get(cid))
        inner = COSArray()
        inner.add(COSInteger.get(0 if zero_width else int(round(natural))))
        w.add(inner)
        descendant.set_w(w)
        descendant.clear_widths_cache()

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        encoded = font.encode(_TEXT)
        cs = COSStream()
        cs.set_data(
            b"BT\n/F1 %d Tf\n4 8 Td\n<%s> Tj\nET\n"
            % (_FONT_SIZE, encoded.hex().encode("ascii"))
        )
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return float(natural)


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


# ---------------------------------------------------------------------------
# fixture proof: the /W really declares an explicit 0 for the shown code
# ---------------------------------------------------------------------------


def test_fixture_declares_explicit_zero_width(tmp_path: Path) -> None:
    """Prove the test exercises the explicit-zero path: the saved PDF's
    descendant ``/W`` declares the middle ``i``'s CID width as exactly 0,
    ``has_explicit_width`` reports True for that code, and the resolved
    glyph width is 0 (NOT the embedded program's non-zero hmtx advance)."""
    out = _build(tmp_path / "zero.pdf", zero_width=True)
    assert out > 0.0  # the glyph's natural (hmtx) advance is genuinely non-zero

    with PDDocument.load(tmp_path / "zero.pdf") as doc:
        font = doc.get_page(0).get_resources().get_font(
            COSName.get_pdf_name("F1")
        )
        code = int.from_bytes(font.encode(_TEXT[1]), "big")
        assert font.has_explicit_width(code) is True
        assert font.get_glyph_width(code) == 0.0


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_zero_width_advance_matches_pdfbox(tmp_path: Path) -> None:
    """Before the fix this FAILS: pypdfbox advances the zero-width ``i`` by
    the embedded program's hmtx width, shifting the trailing ``H`` right by
    ~278/1000 em so the grid diverges far beyond AA (measured MAXDIFF ~115).
    After the fix pypdfbox honours the declared 0 and matches PDFBox."""
    fixture = _build(tmp_path / "zero.pdf", zero_width=True)
    assert fixture > 0.0
    (java_w, java_h), java_grid = _oracle_signature(tmp_path / "zero.pdf")

    with PDDocument.load(tmp_path / "zero.pdf") as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"zero-width: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"zero-width: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — the zero-width glyph advanced (hmtx fallback "
        f"overrode the explicit /W 0), shifting subsequent glyphs"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"zero-width: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — glyph spacing diverges far beyond AA"
    )


@requires_oracle
def test_control_nonzero_width_matches_pdfbox(tmp_path: Path) -> None:
    """Control: the same middle glyph with a non-zero ``/W`` (its natural
    advance) also matches PDFBox. Together with the zero-width test this
    confirms the fix didn't regress the common non-zero path."""
    natural = _build(tmp_path / "ctrl.pdf", zero_width=False)
    assert natural > 0.0
    (java_w, java_h), java_grid = _oracle_signature(tmp_path / "ctrl.pdf")

    with PDDocument.load(tmp_path / "ctrl.pdf") as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    assert img.size == (java_w, java_h)
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"control: non-zero /W render diverges from PDFBox "
        f"(mad={mad:.2f}, maxdiff={maxdiff})"
    )


@requires_oracle
def test_zero_vs_control_genuinely_differ(tmp_path: Path) -> None:
    """Guard: PDFBox's own zero-width vs control renders must differ grossly
    (the explicit 0 collapses the spacing of the trailing ``H`` onto the
    ``i``). If they didn't differ, the zero-width test would pass trivially
    without exercising the zero-advance path. Measured zero-vs-control
    MAXDIFF ~119 — far outside the gate."""
    _build(tmp_path / "zero.pdf", zero_width=True)
    _build(tmp_path / "ctrl.pdf", zero_width=False)
    _dims_z, zero_grid = _oracle_signature(tmp_path / "zero.pdf")
    _dims_c, ctrl_grid = _oracle_signature(tmp_path / "ctrl.pdf")
    diffs = [abs(a - b) for a, b in zip(zero_grid, ctrl_grid, strict=True)]
    maxdiff = max(diffs)
    assert maxdiff >= _MAXDIFF_TOLERANCE, (
        f"explicit-0 /W does not change PDFBox's layout (zero-vs-control "
        f"maxdiff {maxdiff}) — the zero-advance path is not genuinely "
        f"exercised; pick a glyph whose zero advance visibly shifts the page"
    )
