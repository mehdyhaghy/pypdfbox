"""Live PDFBox differential parity (wave 1528) for ``COSWriter``'s per-object
serialization — the ``visitFromXxx`` dispatch that turns a single COS object
into its on-the-wire bytes.

This complements the existing scalar / composite / escape write oracles
(``test_write_scalar_oracle``, ``test_cos_composite_write_oracle``,
``test_cos_string_write_oracle``, ``test_cos_escape_oracle``) by sweeping a
*deeper* fuzz battery of:

* **COSInteger** — zero, ±small, ±256 boundary, the signed 32/64-bit extremes.
* **COSFloat** — built from a raw ``float`` (no original-text shortcut), covering
  ±0.0, the ``1e-3`` / ``1e7`` ``Float.toString`` scientific-notation boundaries,
  exact powers of ten, ``Float.MAX_VALUE``, the smallest subnormal
  ``Float.MIN_VALUE`` (``1.4E-45``), and a few full-mantissa values — plus the
  original-text round-trip path (``--16.33`` repair, ``3.``, ``.5``, ``00.50``).
* **COSBoolean / COSNull** keyword bytes.
* **COSString** literal-vs-hex selection through ``visit_from_string``.
* **COSArray / COSDictionary** framing — empty, nested, the every-10th-element
  EOL, the direct-array-inline vs indirect-dict-reference routing, ``null``-valued
  dict entries skipped, escaped name keys.
* **COSStream** — empty, ASCII, binary, and extra-dict bodies. This is the
  surface the wave-1528 real bug lives on: upstream's ``COSStream`` constructor
  seeds ``/Length`` as the FIRST dictionary entry and the parser updates that
  seeded entry in place, so a serialized stream dict is always
  ``<< /Length N ... >>``. pypdfbox's ``COSStream`` carries no ``/Length`` until
  the body is committed (the absent state is load-bearing — length queries return
  ``-1``), so ``COSWriter.visit_from_stream`` now hoists ``/Length`` to the front
  at serialization time to match upstream byte-for-byte.

The oracle is ``oracle/probes/CosWriterObjectFuzzProbe.java`` (PDFBox 3.0.7).
Each probe line is ``<tag> <id>: <output-hex>``; the Python side rebuilds the
same object and asserts its own ``COSWriter`` visit method emits identical bytes.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text


def _render(visit) -> str:
    sink = io.BytesIO()
    writer = COSWriter(sink)
    visit(writer)
    writer.get_standard_output().flush()
    return sink.getvalue().hex()


def _ci(value: int) -> COSInteger:
    return COSInteger.get(value)


def _array_of(*items: object) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _make_stream(body: bytes, extra: list[tuple[str, object]] | None = None) -> COSStream:
    stream = COSStream()
    if extra:
        for key, value in extra:
            stream.set_item(COSName.get_pdf_name(key), value)
    with stream.create_raw_output_stream() as out:
        out.write(body)
    return stream


def _cos_string(hex_bytes: str, force_hex: bool = False) -> COSString:
    s = COSString(bytes.fromhex(hex_bytes))
    if force_hex:
        s.set_force_hex_form(True)
    return s


# ---------------------------------------------------------------------------
# pypdfbox builders keyed by the EXACT ``<tag> <id>`` the Java probe prints.
# ---------------------------------------------------------------------------

_INT_CASES = {
    "i0": 0,
    "i1": 1,
    "ineg1": -1,
    "i7": 7,
    "ineg7": -7,
    "i255": 255,
    "i256": 256,
    "ineg256": -256,
    "i1m": 1000000,
    "imax32": 2147483647,
    "imin32": -2147483648,
    "imax64": 9223372036854775807,
    "imin64": -9223372036854775808,
}

_FLOAT_CASES = {
    "f0": 0.0,
    "fneg0": -0.0,
    "f1": 1.0,
    "fneg1": -1.0,
    "fhalf": 0.5,
    "fneghalf": -0.5,
    "fpt1": 0.1,
    "f100": 100.0,
    "fpi": 3.14159,
    "f1234p5": 1234.5,
    "f1e7": 1e7,
    "f9999999": 9999999.0,
    "f1em3": 1e-3,
    "f1em4": 1e-4,
    "f1e8": 1e8,
    "f1e20": 1e20,
    "f1em20": 1e-20,
    "f1e38": 1e38,
    "fmax": 3.4028235e38,
    "fmin_sub": 1.4e-45,
    "f123456p78": 123456.78,
    "fneg0p001": -0.001,
    "f42": 42.0,
    "f1em45": 1e-45,
}

_FLOAT_STR_CASES = [
    "0.0",
    "1.5",
    "-2.500",
    "0.10",
    "00.50",
    "3.",
    ".5",
    "1e3",
    "1.0E-2",
    "--16.33",
    "0.-262",
    "-16.-33",
    "42",
    "100000000",
]

_NAME_CASES = {
    "54797065": "Type",
    "": "",
    "412042": "A B",
    "314c656164696e67": "1Leading",
}

_STRING_CASES = {
    "str_empty ": ("", False),
    "str_hello 48656c6c6f": ("48656c6c6f", False),
    "str_parens 286129": ("286129", False),
    "str_back 5c": ("5c", False),
    "str_high ff00": ("ff00", False),
    "str_eol 0d0a": ("0d0a", False),
    "str_forcehex 4142": ("4142", True),
}


def _build(tag: str) -> str:  # noqa: C901 — flat dispatch over the probe battery.
    if tag == "bool_true ":
        return _render(lambda w: w.visit_from_boolean(COSBoolean.TRUE))
    if tag == "bool_false ":
        return _render(lambda w: w.visit_from_boolean(COSBoolean.FALSE))
    if tag == "null ":
        return _render(lambda w: w.visit_from_null(COSNull.NULL))

    if tag.startswith("int_"):
        key = tag.split(" ", 1)[0][len("int_") :]
        value = _INT_CASES[key]
        return _render(lambda w: w.visit_from_integer(_ci(value)))

    if tag.startswith("float_"):
        key = tag.split(" ", 1)[0][len("float_") :]
        value = _FLOAT_CASES[key]
        return _render(lambda w: w.visit_from_float(COSFloat(value)))

    if tag.startswith("fstr "):
        text = tag[len("fstr ") :]
        return _render(lambda w: w.visit_from_float(COSFloat(text)))

    if tag.startswith("name "):
        name_hex = tag[len("name ") :]
        name_text = _NAME_CASES[name_hex]
        return _render(lambda w: w.visit_from_name(COSName.get_pdf_name(name_text)))

    if tag.startswith("str_"):
        hex_bytes, force_hex = _STRING_CASES[tag]
        return _render(lambda w: w.visit_from_string(_cos_string(hex_bytes, force_hex)))

    return _build_container(tag)


def _build_container(tag: str) -> str:  # noqa: C901 — flat dispatch.
    if tag == "arr_empty ":
        return _render(lambda w: w.visit_from_array(COSArray()))
    if tag == "arr_ints ":
        return _render(lambda w: w.visit_from_array(_array_of(_ci(1), _ci(2), _ci(3))))
    if tag == "arr_mixed ":
        arr = _array_of(
            _ci(0),
            COSBoolean.TRUE,
            COSNull.NULL,
            COSFloat(1.5),
            COSString(b"x"),
            COSName.get_pdf_name("K"),
        )
        return _render(lambda w: w.visit_from_array(arr))
    if tag == "arr_ten ":
        arr = _array_of(*[_ci(i) for i in range(10)])
        return _render(lambda w: w.visit_from_array(arr))
    if tag == "arr_twelve ":
        arr = _array_of(*[_ci(i) for i in range(12)])
        return _render(lambda w: w.visit_from_array(arr))
    if tag == "arr_nested ":
        inner = _array_of(_ci(1), _ci(2))
        arr = _array_of(_ci(0), inner, _ci(3))
        return _render(lambda w: w.visit_from_array(arr))
    if tag == "arr_with_dict ":
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("A"), _ci(1))
        arr = _array_of(d, _ci(9))
        return _render(lambda w: w.visit_from_array(arr))
    if tag == "arr_null ":
        return _render(lambda w: w.visit_from_array(_array_of(COSNull.NULL)))

    if tag == "dict_empty ":
        return _render(lambda w: w.visit_from_dictionary(COSDictionary()))
    if tag == "dict_one ":
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page"))
        return _render(lambda w: w.visit_from_dictionary(d))
    if tag == "dict_multi ":
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("A"), _ci(1))
        d.set_item(COSName.get_pdf_name("B"), COSFloat(2.5))
        d.set_item(COSName.get_pdf_name("C"), COSBoolean.FALSE)
        d.set_item(COSName.get_pdf_name("D"), COSString(b"v"))
        return _render(lambda w: w.visit_from_dictionary(d))
    if tag == "dict_null_val ":
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("Keep"), _ci(1))
        d.set_item(COSName.get_pdf_name("Drop"), None)
        d.set_item(COSName.get_pdf_name("Also"), _ci(2))
        return _render(lambda w: w.visit_from_dictionary(d))
    if tag == "dict_nested ":
        inner = COSDictionary()
        inner.set_item(COSName.get_pdf_name("X"), _ci(1))
        outer = COSDictionary()
        outer.set_item(COSName.get_pdf_name("Sub"), inner)
        return _render(lambda w: w.visit_from_dictionary(outer))
    if tag == "dict_arr_val ":
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("L"), _array_of(_ci(1), _ci(2)))
        return _render(lambda w: w.visit_from_dictionary(d))
    if tag == "dict_esc_key ":
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("A B"), _ci(1))
        return _render(lambda w: w.visit_from_dictionary(d))

    if tag == "stream_empty ":
        return _render(lambda w: w.visit_from_stream(_make_stream(b"")))
    if tag == "stream_abc ":
        return _render(lambda w: w.visit_from_stream(_make_stream(b"ABC")))
    if tag == "stream_with_dict ":
        stream = _make_stream(
            b"hello world", [("Type", COSName.get_pdf_name("X"))]
        )
        return _render(lambda w: w.visit_from_stream(stream))
    if tag == "stream_binary ":
        stream = _make_stream(bytes([0, 1, 0xFF, 10, 13]))
        return _render(lambda w: w.visit_from_stream(stream))

    raise AssertionError(f"no pypdfbox builder for probe tag {tag!r}")


# ---------------------------------------------------------------------------
# Parse the probe battery once per session; each line becomes a parametrize id.
# ---------------------------------------------------------------------------


def _load_battery() -> list[tuple[str, str]]:
    text = run_probe_text("CosWriterObjectFuzzProbe")
    cases: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        tag, _, out_hex = line.partition(": ")
        cases.append((tag, out_hex))
    return cases


def _battery() -> list[tuple[str, str]]:
    try:
        return _load_battery()
    except Exception:  # noqa: BLE001 — oracle unavailable; requires_oracle skips.
        return []


_BATTERY = _battery()


def _short_id(tag: str) -> str:
    """A short, env-var-safe parametrize id (no large bytes blobs)."""
    return tag.strip().replace(" ", "_") or "blank"


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "out_hex"),
    _BATTERY,
    ids=[_short_id(tag) for tag, _ in _BATTERY],
)
def test_cos_writer_object_matches_pdfbox(tag: str, out_hex: str) -> None:
    """Every per-object serialization case is byte-identical to PDFBox 3.0.7."""
    assert _build(tag) == out_hex


# ---------------------------------------------------------------------------
# Value-pinned assertions (run even without the oracle) so the contract stays
# enforced on machines without Java — these pin the wave-1528 fix in particular.
# ---------------------------------------------------------------------------


def test_stream_length_is_first_dict_entry() -> None:
    """The wave-1528 fix: ``/Length`` leads the stream dict even when other
    entries were inserted first (upstream constructor-seed invariant)."""
    stream = _make_stream(
        b"hello world", [("Type", COSName.get_pdf_name("X"))]
    )
    out = _render(lambda w: w.visit_from_stream(stream)).encode("ascii")
    assert bytes.fromhex(out.decode("ascii")).startswith(
        b"<<\n/Length 11\n/Type /X\n>>\n"
    )


def test_empty_stream_framing() -> None:
    out = bytes.fromhex(_render(lambda w: w.visit_from_stream(_make_stream(b""))))
    assert out == b"<<\n/Length 0\n>>\nstream\r\n\r\nendstream\n"


def test_boolean_and_null_keywords() -> None:
    assert bytes.fromhex(_render(lambda w: w.visit_from_boolean(COSBoolean.TRUE))) == b"true"
    assert bytes.fromhex(_render(lambda w: w.visit_from_boolean(COSBoolean.FALSE))) == b"false"
    assert bytes.fromhex(_render(lambda w: w.visit_from_null(COSNull.NULL))) == b"null"


def test_signed_integer_extremes() -> None:
    imin = _render(lambda w: w.visit_from_integer(_ci(-2147483648)))
    assert bytes.fromhex(imin) == b"-2147483648"
    imax64 = _render(lambda w: w.visit_from_integer(_ci(9223372036854775807)))
    assert bytes.fromhex(imax64) == b"9223372036854775807"


def test_float_scientific_boundary_expands_to_plain() -> None:
    # 1e-4 < 1e-3 -> Float.toString uses E form -> COSFloat strips it to plain.
    assert bytes.fromhex(_render(lambda w: w.visit_from_float(COSFloat(1e-4)))) == b"0.0001"
    # 1e7 is at the scientific boundary -> plain "10000000".
    assert bytes.fromhex(_render(lambda w: w.visit_from_float(COSFloat(1e7)))) == b"10000000"


def test_float_original_text_round_trips() -> None:
    assert bytes.fromhex(_render(lambda w: w.visit_from_float(COSFloat("00.50")))) == b"00.50"
    assert bytes.fromhex(_render(lambda w: w.visit_from_float(COSFloat(".5")))) == b".5"
