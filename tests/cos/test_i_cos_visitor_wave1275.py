"""Wave 1275 — ICOSVisitor.visit_from_int default parity."""

from __future__ import annotations

from typing import Any

from pypdfbox.cos.i_cos_visitor import ICOSVisitor


class _CountingVisitor(ICOSVisitor):
    """Implements only the abstract surface; relies on the default
    ``visit_from_int`` provided by the base class."""

    def __init__(self) -> None:
        self.from_int_calls: list[Any] = []

    def visit_from_array(self, obj: Any) -> Any: ...
    def visit_from_boolean(self, obj: Any) -> Any: ...
    def visit_from_dictionary(self, obj: Any) -> Any: ...
    def visit_from_document(self, obj: Any) -> Any: ...
    def visit_from_float(self, obj: Any) -> Any: ...

    def visit_from_integer(self, obj: Any) -> Any:
        self.from_int_calls.append(obj)
        return ("integer", obj)

    def visit_from_name(self, obj: Any) -> Any: ...
    def visit_from_null(self, obj: Any) -> Any: ...
    def visit_from_stream(self, obj: Any) -> Any: ...
    def visit_from_string(self, obj: Any) -> Any: ...
    def visit_from_object(self, obj: Any) -> Any: ...


def test_visit_from_int_defaults_to_visit_from_integer() -> None:
    v = _CountingVisitor()
    assert v.visit_from_int(42) == ("integer", 42)
    assert v.from_int_calls == [42]


def test_visit_from_int_can_be_overridden() -> None:
    class CustomVisitor(_CountingVisitor):
        def __init__(self) -> None:
            super().__init__()
            self.strict_calls: list[Any] = []

        def visit_from_int(self, obj: Any) -> Any:
            self.strict_calls.append(obj)
            return ("strict", obj)

    v = CustomVisitor()
    assert v.visit_from_int(7) == ("strict", 7)
    assert v.strict_calls == [7]
    # The contracted spelling stays untouched when only strict is overridden.
    assert v.from_int_calls == []
