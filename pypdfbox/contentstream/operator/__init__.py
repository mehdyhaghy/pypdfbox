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

    @staticmethod
    def with_operands(operator: str, operands: list[COSBase]) -> Operator:
        """Return a fresh, *uncached* ``Operator`` with ``operands``
        already attached.

        This is the safe alternative to
        ``op = Operator.get_operator(name); op.set_operands(operands)``
        for ordinary (non-inline-image) operators — the latter would
        mutate the singleton returned from the cache and leak the
        operand list across all callers (see the class docstring).
        Inline-image operators (``BI`` / ``ID``) are never cached, so
        :meth:`get_operator` is also safe for those — but ``with_operands``
        works uniformly across both kinds.
        """
        op = Operator(operator)
        op.set_operands(operands)
        return op

    @staticmethod
    def is_cached(operator: str) -> bool:
        """Return ``True`` if :meth:`get_operator` would return a
        cached singleton for ``operator``.

        Inline-image operators (``BI`` / ``ID``) intentionally bypass
        the cache because they carry per-occurrence image data and
        parameters; everything else is cached. Mirrors the implicit
        contract of upstream's ``getOperator`` — exposed here as a
        predicate so callers can decide whether mutating the result is
        safe.
        """
        return (
            operator != OperatorName.BEGIN_INLINE_IMAGE
            and operator != OperatorName.BEGIN_INLINE_IMAGE_DATA
        )

    # ---------- name ----------

    def get_name(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    # ---------- predicates ----------

    def is_inline_image_operator(self) -> bool:
        """Return ``True`` if this operator is one of the two
        inline-image markers (``BI`` or ``ID``).

        These two operators are special-cased throughout PDFBox — they
        carry per-occurrence image parameters / image bytes and are
        deliberately never cached. Exposed here as a predicate so
        callers do not have to compare ``get_name()`` against the two
        :class:`OperatorName` constants by hand.
        """
        return (
            self._name == OperatorName.BEGIN_INLINE_IMAGE
            or self._name == OperatorName.BEGIN_INLINE_IMAGE_DATA
        )

    def has_operands(self) -> bool:
        """Return ``True`` iff at least one operand has been attached.

        Convenience predicate used by tooling code that walks the token
        stream and wants to skip operators with no operand window
        (most painting operators: ``S``, ``f``, ``n``, ``q``, ``Q`` …).
        """
        return bool(self._operands)

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

    # ---------- copy ----------

    def __copy__(self) -> Operator:
        """Return a fresh, *uncached* ``Operator`` carrying the same
        name, a shallow copy of the operands list, and the same image
        parameters / image data references.

        ``copy.copy(op)`` is the recommended way to obtain a mutable
        clone of a cached operator instance — assigning new operands to
        the clone leaves the cache singleton untouched. The image
        parameters dict and image bytes are intentionally shared (not
        deep-copied) — same shape as Java's field-by-field copy.
        """
        clone = Operator(self._name)
        clone._operands = list(self._operands)
        clone._image_data = self._image_data
        clone._image_parameters = self._image_parameters
        return clone

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
