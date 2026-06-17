"""Live PDFBox differential parity for ``PDFunction.eval`` (wave 1431).

Compares pypdfbox's Type 0 / 2 / 3 / 4 function evaluation against Apache
PDFBox 3.0.7's ``PDFunction.eval(float[])`` across a fixed input grid.

The Java side is ``oracle/probes/FunctionEvalProbe.java``: it builds the same
battery of functions as COS objects, evaluates them, and prints canonical
``FUNC <name> <in0,in1,...> -> <out...>`` lines (each float ``%.6f``). This
test rebuilds the *identical* functions in pypdfbox, evaluates the same
inputs, and asserts the outputs match within 1e-5.

If the functions here drift from the probe, keep them in lockstep — the probe
is the oracle of record, this module reproduces it.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-5


# ---------- COS builders (mirror FunctionEvalProbe.java) ----------


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    arr.set_float_array([float(v) for v in vals])
    return arr


def _ints(*vals: int) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSInteger.get(int(v)))
    return arr


def _type2(
    c0: list[float] | None,
    c1: list[float] | None,
    n: float,
    domain: list[float],
    rng: list[float] | None,
) -> COSDictionary:
    # Type 2 is dictionary-backed upstream — mirror the probe's COSDictionary.
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _floats(*domain))
    if c0 is not None:
        d.set_item("C0", _floats(*c0))
    if c1 is not None:
        d.set_item("C1", _floats(*c1))
    d.set_item("N", COSFloat(float(n)))
    if rng is not None:
        d.set_item("Range", _floats(*rng))
    return d


def _type4(ps: str, domain: list[float], rng: list[float]) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", _floats(*domain))
    s.set_item("Range", _floats(*rng))
    s.set_data(ps.encode("ascii"))
    return s


def _pack(values: list[int], bits: int) -> bytes:
    """MSB-first bit-packing with no padding between samples (matches the
    probe's BigInteger packing)."""
    total_bits = len(values) * bits
    big = 0
    mask = (1 << bits) - 1
    for v in values:
        big = (big << bits) | (v & mask)
    pad = (-total_bits) % 8
    big <<= pad
    nbytes = (total_bits + pad) // 8
    return big.to_bytes(nbytes, "big") if nbytes else b""


def _type0(
    sample_codes: list[int],
    size: list[int],
    bits: int,
    domain: list[float],
    rng: list[float],
    encode: list[float] | None,
    decode: list[float] | None,
) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 0)
    s.set_item("Domain", _floats(*domain))
    s.set_item("Range", _floats(*rng))
    s.set_item("Size", _ints(*size))
    s.set_int("BitsPerSample", bits)
    if encode is not None:
        s.set_item("Encode", _floats(*encode))
    if decode is not None:
        s.set_item("Decode", _floats(*decode))
    s.set_data(_pack(sample_codes, bits))
    return s


# ---------- the function battery (1:1 with FunctionEvalProbe.main) ----------


