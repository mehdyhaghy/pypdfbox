from __future__ import annotations

from threading import Lock

from pypdfbox.cos import COSBase, COSDictionary

# This subpackage mirrors ``org.apache.pdfbox.contentstream.operator``.
# ``Operator``, ``OperatorName``, ``OperatorProcessor`` and
# ``MissingOperandException`` all live in that Java package upstream.
# In pypdfbox ``OperatorName`` and ``OperatorProcessor`` /
# ``MissingOperandException`` live one level up at
# ``pypdfbox/contentstream/operator_name.py`` /
# ``operator_processor.py`` (a flat shape inherited from cluster #1);
# we re-export them through this ``__init__`` so callers can import
# them at the upstream-faithful path
# ``pypdfbox.contentstream.operator.OperatorName`` etc.
from ..operator_name import OperatorName
from ..operator_processor import MissingOperandException, OperatorProcessor


class Operator:
    """
    A single operator in a PDF content stream — name (e.g. ``BT``,
    ``Tj``, ``TJ``) plus the operands that immediately precede it on the
    operand stack at parse time.

    Mirrors ``org.apache.pdfbox.contentstream.operator.Operator``.

    Operator instances for ordinary operators are interned via
    :meth:`get_operator` — repeated calls with the same name return the
    same singleton (matching upstream's ``ConcurrentHashMap`` cache).

    The two inline-image operators ``BI`` (``BEGIN_INLINE_IMAGE``) and
    ``ID`` (``BEGIN_INLINE_IMAGE_DATA``) are *never* cached: each call
    yields a fresh instance, since they carry per-occurrence
    ``image_parameters`` and ``image_data``.

    Operands semantics: upstream's ``Operator`` does not store operands —
    the operand stack lives on ``PDFStreamEngine`` / ``PDFStreamParser``.
    pypdfbox's parser, however, attaches the just-popped operands to the
    returned ``Operator`` for the convenience of stream-token consumers
    (it spares them re-implementing the same window-of-tokens trick).
    Operand storage is a per-instance list; do *not* mutate the operands
    on a cached instance returned by :meth:`get_operator` — instead pop
    a fresh one via :meth:`get_operator` and assign new operands. The
    parser already takes care of that.
    """

    __slots__ = ("_name", "_operands", "_image_data", "_image_parameters")

    # Singleton cache — Python's GIL makes a plain dict + lock equivalent
    # to upstream's ConcurrentHashMap.putIfAbsent for our purposes.
    _operators: dict[str, Operator] = {}
    _operators_lock: Lock = Lock()

    def __init__(self, operator: str) -> None:
        if operator.startswith("/"):
            raise ValueError(
                f"Operators are not allowed to start with / '{operator}'"
            )
        self._name: str = operator
        self._operands: list[COSBase] = []
        self._image_data: bytes | None = None
        self._image_parameters: COSDictionary | None = None

    # ---------- factory ----------

    @staticmethod
    def get_operator(operator: str) -> Operator:
        """Return a (possibly cached) ``Operator`` for ``operator``.

        Inline-image operators (``BI`` / ``ID``) bypass the cache because
        they carry per-occurrence image data and parameters.
        """
        if (
            operator == OperatorName.BEGIN_INLINE_IMAGE_DATA
            or operator == OperatorName.BEGIN_INLINE_IMAGE
        ):
            return Operator(operator)

        cached = Operator._operators.get(operator)
        if cached is not None:
            return cached
        with Operator._operators_lock:
            cached = Operator._operators.get(operator)
            if cached is None:
                cached = Operator(operator)
                Operator._operators[operator] = cached
            return cached

    # ---------- name ----------

    def get_name(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    # ---------- operands ----------

    def get_operands(self) -> list[COSBase]:
        return self._operands

    def set_operands(self, operands: list[COSBase]) -> None:
        self._operands = operands

    @property
    def operands(self) -> list[COSBase]:
        return self._operands

    # ---------- inline image data (ID operator) ----------

    def get_image_data(self) -> bytes | None:
        return self._image_data

    def set_image_data(self, image_data: bytes | None) -> None:
        self._image_data = image_data

    @property
    def image_data(self) -> bytes | None:
        return self._image_data

    # ---------- inline image parameters (BI operator) ----------

    def get_image_parameters(self) -> COSDictionary | None:
        return self._image_parameters

    def set_image_parameters(self, params: COSDictionary | None) -> None:
        self._image_parameters = params

    @property
    def image_parameters(self) -> COSDictionary | None:
        return self._image_parameters

    # ---------- repr / str ----------

    def __repr__(self) -> str:
        # Mirrors upstream ``Operator.toString()`` — ``"PDFOperator{<op>}"``.
        return f"PDFOperator{{{self._name}}}"

    def __str__(self) -> str:
        # Java's ``toString()`` is the canonical string form; ``__str__``
        # delegates to ``__repr__`` so ``str(op)`` matches upstream output.
        return self.__repr__()


__all__ = [
    "MissingOperandException",
    "Operator",
    "OperatorName",
    "OperatorProcessor",
]
