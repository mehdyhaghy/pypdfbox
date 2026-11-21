"""PDFBox 3.0.9 function forward-ports (wave 1615).

PDFBOX-6331: type 4 integer ``not`` is a bitwise complement, ``roll`` reduces
``j`` modulo ``n``, and ``eq`` / ``ne`` / ``ge`` / ``gt`` / ``le`` compare in
double precision (``lt`` stays on float32 upstream).
PDFBOX-6320: malformed type 4 programs fail with ``OSError``, never a
low-level Python error.
PDFBOX-6332: a type 3 function with too many ``/Bounds`` is rejected.
PDFBOX-6333: type 0 ``/Encode`` / ``/Decode`` of odd length do not overrun.
"""

import contextlib
import random

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSStream
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionType0, PDFunctionType4
from pypdfbox.pdmodel.common.function.type4.bitwise_operators import Not
from pypdfbox.pdmodel.common.function.type4.execution_context import ExecutionContext
from pypdfbox.pdmodel.common.function.type4.operators import Operators
from pypdfbox.pdmodel.common.function.type4.relational_operators import Eq, Ge, Gt, Le, Lt, Ne
from pypdfbox.pdmodel.common.function.type4.stack_operators import Roll


def _type4(body: str, rng: list[float] | None = None) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    domain = COSArray()
    domain.set_float_array([-10.0, 10.0])
    raw.set_item("Domain", domain)
    if rng is not None:
        range_arr = COSArray()
        range_arr.set_float_array(rng)
        raw.set_item("Range", range_arr)
    raw.set_data(body.encode("ascii"))
    return PDFunctionType4(raw)


def _run(body: str) -> list[float]:
    return _type4(body).eval([])


# ---- PDFBOX-6331 ---------------------------------------------------------


def test_not_on_integers_is_bitwise_complement() -> None:
    assert _run("{ 52 not -37 not 0 not -1 not }") == [-53.0, 36.0, -1.0, 0.0]
    assert _run("{ 2147483647 not }") == [-2147483648.0]


def test_not_on_booleans_unchanged() -> None:
    assert _run("{ true not { 1 } { 0 } ifelse }") == [0.0]


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ("1 2 3 4 5 5 7 roll", [4, 5, 1, 2, 3]),
        ("1 2 3 4 5 5 -7 roll", [3, 4, 5, 1, 2]),
        ("1 2 3 4 5 5 10 roll", [1, 2, 3, 4, 5]),
        ("1 2 3 4 5 5 -10 roll", [1, 2, 3, 4, 5]),
        ("1 2 3 0 5 roll", [1, 2, 3]),
        ("1 2 3 3 1000000 roll", [3, 1, 2]),
    ],
    ids=["j_gt_n", "neg_j_gt_n", "j_multiple", "neg_j_multiple", "n_zero", "huge_j"],
)
def test_roll_reduces_j_modulo_n(program: str, expected: list[int]) -> None:
    assert _run("{ " + program + " }") == [float(v) for v in expected]


def test_roll_shallow_stack_still_underflows() -> None:
    with pytest.raises(OSError):
        _run("{ 1 2 9 1 roll }")


def test_roll_negative_n_rangecheck() -> None:
    with pytest.raises(OSError):
        _run("{ 1 2 -1 1 roll }")


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ("2147483647 2147483646 gt", 1.0),
        ("2147483646 2147483647 ge", 0.0),
        ("2147483647 2147483646 le", 0.0),
        ("16777217 16777216 eq", 0.0),
        ("16777217 16777216 ne", 1.0),
        ("16777217 16777217 eq", 1.0),
        # Upstream ``lt`` still narrows to float32.
        ("16777216 16777217 lt", 0.0),
        ("1 2 lt", 1.0),
    ],
)
def test_comparisons_on_large_integers(program: str, expected: float) -> None:
    assert _run("{ " + program + " { 1 } { 0 } ifelse }") == [expected]


def test_eq_follows_double_compare_signed_zero_and_nan() -> None:
    # Double.compare: 0.0 != -0.0, NaN == NaN.
    assert _run("{ 0.0 -0.0 eq { 1 } { 0 } ifelse }") == [0.0]
    assert _run("{ 0 0 div 0 0 div eq { 1 } { 0 } ifelse }") == [1.0]


def _ctx(*values: object) -> ExecutionContext:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().extend(values)
    return ctx


def test_operator_classes_match_engine() -> None:
    ctx = _ctx(52)
    Not().execute(ctx)
    assert ctx.get_stack() == [-53]

    ctx = _ctx(1, 2, 3, 4, 5, 5, 7)
    Roll().execute(ctx)
    assert ctx.get_stack() == [4, 5, 1, 2, 3]

    ctx = _ctx(1, 2, 3, 0, 5)
    Roll().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3]

    for op, a, b, expected in [
        (Gt(), 2147483647, 2147483646, True),
        (Ge(), 2147483646, 2147483647, False),
        (Le(), 2147483647, 2147483646, False),
        (Eq(), 16777217, 16777216, False),
        (Ne(), 16777217, 16777216, True),
        (Lt(), 16777216, 16777217, False),
    ]:
        ctx = _ctx(a, b)
        op.execute(ctx)
        assert ctx.get_stack() == [expected], op


# ---- PDFBOX-6320 ---------------------------------------------------------


