"""Wave 1368 — ICOSVisitor dispatch parity across the entire COS hierarchy.

Round-out tests for paths not yet covered: every concrete ``COSBase``
subclass must dispatch its ``accept(visitor)`` call to the matching
``visit_from_*`` method. This pins the double-dispatch contract that
``COSWriter`` and other visitors depend on.

Also verifies:

* ``visit_from_int`` defaults to ``visit_from_integer`` (Java-name
  passthrough for strict ports of upstream code).
* A return value from a visitor is propagated through ``accept``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
    ICOSVisitor,
)
from tests.cos.helpers import RecordingVisitor


def test_visit_from_array_dispatch() -> None:
    visitor = RecordingVisitor()
    arr = COSArray([COSInteger.get(1)])
    arr.accept(visitor)
    assert visitor.calls == [("array", arr)]


def test_visit_from_boolean_dispatch() -> None:
    visitor = RecordingVisitor()
    COSBoolean.TRUE.accept(visitor)
    COSBoolean.FALSE.accept(visitor)
    assert visitor.calls == [
        ("boolean", COSBoolean.TRUE),
        ("boolean", COSBoolean.FALSE),
    ]


def test_visit_from_dictionary_dispatch() -> None:
    visitor = RecordingVisitor()
    d = COSDictionary([("X", COSInteger.get(1))])
    d.accept(visitor)
    assert visitor.calls == [("dictionary", d)]


def test_visit_from_document_dispatch() -> None:
    visitor = RecordingVisitor()
    doc = COSDocument()
    try:
        doc.accept(visitor)
        assert visitor.calls == [("document", doc)]
    finally:
        doc.close()


def test_visit_from_float_dispatch() -> None:
    visitor = RecordingVisitor()
    f = COSFloat(1.5)
    f.accept(visitor)
    assert visitor.calls == [("float", f)]


def test_visit_from_integer_dispatch() -> None:
    visitor = RecordingVisitor()
    i = COSInteger.get(7)
    i.accept(visitor)
    assert visitor.calls == [("integer", i)]


def test_visit_from_name_dispatch() -> None:
    visitor = RecordingVisitor()
    n = COSName.get_pdf_name("Hello")
    n.accept(visitor)
    assert visitor.calls == [("name", n)]


def test_visit_from_null_dispatch() -> None:
    visitor = RecordingVisitor()
    COSNull.NULL.accept(visitor)
    assert visitor.calls == [("null", COSNull.NULL)]


def test_visit_from_stream_dispatch() -> None:
    visitor = RecordingVisitor()
    stream = COSStream()
    try:
        stream.accept(visitor)
        assert visitor.calls == [("stream", stream)]
    finally:
        stream.close()


def test_visit_from_string_dispatch() -> None:
    visitor = RecordingVisitor()
    s = COSString("hi")
    s.accept(visitor)
    assert visitor.calls == [("string", s)]


def test_visit_from_object_dispatch() -> None:
    visitor = RecordingVisitor()
    ref = COSObject(7, 0, resolved=COSInteger.get(1))
    ref.accept(visitor)
    assert visitor.calls == [("object", ref)]


def test_visit_from_int_delegates_to_visit_from_integer() -> None:
    """``visit_from_int`` (Java spelling) defaults to delegating to
    ``visit_from_integer`` so visitors that only override the Python
    spelling stay compatible with code paths that call the Java name."""

    class _Visitor(ICOSVisitor):
        def __init__(self) -> None:
            self.called: list[str] = []

        def visit_from_array(self, obj: Any) -> Any: ...

        def visit_from_boolean(self, obj: Any) -> Any: ...

        def visit_from_dictionary(self, obj: Any) -> Any: ...

        def visit_from_document(self, obj: Any) -> Any: ...

        def visit_from_float(self, obj: Any) -> Any: ...

        def visit_from_integer(self, obj: Any) -> Any:
            self.called.append("integer")

        def visit_from_name(self, obj: Any) -> Any: ...

        def visit_from_null(self, obj: Any) -> Any: ...

        def visit_from_stream(self, obj: Any) -> Any: ...

        def visit_from_string(self, obj: Any) -> Any: ...

        def visit_from_object(self, obj: Any) -> Any: ...

    visitor = _Visitor()
    visitor.visit_from_int(COSInteger.get(5))
    assert visitor.called == ["integer"]


def test_accept_propagates_visitor_return_value() -> None:
    """``accept`` returns whatever the visitor returns — used by
    ``COSWriter`` to thread results back to the caller."""

    class _ReturningVisitor(ICOSVisitor):
        def visit_from_array(self, obj: Any) -> Any:
            return ("array", obj)

        def visit_from_boolean(self, obj: Any) -> Any:
            return ("boolean", obj)

        def visit_from_dictionary(self, obj: Any) -> Any:
            return ("dictionary", obj)

        def visit_from_document(self, obj: Any) -> Any:
            return ("document", obj)

        def visit_from_float(self, obj: Any) -> Any:
            return ("float", obj)

        def visit_from_integer(self, obj: Any) -> Any:
            return ("integer", obj)

        def visit_from_name(self, obj: Any) -> Any:
            return ("name", obj)

        def visit_from_null(self, obj: Any) -> Any:
            return ("null", obj)

        def visit_from_stream(self, obj: Any) -> Any:
            return ("stream", obj)

        def visit_from_string(self, obj: Any) -> Any:
            return ("string", obj)

        def visit_from_object(self, obj: Any) -> Any:
            return ("object", obj)

    visitor = _ReturningVisitor()
    assert COSInteger.get(1).accept(visitor) == ("integer", COSInteger.get(1))
    assert COSName.get_pdf_name("x").accept(visitor) == (
        "name",
        COSName.get_pdf_name("x"),
    )
    assert COSBoolean.TRUE.accept(visitor) == ("boolean", COSBoolean.TRUE)
    assert COSNull.NULL.accept(visitor) == ("null", COSNull.NULL)


def test_nested_visit_array_recurses_through_children() -> None:
    """Visitors typically walk children manually inside
    ``visit_from_array`` / ``visit_from_dictionary``. Verify the
    accept-then-iterate pattern records every node."""

    class _Walker(RecordingVisitor):
        def visit_from_array(self, obj: Any) -> Any:
            super().visit_from_array(obj)
            for child in obj:
                child.accept(self)

        def visit_from_dictionary(self, obj: Any) -> Any:
            super().visit_from_dictionary(obj)
            for value in obj.values():
                value.accept(self)

    inner_array = COSArray([COSInteger.get(1), COSInteger.get(2)])
    outer_dict = COSDictionary([("Inner", inner_array)])
    visitor = _Walker()
    outer_dict.accept(visitor)
    kinds = [k for k, _ in visitor.calls]
    assert kinds == ["dictionary", "array", "integer", "integer"]
