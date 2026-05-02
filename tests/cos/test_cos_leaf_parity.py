from __future__ import annotations

import io
import struct

from pypdfbox.cos import COSBoolean, COSFloat, COSInteger, COSName, COSString
from pypdfbox.cos.cos_number import COSNumber


# ---------------------------------------------------------------------------
# COSBoolean — get_value / is_true / is_false / __bool__ round-trip
# ---------------------------------------------------------------------------


def test_boolean_get_value_round_trip() -> None:
    assert COSBoolean.TRUE.get_value() is True
    assert COSBoolean.FALSE.get_value() is False


def test_boolean_is_true_is_false() -> None:
    assert COSBoolean.TRUE.is_true() is True
    assert COSBoolean.TRUE.is_false() is False
    assert COSBoolean.FALSE.is_true() is False
    assert COSBoolean.FALSE.is_false() is True


def test_boolean_bool_protocol_round_trip() -> None:
    assert bool(COSBoolean.TRUE) is True
    assert bool(COSBoolean.FALSE) is False


def test_boolean_get_boolean_factory() -> None:
    assert COSBoolean.get_boolean(True) is COSBoolean.TRUE
    assert COSBoolean.get_boolean(False) is COSBoolean.FALSE
    # And consistent with the value-based predicates
    assert COSBoolean.get_boolean(True).is_true()
    assert COSBoolean.get_boolean(False).is_false()


# ---------------------------------------------------------------------------
# COSName — KIDS / FIRST_CHAR / LAST_CHAR / WIDTHS resolve to interned
# COSName instances with the expected upstream string.
# ---------------------------------------------------------------------------


def test_cos_name_constants_resolve() -> None:
    cases = [
        (COSName.KIDS, "Kids"),
        (COSName.FIRST_CHAR, "FirstChar"),
        (COSName.LAST_CHAR, "LastChar"),
        (COSName.WIDTHS, "Widths"),
    ]
    for constant, expected in cases:
        assert isinstance(constant, COSName)
        assert constant.get_name() == expected
        assert constant.name == expected
        # Interned: re-fetch returns the exact same instance.
        assert COSName.get_pdf_name(expected) is constant


# ---------------------------------------------------------------------------
# COSFloat — int_value / long_value / float_value / double_value /
# get_value all consistent.
# ---------------------------------------------------------------------------


def test_cos_float_value_accessors_consistent() -> None:
    f = COSFloat(3.5)
    assert f.float_value() == 3.5
    assert f.double_value() == 3.5
    assert f.get_value() == 3.5
    assert f.value == 3.5
    assert f.int_value() == 3
    assert f.long_value() == 3
    # All numeric accessors agree with each other.
    assert f.float_value() == f.double_value() == f.get_value() == f.value
    assert f.int_value() == f.long_value() == int(f.value)


def test_cos_float_value_accessors_negative_truncates_toward_zero() -> None:
    f = COSFloat(-2.75)
    assert f.float_value() == -2.75
    assert f.double_value() == -2.75
    assert f.get_value() == -2.75
    # Python int() truncates toward zero, mirroring Java (int)/(long) cast.
    assert f.int_value() == -2
    assert f.long_value() == -2


# ---------------------------------------------------------------------------
# COSFloat — set_value clamps to single (32-bit IEEE-754) precision.
# ---------------------------------------------------------------------------


def _to_float32(x: float) -> float:
    return float(struct.unpack(">f", struct.pack(">f", x))[0])


def test_cos_float_set_value_clamps_to_single_precision() -> None:
    f = COSFloat(0.0)
    # 0.1 has no exact float32 representation; setting it must round to
    # the nearest float32 value, not preserve full float64.
    f.set_value(0.1)
    assert f.get_value() == _to_float32(0.1)
    # Sanity: the float32 round-trip of 0.1 is *not* exactly equal to the
    # float64 0.1, otherwise the test would prove nothing.
    assert _to_float32(0.1) != 0.1
    # All accessor methods see the clamped value.
    assert f.float_value() == _to_float32(0.1)
    assert f.double_value() == _to_float32(0.1)
    assert f.value == _to_float32(0.1)


def test_cos_float_set_value_preserves_exact_representable_values() -> None:
    f = COSFloat(0.0)
    # 0.5 is exactly representable in float32, so clamping is a no-op.
    f.set_value(0.5)
    assert f.get_value() == 0.5
    assert f.float_value() == 0.5
    assert f.int_value() == 0
    assert f.long_value() == 0


def test_cos_float_set_value_resets_original_form() -> None:
    f = COSFloat("1.25")
    assert f.get_original_form() == "1.25"
    f.set_value(2.0)
    # Per existing semantics, set_value invalidates the parsed-text form.
    assert f.get_original_form() is None
    assert f.get_value() == 2.0


# ---------------------------------------------------------------------------
# COSBoolean — get_value_as_object alias + write_pdf round-trip parity
# ---------------------------------------------------------------------------


