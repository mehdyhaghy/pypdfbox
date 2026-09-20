"""PDFBOX-6255 on the rendering path — ``cm`` enforces ``checkFloatValues``.

Wave 1605 closed PDFBOX-6255 for
``contentstream.operator.state.Concatenate`` only. The renderer registers
its *own* ``cm`` handler (``PDFRenderer._op_concat_matrix``), which
multiplies plain float tuples through ``_matmul`` and had no
``checkFloatValues`` equivalent at all — so a product that overflows to
infinity / NaN went straight into the CTM and poisoned every later
transform on the page. That is the path a real render takes, so the fix
was effectively not in force.

``_op_concat_matrix`` now runs the shared
:func:`pypdfbox.contentstream.operator.state.concatenate.check_concatenation`
guard, which delegates to :meth:`Matrix.concatenate` (upstream's
``checkFloatValues``) and rethrows its ``ValueError`` as ``OSError`` —
the port of upstream's ``throw new IOException(ex)``.

Upstream's ``PageDrawer`` inherits ``PDFStreamEngine.processOperator``,
whose ``operatorException`` rethrows a plain ``IOException``, so upstream
aborts the page. pypdfbox's renderer instead triages *every* operator
error to log-and-continue (a pre-existing, renderer-wide policy pinned by
waves 381 / 511 / 531 / 561 / 591 / 632 / 1032), so the bad ``cm`` is
dropped and the CTM keeps its previous, finite value. These tests pin
both halves: the operator raises, and the page render survives.
"""

import logging
import math
from typing import Any

import pytest

from pypdfbox.contentstream.operator.state.concatenate import check_concatenation
from pypdfbox.cos import COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState, _matmul

# float32 max is 3.4028235e38 — squaring 3.4e38 overflows a Java float even
# though the same product is a perfectly ordinary finite double (1.156e77).
_HUGE = 3.4e38
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _make_doc(width: float = 60.0, height: float = 60.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer() -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._gs_stack = [_GState()]
    renderer._device_ctm = _IDENTITY
    renderer._gs.ctm = _IDENTITY
    return doc, renderer


def _operands(*values: float) -> list[Any]:
    return [COSFloat(v) for v in values]


def _set_contents(page: PDPage, ops: bytes) -> None:
    contents = COSStream()
    contents.set_raw_data(ops)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)


# ---------------------------------------------------------------------------
# the operator itself
# ---------------------------------------------------------------------------


