"""Live PDFBox differential parity for Type 4 numeric-domain edge cases.

Pins the operators whose out-of-domain inputs do NOT raise in upstream PDFBox
but instead emit an IEEE-754 special value absorbed by the trailing /Range clip:

  - ``div`` by zero  => +/-Infinity (0/0 => NaN) => clamped to the range bound.
  - ``ln`` / ``log`` of 0 => -Infinity => range min; of a negative => NaN.
  - ``exp`` with a negative base and a fractional exponent => Math.pow NaN.

An earlier pypdfbox build raised on all of these; wave 1500 made them mirror
Java's IEEE behaviour. Also pins the cases that legitimately raise (idiv/mod by
zero, sqrt of negative, type mismatch, under-supply, stack underflow) and the
sign / rounding / atan-quadrant corners.

The Java side is ``oracle/probes/FunctionType4DomainErrProbe.java``. ``ERR`` on
a probe line means PDFBox threw; pypdfbox must raise (OSError or ValueError) on
that input too.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-4


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    arr.set_float_array([float(v) for v in vals])
    return arr


def _type4(ps: str, domain: list[float], rng: list[float]) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", _floats(*domain))
    s.set_item("Range", _floats(*rng))
    s.set_data(ps.encode("ascii"))
    return s


def _build_functions() -> dict[str, PDFunction]:
    d = [0.0, 1.0]
    r = [-1000.0, 1000.0]
    big = [0.0, 100000.0]
    fns: dict[str, PDFunction] = {
        # IEEE-special then /Range clip
        "div0": PDFunction.create(_type4("{ pop 1 0 div }", d, r)),
        "div0neg": PDFunction.create(_type4("{ pop -1 0 div }", d, r)),
        "div00": PDFunction.create(_type4("{ pop 0 0 div }", d, r)),
        "ln0": PDFunction.create(_type4("{ pop 0 ln }", d, r)),
        "lnneg": PDFunction.create(_type4("{ pop -5 ln }", d, r)),
        "log0": PDFunction.create(_type4("{ pop 0 log }", d, r)),
        "logneg": PDFunction.create(_type4("{ pop -5 log }", d, r)),
        "exp_negbase": PDFunction.create(_type4("{ pop -2 0.5 exp }", d, r)),
        "exp_00": PDFunction.create(_type4("{ pop 0 0 exp }", d, r)),
        # legitimately raise
        "idiv0": PDFunction.create(_type4("{ pop 1 0 idiv }", d, r)),
        "mod0": PDFunction.create(_type4("{ pop 1 0 mod }", d, r)),
        "sqrt_neg": PDFunction.create(_type4("{ pop -1 sqrt }", d, r)),
        "add_bool": PDFunction.create(_type4("{ pop true 1 add }", d, r)),
        "if_nonbool": PDFunction.create(_type4("{ pop 1 { 5 } if }", d, r)),
        "undersupply": PDFunction.create(_type4("{ pop }", d, r)),
        "exch_under": PDFunction.create(_type4("{ pop exch }", d, r)),
        # sign semantics
        "mod_neg": PDFunction.create(_type4("{ pop -7 3 mod }", d, r)),
        "mod_neg2": PDFunction.create(_type4("{ pop 7 -3 mod }", d, r)),
        "idiv_neg": PDFunction.create(_type4("{ pop -7 2 idiv }", d, r)),
        "idiv_neg2": PDFunction.create(_type4("{ pop 7 -2 idiv }", d, r)),
        # rounding / conversion
        "round_pos": PDFunction.create(_type4("{ pop 2.5 round }", d, r)),
        "round_neg": PDFunction.create(_type4("{ pop -2.5 round }", d, r)),
        "round_neg15": PDFunction.create(_type4("{ pop -1.5 round }", d, r)),
        "cvi_neg": PDFunction.create(_type4("{ pop -3.9 cvi }", d, r)),
        # atan quadrants
        "atan_q1": PDFunction.create(_type4("{ pop 1 1 atan }", d, r)),
        "atan_q2": PDFunction.create(_type4("{ pop 1 -1 atan }", d, r)),
        "atan_q3": PDFunction.create(_type4("{ pop -1 -1 atan }", d, r)),
        "atan_q4": PDFunction.create(_type4("{ pop -1 1 atan }", d, r)),
        "atan_00": PDFunction.create(_type4("{ pop 0 0 atan }", d, r)),
        # bitshift
        "shift_left": PDFunction.create(_type4("{ pop 3 8 bitshift }", d, big)),
        "shift_right": PDFunction.create(_type4("{ pop 256 -2 bitshift }", d, big)),
        "shift_neg_val": PDFunction.create(_type4("{ pop -8 1 bitshift }", d, r)),
        # lenient integer-count stack op
        "index_float": PDFunction.create(
            _type4("{ pop 10 20 30 2.0 0 mul 1 add index }", d, r)
        ),
    }
    return fns


def _parse_probe_lines(text: str) -> list[tuple[str, list[float], list[float] | None]]:
    out: list[tuple[str, list[float], list[float] | None]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("FUNC "):
            continue
        head, _, tail = line.partition(" -> ")
        parts = head.split()
        name = parts[1]
        inputs = [float(v) for v in parts[2].split(",")]
        tail = tail.strip()
        if tail == "ERR":
            out.append((name, inputs, None))
        else:
            outputs = [float(v) for v in tail.split()] if tail else []
            out.append((name, inputs, outputs))
    return out


@requires_oracle
def test_type4_domain_err_matches_pdfbox() -> None:
    java_text = run_probe_text("FunctionType4DomainErrProbe")
    expected = _parse_probe_lines(java_text)
    assert expected, "probe produced no FUNC lines"

    fns = _build_functions()
    mismatches: list[str] = []
    covered: set[str] = set()

    for name, inputs, exp_out in expected:
        fn = fns.get(name)
        assert fn is not None, f"no pypdfbox function built for probe entry {name!r}"
        covered.add(name)

        if exp_out is None:
            # PDFBox threw — pypdfbox must too (OSError analogue, or ValueError
            # for the math-domain cases that surface as ValueError natively).
            with pytest.raises((OSError, ValueError)):
                fn.eval(list(inputs))
            continue

        got = fn.eval(list(inputs))
        if len(got) != len(exp_out):
            mismatches.append(
                f"{name} {inputs}: arity {len(got)} != java {len(exp_out)}"
            )
            continue
        for j, (g, e) in enumerate(zip(got, exp_out, strict=True)):
            if math.isnan(e):
                if not math.isnan(g):
                    mismatches.append(f"{name} {inputs}[{j}]: py={g} != java=NaN")
            elif abs(g - e) > _TOL:
                mismatches.append(
                    f"{name} {inputs}[{j}]: py={g:.6f} != java={e:.6f}"
                )

    assert not mismatches, "Type 4 domain-error divergences vs PDFBox:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), (
        f"probe / pypdfbox battery drift: only-in-py={set(fns) - covered}"
    )


def test_type4_strict_integer_operator_rejects_float_operand() -> None:
    # Wave 1511 restored the Integer/Float type discipline: bitshift pops with
    # (Integer), so a Float (here produced by ``div``, which always yields a
    # Float) raises ClassCastException in Java. pypdfbox now surfaces that as
    # OSError instead of accepting it and returning 6.0. Verified ERR against
    # the live jar (_ScratchType4Probe / FunctionType4OpsProbe).
    fn = PDFunction.create(_type4("{ pop 6 2 div 1 bitshift }", [0.0, 1.0], [-9.0, 9.0]))
    with pytest.raises((OSError, ValueError)):
        fn.eval([0.0])


def test_type4_idiv_rejects_int_valued_float() -> None:
    # ``8.0`` parses as a Real (REAL_PATTERN), not an Integer, so even though it
    # equals 8 the strict ``idiv`` pop raises — matches the jar (ERR).
    fn = PDFunction.create(_type4("{ pop 8.0 2 idiv }", [0.0, 1.0], [-100.0, 100.0]))
    with pytest.raises((OSError, ValueError)):
        fn.eval([0.0])


def test_type4_int_preserving_chain_keeps_idiv_legal() -> None:
    # add/sub/mul/cvi on integer operands preserve the Integer tag, so a strict
    # integer op downstream stays legal. ``5 3 add 2 idiv`` => (8) idiv 2 => 4.
    fn = PDFunction.create(_type4("{ pop 5 3 add 2 idiv }", [0.0, 1.0], [-100.0, 100.0]))
    assert fn.eval([0.0]) == pytest.approx([4.0])


def test_type4_cvi_retags_float_to_int_for_idiv() -> None:
    # ``cvi`` re-tags a Float as an Integer, so ``7.9 cvi 2 idiv`` works where
    # ``7.9 2 idiv`` would raise. (7) idiv 2 => 3. Matches the jar.
    fn = PDFunction.create(_type4("{ pop 7.9 cvi 2 idiv }", [0.0, 1.0], [-100.0, 100.0]))
    assert fn.eval([0.0]) == pytest.approx([3.0])


def test_type4_input_value_is_float_and_rejected_by_idiv() -> None:
    # Inputs are pushed as Float (upstream pushes float[]), so using an input
    # directly in a strict integer op raises — verified ERR against the jar.
    fn = PDFunction.create(_type4("{ 1 idiv }", [0.0, 10.0], [-100.0, 100.0]))
    with pytest.raises((OSError, ValueError)):
        fn.eval([4.0])
