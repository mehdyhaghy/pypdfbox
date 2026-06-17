"""Live PDFBox differential parity for the text-state + text-positioning
operators' text-rendering-matrix evolution.

Drives the content-stream text operators
``BT / Tf / TL / Td / TD / Tm / T* / Tc / Tw / Tz / Ts / Tj / TJ / ' / "``
through :class:`PDFRenderer` and compares, per glyph, the
text-rendering-matrix (``text_local * text_matrix`` in user space) and the
glyph's horizontal displacement against Apache PDFBox's
``PDFStreamEngine.showGlyph(Matrix, PDFont, int, Vector)`` via the
``TextStateMatrixProbe`` Java oracle.

The probe builds a one-page PDF with a FIXED raw content stream (the bytes
live in ``oracle/probes/TextStateMatrixProbe.java`` as ``CONTENT``) and a
Standard-14 Helvetica font (deterministic AFM widths) on a media box
anchored at the origin (identity page CTM). pypdfbox loads that exact PDF
and renders it, capturing each glyph's text-rendering matrix from the
renderer's own text-state.

This exercises:

* the text matrix / text-line matrix evolution across ``Td`` / ``TD`` /
  ``Tm`` / ``T*`` / ``TL`` (relative move, move-and-set-leading, absolute
  set, next-line, leading);
* the ``TJ`` array numeric adjustment (``-N/1000 * Tfs * Th``);
* the text-state params ``Tc`` / ``Tw`` / ``Tz`` / ``Ts`` / ``Tf``
  folding into the per-glyph advance and the text-rendering matrix
  (``Tz`` scales ``trmA``, ``Ts`` shifts ``trmF``, ``Tf`` sets the size);
* ``Tw`` applying only to the single-byte space code 0x20;
* the ``'`` (next-line-then-show) and ``"`` (set-spacing-next-line-show)
  composite operators.

Canonical line grammar (must match ``oracle/probes/TextStateMatrixProbe.java``)::

    code \t trmA \t trmB \t trmC \t trmD \t trmE \t trmF \t dispX

Floats rounded to %.4f, Locale.ROOT, so the rendering is stable across
platforms / locales.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _matmul
from tests.oracle.harness import _PROBES, oracle_available, run_probe_text


def _fmt(value: float) -> str:
    """Match the probe's ``%.4f`` Locale.ROOT rendering."""
    return f"{float(value):.4f}"


class _CapturingRenderer(PDFRenderer):
    """Render normally but record each glyph's text-rendering matrix.

    The text-rendering matrix in user space is ``text_local * text_matrix``
    — exactly what :meth:`PDFRenderer._draw_glyph` composes as
    ``glyph_to_user`` before stacking the device CTM. We recompute it here
    from the live text-state (font size, horizontal scaling, rise) so the
    capture is independent of the device transform (y-flip / DPI), matching
    upstream ``showGlyph`` which receives the user-space matrix.
    """

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)
        self.glyphs: list[tuple[int, tuple[float, ...], float]] = []

    def _draw_glyph(
        self,
        font: Any,
        code: int,
        ttf: Any | None,
        glyph_set: Any | None,
        type1_units_per_em: int | None = None,
        *,
        vertical: bool = False,
    ) -> float:
        font_size = self._gs.text_font_size
        h_scale = self._gs.text_horizontal_scaling / 100.0
        rise = self._gs.text_rise
        text_local = (
            font_size * h_scale, 0.0,
            0.0, font_size,
            0.0, rise,
        )
        glyph_to_user = _matmul(text_local, self._gs.text_matrix)
        advance_units = super()._draw_glyph(
            font, code, ttf, glyph_set, type1_units_per_em, vertical=vertical
        )
        # Java's ``Vector.getX()`` is the displacement in em units; the
        # renderer's advance is in 1/1000 em.
        self.glyphs.append((code, glyph_to_user, advance_units / 1000.0))
        return advance_units


def _emit(pdf_path: Path) -> str:
    with PDDocument.load(pdf_path) as doc:
        renderer = _CapturingRenderer(doc)
        renderer.render_image_with_dpi(0, 72.0)
        lines = []
        for code, trm, disp in renderer.glyphs:
            a, b, c, d, e, f = trm
            lines.append(
                "\t".join(
                    [
                        str(code),
                        _fmt(a),
                        _fmt(b),
                        _fmt(c),
                        _fmt(d),
                        _fmt(e),
                        _fmt(f),
                        _fmt(disp),
                    ]
                )
            )
    return "\n".join(lines) + "\n"


@pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh",
)
def test_text_state_matrix_matches_pdfbox() -> None:
    # The probe both generates the PDF (to the path it is handed) and emits
    # the per-glyph oracle output; pypdfbox loads that exact PDF.
    assert (_PROBES / "TextStateMatrixProbe.java").is_file()
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "text_state.pdf"
        java = run_probe_text("TextStateMatrixProbe", str(pdf_path))
        py = _emit(pdf_path)
        assert py == java
