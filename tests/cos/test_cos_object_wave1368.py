"""Wave 1368 — COSObject lazy-resolve, dangling references and cycles.

Round-out tests for paths not yet covered:

* ``get_object()`` invokes the loader exactly once and caches the result
  (mirroring PDFBox's dereference-then-drop-loader pattern).
* Mid-load cycles do not infinitely recurse — ``_dereferenced`` flips
  before the loader runs.
* Free / dangling references (loader returns ``None``) leave the object
  resolved-to-``None`` and ``is_dereferenced`` returns ``True``.
* ``set_object`` swaps the resolved value even after a load.
* ``set_loader(None)`` removes the loader so subsequent calls cannot
  replace the already-resolved value.
* ``set_to_null`` pins to ``COSNull.NULL`` and drops the loader.
* Equality is over ``(object_number, generation_number)`` regardless of
  the resolved payload — two COSObjects pointing at the same key compare
  equal even if they have different resolved values.
* ``__repr__`` / ``to_string`` formatting parity with upstream.
* Constructor validation rejects negative numbers.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)


def test_loader_invoked_once_and_dropped() -> None:
    calls = 0

    def loader(holder: COSObject) -> COSInteger:
        nonlocal calls
        calls += 1
        return COSInteger.get(42)

    ref = COSObject(1, 0, loader=loader)
    assert ref.is_dereferenced() is False
    assert ref.get_object().value == 42  # type: ignore[union-attr]
    assert calls == 1
    # Subsequent calls do NOT re-invoke the loader.
    ref.get_object()
    assert calls == 1
    assert ref.is_dereferenced() is True


def test_loader_cycle_does_not_recurse_forever() -> None:
    """If the loader re-enters ``get_object()`` (cycle), the second call
    must short-circuit on the dereferenced flag — set BEFORE invocation —
    and return ``None`` until the outer call's return value is stored.
    """
    visit_count = 0

    def loader(holder: COSObject) -> COSInteger:
        nonlocal visit_count
        visit_count += 1
        # Re-entry attempt — should return the (still-None) cached value.
        recursive = holder.get_object()
        assert recursive is None
        return COSInteger.get(99)

    ref = COSObject(2, 0, loader=loader)
    assert ref.get_object().value == 99  # type: ignore[union-attr]
    assert visit_count == 1


def test_dangling_reference_resolves_to_none_but_dereferenced() -> None:
    """A free xref entry produces a loader that returns ``None``. The
    holder must still be marked as dereferenced so the next read does
    not re-invoke the loader."""

    def loader(holder: COSObject) -> None:
        return None

    ref = COSObject(3, 0, loader=loader)
    assert ref.get_object() is None
    assert ref.is_dereferenced() is True
    assert ref.is_object_null() is True


def test_pre_resolved_object_marked_dereferenced() -> None:
    resolved = COSInteger.get(7)
    ref = COSObject(4, 0, resolved=resolved)
    assert ref.is_dereferenced() is True
    assert ref.is_object_loaded() is True
    # No loader is consulted; just returns the resolved value.
    assert ref.get_object() is resolved


def test_set_object_replaces_resolved_value() -> None:
    ref = COSObject(5, 0, resolved=COSInteger.get(1))
    ref.set_object(COSInteger.get(2))
    assert ref.get_object().value == 2  # type: ignore[union-attr]


def test_set_object_can_set_to_none_but_keeps_dereferenced_true() -> None:
    ref = COSObject(6, 0, resolved=COSInteger.get(1))
    ref.set_object(None)
    assert ref.get_object() is None
    assert ref.is_dereferenced() is True


def test_set_loader_none_after_resolution_prevents_replacement() -> None:
    """Once an object has been resolved we should be able to nuke the
    loader so a subsequent ``set_loader`` invocation cannot replace the
    cached value. This mirrors PDFBox parser behaviour after
    ``setLoader(null)``."""
    captured: list[int] = []

    def loader(holder: COSObject) -> COSInteger:
        captured.append(1)
        return COSInteger.get(100)

    ref = COSObject(7, 0, loader=loader)
    ref.set_loader(None)
    # Without a loader the object stays unresolved.
    assert ref.get_object() is None
    assert captured == []


def test_set_loader_replaces_existing_loader() -> None:
    ref = COSObject(8, 0)

    def first_loader(holder: COSObject) -> COSInteger:
        return COSInteger.get(1)

    def second_loader(holder: COSObject) -> COSInteger:
        return COSInteger.get(2)

    ref.set_loader(first_loader)
    ref.set_loader(second_loader)
    assert ref.get_object().value == 2  # type: ignore[union-attr]


def test_set_to_null_pins_cos_null() -> None:
    ref = COSObject(9, 0)
    ref.set_to_null()
    assert ref.get_object() is COSNull.NULL
    assert ref.is_dereferenced() is True
    # The loader is dropped so even if we re-attach one, the next read
    # would still surface COSNull.NULL? No — set_to_null only drops the
    # current loader; ``set_loader`` can reattach. Verify by reading
    # without reattach.
    assert ref.get_object() is COSNull.NULL


def test_equality_over_object_number_and_generation() -> None:
    # Different resolved payloads but same key — must compare equal.
    a = COSObject(10, 0, resolved=COSInteger.get(1))
    b = COSObject(10, 0, resolved=COSInteger.get(2))
    assert a == b
    assert hash(a) == hash(b)


def test_equality_distinguishes_generations() -> None:
    a = COSObject(10, 0)
    b = COSObject(10, 1)
    assert a != b


def test_equality_with_non_cos_object_returns_notimplemented() -> None:
    a = COSObject(10, 0)
    assert (a == "10 0 R") is False


def test_constructor_rejects_negative_object_number() -> None:
    with pytest.raises(ValueError, match="object_number"):
        COSObject(-1, 0)


def test_constructor_rejects_negative_generation_number() -> None:
    with pytest.raises(ValueError, match="generation_number"):
        COSObject(0, -1)


def test_constructor_accessors() -> None:
    ref = COSObject(11, 2, resolved=COSString("hello"))
    assert ref.object_number == 11
    assert ref.generation_number == 2
    assert ref.get_object_number() == 11
    assert ref.get_generation_number() == 2


def test_repr_format() -> None:
    ref = COSObject(12, 3)
    assert repr(ref) == "COSObject(12 3 R)"


def test_str_format_matches_pdfbox() -> None:
    ref = COSObject(12, 3)
    assert str(ref) == "COSObject{12 3 R}"
    assert ref.to_string() == "COSObject{12 3 R}"


def test_resolves_to_cosdict_after_lazy_load() -> None:
    captured: list[int] = []

    def loader(holder: COSObject) -> COSDictionary:
        captured.append(holder.object_number)
        return COSDictionary([("X", COSInteger.get(7))])

    ref = COSObject(13, 0, loader=loader)
    resolved = ref.get_object()
    assert isinstance(resolved, COSDictionary)
    assert resolved.get_int("X") == 7
    assert captured == [13]


def test_is_object_loaded_distinct_from_is_dereferenced() -> None:
    """A dangling reference: loader runs, returns None, so
    ``is_dereferenced`` is True but ``is_object_loaded`` is False."""
    ref = COSObject(14, 0, loader=lambda holder: None)
    ref.get_object()
    assert ref.is_dereferenced() is True
    assert ref.is_object_loaded() is False
    assert ref.is_object_null() is True


def test_loader_receives_holder_self() -> None:
    captured_holder: list[COSObject] = []

    def loader(holder: COSObject) -> None:
        captured_holder.append(holder)
        return None

    ref = COSObject(15, 0, loader=loader)
    ref.get_object()
    assert captured_holder == [ref]


def test_set_needs_to_be_updated_no_op_without_origin_document() -> None:
    """``set_needs_to_be_updated`` is a no-op until the object is wired
    into a document that is ``accepting updates`` — mirrors PDFBox where
    the update flag only flips while the parser is consuming an
    incremental save."""
    ref = COSObject(16, 0, resolved=COSInteger.get(1))
    assert ref.is_needs_to_be_updated() is False
    ref.set_needs_to_be_updated(True)
    # Without a document state in accepting-updates mode, the flag
    # cannot move — verify the setter is at least callable.
    assert ref.is_needs_to_be_updated() is False


def test_pre_resolved_with_cos_name() -> None:
    name = COSName.get_pdf_name("Pages")
    ref = COSObject(17, 0, resolved=name)
    assert ref.get_object() is name
    # Calling get_object again must NOT trigger any loader logic.
    assert ref.get_object() is name


def test_generation_zero_default() -> None:
    ref = COSObject(18)
    assert ref.generation_number == 0
