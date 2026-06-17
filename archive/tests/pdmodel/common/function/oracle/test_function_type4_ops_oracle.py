"""Live PDFBox differential parity for Type 4 stack / conversion operators
and /Domain + /Range clamping.

Complements ``test_function_eval_oracle`` (broad operator battery) and
``test_type4_op_edge_oracle`` (bitwise / sign / rounding corners) by pinning
the surfaces those two do not exercise:

  - stack ops ``roll`` (positive, negative, zero, j == ±n, and the |j| > n
    overflow where PDFBox does *not* reduce j mod n and therefore throws),
    ``index``, ``copy`` (including the 0 cases).
  - conversion ``cvi`` (truncate toward zero) / ``cvr`` over positives,
    negatives, and fractional values, plus the ``cvi cvr`` round-trip.
  - integer ``idiv`` / ``mod`` with positive operands; large ``bitshift``.
  - numeric comparison ``lt`` / ``gt`` and boolean ``eq`` / ``ne`` on
    ``true`` / ``false`` literals, routed through ``ifelse``.
  - ``/Range`` clamping of an over/under-shooting raw output.
  - ``/Domain`` clipping of an out-of-bounds input before the program runs.

The Java side is ``oracle/probes/FunctionType4OpsProbe.java`` (the oracle of
record). Lines whose output token is ``ERR`` mark inputs where PDFBox throws
(a malformed program, e.g. an out-of-range ``roll`` count); pypdfbox must
raise on those too.

This module rebuilds the identical functions in pypdfbox, evaluates the same
inputs, and asserts the outputs match within 1e-5.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-5


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
    fns: dict[str, PDFunction] = {}
    r3 = [-100, 100, -100, 100, -100, 100]
    r4 = [-100, 100, -100, 100, -100, 100, -100, 100]
    r2 = [-100, 100, -100, 100]

    # roll
    fns["T4roll_pos"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 1 roll }", [0, 1], r3)
    )
    fns["T4roll_neg"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 -1 roll }", [0, 1], r3)
    )
    fns["T4roll_zero"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 0 roll }", [0, 1], r3)
    )
    fns["T4roll_eqn"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 3 roll }", [0, 1], r3)
    )
    fns["T4roll_negn"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 -3 roll }", [0, 1], r3)
    )
    fns["T4roll_overflow"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 4 roll }", [0, 1], r3)
    )
    fns["T4roll_overflow_neg"] = PDFunction.create(
        _type4("{ pop 1 2 3 3 -4 roll }", [0, 1], r3)
    )

    # index
    fns["T4index0"] = PDFunction.create(
        _type4("{ pop 10 20 30 0 index }", [0, 1], r4)
    )
    fns["T4index2"] = PDFunction.create(
        _type4("{ pop 10 20 30 2 index }", [0, 1], r4)
    )

    # copy
    fns["T4copy0"] = PDFunction.create(_type4("{ pop 10 20 0 copy }", [0, 1], r2))
    fns["T4copy2"] = PDFunction.create(_type4("{ pop 10 20 2 copy }", [0, 1], r4))

    # conversion
    fns["T4cvi_pos"] = PDFunction.create(_type4("{ cvi }", [-10, 10], [-10, 10]))
    fns["T4cvi_neg"] = PDFunction.create(_type4("{ cvi }", [-10, 10], [-10, 10]))
    fns["T4cvr_frac"] = PDFunction.create(_type4("{ cvr }", [-10, 10], [-10, 10]))
    fns["T4cvi_then_cvr"] = PDFunction.create(
        _type4("{ cvi cvr }", [-10, 10], [-10, 10])
    )

    # integer arithmetic
    fns["T4idiv_pos"] = PDFunction.create(
        _type4("{ pop 17 5 idiv }", [0, 1], [-100, 100])
    )
    fns["T4mod_pos"] = PDFunction.create(
        _type4("{ pop 17 5 mod }", [0, 1], [-100, 100])
    )
    fns["T4shl_big"] = PDFunction.create(
        _type4("{ pop 3 8 bitshift }", [0, 1], [0, 100000])
    )

    # comparison
    fns["T4lt"] = PDFunction.create(
        _type4("{ 3 lt { 1 } { 0 } ifelse }", [0, 5], [0, 1])
    )
    fns["T4gt"] = PDFunction.create(
        _type4("{ 3 gt { 1 } { 0 } ifelse }", [0, 5], [0, 1])
    )
    fns["T4eqbool"] = PDFunction.create(
        _type4("{ pop true true eq { 1 } { 0 } ifelse }", [0, 1], [0, 1])
    )
    fns["T4eqbool2"] = PDFunction.create(
        _type4("{ pop true false eq { 1 } { 0 } ifelse }", [0, 1], [0, 1])
    )
    fns["T4nebool"] = PDFunction.create(
        _type4("{ pop true false ne { 1 } { 0 } ifelse }", [0, 1], [0, 1])
    )

    # /Range clamping
    fns["T4rangeclamp"] = PDFunction.create(_type4("{ 10 mul }", [0, 1], [0, 5]))
    fns["T4rangeclamp_lo"] = PDFunction.create(
        _type4("{ 10 mul neg }", [0, 1], [-3, 0])
    )

    # /Domain clipping
    fns["T4domainclip"] = PDFunction.create(_type4("{ }", [0.25, 0.75], [0, 1]))

    return fns


def _parse_probe_lines(
    text: str,
) -> list[tuple[str, list[float], list[float] | None]]:
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
            out.append((name, inputs, None))  # PDFBox raised
        else:
            outputs = [float(v) for v in tail.split()] if tail else []
            out.append((name, inputs, outputs))
    return out


@requires_oracle
def test_type4_ops_matches_pdfbox() -> None:
    java_text = run_probe_text("FunctionType4OpsProbe")
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
            # PDFBox threw — pypdfbox must too.
            with pytest.raises(OSError):
                fn.eval(list(inputs))
            continue

        got = fn.eval(list(inputs))
        if len(got) != len(exp_out):
            mismatches.append(
                f"{name} {inputs}: arity {len(got)} != java {len(exp_out)} "
                f"(py={got}, java={exp_out})"
            )
            continue
        for j, (g, e) in enumerate(zip(got, exp_out, strict=True)):
            if abs(g - e) > _TOL:
                mismatches.append(
                    f"{name} {inputs}[{j}]: py={g:.6f} != java={e:.6f} "
                    f"(diff={abs(g - e):.2e})"
                )

    assert not mismatches, "Type 4 ops divergences vs PDFBox:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), (
        "probe / pypdfbox battery drift: only-in-py="
        f"{set(fns) - covered}"
    )
