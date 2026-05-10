"""Abstract base for PostScript operators used by Type 4 functions.

Mirrors upstream ``org.apache.pdfbox.pdmodel.common.function.type4.Operator``
(an interface in Java). Python lacks Java-style interfaces, so we use
``abc.ABC`` with a single abstract :meth:`execute` method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .execution_context import ExecutionContext


class Operator(ABC):
    """Interface for PostScript operators.

    Each concrete subclass implements :meth:`execute` to inspect and
    manipulate the execution stack carried by ``context``.
    """

    @abstractmethod
    def execute(self, context: ExecutionContext) -> None:
        """Execute the operator.

        The method can inspect and manipulate the stack via ``context``.
        """
        raise NotImplementedError


__all__ = ["Operator"]
