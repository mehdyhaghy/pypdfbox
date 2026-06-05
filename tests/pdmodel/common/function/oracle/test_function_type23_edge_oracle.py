"""Live PDFBox differential parity for PDFunctionType2/Type3 eval edge cases
(wave 1483).

Drives ``oracle/probes/FunctionType23EdgeProbe.java`` against pypdfbox,
rebuilding the *identical* COS objects and asserting eval outputs match. The
probe is the oracle of record; the hand-written literals in
``tests/pdmodel/common/function/test_pd_function_type23_edge_wave1483.py``
are frozen copies of these same values for oracle-free regression.

Covers: Type 2 missing /N (exponent -1), N=0, negative base with fractional /N
(NaN), C0/C1 length mismatch, missing C0/C1 defaults, input outside [0,1] but
inside /Domain; Type 3 single subfunction, reversed /Encode, input AT a bound,
domain-edge clipping, zero-width subdomains, repeated bounds, nested Type3.
"""

from __future__ import annotations

import math

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-5


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _type2(
    c0: list[float] | None,
    c1: list[float] | None,
    n: float | None,
    domain: list[float],
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _floats(*domain))
    if c0 is not None:
        d.set_item("C0", _floats(*c0))
    if c1 is not None:
        d.set_item("C1", _floats(*c1))
    if n is not None:
        d.set_item("N", COSFloat(float(n)))
    return d


def _type3(
    funcs: list[COSDictionary],
    domain: list[float],
    bounds: list[float],
    encode: list[float],
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    d.set_item("Domain", _floats(*domain))
    fa = COSArray()
    for f in funcs:
        fa.add(f)
    d.set_item("Functions", fa)
    ba = COSArray()
    for b in bounds:
        ba.add(COSFloat(float(b)))
    d.set_item("Bounds", ba)
    d.set_item("Encode", _floats(*encode))
    return d


def _build() -> dict[str, PDFunction]:
    fns: dict[str, PDFunction] = {}
    fns["T2noN"] = PDFunction.create(_type2([0], [1], None, [0, 1]))
    fns["T2n0"] = PDFunction.create(_type2([2], [5], 0.0, [0, 1]))
    fns["T2negfrac"] = PDFunction.create(_type2([0], [1], 0.5, [-2, 2]))
    fns["T2negint"] = PDFunction.create(_type2([0], [1], 2.0, [-2, 2]))
    fns["T2negodd"] = PDFunction.create(_type2([0], [1], 3.0, [-2, 2]))
    fns["T2mismatch"] = PDFunction.create(
        _type2([0, 0.1, 0.2], [1, 0.9], 1.0, [0, 1])
    )
    fns["T2nocoeff"] = PDFunction.create(_type2(None, None, 1.0, [0, 1]))
    fns["T2outside"] = PDFunction.create(_type2([0], [10], 1.0, [-2, 2]))

    fns["T3single"] = PDFunction.create(
        _type3([_type2([0], [1], 1.0, [0, 1])], [0, 1], [], [0, 1])
    )
    fns["T3rev"] = PDFunction.create(
        _type3([_type2([0], [1], 1.0, [0, 1])], [0, 1], [], [1, 0])
    )
    fns["T3bound"] = PDFunction.create(
        _type3(
            [_type2([0], [1], 1.0, [0, 1]), _type2([10], [20], 1.0, [0, 1])],
            [0, 1],
            [0.5],
            [0, 1, 0, 1],
        )
    )
    fns["T3dom"] = PDFunction.create(
        _type3(
            [_type2([0], [1], 1.0, [0, 1]), _type2([1], [2], 1.0, [0, 1])],
            [0.2, 0.8],
            [0.5],
            [0, 1, 0, 1],
        )
    )
    fns["T3zerolo"] = PDFunction.create(
        _type3(
            [_type2([3], [7], 1.0, [0, 1]), _type2([0], [1], 1.0, [0, 1])],
            [0, 1],
            [0.0],
            [0, 1, 0, 1],
        )
    )
    fns["T3rep"] = PDFunction.create(
        _type3(
            [
                _type2([0], [1], 1.0, [0, 1]),
                _type2([5], [6], 1.0, [0, 1]),
                _type2([2], [3], 1.0, [0, 1]),
            ],
            [0, 1],
            [0.5, 0.5],
            [0, 1, 0, 1, 0, 1],
        )
    )
    inner = _type3(
        [_type2([0], [1], 1.0, [0, 1]), _type2([1], [0], 1.0, [0, 1])],
        [0, 1],
        [0.5],
        [0, 1, 0, 1],
    )
    fns["T3nest"] = PDFunction.create(
        _type3(
            [_type2([2], [3], 1.0, [0, 1]), inner],
            [0, 1],
            [0.5],
            [0, 1, 0, 1],
        )
    )
    return fns


def _to_float(token: str) -> float:
    if token == "NaN":
        return math.nan
    if token == "Infinity":
        return math.inf
    if token == "-Infinity":
        return -math.inf
    return float(token)


def _parse(text: str) -> list[tuple[str, list[float], list[float]]]:
    out: list[tuple[str, list[float], list[float]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("FUNC "):
            continue
        head, _, tail = line.partition(" -> ")
        parts = head.split()
        name = parts[1]
        inputs = [float(v) for v in parts[2].split(",")]
        outputs = [_to_float(v) for v in tail.split()] if tail else []
        out.append((name, inputs, outputs))
    return out


@requires_oracle
def test_type23_edge_matches_pdfbox() -> None:
    fns = _build()
    expected = _parse(run_probe_text("FunctionType23EdgeProbe"))
    assert expected, "probe produced no FUNC lines"
    mismatches: list[str] = []
    covered: set[str] = set()
    for name, inputs, exp_out in expected:
        fn = fns.get(name)
        assert fn is not None, f"no pypdfbox function for probe entry {name!r}"
        covered.add(name)
        got = fn.eval(list(inputs))
        assert len(got) == len(exp_out), (
            f"{name} {inputs}: arity {len(got)} != java {len(exp_out)}"
        )
        for j, (g, e) in enumerate(zip(got, exp_out, strict=True)):
            if math.isnan(e):
                if not math.isnan(g):
                    mismatches.append(f"{name} {inputs}[{j}]: py={g} != java=NaN")
            elif math.isinf(e):
                if g != e:
                    mismatches.append(f"{name} {inputs}[{j}]: py={g} != java={e}")
            elif abs(g - e) > _TOL:
                mismatches.append(
                    f"{name} {inputs}[{j}]: py={g:.6f} != java={e:.6f}"
                )
    assert not mismatches, "FunctionType23EdgeProbe divergences:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), f"battery drift: only-in-py={set(fns) - covered}"
