"""``cm`` — Concatenate matrix to current transformation matrix.

Mirrors ``org.apache.pdfbox.contentstream.operator.state.Concatenate``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Concatenate.java``).

Functional logic already lives in
:class:`pypdfbox.contentstream.operator.graphics.concatenate_matrix.ConcatenateMatrix`;
this class is the upstream-named parity surface that delegates to that
handler so PDFBox developers can reach for the familiar identifier.
"""

from typing import TYPE_CHECKING, cast

from pypdfbox.cos import COSBase, COSNumber
from pypdfbox.util.matrix import Matrix

from .. import MissingOperandException, Operator, OperatorName
from ..operator_processor import OperatorProcessor

if TYPE_CHECKING:
    from collections.abc import Sequence

# PDFBOX-6255 — the shared guard every ``cm`` implementation runs.
#
# pypdfbox has more than one ``cm`` entry point (this class, the
# registered ``graphics.ConcatenateMatrix`` handler and the rendering
# engine's own ``PDFRenderer._op_concat_matrix``). The *rule* lives in a
# single place — ``Matrix.concatenate`` -> ``checkFloatValues``, ported in
# :mod:`pypdfbox.util.matrix` — and :func:`check_concatenation` is the one
# place that translates its ``ValueError`` into the ``IOException``
# (``OSError`` here) upstream's ``Concatenate.process`` throws, so a future
# parity fix cannot land on one path and miss the others.
#
# Only *non-finite* products are illegal. A singular matrix (e.g. all
# zeroes, which collapses user space onto a point) is perfectly finite and
# stays legal — upstream accepts it too.

# Fast path bound. Upstream evaluates the product in Java ``float`` (32
# bit), so a cell can only turn non-finite by exceeding ``Float.MAX_VALUE``
# (3.4028235e38). Each cell is a sum of three products, so when every input
# element is within +/-1e19 the largest attainable cell (and every partial
# sum) is 3e38 — below the limit — and the real check provably passes. NaN
# and infinity both fail the magnitude test (every comparison against NaN is
# False), so they fall through to the real check.
_SAFE_ELEMENT_MAGNITUDE = 1e19


def check_concatenation(matrix: Sequence[float], ctm: Sequence[float]) -> None:
    """Raise ``OSError`` if concatenating ``matrix`` onto ``ctm`` would
    produce a matrix holding NaN / infinity.

    Both arguments are the six affine components ``(a, b, c, d, e, f)``.
    The check is delegated to :meth:`Matrix.concatenate` so the rule is
    never restated; the throwaway :class:`Matrix` pair exists only to run
    upstream's ``checkFloatValues`` in single precision, which is what
    ``PageDrawer`` / ``Concatenate`` do.
    """
    limit = _SAFE_ELEMENT_MAGNITUDE
    for value in (*matrix, *ctm):
        if not -limit <= value <= limit:
            break
    else:
        return
    try:
        Matrix(*ctm).concatenate(Matrix(*matrix))
    except ValueError as ex:
        raise OSError(str(ex)) from ex


class Concatenate(OperatorProcessor):
    """``cm`` — pop six numeric operands and concatenate them as a 3×3
    affine matrix onto the current CTM."""

    OPERATOR_NAME = OperatorName.CONCAT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands[:6], COSNumber):
            return
        numbers = cast("list[COSNumber]", operands[:6])
        matrix = tuple(number.float_value() for number in numbers)
        context = self._context
        if context is not None:
            # Prefer the dedicated transform hook (mirrors the
            # ConcatenateMatrix handler); fall back to nudging the
            # graphics-state CTM directly to match upstream semantics
            # for engines that don't expose ``transform``.
            # PDFBOX-6255: ``Matrix.concatenate`` rejects a product that
            # contains NaN / infinity (``checkFloatValues`` ->
            # ``IllegalArgumentException``, ported here as ``ValueError``).
            # Upstream used to let that unchecked exception escape the
            # operator dispatch loop, which aborts the whole page walk with
            # a non-IOException; it is now rethrown as an IOException
            # (``OSError`` here) so the engine's normal malformed-operator
            # handling applies.
            try:
                transform = getattr(context, "transform", None)
                if transform is not None:
                    transform(matrix)
                    return
                graphics_state = context.get_graphics_state()
                ctm = getattr(graphics_state, "get_current_transformation_matrix", None)
                ctm_obj = ctm() if ctm is not None else None
                concat = getattr(ctm_obj, "concatenate", None) if ctm_obj else None
                if concat is not None:
                    # Upstream calls ``CTM.concatenate(matrix)`` with a Matrix,
                    # not the raw six floats; ``Matrix.concatenate`` reads
                    # ``matrix._single`` and would crash on a plain tuple.
                    concat(Matrix(*matrix))
            except ValueError as ex:
                raise OSError(str(ex)) from ex

    def get_name(self) -> str:
        return OperatorName.CONCAT


__all__ = ["Concatenate", "check_concatenation"]
