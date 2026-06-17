"""Live PDFBox differential fuzz parity for the Type 4 PostScript calculator
function — malformed function dicts + deeper operator/execution corners
(wave 1539, agent A).

Drives ``oracle/probes/FunctionType4FuzzWave1539Probe.java`` (the oracle of
record) against pypdfbox, rebuilding the *identical* Type 4 specs and asserting
each ``CASE`` line matches. This is a DIFFERENT angle from the wave-1522 corpus
(``test_function_type4_fuzz_wave1522.py``), which fuzzed the calculator
language over a fixed valid /Domain [0,1] and /Range [-1000,1000]. This wave
fuzzes:

  1. MALFORMED FUNCTION DICTS — missing / short / long / empty / odd-length /
     non-numeric / reversed /Domain and /Range. These drive
     ``get_number_of_input_parameters`` / ``get_number_of_output_parameters``,
     the input/output clip, and the under-supply check (none of which wave
     1522 exercised — it always handed valid arrays). The probe projects the
     declared parameter counts as extra observables.
  2. OPERATOR / EXECUTION CORNERS not covered by wave 1522: sin/cos cardinal
     angles, atan full-quadrant sweep, deep brace / if nesting, mixed int/float
     arithmetic tag preservation, roll boundary semantics, bitshift at exactly
     32, cvi/cvr re-tagging chains, comparison-operator tag handling, and
     stack-surplus / under-supply against the declared /Range arity.

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR> nin=<i|-> nout=<o|-> eval=<ERR | f0 f1 ...>

Semantics:
  - ``create=ERR`` — ``PDFunction.create`` threw (nin/nout/eval are "-").
  - ``nin`` / ``nout`` — ``get_number_of_input_parameters`` /
    ``get_number_of_output_parameters`` (or "-" if that accessor threw).
  - ``eval=ERR`` — construction succeeded, ``eval`` threw.
  - ``eval=<floats>`` — both succeeded.

Real bug fixed this wave (now matching the jar): pypdfbox's Type 4 input/output
clip normalised a reversed ``(min, max)`` /Domain or /Range pair (swapping
lo/hi), but upstream's ``PDFunction.clipToRange(x, min, max)`` is
non-normalising (``if x < min -> min; if x > max -> max; else x``).
``PDFunctionType4`` now overrides the clip with the non-normalising clamp
(mirroring the override already on ``PDFunctionType3``). Pinned by
``range_reversed`` / ``domain_reversed`` / ``two_in_clamp_a``.

Intentional divergences pinned both sides live in ``_DIVERGENCES``.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-3


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(float(v)))
    return arr


def _arr(*items: object) -> COSArray:
    arr = COSArray()
    for it in items:
        arr.add(it)
    return arr


def _t4(ps: str, domain: object, rng: object) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    if domain is not None:
        s.set_item("Domain", domain)
    if rng is not None:
        s.set_item("Range", rng)
    s.set_data(ps.encode("ascii"))
    return s


# Spec descriptor: (postscript_body, domain_base_or_None, range_base_or_None,
# eval_input). Mirrors the probe's edr/e1/e2 helpers.
def _edr(ps: str, domain: object, rng: object) -> tuple:
    return (ps, domain, rng, [0.5])


def _e1(ps: str, i: float) -> tuple:
    return (ps, _floats(0, 1), _floats(-1000, 1000), [i])


def _e2(ps: str, a: float, b: float) -> tuple:
    return (ps, _floats(0, 1, 0, 1), _floats(-1000, 1000), [a, b])


def _build_cases() -> dict[str, tuple]:
    """Return {case_name: (ps, domain, range, inputs)} mirroring the probe."""
    bad_range = _arr(COSFloat(-10.0), COSName.get_pdf_name("bogus"))
    str_range = _arr(COSFloat(-10.0), COSString("x"))
    bool_range = _arr(COSFloat(-10.0), COSBoolean.TRUE)
    int_range = _arr(COSInteger.get(-10), COSInteger.get(10))
    bad_domain = _arr(COSFloat(0.0), COSName.get_pdf_name("bogus"))
    return {
        # ---- malformed /Range ----
        "range_missing": _edr("{ pop 5 }", _floats(0, 1), None),
        "range_empty": _edr("{ pop 5 }", _floats(0, 1), COSArray()),
        "range_odd_len": _edr("{ pop 5 }", _floats(0, 1), _floats(-10, 10, 99)),
        "range_single": _edr("{ pop 5 }", _floats(0, 1), _floats(7)),
        "range_two_pair_under": _edr(
            "{ pop 5 }", _floats(0, 1), _floats(-10, 10, -10, 10)
        ),
        "range_reversed": _edr("{ pop 5000 }", _floats(0, 1), _floats(10, -10)),
        "range_non_numeric": _edr("{ pop 5 }", _floats(0, 1), bad_range),
        "range_cos_string": _edr("{ pop 5 }", _floats(0, 1), str_range),
        "range_cos_bool": _edr("{ pop 5 }", _floats(0, 1), bool_range),
        "range_cos_int": _edr("{ pop 5000 }", _floats(0, 1), int_range),
        "range_not_array": _edr("{ pop 5 }", _floats(0, 1), COSName.get_pdf_name("Bad")),
        # ---- malformed /Domain ----
        "domain_missing": _edr("{ 1000 mul }", None, _floats(-1000, 1000)),
        "domain_empty": _edr("{ 1000 mul }", COSArray(), _floats(-1000, 1000)),
        "domain_odd_len": _edr("{ 1000 mul }", _floats(0, 1, 9), _floats(-1000, 1000)),
        "domain_single": _edr("{ 1000 mul }", _floats(0), _floats(-1000, 1000)),
        "domain_reversed": _edr("{ 1000 mul }", _floats(1, 0), _floats(-1000, 1000)),
        "domain_non_numeric": _edr("{ 1000 mul }", bad_domain, _floats(-1000, 1000)),
        "domain_not_array": _edr(
            "{ 1000 mul }", COSName.get_pdf_name("Bad"), _floats(-1000, 1000)
        ),
        "domain_two_pair_one_in": _edr(
            "{ 1000 mul }", _floats(0, 1, 0, 1), _floats(-1000, 1000)
        ),
        # ---- /Range arity vs program output ----
        "arity_exact_one": _edr("{ pop 5 }", _floats(0, 1), _floats(-10, 10)),
        "arity_surplus_top": _edr("{ 7 8 9 }", _floats(0, 1), _floats(-100, 100)),
        "arity_zero_out": _edr("{ pop }", _floats(0, 1), _floats(-10, 10)),
        "arity_two_exact": _edr(
            "{ pop 3 4 }", _floats(0, 1), _floats(-10, 10, -10, 10)
        ),
        # ---- sin / cos cardinal angles ----
        "sin_0": _e1("{ pop 0 sin }", 0.5),
        "sin_30": _e1("{ pop 30 sin }", 0.5),
        "sin_90": _e1("{ pop 90 sin }", 0.5),
        "sin_180": _e1("{ pop 180 sin }", 0.5),
        "sin_270": _e1("{ pop 270 sin }", 0.5),
        "sin_neg90": _e1("{ pop -90 sin }", 0.5),
        "cos_0": _e1("{ pop 0 cos }", 0.5),
        "cos_60": _e1("{ pop 60 cos }", 0.5),
        "cos_90": _e1("{ pop 90 cos }", 0.5),
        "cos_180": _e1("{ pop 180 cos }", 0.5),
        "sin_int_arg": _e1("{ pop 45 sin }", 0.5),
        # ---- atan full-quadrant sweep ----
        "atan_0_1": _e1("{ pop 0 1 atan }", 0.5),
        "atan_1_0": _e1("{ pop 1 0 atan }", 0.5),
        "atan_0_neg1": _e1("{ pop 0 -1 atan }", 0.5),
        "atan_neg1_0": _e1("{ pop -1 0 atan }", 0.5),
        "atan_neg1_1": _e1("{ pop -1 1 atan }", 0.5),
        "atan_real_args": _e1("{ pop 1.0 1.0 atan }", 0.5),
        # ---- int/float tag preservation through arithmetic ----
        "tag_add_int_idiv": _e1("{ pop 3 4 add 2 idiv }", 0.5),
        "tag_mixed_add_idiv": _e1("{ pop 3.0 4 add 2 idiv }", 0.5),
        "tag_mul_int_mod": _e1("{ pop 6 7 mul 5 mod }", 0.5),
        "tag_sub_int_idiv": _e1("{ pop 10 3 sub 2 idiv }", 0.5),
        "tag_ceil_int": _e1("{ pop 5 ceiling 2 idiv }", 0.5),
        "tag_ceil_float_idiv": _e1("{ pop 5.5 ceiling 2 idiv }", 0.5),
        "tag_cvr_then_idiv": _e1("{ pop 6 cvr 2 idiv }", 0.5),
        "tag_cvi_then_idiv": _e1("{ pop 6.7 cvi 2 idiv }", 0.5),
        # ---- roll boundary semantics ----
        "roll_j_equals_n": _e1("{ 1 2 3 3 3 roll add add }", 0.5),
        "roll_j_neg_n": _e1("{ 1 2 3 3 -3 roll add add }", 0.5),
        "roll_n_one": _e1("{ 5 1 1 roll }", 0.5),
        "roll_4_2": _e1("{ 1 2 3 4 4 2 roll add add add }", 0.5),
        # ---- bitshift boundary ----
        "bitshift_32": _e1("{ pop 1 32 bitshift }", 0.5),
        "bitshift_33": _e1("{ pop 1 33 bitshift }", 0.5),
        "bitshift_31": _e1("{ pop 1 31 bitshift }", 0.5),
        "bitshift_neg31": _e1("{ pop -2147483648 -31 bitshift }", 0.5),
        "bitshift_neg32": _e1("{ pop -2147483648 -32 bitshift }", 0.5),
        # ---- deep nesting ----
        "deep_brace_5": _e1("{ pop { { { { { 5 } } } } } pop 5 }", 0.5),
        "deep_if_chain": _e1(
            "{ pop true { true { true { 7 } if } if } if }", 0.5
        ),
        "nested_ifelse": _e1(
            "{ pop 0.5 0 gt { 1 0 gt { 11 } { 12 } ifelse } { 13 } ifelse }", 0.5
        ),
        # ---- comparison operator tag handling ----
        "lt_int_float": _e1("{ pop 3 4.0 lt { 1 } { 0 } ifelse }", 0.5),
        "ge_equal": _e1("{ pop 5 5 ge { 1 } { 0 } ifelse }", 0.5),
        "le_int_float": _e1("{ pop 5 5.0 le { 1 } { 0 } ifelse }", 0.5),
        "eq_float32_tie": _e1(
            "{ pop 1.0000001 1.0000002 eq { 1 } { 0 } ifelse }", 0.5
        ),
        # ---- multi-input programs ----
        "two_in_add": _e2("{ add 100 mul }", 0.3, 0.7),
        "two_in_sub": _e2("{ sub 100 mul }", 0.7, 0.2),
        "two_in_clamp_a": _e2("{ pop 1000 mul }", 5.0, 0.5),
        # ---- surplus inputs left on stack with /Range ----
        "surplus_inputs_top": _e2("{ }", 0.3, 0.7),
    }


# Cases where pypdfbox *intentionally* diverges from the jar (pinned both
# sides). Maps case name -> the pypdfbox-side verdict it must produce. The jar's
# verdict is recorded in the comment. All divergences here are pre-existing
# base-class robustness/leniency families, NOT Type-4-specific bugs:
_DIVERGENCES: dict[str, str] = {
    # ---- lenient whole-stack return when /Range declares 0 outputs ----
    # Upstream PDFunctionType4.eval allocates a float[getNumberOfOutputParameters]
    # output (== 0 when /Range is absent / empty / single-entry / not-an-array)
    # and pops nothing, so eval returns an EMPTY array. pypdfbox keeps the
    # long-standing lenient whole-stack convenience (Type4Tester-style helpers /
    # inline shading callers depend on it) and returns the surviving stack.
    # Jar verdict for all four: ``create=ok nin=1 nout=0 eval=`` (empty).
    "range_missing": "create=ok nin=1 nout=0 eval=5.000000",
    "range_empty": "create=ok nin=1 nout=0 eval=5.000000",
    "range_single": "create=ok nin=1 nout=0 eval=5.000000",
    "range_not_array": "create=ok nin=1 nout=0 eval=5.000000",
    # ---- lenient COSArray.to_float_array (coerce non-number -> 0.0) ----
    # Java's COSArray.toFloatArray casts each entry to COSNumber and throws a
    # ClassCastException on a COSName / COSString / COSBoolean, so a /Range or
    # /Domain holding a non-numeric entry faults at eval (eval=ERR). pypdfbox's
    # COSArray.to_float_array coerces a non-number to 0.0, so the clip proceeds
    # against a degenerate [-10, 0] / [0, 0] pair instead of raising.
    # Jar verdict: ``create=ok nin=1 nout=1 eval=ERR``.
    "range_non_numeric": "create=ok nin=1 nout=1 eval=0.000000",
    "range_cos_string": "create=ok nin=1 nout=1 eval=0.000000",
    "range_cos_bool": "create=ok nin=1 nout=1 eval=0.000000",
    "domain_non_numeric": "create=ok nin=1 nout=1 eval=0.000000",
    # ---- malformed /Domain: Java NPE / IndexOOBE vs pypdfbox lenient ----
    # Java's PDFunctionType4.eval (via the base clipToRange(float[])) loops over
    # getNumberOfInputParameters() reading getDomainForInput(i). When /Domain is
    # absent or not an array, getDomainValues() returns null and
    # getNumberOfInputParameters() itself NPEs (probe records nin="-") and eval
    # faults. When /Domain is empty or single-entry, nin==0 but the eval clip
    # loop still indexes domain[0]/domain[1] and throws (eval=ERR). pypdfbox
    # treats a missing/empty/short /Domain as "no clipping" (nin 0, input passes
    # through), evaluating 0.5 -> 500.0.
    # Jar verdicts:
    #   domain_missing   create=ok nin=- nout=1 eval=ERR
    #   domain_not_array create=ok nin=- nout=1 eval=ERR
    #   domain_empty     create=ok nin=0 nout=1 eval=ERR
    #   domain_single    create=ok nin=0 nout=1 eval=ERR
    "domain_missing": "create=ok nin=0 nout=1 eval=500.000000",
    "domain_not_array": "create=ok nin=0 nout=1 eval=500.000000",
    "domain_empty": "create=ok nin=0 nout=1 eval=500.000000",
    "domain_single": "create=ok nin=0 nout=1 eval=500.000000",
}


def _fmt(value: float) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return f"{value:.6f}"


def _py_verdict(spec: tuple) -> str:
    ps, domain, rng, eval_input = spec
    cos = _t4(ps, domain, rng)
    try:
        fn = PDFunction.create(cos)
    except Exception:  # noqa: BLE001 - mirror the probe's catch-all
        return "create=ERR nin=- nout=- eval=-"
    try:
        nin = str(fn.get_number_of_input_parameters())
    except Exception:  # noqa: BLE001
        nin = "-"
    try:
        nout = str(fn.get_number_of_output_parameters())
    except Exception:  # noqa: BLE001
        nout = "-"
    try:
        out = fn.eval(eval_input)
        ev = " ".join(_fmt(v) for v in out)
    except Exception:  # noqa: BLE001
        ev = "ERR"
    return f"create=ok nin={nin} nout={nout} eval={ev}"


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


def _eval_token(verdict: str) -> str:
    _, _, ev = verdict.partition("eval=")
    return ev


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


def _verdicts_match(java: str, py: str) -> bool:
    """Whole-line match, tolerating float jitter in the eval= tail.

    The ``create=``/``nin=``/``nout=`` prefix must be byte-identical; the
    ``eval=`` float list compares with a tolerance (ERR-vs-floats never close).
    """
    jp, _, je = java.partition("eval=")
    pp, _, pe = py.partition("eval=")
    if jp != pp:
        return False
    if je == "ERR" or pe == "ERR":
        return je == pe
    return _floats_close(je, pe)


@requires_oracle
def test_function_type4_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text("FunctionType4FuzzWave1539Probe"))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, spec in cases.items():
        java = probe[name]
        py = _py_verdict(spec)

        if name in _DIVERGENCES:
            expected = _DIVERGENCES[name]
            if py != expected:
                mismatches.append(
                    f"{name}: pypdfbox drifted from pinned divergence "
                    f"py={py!r} expected={expected!r} (java={java!r})"
                )
            continue

        if not _verdicts_match(java, py):
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "Type 4 fuzz divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_probe_covers_expected_groups() -> None:
    probe = _parse_probe(run_probe_text("FunctionType4FuzzWave1539Probe"))
    # Regression guards for the wave-1539 reversed-clip fix (jar-proven).
    assert probe["range_reversed"] == "create=ok nin=1 nout=1 eval=-10.000000"
    assert probe["domain_reversed"] == "create=ok nin=1 nout=1 eval=1000.000000"
    assert probe["two_in_clamp_a"] == "create=ok nin=2 nout=1 eval=1000.000000"
    # Java non-normalising clip pins.
    assert probe["bitshift_31"] == "create=ok nin=1 nout=1 eval=-1000.000000"
    assert probe["range_two_pair_under"] == "create=ok nin=1 nout=2 eval=ERR"


# ---- oracle-free frozen regression copies (jar-proven values) ----


def _eval(ps: str, domain: object, rng: object, ins: list[float]) -> list[float]:
    return PDFunction.create(_t4(ps, domain, rng)).eval(ins)


def test_reversed_range_clamps_without_normalising() -> None:
    # /Range [10, -10], output 5000: Java clipToRange(5000, 10, -10) ->
    # 5000 > -10 -> -10 (NOT the normalised [-10, 10] -> 10). pypdfbox now
    # matches via the PDFunctionType4 non-normalising clip override.
    assert _eval("{ pop 5000 }", _floats(0, 1), _floats(10, -10), [0.5]) == (
        pytest.approx([-10.0])
    )


def test_reversed_domain_clamps_without_normalising() -> None:
    # /Domain [1, 0], input 0.5: Java clipToRange(0.5, 1, 0) -> 0.5 < 1 -> 1
    # (NOT the normalised [0, 1] -> 0.5). Then 1 * 1000 = 1000.
    assert _eval(
        "{ 1000 mul }", _floats(1, 0), _floats(-1000, 1000), [0.5]
    ) == pytest.approx([1000.0])


def test_multi_input_reversed_clip_independent_per_dimension() -> None:
    # Two-in domain [0,1]x[0,1], inputs [5.0, 0.5]: first input clips to 1.0,
    # popped; second (0.5) multiplied by 1000 -> ... program pops the first and
    # multiplies the second: 0.5 * 1000 = 500 -> clamped to 1000? No: the second
    # input 0.5 is in-domain, 0.5 * 1000 = 500... the FIRST input 5 -> 1, popped.
    # Program is "{ pop 1000 mul }": pop drops second (0.5), 1000 mul over the
    # first clipped input 1.0 -> 1000.0 (matches the jar).
    assert _eval(
        "{ pop 1000 mul }", _floats(0, 1, 0, 1), _floats(-1000, 1000), [5.0, 0.5]
    ) == pytest.approx([1000.0])


def test_bitshift_at_31_wraps_to_int_min() -> None:
    # 1 << 31 == Integer.MIN_VALUE (-2147483648), clamped to /Range min -1000.
    assert _eval(
        "{ pop 1 31 bitshift }", _floats(0, 1), _floats(-1000, 1000), [0.5]
    ) == pytest.approx([-1000.0])
