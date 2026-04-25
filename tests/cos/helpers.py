from __future__ import annotations

from typing import Any

from pypdfbox.cos import ICOSVisitor


class RecordingVisitor(ICOSVisitor):
    """Test visitor that records every dispatch call as ``(kind, obj)``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def visit_from_array(self, obj: Any) -> None:
        self.calls.append(("array", obj))

    def visit_from_boolean(self, obj: Any) -> None:
        self.calls.append(("boolean", obj))

    def visit_from_dictionary(self, obj: Any) -> None:
        self.calls.append(("dictionary", obj))

    def visit_from_document(self, obj: Any) -> None:
        self.calls.append(("document", obj))

    def visit_from_float(self, obj: Any) -> None:
        self.calls.append(("float", obj))

    def visit_from_integer(self, obj: Any) -> None:
        self.calls.append(("integer", obj))

    def visit_from_name(self, obj: Any) -> None:
        self.calls.append(("name", obj))

    def visit_from_null(self, obj: Any) -> None:
        self.calls.append(("null", obj))

    def visit_from_stream(self, obj: Any) -> None:
        self.calls.append(("stream", obj))

    def visit_from_string(self, obj: Any) -> None:
        self.calls.append(("string", obj))

    def visit_from_object(self, obj: Any) -> None:
        self.calls.append(("object", obj))