def _build_functions() -> dict[str, PDFunction]:
    fns: dict[str, PDFunction] = {}

    # Type 2
    fns["T2quad"] = PDFunction.create(_type2([0], [1], 2.0, [0, 1], None))
    fns["T2sqrt"] = PDFunction.create(_type2([0, 1], [1, 0], 0.5, [0, 1], None))
    fns["T2clamp"] = PDFunction.create(
        _type2([0, 0.2, -0.5], [1, 0.8, 1.5], 3.0, [0, 1], [0, 1, 0, 1, 0, 1])
    )

    # Type 3 — two children, bound at 0.5
    funcs = COSArray()
    funcs.add(_type2([0], [1], 1.0, [0, 1], None))
    funcs.add(_type2([1], [0], 1.0, [0, 1], None))
    t3d = COSDictionary()
    t3d.set_int("FunctionType", 3)
    t3d.set_item("Domain", _floats(0, 1))
    t3d.set_item("Functions", funcs)
    t3d.set_item("Bounds", _floats(0.5))
    t3d.set_item("Encode", _floats(0, 1, 0, 1))
    fns["T3stitch"] = PDFunction.create(t3d)

    # Type 3 — three children, bounds [0.3 0.7], reversed encode in middle
    funcs3 = COSArray()
    funcs3.add(_type2([0], [1], 1.0, [0, 1], None))
    funcs3.add(_type2([0], [1], 1.0, [0, 1], None))
    funcs3.add(_type2([0], [1], 2.0, [0, 1], None))
    t3b = COSDictionary()
    t3b.set_int("FunctionType", 3)
    t3b.set_item("Domain", _floats(0, 1))
    t3b.set_item("Functions", funcs3)
    t3b.set_item("Bounds", _floats(0.3, 0.7))
    t3b.set_item("Encode", _floats(0, 1, 1, 0, 0, 1))
    fns["T3three"] = PDFunction.create(t3b)

    # Type 0
    fns["T0lin"] = PDFunction.create(
        _type0([0, 128, 255], [3], 8, [0, 1], [0, 1], None, None)
    )
    fns["T0rgb"] = PDFunction.create(
        _type0(
            [255, 0, 0, 0, 0, 255], [2], 8, [0, 1], [0, 1, 0, 1, 0, 1], None, None
        )
    )
    fns["T0grid"] = PDFunction.create(
        _type0([0, 85, 170, 255], [2, 2], 8, [0, 1, 0, 1], [0, 1], None, None)
    )
    total3d = 2 * 3 * 4
    s3d = [i * 10 for i in range(total3d)]
    fns["T03d"] = PDFunction.create(
        _type0(s3d, [2, 3, 4], 8, [0, 1, 0, 1, 0, 1], [0, 255], None, None)
    )
    fns["T0enc"] = PDFunction.create(
        _type0([10, 20, 30, 40], [4], 8, [0, 1], [0, 255], [3, 0], None)
    )
    fns["T0dec"] = PDFunction.create(
        _type0([0, 127, 255], [3], 8, [0, 1], [0, 1], None, [1, 0])
    )
    fns["T0n4"] = PDFunction.create(
        _type0([0, 5, 10, 15], [4], 4, [0, 1], [0, 1], None, None)
    )
    fns["T0n16"] = PDFunction.create(
        _type0([0, 65535], [2], 16, [0, 1], [0, 1], None, None)
    )

    # Type 4
    fns["T4sub"] = PDFunction.create(_type4("{ 1 exch sub }", [0, 1], [0, 1]))
    fns["T4tint"] = PDFunction.create(
        _type4("{ dup 0.3 mul exch 0.7 mul }", [0, 1], [0, 1, 0, 1])
    )
    fns["T4divmod"] = PDFunction.create(_type4("{ 7 div }", [0, 100], [0, 100]))
    fns["T4idivmod"] = PDFunction.create(
        _type4("{ pop 17 5 idiv 17 5 mod add }", [0, 100], [0, 100])
    )
    fns["T4math"] = PDFunction.create(_type4("{ 360 mul sin abs }", [0, 1], [0, 1]))
    fns["T4trans"] = PDFunction.create(
        _type4("{ dup sqrt exch 1 add ln add }", [0.01, 10], [0, 100])
    )
    fns["T4atan"] = PDFunction.create(_type4("{ 1 atan }", [-5, 5], [0, 360]))
    fns["T4exp"] = PDFunction.create(_type4("{ 2 exch exp }", [0, 8], [0, 300]))
    fns["T4rounders"] = PDFunction.create(
        _type4("{ 0.5 add floor }", [0, 10], [0, 10])
    )
    fns["T4cvi"] = PDFunction.create(_type4("{ cvi }", [-10, 10], [-10, 10]))
    fns["T4copy"] = PDFunction.create(
        _type4(
            "{ 2 copy add 3 1 roll sub exch }",
            [0, 100, 0, 100],
            [-200, 200, -200, 200],
        )
    )
    fns["T4index"] = PDFunction.create(
        _type4("{ 0 index add }", [0, 100, 0, 100], [0, 200, 0, 200])
    )
    fns["T4roll"] = PDFunction.create(
        _type4("{ 3 1 roll }", [0, 9, 0, 9, 0, 9], [0, 9, 0, 9, 0, 9])
    )
    fns["T4rollneg"] = PDFunction.create(
        _type4("{ 3 -1 roll }", [0, 9, 0, 9, 0, 9], [0, 9, 0, 9, 0, 9])
    )
    fns["T4cond"] = PDFunction.create(
        _type4("{ 0.5 lt { 0 } { 1 } ifelse }", [0, 1], [0, 1])
    )
    fns["T4if"] = PDFunction.create(
        _type4("{ dup 0.5 gt { 0.25 sub } if }", [0, 1], [0, 1])
    )
    fns["T4bool"] = PDFunction.create(
        _type4(
            "{ 2 copy gt 3 1 roll lt and { 1 } { 0 } ifelse }", [0, 10, 0, 10], [0, 1]
        )
    )
    fns["T4rgb"] = PDFunction.create(
        _type4("{ dup 1 exch sub 0.5 }", [0, 1], [0, 1, 0, 1, 0, 1])
    )
    return fns


# ---------- probe-line parser ----------


def _parse_probe_lines(text: str) -> list[tuple[str, list[float], list[float]]]:
    """Parse ``FUNC <name> <in0,in1,...> -> <out...>`` lines into tuples of
    ``(name, inputs, outputs)``."""
    out: list[tuple[str, list[float], list[float]]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("FUNC "):
            continue
        head, _, tail = line.partition(" -> ")
        parts = head.split()
        # parts[0] == "FUNC", parts[1] == name, parts[2] == "in0,in1,..."
        name = parts[1]
        inputs = [float(v) for v in parts[2].split(",")]
        outputs = [float(v) for v in tail.split()] if tail else []
        out.append((name, inputs, outputs))
    return out


# ---------- the differential test ----------


@requires_oracle
def test_function_eval_matches_pdfbox() -> None:
    java_text = run_probe_text("FunctionEvalProbe")
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

    assert not mismatches, "eval divergences vs PDFBox:\n" + "\n".join(mismatches)

    # Every function we built should have been exercised by the probe (guards
    # against the builders silently drifting away from the probe battery).
    assert covered == set(fns), (
        "probe / pypdfbox battery drift: "
        f"only-in-py={set(fns) - covered}"
    )


@requires_oracle
def test_function_eval_covers_all_types() -> None:
    """Sanity guard: the probe battery exercises every function type so a
    future probe edit can't quietly drop a whole type from the parity check."""
    java_text = run_probe_text("FunctionEvalProbe")
    names = {n for n, _, _ in _parse_probe_lines(java_text)}
    assert any(n.startswith("T0") for n in names), "no Type 0 cases in probe"
    assert any(n.startswith("T2") for n in names), "no Type 2 cases in probe"
    assert any(n.startswith("T3") for n in names), "no Type 3 cases in probe"
    assert any(n.startswith("T4") for n in names), "no Type 4 cases in probe"
