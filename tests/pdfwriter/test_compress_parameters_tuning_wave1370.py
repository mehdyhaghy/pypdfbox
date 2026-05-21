"""Wave 1370 — CompressParameters object-stream-size tuning.

Centralizes coverage of the small but load-bearing ``CompressParameters``
value object. Mirrors ``org.apache.pdfbox.pdfwriter.compress.CompressParameters``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters

# ---------- defaults / sentinels ------------------------------------------


def test_default_constructor_uses_default_object_stream_size() -> None:
    cp = CompressParameters()
    assert cp.get_object_stream_size() == CompressParameters.DEFAULT_OBJECT_STREAM_SIZE
    assert cp.is_compress() is True
    assert cp.is_disabled() is False


def test_default_object_stream_size_matches_upstream_constant() -> None:
    """Upstream's constant is 200 — pinned in
    ``CompressParameters.DEFAULT_OBJECT_STREAM_SIZE``. Any change to this
    value would break compression-pool chunk-size expectations."""
    assert CompressParameters.DEFAULT_OBJECT_STREAM_SIZE == 200


def test_no_compression_sentinel_disables_compression() -> None:
    cp = CompressParameters.NO_COMPRESSION
    assert cp.get_object_stream_size() == 0
    assert cp.is_compress() is False
    assert cp.is_disabled() is True


def test_default_compression_sentinel_uses_default_size() -> None:
    cp = CompressParameters.DEFAULT_COMPRESSION
    assert cp.get_object_stream_size() == CompressParameters.DEFAULT_OBJECT_STREAM_SIZE
    assert cp.is_compress() is True


# ---------- explicit tuning -----------------------------------------------


def test_custom_object_stream_size_round_trips() -> None:
    cp = CompressParameters(50)
    assert cp.get_object_stream_size() == 50
    assert cp.is_compress() is True


def test_object_stream_size_zero_disables_compression() -> None:
    cp = CompressParameters(0)
    assert cp.is_compress() is False
    assert cp.is_disabled() is True


def test_object_stream_size_one_still_enables_compression() -> None:
    """Boundary case — a single-object stream is technically wasteful
    but still counts as compression on."""
    cp = CompressParameters(1)
    assert cp.is_compress() is True
    assert cp.is_disabled() is False


# ---------- input validation ----------------------------------------------


def test_negative_object_stream_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative value"):
        CompressParameters(-1)


def test_non_int_object_stream_size_is_rejected() -> None:
    with pytest.raises(TypeError):
        CompressParameters(1.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CompressParameters("10")  # type: ignore[arg-type]


# ---------- with_object_stream_size: immutable update --------------------


def test_with_object_stream_size_returns_new_instance() -> None:
    """The value type is conceptually immutable; ``with_object_stream_size``
    returns a fresh instance for a different size."""
    base = CompressParameters(100)
    updated = base.with_object_stream_size(50)
    assert updated is not base
    assert updated.get_object_stream_size() == 50
    # Original untouched.
    assert base.get_object_stream_size() == 100


def test_with_object_stream_size_returns_self_for_same_size() -> None:
    """Sweet spot: no allocation when the size matches."""
    base = CompressParameters(42)
    same = base.with_object_stream_size(42)
    assert same is base


# ---------- value-type semantics ------------------------------------------


def test_equal_instances_compare_and_hash_equal() -> None:
    a = CompressParameters(100)
    b = CompressParameters(100)
    assert a == b
    assert hash(a) == hash(b)


def test_different_sizes_compare_unequal() -> None:
    a = CompressParameters(50)
    b = CompressParameters(100)
    assert a != b


def test_equality_does_not_match_other_types() -> None:
    cp = CompressParameters(50)
    assert (cp == 50) is False
    assert (cp == "50") is False
    assert (cp == None) is False  # noqa: E711 — explicit identity-aware compare


def test_repr_contains_object_stream_size() -> None:
    cp = CompressParameters(77)
    text = repr(cp)
    assert "77" in text
    assert "CompressParameters" in text


def test_set_membership_uses_value_equality() -> None:
    """The value-type ``__hash__`` lets two structurally identical
    instances collapse to one entry in a set."""
    members = {CompressParameters(50), CompressParameters(50)}
    assert len(members) == 1


# ---------- bool accepted as int (Python ``bool`` subclasses ``int``) -----


def test_bool_object_stream_size_treated_as_int() -> None:
    """Upstream uses primitive ``int`` so ``true``/``false`` widen to
    1/0. Python's ``bool`` is an ``int`` subclass; the constructor
    accepts it as the numeric value (1 → compress, 0 → no-compress)."""
    cp_true = CompressParameters(True)  # type: ignore[arg-type]
    assert cp_true.get_object_stream_size() == 1
    assert cp_true.is_compress() is True
    cp_false = CompressParameters(False)  # type: ignore[arg-type]
    assert cp_false.get_object_stream_size() == 0
    assert cp_false.is_disabled() is True
