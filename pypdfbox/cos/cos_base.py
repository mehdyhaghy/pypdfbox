from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .i_cos_visitor import ICOSVisitor


class COSBase(ABC):
    """
    Abstract root of every COS object. Carries the metadata shared by all
    COS types: indirect-vs-direct status (whether this object is referenced
    via the xref table) and the ``needs_to_be_updated`` flag the writer
    consults during incremental save.
    """

    def __init__(self) -> None:
        self._direct: bool = False
        self._needs_to_be_updated: bool = False

    @abstractmethod
    def accept(self, visitor: ICOSVisitor) -> Any:
        """Double-dispatch entry point — concrete subclasses call the
        matching ``visit_from_*`` on the visitor."""

    def is_direct(self) -> bool:
        """``True`` if this object is written inline (not via an indirect
        reference). Mirrors PDFBox's direct/indirect distinction."""
        return self._direct

    def set_direct(self, direct: bool) -> None:
        self._direct = direct

    def is_needs_to_be_updated(self) -> bool:
        """Used by the incremental writer to decide whether this object
        must be re-emitted in the appended xref."""
        return self._needs_to_be_updated

    def set_needs_to_be_updated(self, value: bool) -> None:
        self._needs_to_be_updated = value
