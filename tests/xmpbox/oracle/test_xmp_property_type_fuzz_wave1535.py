"""Live Apache xmpbox differential parity for the simple-property TYPE classes.

Where ``test_xmp_schema_oracle.py`` / ``test_xmp_array_container_oracle.py``
compare what the *parser* builds from a packet, this file reaches the individual
``org.apache.xmpbox.type.*`` value-conversion classes directly: it constructs
``IntegerType`` / ``RealType`` / ``BooleanType`` / ``TextType`` / ``DateType``
with a raw (often malformed) value and compares the outcome against the live
Apache xmpbox 3.0.7 jar via the ``XmpPropertyTypeFuzzProbe`` probe.

The comparison surface is repr-stable: for a value that converts successfully we
compare ``get_string_value()`` (Java ``getStringValue`` — the canonical XML
serialization); for a value the type rejects we compare the *classification*
(both sides raise). We do NOT compare ``repr(get_value())`` because Java boxes
the primitive (``Float``/``Integer``) and renders it via the same
``toString`` while Python's ``get_value`` returns a Python ``float``/``int``
whose ``repr`` shows full double precision — the stored float32 value is
identical (proven by the matching ``get_string_value``), only its ``repr``
differs.

Key parities pinned here (wave 1535):

  * ``IntegerType`` overflows the signed 32-bit range exactly like
    ``Integer.parseInt`` (``2147483648`` / ``99999999999`` -> error), and
    rejects whitespace-padded / float / radix-prefixed strings.
  * ``RealType`` parses the ``Float.parseFloat`` grammar (type suffix ``f``/``d``,
    hex floats, exact-case ``Infinity``/``NaN``; rejects lower-case
    ``inf``/``nan`` and underscores), stores single precision (``1e40`` ->
    ``Infinity``), and renders ``getStringValue`` byte-for-byte like Java
    ``Float.toString`` (``1234567.89`` -> ``1234567.9``).
  * ``BooleanType`` is case-insensitive + whitespace-trimming (``" true "``,
    ``TrUe``) but rejects ``1``/``0``/``yes``.
  * ``TextType`` accepts any string (incl. empty / whitespace).
  * ``DateType`` rejects unparseable strings, stores ``None`` for the
    empty/whitespace string, and rejects a ``None`` raw value.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type.boolean_type import BooleanType
from pypdfbox.xmpbox.type.date_type import DateType
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.real_type import RealType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

_US = chr(0x1F)
_NULL = "__NULL__"

_CLS = {
    "integer": IntegerType,
    "real": RealType,
    "boolean": BooleanType,
    "text": TextType,
    "date": DateType,
}

# (id, type, raw_token). The probe maps "__NULL__" to a Java null; everything
# else is the raw String value. IDs are short ASCII so the Windows 32 KB
# test-id env-var cap is never approached.
_CASES: list[tuple[str, str, str]] = [
    # IntegerType ---------------------------------------------------------
    ("int_plain", "integer", "5"),
    ("int_plus", "integer", "+5"),
    ("int_neg", "integer", "-5"),
    ("int_zero", "integer", "0"),
    ("int_leading_zeros", "integer", "007"),
    ("int_pad_both", "integer", "  5  "),
    ("int_trail_ws", "integer", "5 "),
    ("int_lead_ws", "integer", " 5"),
    ("int_float", "integer", "5.0"),
    ("int_alpha", "integer", "abc"),
    ("int_empty", "integer", ""),
    ("int_exp", "integer", "1e3"),
    ("int_hex", "integer", "0x10"),
    ("int_huge", "integer", "99999999999"),
    ("int_max32", "integer", "2147483647"),
    ("int_over_max32", "integer", "2147483648"),
    ("int_min32", "integer", "-2147483648"),
    ("int_under_min32", "integer", "-2147483649"),
    ("int_double_sign", "integer", "+-5"),
    ("int_underscore", "integer", "5_000"),
    ("int_binary", "integer", "0b10"),
    ("int_null", "integer", _NULL),
    # RealType ------------------------------------------------------------
    ("real_int", "real", "5"),
    ("real_plain", "real", "5.5"),
    ("real_neg", "real", "-3.14"),
    ("real_plus", "real", "+2.5"),
    ("real_exp", "real", "1e3"),
    ("real_exp_neg", "real", "1.5e-2"),
    ("real_pad", "real", "  2.5  "),
    ("real_suffix_f", "real", "2.5f"),
    ("real_suffix_d", "real", "2.5d"),
    ("real_suffix_F", "real", "3.0F"),
    ("real_nan", "real", "NaN"),
    ("real_inf", "real", "Infinity"),
    ("real_neg_inf", "real", "-Infinity"),
    ("real_lower_inf", "real", "inf"),
    ("real_lower_nan", "real", "nan"),
    ("real_alpha", "real", "abc"),
    ("real_empty", "real", ""),
    ("real_hex", "real", "0x1.8p1"),
    ("real_lead_dot", "real", ".5"),
    ("real_trail_dot", "real", "5."),
    ("real_underscore", "real", "1_000.0"),
    ("real_big", "real", "100000000000000000000"),
    ("real_prec", "real", "1234567.89"),
    ("real_near_max", "real", "3.4028235e38"),
    ("real_overflow", "real", "1e40"),
    ("real_null", "real", _NULL),
    # BooleanType ---------------------------------------------------------
    ("bool_True", "boolean", "True"),
    ("bool_False", "boolean", "False"),
    ("bool_lower_true", "boolean", "true"),
    ("bool_lower_false", "boolean", "false"),
    ("bool_upper", "boolean", "TRUE"),
    ("bool_mixed", "boolean", "TrUe"),
    ("bool_padded", "boolean", " true "),
    ("bool_one", "boolean", "1"),
    ("bool_zero", "boolean", "0"),
    ("bool_yes", "boolean", "yes"),
    ("bool_empty", "boolean", ""),
    ("bool_ws", "boolean", "  "),
    ("bool_T", "boolean", "T"),
    ("bool_null", "boolean", _NULL),
    # TextType ------------------------------------------------------------
    ("text_plain", "text", "hello"),
    ("text_empty", "text", ""),
    ("text_ws", "text", "  "),
    ("text_digits", "text", "123"),
    ("text_markup", "text", "<xml>"),
    ("text_null", "text", _NULL),
    # DateType (zone-independent classification surface) ------------------
    ("date_garbage", "date", "garbage"),
    ("date_slash", "date", "2024/06/15"),
    ("date_word", "date", "now"),
    ("date_empty", "date", ""),
    ("date_ws", "date", "  "),
    ("date_iso_z", "date", "2024-06-15T10:30:00Z"),
    ("date_null", "date", _NULL),
]


def _java_outcome(type_name: str, raw: str) -> tuple[str, str | None]:
    """``("OK", get_string_value)`` or ``("ERR", None)`` from the live probe.

    The probe emits ``OK<US>value<US>stringValue`` or ``ERR<US>class``; we keep
    only the classification + the canonical string value (the date probe maps a
    null Calendar to the literal ``"<null>"``).
    """
    fields = run_probe_text("XmpPropertyTypeFuzzProbe", type_name, raw).rstrip("\n").split(_US)
    if fields[0] == "OK":
        return ("OK", fields[2])
    return ("ERR", None)


def _py_outcome(type_name: str, raw: str) -> tuple[str, str | None]:
    meta = XMPMetadata.create_xmp_metadata()
    value = None if raw == _NULL else raw
    try:
        obj = _CLS[type_name](meta, "http://ns.example/", "ex", "p", value)
    except (ValueError, TypeError):
        return ("ERR", None)
    if type_name == "date":
        string_value = obj.get_string_value()
        return ("OK", "<null>" if string_value is None else string_value)
    return ("OK", obj.get_string_value())


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "type_name", "raw"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_property_type_matches_xmpbox(case_id: str, type_name: str, raw: str) -> None:
    java = _java_outcome(type_name, raw)
    py = _py_outcome(type_name, raw)

    # For successful DateType parses the rendered string is the JVM's local zone
    # for partial / zone-less inputs (environment-dependent), so for date OK
    # cases compare only the OK/ERR classification and the null-vs-non-null
    # distinction — the value-vs-error boundary is the parity surface here.
    if type_name == "date" and java[0] == "OK":
        assert py[0] == "OK", f"{case_id}: java OK, py {py}"
        assert (py[1] == "<null>") == (java[1] == "<null>"), (
            f"{case_id}: null-mismatch java={java} py={py}"
        )
        return

    assert py == java, f"property-type divergence for {case_id}: java={java} py={py}"
