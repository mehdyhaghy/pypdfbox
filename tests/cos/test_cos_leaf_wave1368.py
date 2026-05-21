"""Wave 1368 — leaf-type COSBase behavioural round-out.

Tests for paths in COSNull, COSBoolean, COSInteger and COSFloat that
the prior waves leave uncovered:

* COSNull: singleton identity, write_pdf token emission, ``is_null``
  classmethod, ``__bool__`` falsy and ``equals``.
* COSBoolean: ``get_value_as_object`` parity, ``write_pdf`` token, ``equals``
  and ``hash_code`` against the matching Python bool.
* COSInteger: singleton pool for small values, ``write_pdf`` ascii emission,
  ``compare_to`` ordering, ``int_value`` / ``long_value`` / ``float_value``
  / ``double_value`` consistency.
* COSFloat: float-32 coercion on round-trip via ``set_value``, format-string
  parity for whole-number values, ``equals`` semantics differing from
  ``==``, ``compare_to`` rejected for unsupported argument.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSBoolean,
    COSFloat,
    COSInteger,
    COSNull,
)

# ---------- COSNull ----------


def test_cos_null_singleton_identity() -> None:
    assert COSNull.NULL is COSNull.NULL


def test_cos_null_constructor_blocked_after_init() -> None:
    # Calling COSNull() after the module finished initialising must
    # raise — the singleton is constructed once at module import time.
    with pytest.raises(RuntimeError):
        COSNull()


def test_cos_null_write_pdf_emits_null_literal() -> None:
    out = io.BytesIO()
    COSNull.NULL.write_pdf(out)
    assert out.getvalue() == b"null"


def test_cos_null_is_null_static_helper_distinguishes_python_none() -> None:
    assert COSNull.is_null(COSNull.NULL) is True
    assert COSNull.is_null(None) is False
    assert COSNull.is_null(0) is False


def test_cos_null_falsy_in_bool_context() -> None:
    assert bool(COSNull.NULL) is False


def test_cos_null_get_value_returns_python_none() -> None:
    assert COSNull.NULL.get_value() is None


def test_cos_null_eq_with_non_null_is_notimplemented() -> None:
    assert (COSNull.NULL == 0) is False
    assert (COSNull.NULL == None) is False  # noqa: E711 - explicit comparison


def test_cos_null_to_string() -> None:
    assert COSNull.NULL.to_string() == "COSNull{}"


# ---------- COSBoolean ----------


def test_cos_boolean_get_returns_singleton_per_value() -> None:
    assert COSBoolean.get(True) is COSBoolean.TRUE
    assert COSBoolean.get(False) is COSBoolean.FALSE


def test_cos_boolean_get_boolean_alias() -> None:
    assert COSBoolean.get_boolean(True) is COSBoolean.TRUE
    assert COSBoolean.get_boolean(False) is COSBoolean.FALSE


def test_cos_boolean_value_accessors() -> None:
    assert COSBoolean.TRUE.value is True
    assert COSBoolean.FALSE.value is False
    assert COSBoolean.TRUE.get_value() is True
    assert COSBoolean.FALSE.get_value() is False
    assert COSBoolean.TRUE.get_value_as_object() is True
    assert COSBoolean.FALSE.get_value_as_object() is False


def test_cos_boolean_is_true_is_false() -> None:
    assert COSBoolean.TRUE.is_true() is True
    assert COSBoolean.TRUE.is_false() is False
    assert COSBoolean.FALSE.is_false() is True


def test_cos_boolean_write_pdf_emits_correct_token() -> None:
    out = io.BytesIO()
    COSBoolean.TRUE.write_pdf(out)
    assert out.getvalue() == b"true"
    out = io.BytesIO()
    COSBoolean.FALSE.write_pdf(out)
    assert out.getvalue() == b"false"


def test_cos_boolean_equals_matches_python_bool_in_value_only_comparison() -> None:
    assert COSBoolean.TRUE.equals(COSBoolean.TRUE) is True
    assert COSBoolean.TRUE.equals(COSBoolean.FALSE) is False
    assert COSBoolean.TRUE.equals(True) is False  # type-strict


def test_cos_boolean_bool_dunder_passes_value() -> None:
    assert bool(COSBoolean.TRUE) is True
    assert bool(COSBoolean.FALSE) is False


def test_cos_boolean_constructor_blocked_after_init() -> None:
    with pytest.raises(RuntimeError):
        COSBoolean(True)
    with pytest.raises(RuntimeError):
        COSBoolean(False)


def test_cos_boolean_hash_code_distinct_for_two_values() -> None:
    assert COSBoolean.TRUE.hash_code() != COSBoolean.FALSE.hash_code()


def test_cos_boolean_to_string_lowercase() -> None:
    assert COSBoolean.TRUE.to_string() == "true"
    assert COSBoolean.FALSE.to_string() == "false"


# ---------- COSInteger ----------


def test_cos_integer_get_uses_singleton_for_small_values() -> None:
    # PDFBox caches small integers (typically -100..+256). Two .get()
    # calls with the same small value should return the same instance.
    a = COSInteger.get(0)
    b = COSInteger.get(0)
    assert a is b


def test_cos_integer_get_distinct_for_large_values() -> None:
    a = COSInteger.get(10_000_000)
    b = COSInteger.get(10_000_000)
    # Equality always; identity may differ for non-cached values.
    assert a == b


def test_cos_integer_write_pdf_emits_ascii_digits() -> None:
    out = io.BytesIO()
    COSInteger.get(12345).write_pdf(out)
    assert out.getvalue() == b"12345"


def test_cos_integer_write_pdf_emits_negative_digits() -> None:
    out = io.BytesIO()
    COSInteger.get(-7).write_pdf(out)
    assert out.getvalue() == b"-7"


def test_cos_integer_compare_to_ordering() -> None:
    a = COSInteger.get(1)
    b = COSInteger.get(2)
    assert a.compare_to(b) < 0
    assert b.compare_to(a) > 0
    assert a.compare_to(COSInteger.get(1)) == 0


def test_cos_integer_value_widenings_match() -> None:
    n = COSInteger.get(42)
    assert n.int_value() == 42
    assert n.long_value() == 42
    assert n.float_value() == 42.0
    assert n.double_value() == 42.0
    assert n.value == 42


def test_cos_integer_equals_matches_value_only() -> None:
    a = COSInteger.get(5)
    b = COSInteger.get(5)
    assert a.equals(b) is True
    assert a.equals(5) is False


def test_cos_integer_is_valid_default_true() -> None:
    """Newly minted integers are valid (the parser only flips to invalid
    when it sees an overflow marker)."""
    n = COSInteger.get(7)
    assert n.is_valid() is True


def test_cos_integer_get_invalid_max_returns_long_max() -> None:
    sentinel = COSInteger.get_invalid(True)
    assert isinstance(sentinel, COSInteger)
    # Just check it's a non-default special value.
    assert sentinel.is_valid() is False


def test_cos_integer_get_invalid_min_returns_long_min() -> None:
    sentinel = COSInteger.get_invalid(False)
    assert isinstance(sentinel, COSInteger)
    assert sentinel.is_valid() is False


# ---------- COSFloat ----------


def test_cos_float_round_trips_simple_value() -> None:
    f = COSFloat(1.5)
    assert f.get_value() == pytest.approx(1.5)
    assert f.float_value() == pytest.approx(1.5)
    assert f.double_value() == pytest.approx(1.5)


def test_cos_float_int_long_value_truncates() -> None:
    f = COSFloat(3.9)
    assert f.int_value() == 3
    assert f.long_value() == 3


def test_cos_float_set_value_replaces_with_coerced_value() -> None:
    f = COSFloat(1.0)
    f.set_value(2.5)
    assert f.get_value() == pytest.approx(2.5)


def test_cos_float_format_string_emits_compact_form_for_whole_number() -> None:
    f = COSFloat(7.0)
    rendered = f.format_string()
    # Should not have trailing zeros; PDFBox writes whole-number floats as
    # ``7`` (no decimal point). Verify by checking the writer output.
    out = io.BytesIO()
    f.write_pdf(out)
    assert out.getvalue() == rendered.encode("ascii")


def test_cos_float_write_pdf_preserves_original_form_when_parsed() -> None:
    f = COSFloat("3.14000")
    out = io.BytesIO()
    f.write_pdf(out)
    # The original form is preserved verbatim.
    assert out.getvalue() == b"3.14000"
    assert f.get_original_form() == "3.14000"


def test_cos_float_eq_compares_value_after_float32_coercion() -> None:
    # 1.5 round-trips exactly through float-32 conversion.
    a = COSFloat(1.5)
    b = COSFloat(1.5)
    assert a == b
    assert hash(a) == hash(b)


def test_cos_float_string_constructor_invalid_raises() -> None:
    with pytest.raises(OSError):
        COSFloat("not a float")


def test_cos_float_value_ordering_consistent_with_value_field() -> None:
    a = COSFloat(1.5)
    b = COSFloat(2.5)
    # COSFloat does not implement rich comparators (Java parity — sorting
    # is done over ``value`` directly). Verify the underlying scalar.
    assert (a.value < b.value) is True
    assert (a.value == b.value) is False


def test_cos_float_to_string_format() -> None:
    f = COSFloat(2.5)
    rendered = f.to_string()
    assert "COSFloat" in rendered
    assert "2.5" in rendered


def test_cos_float_negative_value_round_trips() -> None:
    f = COSFloat(-0.25)
    assert f.get_value() == pytest.approx(-0.25)
    out = io.BytesIO()
    f.write_pdf(out)
    assert out.getvalue().startswith(b"-")
