"""Wave 1337 coverage-boost tests for ``pypdfbox.xmpbox.xmp_schema``.

Targets the typed-property cache-eviction branches, the ArrayProperty arm of
``internal_add_bag_value``, ``reorganize_alt_order`` over a dict, the
``instanciate_simple`` factory, and the standalone ``merge_complex_property``
helper.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata, XMPSchema
from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.boolean_type import BooleanType
from pypdfbox.xmpbox.type.date_type import DateType
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.text_type import TextType


def _schema() -> XMPSchema:
    return XMPSchema(
        XMPMetadata.create_xmp_metadata(),
        namespace_uri="http://example.com/ns#",
        prefix="ex",
    )


def test_typed_boolean_cache_evicts_on_value_change() -> None:
    """``set_boolean_property_value`` evicts a stale cached wrapper
    whose value disagrees with the new raw value (line 517)."""
    s = _schema()
    s.set_boolean_property_value("flag", True)
    # Prime the typed cache by reading through the typed getter.
    wrapper = s.get_boolean_property("flag")
    assert wrapper is not None
    # Change the raw value — eviction branch executes.
    s.set_boolean_property_value("flag", False)
    assert s.get_boolean_property_value("flag") is False
    # Verify the cache was cleared (or refreshed) — the typed wrapper
    # we get back now must agree with the new raw value.
    new_wrapper = s.get_boolean_property("flag")
    assert new_wrapper is not None
    assert new_wrapper.get_value() is False


def test_typed_integer_cache_evicts_on_value_change() -> None:
    s = _schema()
    s.set_integer_property_value("count", 5)
    wrapper = s.get_integer_property("count")
    assert wrapper is not None
    s.set_integer_property_value("count", 99)
    assert s.get_integer_property_value("count") == 99
    new_wrapper = s.get_integer_property("count")
    assert new_wrapper is not None
    assert new_wrapper.get_value() == 99


def test_typed_date_cache_evicts_on_value_change() -> None:
    s = _schema()
    d1 = datetime(2024, 1, 1, tzinfo=UTC)
    d2 = datetime(2025, 6, 15, tzinfo=UTC)
    s.set_date_property_value("when", d1)
    wrapper = s.get_date_property("when")
    assert wrapper is not None
    s.set_date_property_value("when", d2)
    assert s.get_date_property_value("when") == d2
    new_wrapper = s.get_date_property("when")
    assert new_wrapper is not None
    assert new_wrapper.get_value() == d2


def test_typed_property_or_raise_returns_none_when_both_absent() -> None:
    """Line 773 — when neither the raw value nor a cached wrapper
    exists, the typed getter returns ``None`` instead of raising."""
    s = _schema()
    assert s.get_boolean_property("missing") is None
    assert s.get_integer_property("missing") is None
    assert s.get_date_property("missing") is None


def test_typed_property_or_raise_unknown_raw_type_raises() -> None:
    """Line 806 — ``_rehydrate_simple_or_raise`` raises
    ``BadFieldValueException`` for raw values that don't match any
    supported XMP scalar shape."""
    from pypdfbox.xmpbox.xmp_schema import BadFieldValueException

    s = _schema()
    # Inject a raw value of an unexpected type — e.g. a tuple — to
    # force the final ``else`` arm of the type-discriminator.
    s._properties["weird"] = (1, 2, 3)
    with pytest.raises(BadFieldValueException):
        s.get_boolean_property("weird")


def test_typed_property_or_raise_raw_type_mismatch_raises() -> None:
    """``_rehydrate_simple_or_raise`` also raises when the raw value's
    Python type maps to a different XMP type than the caller asked for
    (e.g. asking for Boolean when the raw is an int)."""
    from pypdfbox.xmpbox.xmp_schema import BadFieldValueException

    s = _schema()
    s.set_integer_property_value("num", 42)
    # Prime as IntegerType, then ask for BooleanType — must raise.
    with pytest.raises(BadFieldValueException):
        s.get_boolean_property("num")


def test_internal_add_bag_value_str_fallback() -> None:
    """Line 886 — non-:class:`AbstractSimpleProperty` values fall through
    to ``str(value)`` before being appended."""
    s = _schema()
    s.internal_add_bag_value("subject", 42)  # int → str fallback
    assert s.get_unqualified_bag_value_list("subject") == ["42"]


def test_internal_add_bag_value_array_property_arm() -> None:
    """Lines 888-899 — when the existing storage is an
    :class:`ArrayProperty`, the new value is wrapped as a ``TextType``
    and appended via ``add_property``."""
    s = _schema()
    metadata = s.get_metadata()
    arr = ArrayProperty(
        metadata, "http://example.com/ns#", "ex", "subject", Cardinality.Bag
    )
    s._properties["subject"] = arr
    s.internal_add_bag_value("subject", "hello")
    # The array now holds one TextType
    children = arr.get_all_properties()
    assert len(children) == 1
    assert isinstance(children[0], TextType)
    assert children[0].get_string_value() == "hello"


def test_internal_add_bag_value_array_property_with_simple_property() -> None:
    """An :class:`AbstractSimpleProperty` value falls through to
    ``get_string_value()`` before being wrapped (line 884)."""
    s = _schema()
    metadata = s.get_metadata()
    arr = ArrayProperty(
        metadata, "http://example.com/ns#", "ex", "subject", Cardinality.Bag
    )
    s._properties["subject"] = arr
    inner = TextType(metadata, "http://example.com/ns#", "ex", "li", "world")
    s.internal_add_bag_value("subject", inner)
    children = arr.get_all_properties()
    assert len(children) == 1
    assert children[0].get_string_value() == "world"


def test_reorganize_alt_order_with_dict() -> None:
    """Lines 915-916 — ``reorganize_alt_order`` delegates to the
    underscored helper when handed a dict."""
    s = _schema()
    values = {"fr": "Bonjour", "x-default": "Hello", "de": "Hallo"}
    s.reorganize_alt_order(values)
    # x-default must be the first key after reorganisation.
    assert next(iter(values.keys())) == "x-default"


def test_reorganize_alt_order_non_dict_is_no_op() -> None:
    """A non-dict input is silently ignored (line 916 not entered)."""
    s = _schema()
    # No exception, just a no-op
    s.reorganize_alt_order(["a", "b"])
    s.reorganize_alt_order(None)


def test_instanciate_simple_dispatches_per_type() -> None:
    """Lines 932-951 — ``instanciate_simple`` returns the right
    :class:`AbstractSimpleProperty` subclass for each Python scalar
    type."""
    s = _schema()
    assert isinstance(s.instanciate_simple("p", True), BooleanType)
    assert isinstance(s.instanciate_simple("p", 5), IntegerType)
    assert isinstance(
        s.instanciate_simple("p", datetime(2024, 1, 1, tzinfo=UTC)), DateType
    )
    assert isinstance(s.instanciate_simple("p", "hello"), TextType)


def test_instanciate_simple_rejects_unknown_type() -> None:
    """``instanciate_simple`` raises ``TypeError`` for values whose
    Python type doesn't map to a supported XMP scalar."""
    s = _schema()
    with pytest.raises(TypeError, match="Cannot instanciate"):
        s.instanciate_simple("p", [1, 2, 3])