def test_overflowing_matrix_raises_oserror() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.ctm = (_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
        with pytest.raises(OSError, match="Multiplying two matrices produces illegal"):
            renderer._op_concat_matrix(
                None, _operands(_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
            )
    finally:
        doc.close()


def test_value_error_is_not_leaked_untranslated() -> None:
    """Mirrors the wave-1605 assertion for ``Concatenate``: the raised
    object is an ``OSError`` (upstream ``IOException``) chaining the
    original matrix failure, not a bare ``ValueError``."""
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.ctm = (_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
        with pytest.raises(OSError) as exc:
            renderer._op_concat_matrix(
                None, _operands(_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
            )
        assert not isinstance(exc.value, ValueError)
        assert isinstance(exc.value.__cause__, ValueError)
    finally:
        doc.close()


def test_rejection_boundary_is_float32_not_double() -> None:
    """The guard must reuse ``Matrix``'s single-precision rule.

    ``_matmul`` works in Python doubles, where the same operands produce a
    finite 1.156e77. If the renderer grew its own double-precision
    ``isfinite`` check instead of delegating to ``Matrix``, this pair
    would be accepted while upstream's ``PageDrawer`` rejects it.
    """
    bad = (_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
    assert all(math.isfinite(v) for v in _matmul(bad, bad))
    with pytest.raises(OSError):
        check_concatenation(bad, bad)


def test_ctm_is_unchanged_when_the_concatenation_is_rejected() -> None:
    doc, renderer = _prepared_renderer()
    try:
        before = (_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
        renderer._gs.ctm = before
        with pytest.raises(OSError):
            renderer._op_concat_matrix(
                None, _operands(_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
            )
        assert renderer._gs.ctm == before
    finally:
        doc.close()


def test_nan_operand_is_rejected() -> None:
    doc, renderer = _prepared_renderer()
    try:
        with pytest.raises(OSError):
            renderer._op_concat_matrix(
                None, _operands(float("nan"), 0.0, 0.0, 1.0, 0.0, 0.0)
            )
        assert renderer._gs.ctm == _IDENTITY
    finally:
        doc.close()


def test_infinite_operand_is_clamped_by_cosfloat_then_overflows_on_reuse() -> None:
    """``COSFloat`` already clamps an infinite literal to
    ``Float.MAX_VALUE`` (upstream parity), so an infinite operand alone is
    finite and legal. It becomes illegal only once it is multiplied by
    another element of the same size."""
    doc, renderer = _prepared_renderer()
    try:
        flt_max = COSFloat(float("inf")).float_value()
        assert math.isfinite(flt_max)
        renderer._op_concat_matrix(
            None, _operands(float("inf"), 0.0, 0.0, float("inf"), 0.0, 0.0)
        )
        assert renderer._gs.ctm == pytest.approx(
            (flt_max, 0.0, 0.0, flt_max, 0.0, 0.0)
        )
        with pytest.raises(OSError):
            renderer._op_concat_matrix(
                None, _operands(float("inf"), 0.0, 0.0, float("inf"), 0.0, 0.0)
            )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# what must NOT be rejected
# ---------------------------------------------------------------------------


def test_singular_all_zero_matrix_is_not_rejected() -> None:
    """Upstream rejects only *non-finite* products. An all-zero matrix is
    singular (it collapses user space onto a point) but perfectly finite,
    so it is legal PDF and must still be applied — same boundary the
    wave-1605 ``Concatenate`` test pins."""
    doc, renderer = _prepared_renderer()
    try:
        renderer._op_concat_matrix(None, _operands(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        assert renderer._gs.ctm == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    finally:
        doc.close()


def test_normal_matrix_still_concatenates() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._op_concat_matrix(None, _operands(2.0, 0.0, 0.0, 3.0, 10.0, 20.0))
        assert renderer._gs.ctm == pytest.approx(
            (2.0, 0.0, 0.0, 3.0, 10.0, 20.0)
        )
        renderer._op_concat_matrix(None, _operands(1.0, 0.0, 0.0, 1.0, 5.0, 5.0))
        # Second cm post-multiplies: translate (5,5) scaled by (2,3).
        assert renderer._gs.ctm == pytest.approx(
            (2.0, 0.0, 0.0, 3.0, 20.0, 35.0)
        )
    finally:
        doc.close()


@pytest.mark.parametrize(
    "value",
    [1.0, 1.0e6, 1.0e18, 1.0e19, -1.0e19],
    ids=["one", "million", "e18", "fastpath_bound", "neg_fastpath_bound"],
)
def test_large_but_finite_matrices_are_accepted(value: float) -> None:
    """The guard's conservative magnitude fast path (|element| <= 1e19)
    must never reject: three products of two such elements stay under
    ``Float.MAX_VALUE``."""
    doc, renderer = _prepared_renderer()
    try:
        renderer._op_concat_matrix(None, _operands(value, 0.0, 0.0, value, 0.0, 0.0))
        assert renderer._gs.ctm == pytest.approx((value, 0.0, 0.0, value, 0.0, 0.0))
    finally:
        doc.close()


def test_missing_operands_are_still_a_silent_skip() -> None:
    """The guard must not disturb the short-operand early return."""
    doc, renderer = _prepared_renderer()
    try:
        renderer._op_concat_matrix(None, _operands(1.0, 0.0, 0.0, 1.0, 5.0))
        assert renderer._gs.ctm == _IDENTITY
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# net effect on a page render
# ---------------------------------------------------------------------------


def test_process_operator_drops_the_bad_cm_and_keeps_rendering(caplog: Any) -> None:
    """The renderer triages the ``OSError`` like any other malformed
    operator: logged at DEBUG, CTM left at its previous finite value, and
    the following operators still run. (Upstream aborts the page instead —
    see the module docstring.)"""
    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        renderer._gs.ctm = (_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
        renderer.process_operator("cm", _operands(_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0))
        assert "dropping operator cm" in caplog.text
        assert renderer._gs.ctm == (_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)

        # The engine is still usable afterwards.
        renderer.process_operator("w", [COSFloat(4.0)])
        assert renderer._gs.line_width == pytest.approx(4.0)
    finally:
        doc.close()


def test_page_with_an_overflowing_cm_still_renders() -> None:
    """End-to-end: a content stream whose ``cm`` overflows must not abort
    ``render_image`` and must not leave a non-finite CTM behind — the blue
    fill after it is painted through the *pre-``cm``* CTM."""
    doc, page = _make_doc(40.0, 40.0)
    try:
        _set_contents(
            page,
            b"q\n"
            b"3.4e38 0 0 3.4e38 0 0 cm\n"
            b"3.4e38 0 0 3.4e38 0 0 cm\n"
            b"0 0 1 rg\n"
            b"0 0 40 40 re\n"
            b"f\n"
            b"Q\n",
        )
        image = PDFRenderer(doc).render_image(0)
        assert image is not None
        assert image.size[0] > 0
        # The first cm is legal on its own (3.4e38 x identity is still
        # finite in float32); the *second* one squares it and overflows, so
        # it is the one that gets dropped. The page still paints.
        pixel = image.convert("RGB").getpixel((20, 20))
        assert isinstance(pixel, tuple)
    finally:
        doc.close()
