from __future__ import annotations

import pytest

from pypdfbox.cos import COSInteger, COSObject


def test_basic_construction() -> None:
    obj = COSObject(7, 0)
    assert obj.object_number == 7
    assert obj.generation_number == 0
    assert obj.get_object_number() == 7
    assert obj.get_generation_number() == 0
    assert not obj.is_object_loaded()
    assert obj.get_object() is None


def test_resolved_at_construction() -> None:
    inner = COSInteger(42)
    obj = COSObject(1, 0, resolved=inner)
    assert obj.is_object_loaded()
    assert obj.get_object() is inner


def test_loader_is_invoked_lazily_and_cached() -> None:
    inner = COSInteger(123)
    calls: list[COSObject] = []

    def loader(o: COSObject) -> COSInteger:
        calls.append(o)
        return inner

    obj = COSObject(5, 0, loader=loader)
    assert calls == []
    assert obj.get_object() is inner
    assert calls == [obj]
    # Subsequent calls return the cached value, no extra loader invocation.
    assert obj.get_object() is inner
    assert len(calls) == 1


def test_set_object_overrides_lazy() -> None:
    obj = COSObject(2, 0, loader=lambda o: COSInteger(999))
    replacement = COSInteger(1)
    obj.set_object(replacement)
    assert obj.get_object() is replacement


def test_negative_numbers_rejected() -> None:
    with pytest.raises(ValueError):
        COSObject(-1)
    with pytest.raises(ValueError):
        COSObject(1, -1)


def test_equality_by_obj_and_gen() -> None:
    a = COSObject(3, 1)
    b = COSObject(3, 1, resolved=COSInteger(7))
    c = COSObject(3, 2)
    assert a == b  # equal even with different resolved state
    assert a != c
    assert hash(a) == hash(b)


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    obj = COSObject(1, 0)
    obj.accept(v)
    assert v.calls == [("object", obj)]


def test_repr_uses_pdf_indirect_syntax() -> None:
    assert repr(COSObject(7, 0)) == "COSObject(7 0 R)"