def test_boolean_get_value_as_object_matches_get_value() -> None:
    # Java distinguishes ``boolean`` from ``Boolean``; in Python the values
    # are identical, so the alias must round-trip the same identity.
    assert COSBoolean.TRUE.get_value_as_object() is True
    assert COSBoolean.FALSE.get_value_as_object() is False
    assert COSBoolean.TRUE.get_value_as_object() is COSBoolean.TRUE.get_value()


def test_boolean_write_pdf_emits_keyword_tokens() -> None:
    buf_t = io.BytesIO()
    COSBoolean.TRUE.write_pdf(buf_t)
    assert buf_t.getvalue() == b"true"
    buf_f = io.BytesIO()
    COSBoolean.FALSE.write_pdf(buf_f)
    assert buf_f.getvalue() == b"false"


# ---------------------------------------------------------------------------
# COSInteger — write_pdf decimal round-trip and OUT_OF_RANGE_* singletons.
# ---------------------------------------------------------------------------


def test_cos_integer_write_pdf_writes_decimal_iso_8859_1() -> None:
    # Mirrors PDFBox TestCOSInteger.testWritePDF: walk -1000..3000 step 200.
    for i in range(-1000, 3000, 200):
        buf = io.BytesIO()
        COSInteger.get(i).write_pdf(buf)
        assert buf.getvalue() == str(i).encode("iso-8859-1")


def test_cos_integer_out_of_range_singletons_exist_and_are_invalid() -> None:
    # Sentinels must be COSInteger instances flagged as invalid (PDFBOX-5176).
    assert isinstance(COSInteger.OUT_OF_RANGE_MAX, COSInteger)
    assert isinstance(COSInteger.OUT_OF_RANGE_MIN, COSInteger)
    assert COSInteger.OUT_OF_RANGE_MAX.is_valid() is False
    assert COSInteger.OUT_OF_RANGE_MIN.is_valid() is False
    # Carry the Long.MAX_VALUE / Long.MIN_VALUE payload upstream uses.
    assert COSInteger.OUT_OF_RANGE_MAX.get_value() == 2**63 - 1
    assert COSInteger.OUT_OF_RANGE_MIN.get_value() == -(2**63)


def test_cos_number_get_returns_out_of_range_singletons() -> None:
    # Numbers above Long.MAX_VALUE / below Long.MIN_VALUE must resolve to
    # the canonical sentinel — identity comparison matches PDFBox semantics.
    too_big = str(2**70)
    too_small = "-" + str(2**70)
    assert COSNumber.get(too_big) is COSInteger.OUT_OF_RANGE_MAX
    assert COSNumber.get(too_small) is COSInteger.OUT_OF_RANGE_MIN


# ---------------------------------------------------------------------------
# COSFloat — ZERO/ONE constants + write_pdf round-trip parity.
# ---------------------------------------------------------------------------


def test_cos_float_zero_and_one_constants() -> None:
    assert isinstance(COSFloat.ZERO, COSFloat)
    assert isinstance(COSFloat.ONE, COSFloat)
    assert COSFloat.ZERO.get_value() == 0.0
    assert COSFloat.ONE.get_value() == 1.0
    # Constructed from "0.0" / "1.0" so the original textual form is preserved.
    assert COSFloat.ZERO.get_original_form() == "0.0"
    assert COSFloat.ONE.get_original_form() == "1.0"


def test_cos_float_write_pdf_preserves_original_form() -> None:
    # When constructed from text, write_pdf must round-trip the exact bytes
    # — content streams and incremental save rely on this (PRD §3.5).
    buf = io.BytesIO()
    COSFloat("3.14159").write_pdf(buf)
    assert buf.getvalue() == b"3.14159"


def test_cos_float_format_string_avoids_scientific_notation() -> None:
    # PDFBox's writePDF goes through BigDecimal.toPlainString when the
    # default ``str(float)`` would emit scientific notation.
    f = COSFloat(1e-7)  # repr is "1e-07"
    s = f.format_string()
    assert "e" not in s and "E" not in s


# ---------------------------------------------------------------------------
# COSString — get_ascii + get_force_hex_form snake_case alias.
# ---------------------------------------------------------------------------


def test_cos_string_get_ascii_returns_ascii_decoded_text() -> None:
    # Typical ASCII payload (a PDF date string).
    s = COSString(b"D:20240101120000Z")
    assert s.get_ascii() == "D:20240101120000Z"


def test_cos_string_get_ascii_replaces_non_ascii_bytes() -> None:
    # Java's ``new String(bytes, US_ASCII)`` substitutes ``?`` for high bytes;
    # we mirror that so the API surface stays interchangeable.
    s = COSString(b"caf\xe9")  # 0xE9 = é in latin-1, not ASCII.
    assert s.get_ascii() == "caf?"


def test_cos_string_get_force_hex_form_alias() -> None:
    # ``getForceHexForm`` exists upstream alongside ``isForceHexForm`` —
    # the snake_case spelling is the canonical pypdfbox API.
    s = COSString(b"abc")
    assert s.get_force_hex_form() is False
    s.set_force_hex_form(True)
    assert s.get_force_hex_form() is True
    # Both accessors agree.
    assert s.get_force_hex_form() == s.is_force_hex_form()
