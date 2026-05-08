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

    Operand semantics: upstream's ``Operator`` does not store operands —
    the operand stack lives on ``PDFStreamEngine`` / ``PDFStreamParser``.
    pypdfbox's parser, however, attaches the just-popped operands to the
    returned ``Operator`` for the convenience of stream-token consumers
    (it spares them re-implementing the same window-of-tokens trick).
    Operand storage is a per-instance list; do *not* mutate the operands
    on a cached instance returned by :meth:`get_operator` — instead pop
    a fresh one via :meth:`with_operands` or ``copy.copy`` and assign new
    operands.
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

    @staticmethod
    def is_inline_image_operator_name(operator: str) -> bool:
        """Return ``True`` for the inline-image operator names whose
        instances carry per-occurrence payload state.

        ``BI`` carries the parameter dictionary and final image bytes in
        parser-collated streams; ``ID`` carries raw image bytes in lower-
        level parser token streams. ``EI`` is only a delimiter and is not
        classified as payload-bearing.
        """
        return (
            operator == OperatorName.BEGIN_INLINE_IMAGE
            or operator == OperatorName.BEGIN_INLINE_IMAGE_DATA
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
        return self.is_inline_image_operator_name(self._name)

    def is_inline_image(self) -> bool:
        """Alias for :meth:`is_inline_image_operator`, matching the
        parser-internal operator surface."""
        return self.is_inline_image_operator()

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

    def clear_operands(self) -> None:
        """Remove any attached operands from this instance."""
        self._operands = []

    @property
    def operands(self) -> list[COSBase]:
        return self._operands

    # ---------- inline image data (ID operator) ----------

    def get_image_data(self) -> bytes | None:
        return self._image_data

    def set_image_data(self, image_data: bytes | None) -> None:
        self._image_data = image_data

    def has_image_data(self) -> bool:
        """Return ``True`` iff image bytes have been attached.

        Empty bytes count as present; only ``None`` means absent.
        """
        return self._image_data is not None

    def clear_image_data(self) -> None:
        """Remove any attached inline-image bytes."""
        self._image_data = None

    @property
    def image_data(self) -> bytes | None:
        return self._image_data

    # ---------- inline image parameters (BI operator) ----------

    def get_image_parameters(self) -> COSDictionary | None:
        return self._image_parameters

    def set_image_parameters(self, params: COSDictionary | None) -> None:
        self._image_parameters = params

    def has_image_parameters(self) -> bool:
        """Return ``True`` iff an inline-image parameter dictionary is attached."""
        return self._image_parameters is not None

    def clear_image_parameters(self) -> None:
        """Remove any attached inline-image parameter dictionary."""
        self._image_parameters = None

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

    def __len__(self) -> int:
        return len(self._name)


__all__ = [
    "MissingOperandException",
    "Operator",
    "OperatorName",
    "OperatorProcessor",
]
