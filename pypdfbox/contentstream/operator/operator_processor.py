from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from pypdfbox.cos import COSBase

from . import Operator

if TYPE_CHECKING:
    from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine

_log = logging.getLogger(__name__)


class OperatorProcessor(ABC):
    """
    Lite abstract base for content-stream operator handlers used by
    :class:`OperatorRegistry`.

    This is intentionally a slimmer sibling of
    ``pypdfbox.contentstream.operator_processor.OperatorProcessor``: that
    one is bound to a :class:`PDFStreamEngine` instance and forwards
    notifications through engine hooks; this one decouples dispatch from
    the engine entirely so the registry can be used standalone (e.g. by
    tooling that only needs operator-name routing without any
    text-state, graphics-state, or rendering pipeline behind it).

    Mirrors the shape of
    ``org.apache.pdfbox.contentstream.operator.OperatorProcessor`` but
    drops the ``context`` field — concrete subclasses in this scaffold
    are no-op stubs (just log) until later clusters layer on real
    semantics. Subclasses set the class attribute :attr:`OPERATOR_NAME`
    to the operator token they handle (e.g. ``"Tj"``, ``"q"``, ``"m"``).
    """

    OPERATOR_NAME: ClassVar[str] = ""

    def __init__(self, context: PDFStreamEngine | None = None) -> None:
        self._context: PDFStreamEngine | None = context

    def set_context(self, context: PDFStreamEngine) -> None:
        """Bind this processor to a stream engine when used in the
        engine-dispatch path. Standalone registry use leaves it unset."""
        self._context = context

    @abstractmethod
    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        """Handle one occurrence of the operator with its operand list."""

    def get_name(self) -> str:
        """Return the operator token this processor handles. Default
        implementation returns :attr:`OPERATOR_NAME`."""
        return self.OPERATOR_NAME

    def _log_invocation(
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        """Helper for stub handlers — emits a debug-level log line so
        dispatch is observable during development without flooding info
        logs in production."""
        _log.debug(
            "%s dispatched: operator=%s operands=%r",
            type(self).__name__,
            operator.get_name(),
            operands,
        )


__all__ = ["OperatorProcessor"]
