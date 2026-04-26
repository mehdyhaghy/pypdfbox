from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase

if TYPE_CHECKING:
    from .operator import Operator
    from .pdf_stream_engine import PDFStreamEngine


class MissingOperandException(OSError):
    """
    Raised when a content-stream operator handler is invoked with too few
    operands.

    Mirrors ``org.apache.pdfbox.contentstream.operator.MissingOperandException``.
    Upstream extends ``IOException``; per CLAUDE.md test-porting table we
    map ``IOException`` to ``OSError`` in pypdfbox.

    The message format mirrors upstream verbatim:
    ``Operator <name> has too few operands: <operands>``.
    """

    def __init__(self, operator: Operator, operands: list[COSBase]) -> None:
        super().__init__(
            f"Operator {operator.get_name()} has too few operands: {operands}"
        )
        self.operator = operator
        self.operands = operands


class OperatorProcessor(ABC):
    """
    Abstract base for a single PDF content-stream operator handler.

    Mirrors ``org.apache.pdfbox.contentstream.operator.OperatorProcessor``.
    Subclasses implement :meth:`process` to handle one operator (their
    :meth:`get_name` returns the operator's two-or-three-letter token,
    e.g. ``BT``, ``Tj``, ``TJ``).

    A processor is registered with a :class:`PDFStreamEngine` via
    :meth:`PDFStreamEngine.add_operator`; the engine then invokes
    :meth:`process` whenever the corresponding operator is encountered in
    the token stream.

    Upstream's constructor takes a ``PDFStreamEngine`` context and the
    field is final. We mirror the shape but allow ``None`` so a processor
    can be constructed standalone and bound later via :meth:`set_context`
    — useful both for testing and for the typical ``add_operator``
    rebind that the engine performs at registration time.
    """

    def __init__(self, context: PDFStreamEngine | None = None) -> None:
        self._context: PDFStreamEngine | None = context

    def set_context(self, context: PDFStreamEngine) -> None:
        """Bind this processor to its dispatching engine."""
        self._context = context

    def get_context(self) -> PDFStreamEngine:
        """Return the bound engine, or raise if none has been set yet.

        Upstream marks ``getContext`` as ``protected final`` and never
        nulls the context after construction; we raise rather than return
        ``None`` so accidental misuse fails fast.
        """
        if self._context is None:
            raise RuntimeError(
                f"{type(self).__name__} has no PDFStreamEngine context bound; "
                "register it with engine.add_operator(...) first"
            )
        return self._context

    @abstractmethod
    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        """Handle one occurrence of the operator with its operand stack."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the operator token this processor handles (e.g. ``BT``)."""

    def check_array_types_class(
        self, operands: list[COSBase], expected: type
    ) -> bool:
        """Return ``True`` iff every entry in ``operands`` is an instance
        of ``expected``. Mirrors upstream's ``checkArrayTypesClass``."""
        return all(isinstance(o, expected) for o in operands)