@pytest.mark.parametrize(
    "program",
    [
        "{ add }",
        "{ true 1 add }",
        "{ 5 3 roll }",
        "{ 1 0 div 1 roll }",
        "{ 1 0 div copy }",
        "{ -1 sqrt index }",
        "{ 1.5 2 idiv }",
        "{ true 5 if }",
        "{ 1.5 2 and }",
        "{ 1.0 not }",
    ],
)
def test_malformed_type4_programs_raise_oserror(program: str) -> None:
    with pytest.raises(OSError):
        _type4(program, rng=[-10.0, 10.0]).eval([1.0])


def test_random_type4_programs_never_leak_low_level_errors() -> None:
    ops = [
        "abs", "add", "atan", "ceiling", "cos", "cvi", "cvr", "div", "exp",
        "floor", "idiv", "ln", "log", "mod", "mul", "neg", "round", "sin",
        "sqrt", "sub", "truncate", "and", "bitshift", "eq", "false", "ge", "gt",
        "le", "lt", "ne", "not", "or", "true", "xor", "if", "ifelse", "copy",
        "dup", "exch", "index", "pop", "roll",
    ]  # fmt: skip
    tokens = [*ops, "0", "1", "-1", "2", "3", "1.5", "-2.5", "1e30", "2147483647", "{ 1 }"]
    rng = random.Random(1615)
    for _ in range(3000):
        body = "{ " + " ".join(rng.choice(tokens) for _ in range(rng.randint(1, 8))) + " }"
        # Only OSError may escape; anything else fails the test.
        with contextlib.suppress(OSError):
            _type4(body, rng=[-10.0, 10.0]).eval([1.0])


# ---- PDFBOX-6332 ---------------------------------------------------------


def _type2() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    d.set_item("Domain", domain)
    d.set_int("N", 1)
    return d


def _type3(n_functions: int, bounds: list[float], encode: list[float]) -> PDFunction:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    d.set_item("Domain", domain)
    functions = COSArray()
    for _ in range(n_functions):
        functions.add(_type2())
    d.set_item("Functions", functions)
    bounds_arr = COSArray()
    bounds_arr.set_float_array(bounds)
    d.set_item("Bounds", bounds_arr)
    encode_arr = COSArray()
    encode_arr.set_float_array(encode)
    d.set_item("Encode", encode_arr)
    return PDFunction.create(d)


@pytest.mark.parametrize("x", [0.1, 0.5, 0.9])
def test_type3_too_many_bounds_rejected(x: float) -> None:
    fn = _type3(2, [0.3, 0.6], [0.0, 1.0, 0.0, 1.0])
    with pytest.raises(ValueError, match="2 bounds for 2 functions"):
        fn.eval([x])


def test_type3_matching_bounds_still_evaluates() -> None:
    fn = _type3(2, [0.5], [0.0, 1.0, 0.0, 1.0])
    assert fn.eval([0.25]) == pytest.approx([0.5])


# ---- PDFBOX-6333 ---------------------------------------------------------


def test_type3_odd_encode_length_raises_cleanly() -> None:
    fn = _type3(2, [0.5], [0.0, 1.0, 0.0])
    assert fn.get_encode_for_parameter(1) is None
    with pytest.raises(ValueError, match="Encode"):
        fn.eval([0.9])
    single = _type3(1, [], [0.0])
    assert single.get_encode_for_parameter(0) is None
    with pytest.raises(ValueError, match="Encode"):
        single.eval([0.5])


def _type0(encode: list[float], decode: list[float]) -> PDFunctionType0:
    stream = COSStream()
    stream.set_int("FunctionType", 0)
    for key, values in (("Domain", [0.0, 1.0]), ("Range", [0.0, 1.0])):
        arr = COSArray()
        arr.set_float_array(values)
        stream.set_item(key, arr)
    size = COSArray()
    size.add(COSInteger.get(2))
    stream.set_item("Size", size)
    stream.set_int("BitsPerSample", 8)
    encode_arr = COSArray()
    encode_arr.set_float_array(encode)
    stream.set_item("Encode", encode_arr)
    decode_arr = COSArray()
    decode_arr.set_float_array(decode)
    stream.set_item("Decode", decode_arr)
    stream.set_data(b"\x00\xff")
    return PDFunctionType0(stream)


def test_type0_odd_length_encode_decode_return_none() -> None:
    fn = _type0([0.0], [0.0, 1.0, 0.0])
    assert fn.get_encode_for_parameter(0) is None
    assert fn.get_decode_for_parameter(0) == (0.0, 1.0)
    assert fn.get_decode_for_parameter(1) is None


def test_type0_odd_length_encode_eval_raises_cleanly() -> None:
    with pytest.raises(ValueError, match="Encode"):
        _type0([0.0], [0.0, 1.0]).eval([0.5])


def test_type0_odd_length_decode_eval_raises_cleanly() -> None:
    with pytest.raises(ValueError, match="Decode"):
        _type0([0.0, 1.0], [0.0]).eval([0.5])


def test_type0_well_formed_still_evaluates() -> None:
    assert _type0([0.0, 1.0], [0.0, 1.0]).eval([1.0]) == pytest.approx([1.0])


def test_nan_and_infinite_counts_follow_java_int_value() -> None:
    # Java ``intValue()``: NaN -> 0 (roll is a no-op), +Inf saturates.
    assert _run("{ 7 -1 log 3 roll }") == [7.0]
    assert _run("{ 1 2 2 1 0 div roll }") == [2.0, 1.0]