def test_merge_complex_property_short_circuits_on_duplicate() -> None:
    """Lines 1012-1016 — ``merge_complex_property`` returns True the
    moment it encounters a duplicate; remaining new entries are
    dropped."""
    s = _schema()
    existing: list[object] = ["a", "b"]
    new_values: list[object] = ["c", "b", "d"]  # b is a duplicate
    result = s.merge_complex_property(new_values, existing)
    assert result is True
    # c was appended before the short-circuit; d was never seen.
    assert existing == ["a", "b", "c"]


def test_merge_complex_property_returns_false_when_all_appended() -> None:
    """When every new entry is unique, ``merge_complex_property`` walks
    the full iterable and returns False."""
    s = _schema()
    existing: list[object] = ["a"]
    new_values: list[object] = ["b", "c"]
    result = s.merge_complex_property(new_values, existing)
    assert result is False
    assert existing == ["a", "b", "c"]


def test_set_specified_simple_type_property_round_trip() -> None:
    """``set_specified_simple_type_property`` installs both the raw
    value (so string-form readers see it) and caches the wrapper (so
    typed getters return the same instance)."""
    s = _schema()
    text = TextType(s.get_metadata(), s.get_namespace(), s.get_prefix(), "title", "T")
    s.set_specified_simple_type_property(text)
    assert s.get_property("title") == "T"
