from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ICOSVisitor(ABC):
    """
    Visitor interface over the COS object tree (double dispatch via
    ``COSBase.accept``). Includes ``visit_from_object`` per Apache PDFBox
    4.0 (PRD §4 alignment).

    Parameters are typed as ``Any`` rather than the concrete COS classes
    to keep the interface decoupled from the rest of the cos module
    (avoids circular imports). Subclasses are encouraged to narrow.
    """

    @abstractmethod
    def visit_from_array(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_boolean(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_dictionary(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_document(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_float(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_integer(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_name(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_null(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_stream(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_string(self, obj: Any) -> Any: ...

    @abstractmethod
    def visit_from_object(self, obj: Any) -> Any: ...
