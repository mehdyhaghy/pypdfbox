"""Live PDFBox differential parity for composite (Type0 / CID) font
show-text byte to code chunking.

Drives a content stream that shows multi-byte (2-byte) codes through an
Identity-H Type0 font, and compares — per code — the chunked character
code, the resolved CID (``PDType0Font.codeToCID``), the glyph's
horizontal displacement (``Vector.getX()``) and the glyph origin in user
space (the text-rendering-matrix translate components) against Apache
PDFBox's ``PDFStreamEngine.showGlyph(Matrix, PDFont, int, Vector)`` via
the ``CompositeShowTextProbe`` Java oracle.

The probe builds the one-page PDF (an Identity-H Type0 font embedded from
the bundled ``LiberationSans-Regular.ttf``, a content stream with a ``Tj``
run plus a ``TJ`` array carrying a numeric adjustment) and saves it; the
Python side loads that EXACT PDF and renders it, so both engines decode
the identical byte string. This exercises:

* the ``showText`` decode loop splitting the byte string into 2-byte
  codes through the font's ``/Encoding`` (Identity-H) codespace
  (``font.read_code``), one ``showGlyph`` per code;
* ``code -> CID`` resolution (Identity: CID == code) per chunked code;
* the per-code horizontal advance (``get_displacement(code)[0]``) folding
  into the running text matrix, including the ``TJ`` ``-N/1000 * Tfs *
  Th`` adjustment between two codes.

Canonical line grammar (must match
``oracle/probes/CompositeShowTextProbe.java``)::

    code \t cid \t dispX \t trmE \t trmF

Floats rounded to %.4f, Locale.ROOT.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _matmul
from tests.oracle.harness import _PROBES, oracle_available, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _fmt(value: float) -> str:
    """Match the probe's ``%.4f`` Locale.ROOT rendering."""
    return f"{float(value):.4f}"


class _CapturingRenderer(PDFRenderer):
    """Render normally but record each glyph's code, CID, displacement and
    user-space origin — the four-field shape the probe emits."""

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)
        self.glyphs: list[tuple[int, int, float, float, float]] = []

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
        cid = code
        code_to_cid = getattr(font, "code_to_cid", None)
        if callable(code_to_cid):
            cid = code_to_cid(code)
        disp_x = 0.0
        get_displacement = getattr(font, "get_displacement", None)
        if callable(get_displacement):
            disp_x = get_displacement(code)[0]
        advance_units = super()._draw_glyph(
            font, code, ttf, glyph_set, type1_units_per_em, vertical=vertical
        )
        self.glyphs.append(
            (code, cid, disp_x, glyph_to_user[4], glyph_to_user[5])
        )
        return advance_units


def _emit(pdf_path: Path) -> str:
    with PDDocument.load(pdf_path) as doc:
        renderer = _CapturingRenderer(doc)
        renderer.render_image_with_dpi(0, 72.0)
        lines = []
        for code, cid, disp, e, f in renderer.glyphs:
            lines.append(
                "\t".join(
                    [str(code), str(cid), _fmt(disp), _fmt(e), _fmt(f)]
                )
            )
    return "\n".join(lines) + "\n"


@pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh",
)
def test_composite_show_text_matches_pdfbox() -> None:
    assert (_PROBES / "CompositeShowTextProbe.java").is_file()
    assert _TTF.is_file()
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "composite_show_text.pdf"
        java = run_probe_text(
            "CompositeShowTextProbe", str(_TTF), str(pdf_path)
        )
        py = _emit(pdf_path)
        assert py == java
