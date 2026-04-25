from __future__ import annotations

import pytest

from pypdfbox.cos import COSBoolean, COSNull


def test_boolean_singletons_distinct() -> None:
    assert COSBoolean.TRUE is not COSBoolean.FALSE
    assert COSBoolean.TRUE.value is True
    assert COSBoolean.FALSE.value is False


def test_boolean_get() -> None:
    assert COSBoolean.get(True) is COSBoolean.TRUE
    assert COSBoolean.get(False) is COSBoolean.FALSE


def test_boolean_bool_protocol() -> None:
    assert bool(COSBoolean.TRUE) is True
    assert bool(COSBoolean.FALSE) is False


def test_boolean_constructor_blocked_after_init() -> None:
    with pytest.raises(RuntimeError):
        COSBoolean(True)


def test_null_singleton() -> None:
    assert COSNull.NULL is COSNull.NULL


def test_null_constructor_blocked_after_init() -> None:
    with pytest.raises(RuntimeError):
        COSNull()


def test_boolean_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    COSBoolean.TRUE.accept(v)
    COSBoolean.FALSE.accept(v)
    assert v.calls == [("boolean", COSBoolean.TRUE), ("boolean", COSBoolean.FALSE)]


def test_null_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    COSNull.NULL.accept(v)
    assert v.calls == [("null", COSNull.NULL)]
