"""Live PDFBox differential parity for the DECOMPOSITION of the
move-to-next-line-and-show text operators ``'`` and ``"`` (ISO 32000-1
§9.4.3).

Wave 1457's ``test_text_state_matrix_oracle`` already pinned the per-glyph
text-rendering matrix as ``'``/``"`` are rendered. This test targets a
distinct observable: the *decomposition* of each composite into its
sub-operators, captured at the engine-dispatch level rather than per glyph.

    ' string        ==  T* ; Tj string        (advance line by leading TL)
    " aw ac string  ==  Tw aw ; Tc ac ; ' string

The ``ShowTextLineDecompProbe`` Java oracle drives a fixed content stream
through ``PDFStreamEngine`` and, immediately AFTER each ``'``/``"`` operator's
decomposition has run, snapshots the text state the decomposition mutates:

* the text-LINE-matrix origin (``translateX`` / ``translateY``), advanced by
  the ``T*`` step (so it drops by the leading ``TL`` each line);
* the word spacing (``Tw``) and character spacing (``Tc``) text-state fields,
  set by the ``"`` decomposition and left untouched by a bare ``'``.

pypdfbox loads the exact PDF the probe generated and drives it through
:class:`PDFRenderer`, whose ``process_operator`` dispatches ``'``/``"`` to its
own ``_op_show_text_line`` / ``_op_show_text_line_with_spacing`` decomposers.
We override ``process_operator`` to snapshot the same fields after each
``'``/``"`` and assert byte-identical output.

Canonical line grammar (must match ``oracle/probes/ShowTextLineDecompProbe.java``)::

    opName \t lineTx \t lineTy \t wordSpacing \t charSpacing

Floats rounded to %.4f, Locale.ROOT, for cross-platform stability.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from tests.oracle.harness import _PROBES, oracle_available, run_probe_text


def _fmt(value: float) -> str:
    """Match the probe's ``%.4f`` Locale.ROOT rendering."""
    return f"{float(value):.4f}"


class _CapturingRenderer(PDFRenderer):
    """Render normally but record, after each ``'``/``"`` dispatch, the
    text-line-matrix origin and the word/char spacing state — exactly the
    state the composite's decomposition is responsible for mutating."""

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)
        self.events: list[tuple[str, float, float, float, float]] = []

    def process_operator(
        self,
        operator: Any,
        operands: list[Any] | None,
    ) -> None:
        super().process_operator(operator, operands)
        from pypdfbox.contentstream.operator import Operator as _Op  # noqa: PLC0415

        op = operator if isinstance(operator, _Op) else _Op.get_operator(operator)
        name = op.get_name()
        if name in ("'", '"'):
            line = self._gs.text_line_matrix
            self.events.append(
                (
                    name,
                    line[4],
                    line[5],
                    self._gs.text_wordspace,
                    self._gs.text_charspace,
                )
            )


def _emit(pdf_path: Path) -> str:
    with PDDocument.load(pdf_path) as doc:
        renderer = _CapturingRenderer(doc)
        renderer.render_image_with_dpi(0, 72.0)
        lines = []
        for name, tx, ty, tw, tc in renderer.events:
            lines.append(
                "\t".join([name, _fmt(tx), _fmt(ty), _fmt(tw), _fmt(tc)])
            )
    return "\n".join(lines) + "\n"


@pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh",
)
def test_show_text_line_decomposition_matches_pdfbox() -> None:
    # The probe both generates the PDF (to the path it is handed) and emits
    # the per-operator oracle output; pypdfbox loads that exact PDF.
    assert (_PROBES / "ShowTextLineDecompProbe.java").is_file()
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "show_text_line_decomp.pdf"
        java = run_probe_text("ShowTextLineDecompProbe", str(pdf_path))
        py = _emit(pdf_path)
        assert py == java
