"""Live PDFBox differential fuzz parity for the Type 4 PostScript calculator
function — the token-stream lexer/parser and the stack-machine evaluator
(wave 1522, agent A).

Drives ``oracle/probes/FunctionType4FuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* Type 4 specs and asserting each
``CASE`` line matches. This is a DEEPER angle than ``FunctionEvalFuzzProbe``
(which fuzzes the COS-spec construction contract across all function types):
every case here is a Type 4 PostScript program, stressing the calculator
language itself — malformed braces, numeric literal forms, division by zero,
transcendental domain corners, type errors, stack under/overflow, index / roll
/ copy bounds, bitshift / bitwise, 32-bit integer wrap, and /Range clamping.

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR> eval=<ERR | f0 f1 ...>

Semantics:
  - ``create=ERR`` — upstream ``PDFunction.create`` threw (Type 4 parses the
    body eagerly at construction, so a literal-parse fault surfaces here).
  - ``create=ok eval=ERR`` — construction succeeded, ``eval`` threw.
  - ``create=ok eval=<floats>`` — both succeeded.

Real bugs fixed this wave (now matching the jar): bitshift shift-count masking
to 5 bits + 32-bit result wrap; ``abs(Integer.MIN_VALUE)`` staying negative;
``eq`` / ``ne`` treating a boolean-vs-number pair as unequal (Java
``Boolean.equals``, not Python ``True == 1``); ``roll`` raising when ``n``
exceeds the stack depth; a boolean left in a declared /Range output slot
raising (upstream ``(Number) popReal`` ClassCastException) instead of being
coerced to 1.0 / 0.0.

Intentional divergences pinned both sides live in ``_DIVERGENCES``.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-3


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    arr.set_float_array([float(v) for v in vals])
    return arr


def _t4(ps: str, domain: COSArray, rng: COSArray) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", domain)
    s.set_item("Range", rng)
    s.set_data(ps.encode("ascii"))
    return s


# Spec descriptor: (postscript_body, domain_array, range_array, eval_input)
_D01 = (0.0, 1.0)
_R = (-1000.0, 1000.0)


def _e1(ps: str, i: float) -> tuple[str, tuple, tuple, list[float]]:
    return (ps, _D01, _R, [i])


def _e1r2(ps: str, i: float) -> tuple[str, tuple, tuple, list[float]]:
    return (ps, _D01, (-1000.0, 1000.0, -1000.0, 1000.0), [i])


def _e2(ps: str, a: float, b: float) -> tuple[str, tuple, tuple, list[float]]:
    return (ps, (0.0, 1.0, 0.0, 1.0), _R, [a, b])


def _e1r(
    ps: str, i: float, lo: float, hi: float
) -> tuple[str, tuple, tuple, list[float]]:
    return (ps, _D01, (lo, hi), [i])


def _build_cases() -> dict[str, tuple[str, tuple, tuple, list[float]]]:
    """Return {case_name: (ps, domain, range, inputs)} mirroring the probe."""
    return {
        # ---- brace / structural corners ----
        "empty_prog": _e1("{ }", 0.5),
        "empty_no_braces": _e1("", 0.5),
        "just_open": _e1("{", 0.5),
        "just_close": _e1("}", 0.5),
        "double_close": _e1("{ pop 5 } }", 0.5),
        "missing_close": _e1("{ pop 1 2 add", 0.0),
        "trailing_after_close": _e1("{ 1 } 99", 0.0),
        "no_outer_wrapper": _e1("pop 7", 0.5),
        "nested_unbalanced": _e1("{ pop { 1 2 add }", 0.0),
        "stray_open_mid": _e1("{ pop 3 { 4 }", 0.0),
        "whitespace_only": _e1("   \n\t  ", 0.5),
        "comment_only": _e1("% just a comment", 0.5),
        "comment_inline": _e1("{ pop % drop input\n 42 }", 0.5),
        # ---- numeric literal forms ----
        "lit_plus": _e1("{ pop +5 }", 0.5),
        "lit_minus": _e1("{ pop -5 }", 0.5),
        "lit_real": _e1("{ pop 3.14 }", 0.5),
        "lit_real_lead_dot": _e1("{ pop .5 }", 0.5),
        "lit_real_trail_dot": _e1("{ pop 5. }", 0.5),
        "lit_exp": _e1("{ pop 1.5e2 }", 0.5),
        "lit_exp_neg": _e1("{ pop 1.5e-1 }", 0.5),
        "lit_exp_cap": _e1("{ pop 2.0E1 }", 0.5),
        "lit_huge_int": _e1("{ pop 9999999999 }", 0.5),
        "lit_int_max": _e1("{ pop 2147483647 }", 0.5),
        "lit_int_overflow": _e1("{ pop 2147483648 }", 0.5),
        "lit_radix_hex": _e1("{ pop 16#FF }", 0.5),
        "lit_radix_oct": _e1("{ pop 8#17 }", 0.5),
        "lit_neg_zero": _e1("{ pop -0 }", 0.5),
        # ---- unknown / illegal operators ----
        "unknown_op": _e1("{ pop frobnicate }", 0.5),
        "unknown_def": _e1("{ pop /x 5 def }", 0.5),
        "unknown_for": _e1("{ pop 0 1 3 { } for }", 0.5),
        "unknown_forall": _e1("{ pop forall }", 0.5),
        # ---- division / modulo by zero ----
        "div0_pos": _e1("{ pop 1 0 div }", 0.0),
        "div0_neg": _e1("{ pop -1 0 div }", 0.0),
        "div0_zero": _e1("{ pop 0 0 div }", 0.0),
        "idiv0": _e1("{ pop 1 0 idiv }", 0.0),
        "mod0": _e1("{ pop 1 0 mod }", 0.0),
        "idiv_neg": _e1("{ pop -7 2 idiv }", 0.0),
        "idiv_neg_div": _e1("{ pop 7 -2 idiv }", 0.0),
        "mod_neg": _e1("{ pop -7 3 mod }", 0.0),
        "mod_neg_div": _e1("{ pop 7 -3 mod }", 0.0),
        "idiv_real_operand": _e1("{ pop 7.5 2 idiv }", 0.0),
        "div_int_result_idiv": _e1("{ pop 6 2 div 1 idiv }", 0.0),
        # ---- transcendental domain corners ----
        "sqrt_neg": _e1("{ pop -1 sqrt }", 0.0),
        "sqrt_zero": _e1("{ pop 0 sqrt }", 0.0),
        "ln_zero": _e1("{ pop 0 ln }", 0.0),
        "ln_neg": _e1("{ pop -5 ln }", 0.0),
        "log_zero": _e1("{ pop 0 log }", 0.0),
        "log_neg": _e1("{ pop -5 log }", 0.0),
        "exp_neg_base_frac": _e1("{ pop -2 0.5 exp }", 0.0),
        "exp_zero_zero": _e1("{ pop 0 0 exp }", 0.0),
        "exp_big": _e1("{ pop 10 100 exp }", 0.0),
        # ---- atan two-arg ----
        "atan_q1": _e1("{ pop 1 1 atan }", 0.0),
        "atan_q2": _e1("{ pop 1 -1 atan }", 0.0),
        "atan_neg": _e1("{ pop -1 -1 atan }", 0.0),
        "atan_zero_zero": _e1("{ pop 0 0 atan }", 0.0),
        "atan_axis": _e1("{ pop 1 0 atan }", 0.0),
        # ---- truncate / round / floor / ceiling / cvi / cvr ----
        "round_half": _e1("{ pop 2.5 round }", 0.0),
        "round_neg_half": _e1("{ pop -2.5 round }", 0.0),
        "trunc_neg": _e1("{ pop -2.7 truncate }", 0.0),
        "floor_neg": _e1("{ pop -2.3 floor }", 0.0),
        "ceil_neg": _e1("{ pop -2.3 ceiling }", 0.0),
        "cvi_real": _e1("{ pop 7.9 cvi }", 0.0),
        "cvi_neg_real": _e1("{ pop -7.9 cvi }", 0.0),
        "cvr_int": _e1("{ pop 5 cvr }", 0.0),
        "cvi_then_idiv": _e1("{ pop 7.9 cvi 2 idiv }", 0.0),
        # ---- type errors (boolean where number expected) ----
        "add_bool": _e1("{ pop true 1 add }", 0.0),
        "lt_bool": _e1("{ pop true 1 lt }", 0.0),
        "neg_bool": _e1("{ pop true neg }", 0.0),
        "and_int_bool": _e1("{ pop 5 true and }", 0.0),
        "and_float": _e1("{ pop 1.0 2.0 and }", 0.0),
        "not_real": _e1("{ pop 1.5 not }", 0.0),
        "bitshift_real": _e1("{ pop 1.0 2 bitshift }", 0.0),
        # ---- stack underflow ----
        "underflow_add": _e1("{ pop add }", 0.0),
        "underflow_pop": _e1("{ pop pop }", 0.0),
        "underflow_dup": _e1("{ pop pop dup }", 0.0),
        "underflow_exch": _e1("{ pop exch }", 0.0),
        # ---- index / roll / copy ----
        "copy2": _e2("{ 2 copy add add }", 0.3, 0.7),
        "copy0": _e1("{ 0 copy 5 }", 0.5),
        "copy_neg": _e1("{ pop 1 2 -1 copy add }", 0.5),
        "copy_overrange": _e1("{ pop 1 5 copy }", 0.5),
        "index0": _e1("{ pop 1 2 3 0 index }", 0.5),
        "index2": _e1("{ 10 20 30 2 index }", 0.5),
        "index_neg": _e1("{ 10 20 -1 index }", 0.5),
        "index_overrange": _e1("{ 10 20 9 index }", 0.5),
        "index_real": _e1("{ 10 20 30 1.9 index }", 0.5),
        "roll_pos": _e1("{ 1 2 3 3 1 roll add add }", 0.5),
        "roll_neg": _e1("{ 1 2 3 3 -1 roll }", 0.5),
        "roll_zero": _e1("{ 1 2 3 3 0 roll add add }", 0.5),
        "roll_n_neg": _e1("{ 1 2 3 -1 1 roll }", 0.5),
        "roll_j_overflow": _e1("{ 1 2 3 3 7 roll }", 0.5),
        "roll_n_overflow": _e1("{ 1 2 9 1 roll }", 0.5),
        # ---- bitshift / bitwise ----
        "bitshift_left": _e1("{ pop 1 4 bitshift }", 0.5),
        "bitshift_right": _e1("{ pop 256 -2 bitshift }", 0.5),
        "bitshift_big_left": _e1("{ pop 1 40 bitshift }", 0.5),
        "bitshift_neg_val": _e1("{ pop -8 -1 bitshift }", 0.5),
        "and_ints": _e1("{ pop 12 10 and }", 0.5),
        "or_ints": _e1("{ pop 12 10 or }", 0.5),
        "xor_ints": _e1("{ pop 12 10 xor }", 0.5),
        "not_int": _e1("{ pop 5 not }", 0.5),
        "and_bools": _e1("{ pop true false and }", 0.5),
        "xor_bools": _e1("{ pop true false xor }", 0.5),
        # ---- 32-bit integer wrap ----
        "mul_overflow": _e1("{ pop 100000 100000 mul }", 0.5),
        "add_overflow": _e1("{ pop 2147483647 1 add }", 0.5),
        "sub_overflow": _e1("{ pop -2147483648 1 sub }", 0.5),
        "neg_intmin": _e1("{ pop -2147483648 neg }", 0.5),
        "abs_intmin": _e1("{ pop -2147483648 abs }", 0.5),
        # ---- relational / eq / ne ----
        "eq_true": _e1("{ pop 5 5 eq { 1 } { 0 } ifelse }", 0.5),
        "eq_int_float": _e1("{ pop 5 5.0 eq { 1 } { 0 } ifelse }", 0.5),
        "ne_bool": _e1("{ pop true false ne { 1 } { 0 } ifelse }", 0.5),
        "eq_bool_int": _e1("{ pop true 1 eq { 1 } { 0 } ifelse }", 0.5),
        # ---- if / ifelse arity / type ----
        "if_true": _e1("{ pop true { 11 } if }", 0.5),
        "if_false": _e1("{ pop false { 11 } if 22 }", 0.5),
        "if_non_bool": _e1("{ pop 1 { 11 } if }", 0.5),
        "if_no_proc": _e1("{ pop true if }", 0.5),
        "ifelse_true": _e1("{ pop true { 1 } { 2 } ifelse }", 0.5),
        "ifelse_non_bool": _e1("{ pop 5 { 1 } { 2 } ifelse }", 0.5),
        "nested_if": _e1("{ pop 1 { 2 { 3 } if } if }", 0.0),
        "deep_nest": _e1("{ pop { { { 5 } if } if } pop 5 }", 0.0),
        # ---- Range clamping ----
        "clamp_high": _e1r("{ pop 5000 }", 0.5, -10, 10),
        "clamp_low": _e1r("{ pop -5000 }", 0.5, -10, 10),
        "clamp_div0": _e1r("{ pop 1 0 div }", 0.5, -10, 10),
        "clamp_nan": _e1r("{ pop 0 0 div }", 0.5, -10, 10),
        "clamp_ln0": _e1r("{ pop 0 ln }", 0.5, -10, 10),
        "clamp_neg_inf": _e1r("{ pop -1 0 div }", 0.5, -10, 10),
        # ---- multi-output programs ----
        "two_out": _e1r2("{ dup 100 mul exch 200 mul }", 0.5),
        "two_out_surplus": _e1r2("{ 1 2 3 }", 0.5),
        # ---- Domain clamping of input ----
        "dom_clamp_over": _e1("{ 1000 mul }", 5.0),
        "dom_clamp_under": _e1("{ 1000 mul }", -5.0),
    }


# Cases where pypdfbox *intentionally* diverges from the jar (pinned both
# sides). Maps case name -> the pypdfbox-side verdict it must produce. The jar's
# verdict for these is recorded in the comments.
_DIVERGENCES = {
    # Java parses the program body eagerly at construction with
    # ``Integer.parseInt`` and rejects an integer literal that overflows a
    # 32-bit int (``9999999999`` / ``2147483648``) -> NumberFormatException ->
    # create=ERR. pypdfbox uses unbounded Python ints and a lazy parse, so the
    # literal is accepted and pushed verbatim, then clamped to /Range at eval.
    # This is a Python-int-unbounded divergence (documented in CHANGES.md,
    # wave 1522). Jar verdict: create=ERR.
    "lit_huge_int": "create=ok eval=1000.000000",
    "lit_int_overflow": "create=ok eval=1000.000000",
}


def _fmt(value: float) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return f"{value:.6f}"


def _py_verdict(spec: tuple, eval_input: list[float]) -> str:
    ps, domain, rng, _ = spec
    cos = _t4(ps, _floats(*domain), _floats(*rng))
    try:
        fn = PDFunction.create(cos)
    except Exception:  # noqa: BLE001 - mirror the probe's catch-all
        return "create=ERR"
    try:
        out = fn.eval(eval_input)
    except Exception:  # noqa: BLE001
        return "create=ok eval=ERR"
    return "create=ok eval=" + " ".join(_fmt(v) for v in out)


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        name, _, verdict = rest.partition(" ")
        out[name] = verdict
    return out


def _floats_close(a: str, b: str) -> bool:
    fa = a.split()
    fb = b.split()
    if len(fa) != len(fb):
        return False
    for sa, sb in zip(fa, fb, strict=True):
        if sa == sb:
            continue
        try:
            va, vb = float(sa), float(sb)
        except ValueError:
            return False
        if math.isnan(va) and math.isnan(vb):
            continue
        if abs(va - vb) > _TOL:
            return False
    return True


@requires_oracle
def test_function_type4_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text("FunctionType4FuzzProbe"))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, spec in cases.items():
        java = probe[name]
        eval_input = spec[3]
        py = _py_verdict(spec, eval_input)

        if name in _DIVERGENCES:
            expected = _DIVERGENCES[name]
            if py != expected:
                mismatches.append(
                    f"{name}: pypdfbox drifted from pinned divergence "
                    f"py={py!r} expected={expected!r} (java={java!r})"
                )
            continue

        if java.startswith("create=ok eval=") and py.startswith("create=ok eval="):
            jv = java[len("create=ok eval=") :]
            pv = py[len("create=ok eval=") :]
            if jv == "ERR" or pv == "ERR":
                if jv != pv:
                    mismatches.append(f"{name}: java={java!r} py={py!r}")
            elif not _floats_close(jv, pv):
                mismatches.append(f"{name}: java={java!r} py={py!r}")
        elif java != py:
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "Type 4 fuzz divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_probe_covers_expected_groups() -> None:
    probe = _parse_probe(run_probe_text("FunctionType4FuzzProbe"))
    # Regression guards for the wave-1522 fixes (jar-proven verdicts).
    assert probe["bitshift_big_left"] == "create=ok eval=256.000000"
    assert probe["abs_intmin"] == "create=ok eval=-1000.000000"
    assert probe["eq_bool_int"] == "create=ok eval=0.000000"
    assert probe["and_bools"] == "create=ok eval=ERR"
    assert probe["roll_n_overflow"] == "create=ok eval=ERR"


# ---- oracle-free frozen regression copies of the wave-1522 fixes ----


def _eval(ps: str, domain: tuple, rng: tuple, ins: list[float]) -> list[float]:
    fn = PDFunction.create(_t4(ps, _floats(*domain), _floats(*rng)))
    return fn.eval(ins)


def test_bitshift_masks_count_and_wraps_32bit() -> None:
    # Java ``<<`` uses the low 5 bits of the count and wraps to 32-bit.
    assert _eval("{ pop 1 40 bitshift }", _D01, _R, [0.5]) == pytest.approx([256.0])
    assert _eval("{ pop 1 31 bitshift }", _D01, (-1e10, 1e10), [0.5]) == pytest.approx(
        [-2147483648.0]
    )


def test_abs_int_min_stays_negative() -> None:
    # Java ``Math.abs(Integer.MIN_VALUE) == Integer.MIN_VALUE`` (overflow).
    assert _eval("{ pop -2147483648 abs }", _D01, (-1e10, 1e10), [0.5]) == pytest.approx(
        [-2147483648.0]
    )


def test_eq_boolean_vs_number_is_unequal() -> None:
    # Java ``Boolean.equals(Integer)`` is false; Python ``True == 1`` is true.
    assert _eval(
        "{ pop true 1 eq { 1 } { 0 } ifelse }", _D01, _R, [0.5]
    ) == pytest.approx([0.0])


def test_roll_n_exceeding_stack_raises() -> None:
    # Java StackOperators$Roll pops ``n`` entries before rotating; a too-deep
    # ``n`` throws EmptyStackException.
    with pytest.raises(OSError):
        _eval("{ 1 2 9 1 roll }", _D01, _R, [0.5])


def test_boolean_in_range_output_raises() -> None:
    # A boolean left in a declared /Range slot raises (upstream popReal cast).
    with pytest.raises(OSError):
        _eval("{ pop true false and }", _D01, _R, [0.5])
