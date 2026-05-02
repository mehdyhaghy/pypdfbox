"""Hand-written parity tests for :class:`CompressParameters`.

Exercises the full public surface mirrored from
``org.apache.pdfbox.pdfwriter.compress.CompressParameters`` (PDFBox
3.0.x): the two pre-built singletons, the default object-stream size
constant, the size getter, the ``is_compress`` predicate, and the
negative-size validation.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfwriter import CompressParameters
from pypdfbox.pdfwriter.compress import CompressParameters as CP_FromCompress
from pypdfbox.pdfwriter.compress.compress_parameters import (
    CompressParameters as CP_FromModule,
)


def test_class_is_re_exported_consistently() -> None:
    assert CompressParameters is CP_FromCompress
    assert CompressParameters is CP_FromModule


def test_default_object_stream_size_constant() -> None:
    # Upstream pins this at 200; downstream consumers depend on it.
    assert CompressParameters.DEFAULT_OBJECT_STREAM_SIZE == 200


def test_default_constructor_uses_default_size() -> None:
    params = CompressParameters()
    assert params.get_object_stream_size() == 200
    assert params.is_compress() is True


def test_explicit_size_is_round_trippable() -> None:
    for size in (1, 50, 200, 1024):
        params = CompressParameters(size)
        assert params.get_object_stream_size() == size
        assert params.is_compress() is True


def test_zero_disables_compression() -> None:
    params = CompressParameters(0)
    assert params.get_object_stream_size() == 0
    assert params.is_compress() is False


def test_negative_size_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        CompressParameters(-1)


def test_default_compression_singleton_matches_default_constructor() -> None:
    assert (
        CompressParameters.DEFAULT_COMPRESSION.get_object_stream_size()
        == CompressParameters.DEFAULT_OBJECT_STREAM_SIZE
    )
    assert CompressParameters.DEFAULT_COMPRESSION.is_compress() is True


def test_no_compression_singleton_disables_compression() -> None:
    assert CompressParameters.NO_COMPRESSION.get_object_stream_size() == 0
    assert CompressParameters.NO_COMPRESSION.is_compress() is False


def test_singletons_are_independent_instances() -> None:
    # Upstream constructs them as separate ``new`` instances; mutation of
    # one (if a future field is added) must not bleed into the other.
    assert (
        CompressParameters.DEFAULT_COMPRESSION
        is not CompressParameters.NO_COMPRESSION
    )


# ---------- value-type semantics (pypdfbox extension) ----------


def test_eq_compares_by_object_stream_size() -> None:
    assert CompressParameters(50) == CompressParameters(50)
    assert CompressParameters(50) != CompressParameters(51)
    # Default ctor matches the constant.
    assert CompressParameters() == CompressParameters(
        CompressParameters.DEFAULT_OBJECT_STREAM_SIZE
    )


def test_eq_against_non_instance_returns_not_implemented() -> None:
    # ``NotImplemented`` from __eq__ surfaces as ``False`` from ``==``
    # but lets Python try the reflected ``__eq__`` first — the contract
    # we want for cross-type comparisons.
    params = CompressParameters(10)
    assert (params == 10) is False
    assert (params == "10") is False
    assert (params == None) is False  # noqa: E711


def test_no_compression_singleton_equals_zero_constructor() -> None:
    assert CompressParameters.NO_COMPRESSION == CompressParameters(0)


def test_default_compression_singleton_equals_default_constructor() -> None:
    assert CompressParameters.DEFAULT_COMPRESSION == CompressParameters()


def test_hash_equal_for_equal_instances() -> None:
    a = CompressParameters(123)
    b = CompressParameters(123)
    assert hash(a) == hash(b)
    # Two unequal instances should very probably hash differently —
    # collisions are legal but our hash mixes the size in directly so
    # they shouldn't collide for small values.
    assert hash(CompressParameters(0)) != hash(CompressParameters(200))


def test_set_membership_uses_value_equality() -> None:
    s = {CompressParameters(50), CompressParameters(50), CompressParameters(0)}
    # The two equal-sized instances collapse into one set element.
    assert len(s) == 2
    assert CompressParameters(50) in s
    assert CompressParameters.NO_COMPRESSION in s


def test_dict_key_uses_value_equality() -> None:
    d = {CompressParameters(10): "small", CompressParameters(1000): "big"}
    # Lookup with a freshly constructed key with the same size hits the
    # same bucket as the original.
    assert d[CompressParameters(10)] == "small"
    assert d[CompressParameters(1000)] == "big"


def test_repr_includes_object_stream_size() -> None:
    assert repr(CompressParameters(42)) == (
        "CompressParameters(object_stream_size=42)"
    )
    assert repr(CompressParameters(0)) == (
        "CompressParameters(object_stream_size=0)"
    )
    assert repr(CompressParameters()) == (
        "CompressParameters(object_stream_size=200)"
    )


# ---------- with_object_stream_size ----------


def test_with_object_stream_size_returns_new_instance() -> None:
    a = CompressParameters(50)
    b = a.with_object_stream_size(100)
    assert b is not a
    assert a.get_object_stream_size() == 50
    assert b.get_object_stream_size() == 100


def test_with_object_stream_size_returns_self_when_size_matches() -> None:
    a = CompressParameters(50)
    # No allocation churn when the requested size is already current.
    assert a.with_object_stream_size(50) is a


def test_with_object_stream_size_can_disable() -> None:
    a = CompressParameters(200)
    assert a.is_compress() is True
    b = a.with_object_stream_size(0)
    assert b.is_compress() is False
    assert b.is_disabled() is True


def test_with_object_stream_size_rejects_negative() -> None:
    a = CompressParameters(50)
    with pytest.raises(ValueError, match="negative"):
        a.with_object_stream_size(-1)


# ---------- is_disabled ----------


def test_is_disabled_inverse_of_is_compress() -> None:
    assert CompressParameters(0).is_disabled() is True
    assert CompressParameters(0).is_compress() is False
    assert CompressParameters(1).is_disabled() is False
    assert CompressParameters(1).is_compress() is True
    assert CompressParameters().is_disabled() is False


def test_no_compression_singleton_is_disabled() -> None:
    assert CompressParameters.NO_COMPRESSION.is_disabled() is True


def test_default_compression_singleton_not_disabled() -> None:
    assert CompressParameters.DEFAULT_COMPRESSION.is_disabled() is False


# ---------- input validation ----------


def test_non_int_size_raises_type_error() -> None:
    with pytest.raises(TypeError, match="must be an int"):
        CompressParameters("200")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be an int"):
        CompressParameters(2.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be an int"):
        CompressParameters([])  # type: ignore[arg-type]


def test_bool_is_accepted_as_int_subclass() -> None:
    # Python's ``bool`` is a subclass of ``int`` (``True == 1``,
    # ``False == 0``). The principle-of-least-surprise behavior for a
    # numeric tunable is to treat them as integer values rather than
    # rejecting them outright — matches Python convention.
    assert CompressParameters(True).get_object_stream_size() == 1
    assert CompressParameters(True).is_compress() is True
    assert CompressParameters(False).get_object_stream_size() == 0
    assert CompressParameters(False).is_compress() is False
    assert CompressParameters(False).is_disabled() is True
