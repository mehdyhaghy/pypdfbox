from __future__ import annotations

import pytest

from pypdfbox.cos import COSInteger, COSNull, COSObject


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


def test_is_object_null_when_unresolved() -> None:
    obj = COSObject(4, 0)
    assert obj.is_object_null()


def test_is_object_null_after_resolution() -> None:
    obj = COSObject(4, 0, resolved=COSInteger(1))
    assert not obj.is_object_null()


def test_is_dereferenced_starts_false_until_load() -> None:
    obj = COSObject(8, 0, loader=lambda o: COSInteger(5))
    assert not obj.is_dereferenced()
    obj.get_object()
    assert obj.is_dereferenced()


def test_is_dereferenced_true_when_constructed_with_resolved() -> None:
    assert COSObject(9, 0, resolved=COSInteger(0)).is_dereferenced()


def test_is_dereferenced_after_failed_load_remains_true() -> None:
    """A loader that returns ``None`` (free xref entry) still flips the
    dereferenced flag — preventing endless retry loops."""
    obj = COSObject(10, 0, loader=lambda o: None)
    assert obj.get_object() is None
    assert obj.is_dereferenced()
    assert obj.is_object_null()


def test_get_object_does_not_recurse_through_loader() -> None:
    """A loader that re-enters ``get_object()`` must not loop forever —
    upstream marks the object dereferenced before invoking the loader."""
    holder: list[COSObject] = []

    def loader(o: COSObject) -> COSInteger | None:
        # Re-entrant call inside the loader: must short-circuit.
        holder.append(o)
        assert o.get_object() is None  # not yet attached
        return COSInteger(11)

    obj = COSObject(11, 0, loader=loader)
    assert obj.get_object() == COSInteger(11)
    assert len(holder) == 1


def test_set_to_null_pins_to_cos_null() -> None:
    obj = COSObject(12, 0, loader=lambda o: COSInteger(99))
    obj.set_to_null()
    # Loader is dropped; the resolved object is the canonical COSNull.NULL.
    assert obj.get_object() is COSNull.NULL
    assert obj.is_dereferenced()
    # ``is_object_null`` is False because COSNull.NULL is a concrete object,
    # mirroring upstream where ``baseObject`` is non-null after setToNull.
    assert not obj.is_object_null()


def test_set_object_marks_dereferenced() -> None:
    obj = COSObject(13, 0)
    assert not obj.is_dereferenced()
    obj.set_object(COSInteger(7))
    assert obj.is_dereferenced()
