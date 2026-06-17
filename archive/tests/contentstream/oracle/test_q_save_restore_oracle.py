"""Live PDFBox differential parity for the ``q`` / ``Q`` graphics-state
SAVE / RESTORE stack.

Drives a content stream that exercises the full save/restore surface
through :class:`PDFRenderer` and compares, after every operator, the
graphics-state stack depth, the current line width, and the six CTM
components against Apache PDFBox's ``PDFStreamEngine`` driven over the
SAME bytes via the ``QSaveRestoreProbe`` Java oracle.

The probe builds a one-page PDF with a FIXED raw content stream (the
bytes live in ``oracle/probes/QSaveRestoreProbe.java`` as ``CONTENT``)
on a media box anchored at the origin (identity page CTM), so the
captured CTM is the pure user-space CTM independent of any device /
y-flip transform. pypdfbox loads that exact PDF and renders it,
capturing the same state after each operator from the renderer's own
graphics-state stack.

This exercises:

* nested ``q ... q ... Q ... Q`` — a two-level save/restore stack;
* a ``cm`` (CTM concat) and a ``w`` (line width) mutated INSIDE each
  ``q`` block, verifying the prior CTM + line width are correctly
  restored on the matching ``Q``;
* an UNBALANCED extra ``Q`` (more ``Q`` than ``q``) — PDFBox swallows
  the ``EmptyGraphicsStackException`` (PDFBOX-161) and continues, so the
  operator AFTER the bad ``Q`` still runs and the stack depth never
  drops below 1;
* a final ``q`` left OPEN at end-of-stream (no matching ``Q``).

Canonical line grammar (must match ``oracle/probes/QSaveRestoreProbe.java``)::

    seq \t opName \t depth \t lw \t a \t b \t c \t d \t e \t f

Floats rounded to ``%.4f`` Locale.ROOT, so the rendering is stable
across platforms / locales.

A second, self-contained assertion pins the lenient unbalanced-``Q``
behaviour directly on the base engine path: ``RestoreGraphicsState`` /
``Restore`` raise ``EmptyGraphicsStackException`` when the stack is
empty, and ``PDFStreamEngine.operator_exception`` must swallow it
(log + continue) — mirroring upstream's ``operatorException`` triage —
rather than re-raising and aborting the stream.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from tests.oracle.harness import _PROBES, oracle_available, run_probe_text

# The fixed content stream the probe writes into its PDF. Kept byte-for-byte
# identical to ``QSaveRestoreProbe.CONTENT`` so the differential test is a
# true apples-to-apples comparison; we don't actually feed this constant to
# pypdfbox (the renderer loads the probe-written PDF), but pinning it here
# documents the surface and guards against silent drift.
_CONTENT = (
    "1 w\n"
    "q\n"
    "2 w\n"
    "3 0 0 3 10 20 cm\n"
    "q\n"
    "5 w\n"
    "1 0 0 1 5 5 cm\n"
    "Q\n"
    "Q\n"
    "Q\n"
    "4 w\n"
    "q\n"
    "6 w\n"
    "7 0 0 7 1 2 cm\n"
)


def _fmt(value: float) -> str:
    """Match the probe's ``%.4f`` Locale.ROOT rendering."""
    return f"{float(value):.4f}"


class _CapturingRenderer(PDFRenderer):
    """Render normally but record graphics-state after every operator.

    After each operator completes, the renderer's user-space CTM lives in
    ``self._gs.ctm`` (separate from the device CTM that applies the dpi
    scale + y-flip), the current line width in ``self._gs.line_width``, and
    the stack depth in ``len(self._gs_stack)`` — directly comparable to
    upstream's ``getGraphicsState().getCurrentTransformationMatrix()`` /
    ``getLineWidth()`` / ``getGraphicsStackSize()``.
    """

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)
        self.rows: list[tuple[int, str, int, float, tuple[float, ...]]] = []
        self._seq = 0

    def process_operator(
        self,
        operator: Any,
        operands: list[Any] | None,
    ) -> None:
        super().process_operator(operator, operands)
        from pypdfbox.contentstream.operator import Operator as _Op  # noqa: PLC0415

        op = operator if isinstance(operator, _Op) else _Op.get_operator(operator)
        name = op.get_name()
        # Only record the operators the oracle line-grammar covers; the
        # probe captures after q / Q / cm / w (the only ops in the stream).
        if name not in {"q", "Q", "cm", "w"}:
            return
        self.rows.append(
            (
                self._seq,
                name,
                len(self._gs_stack),
                float(self._gs.line_width),
                tuple(float(v) for v in self._gs.ctm),
            )
        )
        self._seq += 1


def _emit(pdf_path: Path) -> str:
    with PDDocument.load(pdf_path) as doc:
        renderer = _CapturingRenderer(doc)
        renderer.render_image_with_dpi(0, 72.0)
        lines = []
        for seq, name, depth, lw, ctm in renderer.rows:
            a, b, c, d, e, f = ctm
            lines.append(
                "\t".join(
                    [
                        str(seq),
                        name,
                        str(depth),
                        _fmt(lw),
                        _fmt(a),
                        _fmt(b),
                        _fmt(c),
                        _fmt(d),
                        _fmt(e),
                        _fmt(f),
                    ]
                )
            )
    return "\n".join(lines) + "\n"


@pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh",
)
def test_q_save_restore_matches_pdfbox() -> None:
    # The probe both generates the PDF (to the path it is handed) and emits
    # the per-operator oracle output; pypdfbox loads that exact PDF.
    assert (_PROBES / "QSaveRestoreProbe.java").is_file()
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "q_save_restore.pdf"
        java = run_probe_text("QSaveRestoreProbe", str(pdf_path))
        py = _emit(pdf_path)
        assert py == java


def test_content_constant_in_sync_with_probe() -> None:
    """Guard: the pinned content constant matches the probe's CONTENT so the
    differential test stays a true byte-for-byte reproduction."""
    src = (_PROBES / "QSaveRestoreProbe.java").read_text(encoding="utf-8")
    # Reconstruct the probe's CONTENT literal from its "...\n" + "...\n" lines.
    start = src.index("static final String CONTENT")
    end = src.index(";", start)
    literal_block = src[start:end]
    pieces = []
    for raw in literal_block.splitlines():
        token = raw.strip()
        if token.startswith('"') or token.startswith('+ "'):
            inner = token[token.index('"') + 1 : token.rindex('"')]
            pieces.append(inner.replace("\\n", "\n"))
    assert "".join(pieces) == _CONTENT


def test_unbalanced_q_is_lenient_on_base_engine() -> None:
    """An unbalanced ``Q`` (empty stack) must not abort: the operator's
    ``EmptyGraphicsStackException`` is swallowed by ``operator_exception``
    (log + continue), mirroring upstream's ``operatorException`` triage."""
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.contentstream.operator.state.empty_graphics_stack_exception import (
        EmptyGraphicsStackException,
    )
    from pypdfbox.contentstream.operator.state.restore_graphics_state import (
        RestoreGraphicsState,
    )
    from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine

    engine = PDFStreamEngine()
    restore = RestoreGraphicsState()
    engine.add_operator(restore)

    # Stack is empty (size 0 <= 1) → Restore.process raises
    # EmptyGraphicsStackException directly.
    with pytest.raises(EmptyGraphicsStackException):
        restore.process(Operator.get_operator("Q"), [])

    # But routed through the engine's process_operator → operator_exception,
    # the exception is swallowed and processing continues (no raise).
    engine.process_operator(Operator.get_operator("Q"), [])
