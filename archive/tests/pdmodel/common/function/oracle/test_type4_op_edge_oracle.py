"""Live PDFBox differential parity for Type 4 operator edge cases (wave 1459).

Complements ``test_function_eval_oracle`` (which covers the broad operator
battery) by pinning the easy-to-get-subtly-wrong corners where Apache
PDFBox's *concrete* behaviour — not the PostScript Reference text — is the
parity contract:

  - ``not`` on an integer negates (``-int``) rather than bit-inverting; on a
    boolean it logically negates.
  - ``or`` / ``xor`` / ``and`` on integer literals do C-style bit ops.
  - ``bitshift`` left (positive) and right (negative shift).
  - ``idiv`` / ``mod`` sign semantics with negative operands (quotient
    truncates toward zero; remainder sign follows the dividend).
  - ``round`` ties go toward +infinity; ``ceiling`` / ``floor`` / ``truncate``
    / ``cvi`` on negatives.
  - transcendental ``cos`` / ``log`` / ``neg`` / ``abs`` and ``atan`` over
    the ``[0, 360)`` wrap.
  - relational ``eq`` / ``ne`` / ``le`` / ``ge`` routed through ``ifelse``.
  - Type 2 inputs outside ``/Domain`` (PDFBox does *not* clip the input
    before exponentiation).

The Java side is ``oracle/probes/Type4OpEdgeProbe.java``: it is the oracle of
record. This module rebuilds the identical functions in pypdfbox, evaluates
the same inputs, and asserts the outputs match within 1e-5.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSStream
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


def _type2(
    c0: list[float],
    c1: list[float],
    n: float,
    domain: list[float],
    rng: list[float] | None,
) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 2)
    s.set_item("Domain", _floats(*domain))
    s.set_item("C0", _floats(*c0))
    s.set_item("C1", _floats(*c1))
    s.set_item("N", COSFloat(float(n)))
    if rng is not None:
        s.set_item("Range", _floats(*rng))
    return s


def _build_functions() -> dict[str, PDFunction]:
    fns: dict[str, PDFunction] = {}

    # bitwise / boolean on integers
    fns["T4notint"] = PDFunction.create(_type4("{ pop 5 not }", [0, 1], [-10, 10]))
    fns["T4notbool"] = PDFunction.create(
        _type4("{ 0.5 gt not { 1 } { 0 } ifelse }", [0, 1], [0, 1])
    )
    fns["T4orint"] = PDFunction.create(_type4("{ pop 12 10 or }", [0, 1], [0, 64]))
    fns["T4xorint"] = PDFunction.create(_type4("{ pop 12 10 xor }", [0, 1], [0, 64]))
    fns["T4andint"] = PDFunction.create(_type4("{ pop 12 10 and }", [0, 1], [0, 64]))
    fns["T4shl"] = PDFunction.create(_type4("{ pop 1 4 bitshift }", [0, 1], [0, 256]))
    fns["T4shr"] = PDFunction.create(
        _type4("{ pop 64 -3 bitshift }", [0, 1], [0, 256])
    )

    # sign semantics: idiv / mod with negatives
    fns["T4idivneg"] = PDFunction.create(
        _type4("{ pop -17 5 idiv }", [0, 1], [-100, 100])
    )
    fns["T4idivnegb"] = PDFunction.create(
        _type4("{ pop 17 -5 idiv }", [0, 1], [-100, 100])
    )
    fns["T4modneg"] = PDFunction.create(
        _type4("{ pop -17 5 mod }", [0, 1], [-100, 100])
    )
    fns["T4modnegb"] = PDFunction.create(
        _type4("{ pop 17 -5 mod }", [0, 1], [-100, 100])
    )

    # rounding family on negatives + ties
    fns["T4round"] = PDFunction.create(_type4("{ round }", [-10, 10], [-10, 10]))
    fns["T4ceil"] = PDFunction.create(_type4("{ ceiling }", [-10, 10], [-10, 10]))
    fns["T4floorneg"] = PDFunction.create(_type4("{ floor }", [-10, 10], [-10, 10]))
    fns["T4trunc"] = PDFunction.create(_type4("{ truncate }", [-10, 10], [-10, 10]))
    fns["T4cvineg"] = PDFunction.create(_type4("{ cvi }", [-10, 10], [-10, 10]))
    fns["T4cvr"] = PDFunction.create(
        _type4("{ cvi cvr 0.5 add }", [-10, 10], [-10, 10])
    )

    # transcendental
    fns["T4cos"] = PDFunction.create(_type4("{ 180 mul cos }", [0, 2], [-1, 1]))
    fns["T4log"] = PDFunction.create(_type4("{ 1000 mul log }", [0.001, 1], [0, 3]))
    fns["T4neg"] = PDFunction.create(_type4("{ neg }", [-5, 5], [-5, 5]))
    fns["T4absneg"] = PDFunction.create(_type4("{ abs }", [-5, 5], [0, 5]))
    fns["T4atanwrap"] = PDFunction.create(
        _type4("{ 90 mul dup sin exch cos atan }", [0, 4], [0, 360])
    )

    # relational via ifelse
    fns["T4eq"] = PDFunction.create(
        _type4("{ 2 eq { 1 } { 0 } ifelse }", [0, 5], [0, 1])
    )
    fns["T4ne"] = PDFunction.create(
        _type4("{ 2 ne { 1 } { 0 } ifelse }", [0, 5], [0, 1])
    )
    fns["T4le"] = PDFunction.create(
        _type4("{ 2 le { 1 } { 0 } ifelse }", [0, 5], [0, 1])
    )
    fns["T4ge"] = PDFunction.create(
        _type4("{ 2 ge { 1 } { 0 } ifelse }", [0, 5], [0, 1])
    )

    # Type 2 input outside /Domain (no input clip before exponentiation)
    fns["T2dom"] = PDFunction.create(_type2([0], [1], 2.0, [0.25, 0.75], None))

    return fns


def _parse_probe_lines(text: str) -> list[tuple[str, list[float], list[float]]]:
    out: list[tuple[str, list[float], list[float]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("FUNC "):
            continue
        head, _, tail = line.partition(" -> ")
        parts = head.split()
        name = parts[1]
        inputs = [float(v) for v in parts[2].split(",")]
        outputs = [float(v) for v in tail.split()] if tail else []
        out.append((name, inputs, outputs))
    return out


@requires_oracle
def test_type4_op_edge_matches_pdfbox() -> None:
    java_text = run_probe_text("Type4OpEdgeProbe")
    expected = _parse_probe_lines(java_text)
    assert expected, "probe produced no FUNC lines"

    fns = _build_functions()
    mismatches: list[str] = []
    covered: set[str] = set()

    for name, inputs, exp_out in expected:
        fn = fns.get(name)
        assert fn is not None, f"no pypdfbox function built for probe entry {name!r}"
        covered.add(name)
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

    assert not mismatches, "Type 4 edge divergences vs PDFBox:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), (
        "probe / pypdfbox battery drift: only-in-py="
        f"{set(fns) - covered}"
    )
