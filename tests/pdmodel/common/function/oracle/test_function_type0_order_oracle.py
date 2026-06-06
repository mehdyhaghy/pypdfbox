"""Live PDFBox differential parity for Type 0 (sampled) function eval.

Complements ``test_function_type0_degenerate_oracle`` (degenerate-shape corners)
and the Bit32 probe by pinning:

  - /Order 1 vs 3 producing identical output. Upstream PDFunctionType0.eval has
    no cubic branch — it ignores /Order and always interpolates n-linearly. This
    locks pypdfbox to that behaviour (an earlier pypdfbox build applied a
    Catmull-Rom spline for /Order 3, which diverged; wave 1500 reverted it).
  - /Size 1 degenerate dimension, inverted /Encode and /Decode, 2-input
    bilinear interpolation, /BitsPerSample 1 / 12 / 16, and out-of-domain
    input clamping.

The Java side is ``oracle/probes/FunctionType0OrderProbe.java``. This module
rebuilds the identical functions in pypdfbox and asserts the outputs match
within 1e-4.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-4


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    arr.set_float_array([float(v) for v in vals])
    return arr


def _ints(*vals: int) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSInteger.get(v))
    return arr


def _t0(
    bits: int,
    order: int,
    size: COSArray,
    domain: COSArray,
    rng: COSArray,
    encode: COSArray | None,
    decode: COSArray | None,
    body: bytes,
) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 0)
    s.set_item("Domain", domain)
    s.set_item("Range", rng)
    s.set_item("Size", size)
    s.set_int("BitsPerSample", bits)
    if order != 1:
        s.set_int("Order", order)
    if encode is not None:
        s.set_item("Encode", encode)
    if decode is not None:
        s.set_item("Decode", decode)
    s.set_data(body)
    return s


def _build_functions() -> dict[str, list[PDFunction]]:
    """Mirror FunctionType0OrderProbe's function construction. The value is a
    list because the two /Order batteries reuse the names ``ord1`` / ``ord3``
    against a single shared function each."""
    b4 = bytes([0, 64, 192, 255])
    fns: dict[str, list[PDFunction]] = {}

    fns["ord1"] = [
        PDFunction.create(
            _t0(8, 1, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4)
        )
    ]
    fns["ord3"] = [
        PDFunction.create(
            _t0(8, 3, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4)
        )
    ]
    fns["size1"] = [
        PDFunction.create(
            _t0(8, 1, _ints(1), _floats(0, 1), _floats(0, 1), None, None, bytes([128]))
        )
    ]
    fns["invenc"] = [
        PDFunction.create(
            _t0(8, 1, _ints(4), _floats(0, 1), _floats(0, 1), _floats(3, 0), None, b4)
        )
    ]
    fns["invdec"] = [
        PDFunction.create(
            _t0(8, 1, _ints(4), _floats(0, 1), _floats(0, 1), None, _floats(1, 0), b4)
        )
    ]
    b22 = bytes([0, 100, 200, 255])
    fns["bilin"] = [
        PDFunction.create(
            _t0(
                8,
                1,
                _ints(2, 2),
                _floats(0, 1, 0, 1),
                _floats(0, 255),
                None,
                _floats(0, 255),
                b22,
            )
        )
    ]
    fns["bit1"] = [
        PDFunction.create(
            _t0(1, 1, _ints(4), _floats(0, 1), _floats(0, 1), None, None, bytes([0xB0]))
        )
    ]
    fns["bit16"] = [
        PDFunction.create(
            _t0(
                16,
                1,
                _ints(2),
                _floats(0, 1),
                _floats(0, 1),
                None,
                None,
                bytes([0, 0, 0xFF, 0xFF]),
            )
        )
    ]
    fns["bit12"] = [
        PDFunction.create(
            _t0(
                12,
                1,
                _ints(2),
                _floats(0, 1),
                _floats(0, 1),
                None,
                None,
                bytes([0x00, 0x0F, 0xFF]),
            )
        )
    ]
    fns["domclamp"] = [
        PDFunction.create(
            _t0(8, 1, _ints(4), _floats(0.2, 0.8), _floats(0, 1), None, None, b4)
        )
    ]
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
def test_type0_order_matches_pdfbox() -> None:
    java_text = run_probe_text("FunctionType0OrderProbe")
    expected = _parse_probe_lines(java_text)
    assert expected, "probe produced no FUNC lines"

    fns = _build_functions()
    mismatches: list[str] = []
    covered: set[str] = set()

    for name, inputs, exp_out in expected:
        candidates = fns.get(name)
        assert candidates, f"no pypdfbox function built for probe entry {name!r}"
        fn = candidates[0]
        covered.add(name)

        assert exp_out is not None, f"unexpected PDFBox error for {name} {inputs}"
        got = fn.eval(list(inputs))
        if len(got) != len(exp_out):
            mismatches.append(
                f"{name} {inputs}: arity {len(got)} != java {len(exp_out)}"
            )
            continue
        for j, (g, e) in enumerate(zip(got, exp_out, strict=True)):
            if abs(g - e) > _TOL:
                mismatches.append(
                    f"{name} {inputs}[{j}]: py={g:.6f} != java={e:.6f}"
                )

    assert not mismatches, "Type 0 order divergences vs PDFBox:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), (
        f"probe / pypdfbox battery drift: only-in-py={set(fns) - covered}"
    )
