"""Live PDFBox differential parity for PDFunctionType2 (exponential
interpolation) eval fuzz (wave 1536).

Drives ``oracle/probes/FunctionType2FuzzProbe.java`` against pypdfbox,
rebuilding the *identical* COS objects and asserting eval outputs match. The
probe is the oracle of record.

Dedicated Type 2 angles complementing FunctionType23EdgeProbe:
- /N = 1, huge (1000), fractional (0.5), negative-even (-2).
- x=0 with negative /N: Java ``Math.pow(0, neg)`` => +Infinity (pypdfbox
  previously returned NaN — fixed wave 1536).
- /C0 or /C1 present-but-empty: the PDFBox constructor materialises [0]/[1]
  (pypdfbox previously returned [] => zero output components — fixed
  wave 1536).
- C0/C1 length mismatch (min sizing), multi-component interpolation.
- /Domain missing / reversed; input outside /Domain (eval does NOT clip input).
- /Range clipping of each output component.
- negative base with fractional /N => NaN.
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


def _t2(
    c0: list[float] | None,
    c1: list[float] | None,
    n: float | None,
    domain: list[float] | None,
    rng: list[float] | None = None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    if domain is not None:
        d.set_item("Domain", _floats(*domain))
    if c0 is not None:
        d.set_item("C0", _floats(*c0))
    if c1 is not None:
        d.set_item("C1", _floats(*c1))
    if n is not None:
        d.set_item("N", COSFloat(float(n)))
    if rng is not None:
        d.set_item("Range", _floats(*rng))
    return d


def _empty(key: str, base: COSDictionary) -> COSDictionary:
    base.set_item(key, COSArray())
    return base


def _build() -> dict[str, PDFunction]:
    fns: dict[str, PDFunction] = {}
    fns["N1"] = PDFunction.create(_t2([0], [1], 1.0, [0, 1]))
    fns["Nhuge"] = PDFunction.create(_t2([0], [1], 1000.0, [0, 1]))
    fns["Nfrac"] = PDFunction.create(_t2([0], [1], 0.5, [0, 1]))
    fns["Nnegeven"] = PDFunction.create(_t2([0], [1], -2.0, [0.001, 4]))
    fns["Nnegzero"] = PDFunction.create(_t2([0], [1], -1.0, [0, 1]))
    fns["Nneg2zero"] = PDFunction.create(_t2([0], [1], -2.0, [0, 1]))

    c0e = _t2(None, [5], 1.0, [0, 1])
    c0e.set_item("C0", COSArray())
    fns["C0empty"] = PDFunction.create(c0e)
    c1e = _t2([3], None, 1.0, [0, 1])
    c1e.set_item("C1", COSArray())
    fns["C1empty"] = PDFunction.create(c1e)
    be = _t2(None, None, 1.0, [0, 1])
    be.set_item("C0", COSArray())
    be.set_item("C1", COSArray())
    fns["BothEmpty"] = PDFunction.create(be)

    fns["C0long"] = PDFunction.create(_t2([1, 2, 3], [9], 1.0, [0, 1]))
    fns["C1long"] = PDFunction.create(_t2([1], [7, 8, 9], 1.0, [0, 1]))
    fns["Multi"] = PDFunction.create(_t2([0, 1, 2], [10, 5, -2], 2.0, [0, 1]))

    nodom = _t2([0], [1], 1.0, None)
    fns["NoDomain"] = PDFunction.create(nodom)
    fns["DomClip"] = PDFunction.create(_t2([0], [10], 1.0, [0.2, 0.8]))
    fns["DomRev"] = PDFunction.create(_t2([0], [4], 1.0, [1, 0]))
    fns["Range"] = PDFunction.create(
        _t2([0, 0], [100, -100], 1.0, [0, 1], [0, 10, -10, 0])
    )
    fns["NegBase"] = PDFunction.create(_t2([0], [1], 0.5, [-4, 4]))
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
def test_type2_fuzz_matches_pdfbox() -> None:
    fns = _build()
    expected = _parse(run_probe_text("FunctionType2FuzzProbe"))
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
    assert not mismatches, "FunctionType2FuzzProbe divergences:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), f"battery drift: only-in-py={set(fns) - covered}"
