from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSInteger, COSNull

# ---------------------------------------------------------------------------
# COSNull — singleton helpers + falsy semantics + write_pdf round-trip.
# ---------------------------------------------------------------------------


def test_cos_null_is_null_static_helper() -> None:
    assert COSNull.is_null(COSNull.NULL) is True
    # Plain Python values — including ``None`` and ``0`` — are NOT COSNull.
    # The COS layer treats ``COSNull`` as a real PDF object, so the helper
    # only matches the canonical singleton.
    assert COSNull.is_null(0) is False
    assert COSNull.is_null(None) is False
    assert COSNull.is_null("null") is False
    assert COSNull.is_null(False) is False


def test_cos_null_bool_protocol_is_false() -> None:
    assert bool(COSNull.NULL) is False
    # And usable directly in conditionals.
    assert not COSNull.NULL


def test_cos_null_get_value_returns_python_none() -> None:
    assert COSNull.NULL.get_value() is None


def test_cos_null_equality_among_instances() -> None:
    # Singleton: every reference is the same instance, but equality and hash
    # also agree so the pair behaves correctly in sets / dict keys.
    assert COSNull.NULL == COSNull.NULL
    assert hash(COSNull.NULL) == hash(COSNull.NULL)
    # Python None is NOT equal to COSNull (they are distinct concepts).
    assert (COSNull.NULL == None) is False  # noqa: E711 — testing __eq__


def test_cos_null_write_pdf_emits_null_token() -> None:
    buf = io.BytesIO()
    COSNull.NULL.write_pdf(buf)
    assert buf.getvalue() == b"null"


# ---------------------------------------------------------------------------
# COSInteger — value-accessor parity + Java-style equals / compare_to.
# ---------------------------------------------------------------------------


def test_cos_integer_float_and_double_value_consistent() -> None:
    i = COSInteger(42)
    assert i.float_value() == 42.0
    assert i.double_value() == 42.0
    # Both accessors agree with each other and with ``int_value``.
    assert i.float_value() == i.double_value() == float(i.int_value())
    assert isinstance(i.float_value(), float)
    assert isinstance(i.double_value(), float)


def test_cos_integer_get_value_alias() -> None:
    assert COSInteger(7).get_value() == 7
    assert COSInteger(-3).get_value() == -3


def test_cos_integer_is_valid_set_valid_round_trip() -> None:
    i = COSInteger(7)
    assert i.get_value() == 7
    assert i.is_valid() is True
    i.set_valid(False)
    assert i.is_valid() is False
    i.set_valid(True)
    assert i.is_valid() is True


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (1, 2, -1),
        (5, 5, 0),
        (10, 4, 1),
        (-1, 0, -1),
        (0, 0, 0),
        (2**60, 2**60 - 1, 1),
    ],
)
def test_cos_integer_compare_to_behaves_like_cmp(a: int, b: int, expected: int) -> None:
    assert COSInteger(a).compare_to(COSInteger(b)) == expected


def test_cos_integer_compare_to_rejects_non_cos_integer() -> None:
    with pytest.raises(TypeError):
        COSInteger(1).compare_to(2)  # type: ignore[arg-type]


def test_cos_integer_equals_value_equality() -> None:
    assert COSInteger(7).equals(COSInteger(7)) is True
    # Even for values outside the small-int cache (different instances).
    assert COSInteger(2**40).equals(COSInteger(2**40)) is True
    # Different value → False.
    assert COSInteger(7).equals(COSInteger(8)) is False
    # Non-COSInteger values → False (mirrors Java equals contract).
    assert COSInteger(7).equals(7) is False
    assert COSInteger(7).equals(None) is False
