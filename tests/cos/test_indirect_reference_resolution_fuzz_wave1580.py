"""Fuzz/parity coverage for indirect-object reference resolution.

Exercises the lazy-dereference path that spans ``COSObject`` (the indirect
reference holder), ``COSDocument``'s object pool, and the single-hop
dereferencing baked into ``COSDictionary.get_dictionary_object`` /
``COSArray.get_object``.

Upstream parity anchors (PDFBox 3.0.7):
  * ``COSObject.getObject`` (COSObject.java:109) — marks ``isDereferenced``
    *before* invoking the parser so a re-entrant resolve (object-graph
    cycle) terminates and yields ``null`` instead of recursing forever; the
    parser callback is dropped in ``finally`` regardless of outcome, so a
    second call returns the cached ``baseObject`` without re-invoking the
    loader.
  * ``COSDictionary.getDictionaryObject(COSName)`` (COSDictionary.java:181) —
    a *single* ``if (retval instanceof COSObject)`` hop, then a
    ``COSNull -> null`` collapse. NOT a ``while`` loop: an on-disk object
    whose body is itself a bare ``N G R`` reference resolves to another
    ``COSObject`` and is returned as-is.
  * ``COSArray.getObject(int)`` (COSArray.java:231) — same single hop +
    ``COSNull -> null``; ``COSArray.get(int)`` (COSArray.java:253) returns
    the raw list entry with NO dereference.
  * ``COSArray.getInt/getName/getString`` (COSArray.java:265/318/366) read
    the *raw* entry (``objects.get(index)``) and only match a direct
    ``COSNumber``/``COSName``/``COSString`` — an indirect reference falls
    through to the default.

Deliberate divergence under test: pypdfbox ``COSObject.__eq__`` compares by
``(object_number, generation_number)`` whereas upstream ``COSObject`` keeps
Java identity equality (no ``equals`` override). See CHANGES.md.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString

K = COSName.get_pdf_name("K")


# --------------------------------------------------------------------------
# get_object: loader, caching, null
# --------------------------------------------------------------------------


def test_get_object_invokes_loader_once_and_caches() -> None:
    calls: list[int] = []

    def loader(_o: COSObject) -> COSInteger:
        calls.append(1)
        return COSInteger.get(42)

    obj = COSObject(7, 0, loader=loader)
    first = obj.get_object()
    second = obj.get_object()
    assert first is second
    assert len(calls) == 1
    assert isinstance(first, COSInteger)
    assert first.value == 42


def test_get_object_no_loader_returns_none() -> None:
    obj = COSObject(9, 0)
    assert obj.get_object() is None


def test_resolved_construction_marks_dereferenced() -> None:
    target = COSInteger.get(5)
    obj = COSObject(3, 0, resolved=target)
    assert obj.is_dereferenced() is True
    assert obj.get_object() is target


def test_unresolved_before_after_dereference() -> None:
    obj = COSObject(4, 0, loader=lambda _o: COSInteger.get(1))
    assert obj.is_dereferenced() is False
    assert obj.is_object_loaded() is False
    obj.get_object()
    assert obj.is_dereferenced() is True
    assert obj.is_object_loaded() is True


def test_loader_returning_none_stays_dereferenced() -> None:
    # A free xref entry resolves to None; upstream marks it dereferenced and
    # never retries (isObjectNull true, isDereferenced true).
    obj = COSObject(11, 0, loader=lambda _o: None)
    assert obj.get_object() is None
    assert obj.is_dereferenced() is True
    assert obj.is_object_null() is True
    # second access does not re-run the (now-dropped) loader
    assert obj.get_object() is None


def test_loader_oserror_resolves_to_none(caplog: pytest.LogCaptureFixture) -> None:
    # Mirrors upstream catch(IOException) -> log + baseObject stays null.
    def boom(_o: COSObject) -> COSInteger:
        raise OSError("malformed xref target")

    obj = COSObject(12, 0, loader=boom)
    assert obj.get_object() is None
    assert obj.is_dereferenced() is True


def test_set_to_null_pins_null_and_drops_loader() -> None:
    obj = COSObject(13, 0, loader=lambda _o: COSInteger.get(7))
    obj.set_to_null()
    assert obj.get_object() is COSNull.NULL
    assert obj.is_dereferenced() is True


# --------------------------------------------------------------------------
# cycle / self-reference termination
# --------------------------------------------------------------------------


def test_self_reference_terminates() -> None:
    obj = COSObject(1, 0)
    obj.set_loader(lambda o: o.get_object())
    # Re-entrant resolve: isDereferenced set before loader runs, so the inner
    # get_object short-circuits to the (still-None) baseObject.
    assert obj.get_object() is None


def test_two_node_cycle_terminates() -> None:
    a = COSObject(1, 0)
    b = COSObject(2, 0)
    a.set_loader(lambda _o: b.get_object())
    b.set_loader(lambda _o: a.get_object())
    assert a.get_object() is None
    assert b.get_object() is None


def test_three_node_cycle_terminates() -> None:
    a = COSObject(1, 0)
    b = COSObject(2, 0)
    c = COSObject(3, 0)
    a.set_loader(lambda _o: b.get_object())
    b.set_loader(lambda _o: c.get_object())
    c.set_loader(lambda _o: a.get_object())
    assert a.get_object() is None


def test_cycle_through_dictionary_terminates() -> None:
    a = COSObject(1, 0)
    d = COSDictionary()
    d.set_item(K, a)
    a.set_loader(lambda _o: d.get_dictionary_object(K))
    # get_dictionary_object hops once into a, a re-enters via loader -> None.
    assert d.get_dictionary_object(K) is None


# --------------------------------------------------------------------------
# COSDictionary.get_dictionary_object dereference semantics
# --------------------------------------------------------------------------


def test_dict_dereferences_single_hop_to_value() -> None:
    target = COSInteger.get(77)
    ref = COSObject(5, 0, resolved=target)
    d = COSDictionary()
    d.set_item(K, ref)
    assert d.get_dictionary_object(K) is target


def test_dict_single_hop_only_chain_returns_intermediate_object() -> None:
    # A -> B -> C: get_dictionary_object does ONE hop (upstream `if`, not
    # `while`), so A resolves to B (a COSObject), and B is returned verbatim.
    c = COSObject(3, 0, resolved=COSInteger.get(42))
    b = COSObject(2, 0, resolved=c)
    a = COSObject(1, 0, resolved=b)
    d = COSDictionary()
    d.set_item(K, a)
    result = d.get_dictionary_object(K)
    assert isinstance(result, COSObject)
    assert result is b


def test_dict_get_item_does_not_dereference() -> None:
    ref = COSObject(5, 0, resolved=COSInteger.get(1))
    d = COSDictionary()
    d.set_item(K, ref)
    assert d.get_item(K) is ref


def test_dict_null_reference_resolves_to_none() -> None:
    ref = COSObject(5, 0, resolved=COSNull.NULL)
    d = COSDictionary()
    d.set_item(K, ref)
    assert d.get_dictionary_object(K) is None
    # raw item is still the COSObject holder
    assert isinstance(d.get_item(K), COSObject)


def test_dict_missing_key_returns_default() -> None:
    d = COSDictionary()
    assert d.get_dictionary_object(K) is None
    sentinel = COSInteger.get(0)
    assert d.get_dictionary_object(K, sentinel) is sentinel


def test_dict_dangling_reference_resolves_to_none() -> None:
    # An indirect ref whose target was never loaded and has no loader.
    dangling = COSObject(404, 0)
    d = COSDictionary()
    d.set_item(K, dangling)
    assert d.get_dictionary_object(K) is None


def test_dict_two_key_overload_falls_through_when_first_null() -> None:
    second = COSName.get_pdf_name("K2")
    d = COSDictionary()
    d.set_item(K, COSObject(5, 0, resolved=COSNull.NULL))
    d.set_item(second, COSInteger.get(9))
    # First key resolves to null -> upstream tries the second key.
    result = d.get_dictionary_object(K, second)
    assert isinstance(result, COSInteger)
    assert result.value == 9


# --------------------------------------------------------------------------
# COSDictionary typed accessors auto-dereference
# --------------------------------------------------------------------------


def test_dict_get_int_dereferences() -> None:
    d = COSDictionary()
    d.set_item(K, COSObject(5, 0, resolved=COSInteger.get(123)))
    assert d.get_int(K) == 123


def test_dict_get_string_dereferences() -> None:
    d = COSDictionary()
    d.set_item(K, COSObject(5, 0, resolved=COSString("hi")))
    assert d.get_string(K) == "hi"


def test_dict_get_name_dereferences() -> None:
    d = COSDictionary()
    d.set_item(K, COSObject(5, 0, resolved=COSName.get_pdf_name("Foo")))
    assert d.get_name(K) == "Foo"


def test_dict_get_cos_array_dereferences() -> None:
    inner = COSArray()
    inner.add(COSInteger.get(1))
    d = COSDictionary()
    d.set_item(K, COSObject(5, 0, resolved=inner))
    got = d.get_cos_array(K)
    assert got is inner


def test_dict_get_cos_dictionary_dereferences() -> None:
    inner = COSDictionary()
    d = COSDictionary()
    d.set_item(K, COSObject(5, 0, resolved=inner))
    assert d.get_cos_dictionary(K) is inner


# --------------------------------------------------------------------------
# COSArray dereference semantics
# --------------------------------------------------------------------------


def test_array_get_returns_raw_reference() -> None:
    ref = COSObject(5, 0, resolved=COSInteger.get(1))
    arr = COSArray()
    arr.add(ref)
    assert arr.get(0) is ref


def test_array_get_object_dereferences() -> None:
    target = COSInteger.get(8)
    ref = COSObject(5, 0, resolved=target)
    arr = COSArray()
    arr.add(ref)
    assert arr.get_object(0) is target


def test_array_get_object_null_collapses_to_none() -> None:
    arr = COSArray()
    arr.add(COSObject(5, 0, resolved=COSNull.NULL))
    assert arr.get_object(0) is None


def test_array_get_raw_null_returns_sentinel() -> None:
    # Upstream get(int) returns the raw list entry, including COSNull.NULL.
    arr = COSArray()
    arr.add(COSNull.NULL)
    assert arr.get(0) is COSNull.NULL
    assert arr.get_object(0) is None


def test_array_get_object_dangling_resolves_to_none() -> None:
    arr = COSArray()
    arr.add(COSObject(404, 0))
    assert arr.get_object(0) is None


def test_array_get_int_does_not_dereference_indirect() -> None:
    # Upstream getInt reads the raw entry; an indirect COSNumber falls through.
    arr = COSArray()
    arr.add(COSObject(5, 0, resolved=COSInteger.get(99)))
    assert arr.get_int(0) == -1
    assert arr.get_int(0, 7) == 7


def test_array_get_int_direct_value() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(99))
    assert arr.get_int(0) == 99


def test_array_get_name_does_not_dereference_indirect() -> None:
    arr = COSArray()
    arr.add(COSObject(5, 0, resolved=COSName.get_pdf_name("Foo")))
    assert arr.get_name(0) is None
    assert arr.get_name(0, "fallback") == "fallback"


def test_array_get_string_does_not_dereference_indirect() -> None:
    arr = COSArray()
    arr.add(COSObject(5, 0, resolved=COSString("hi")))
    assert arr.get_string(0) is None
    assert arr.get_string(0, "fallback") == "fallback"


# --------------------------------------------------------------------------
# COSDocument object pool / dereference wiring
# --------------------------------------------------------------------------


def test_pool_returns_same_instance_per_key() -> None:
    doc = COSDocument()
    try:
        key = COSObjectKey(5, 0)
        a = doc.get_object_from_pool(key)
        b = doc.get_object_from_pool(key)
        assert a is b
        assert a.object_number == 5
        assert a.generation_number == 0
    finally:
        doc.close()


def test_pool_distinct_keys_distinct_objects() -> None:
    doc = COSDocument()
    try:
        a = doc.get_object_from_pool(COSObjectKey(5, 0))
        b = doc.get_object_from_pool(COSObjectKey(6, 0))
        assert a is not b
    finally:
        doc.close()


def test_pool_generation_distinguishes() -> None:
    doc = COSDocument()
    try:
        a = doc.get_object_from_pool(COSObjectKey(5, 0))
        b = doc.get_object_from_pool(COSObjectKey(5, 1))
        assert a is not b
    finally:
        doc.close()


def test_get_object_missing_key_returns_none_without_creating() -> None:
    doc = COSDocument()
    try:
        key = COSObjectKey(77, 0)
        assert doc.get_object(key) is None
        # confirm no placeholder was created
        assert doc.has_object(key) is False
    finally:
        doc.close()


def test_pool_dangling_reference_resolves_to_none_via_dict() -> None:
    # A reference whose pool placeholder is never wired to a loader/offset
    # dereferences to None (free / missing object).
    doc = COSDocument()
    try:
        ref = doc.get_object_from_pool(COSObjectKey(99, 0))
        d = COSDictionary()
        d.set_item(K, ref)
        assert d.get_dictionary_object(K) is None
    finally:
        doc.close()


def test_pool_loader_wired_after_creation_dereferences() -> None:
    doc = COSDocument()
    try:
        key = COSObjectKey(5, 0)
        ref = doc.get_object_from_pool(key)
        target = COSInteger.get(314)
        ref.set_loader(lambda _o: target)
        d = COSDictionary()
        d.set_item(K, ref)
        assert d.get_dictionary_object(K) is target
        # cached on the same pool instance for any other holder of the key
        assert doc.get_object_from_pool(key).get_object() is target
    finally:
        doc.close()


# --------------------------------------------------------------------------
# COSObject equality (deliberate pypdfbox divergence — value equality)
# --------------------------------------------------------------------------


def test_equality_by_num_and_gen() -> None:
    a = COSObject(5, 0, resolved=COSInteger.get(1))
    b = COSObject(5, 0)  # different resolved state, same key
    assert a == b
    assert hash(a) == hash(b)


def test_inequality_different_num() -> None:
    assert COSObject(5, 0) != COSObject(6, 0)


def test_inequality_different_gen() -> None:
    assert COSObject(5, 0) != COSObject(5, 1)


def test_equality_against_non_cosobject() -> None:
    assert (COSObject(5, 0) == COSInteger.get(5)) is False


# --------------------------------------------------------------------------
# misc invariants
# --------------------------------------------------------------------------


def test_negative_object_number_rejected() -> None:
    with pytest.raises(ValueError):
        COSObject(-1, 0)


def test_negative_generation_rejected() -> None:
    with pytest.raises(ValueError):
        COSObject(5, -1)


@pytest.mark.parametrize(
    ("num", "gen"),
    [(0, 0), (1, 0), (65535, 65535), (1000000, 0)],
)
def test_key_round_trips(num: int, gen: int) -> None:
    obj = COSObject(num, gen)
    assert obj.object_number == num
    assert obj.generation_number == gen
    assert obj.get_object_number() == num
    assert obj.get_generation_number() == gen
