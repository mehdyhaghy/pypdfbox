"""Live PDFBox differential parity for PDFunctionType0 degenerate / boundary
eval cases (wave 1482).

Drives ``oracle/probes/FunctionType0DegenerateProbe.java`` and
``oracle/probes/FunctionType0Bit32Probe.java`` against pypdfbox, rebuilding
the *identical* COS objects and asserting eval outputs match. The probes are
the oracle of record; the hand-written literals in
``tests/pdmodel/common/function/test_pd_function_type0_degenerate_wave1482.py``
are frozen copies of these same values for oracle-free regression.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-5


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    arr.set_float_array([float(v) for v in vals])
    return arr


def _ints(*vals: int) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSInteger.get(int(v)))
    return arr


def _pack(values: list[int], bits: int) -> bytes:
    total_bits = len(values) * bits
    big = 0
    mask = (1 << bits) - 1
    for v in values:
        big = (big << bits) | (v & mask)
    pad = (-total_bits) % 8
    big <<= pad
    nbytes = (total_bits + pad) // 8
    return big.to_bytes(nbytes, "big") if nbytes else b""


def _pack32(values: list[int]) -> bytes:
    out = bytearray()
    for v in values:
        out += (v & 0xFFFFFFFF).to_bytes(4, "big")
    return bytes(out)


def _type0(
    body: bytes,
    size: list[int],
    bits: int,
    domain: list[float],
    rng: list[float],
    encode: list[float] | None = None,
    decode: list[float] | None = None,
) -> PDFunction:
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
    s.set_data(body)
    return PDFunction.create(s)


def _build_degenerate() -> dict[str, PDFunction]:
    fns: dict[str, PDFunction] = {}
    fns["T0size1"] = _type0(_pack([200], 8), [1], 8, [0, 1], [0, 255])
    fns["T0collapse"] = _type0(_pack([10, 20, 30], 8), [1, 3], 8, [0, 1, 0, 1], [0, 255])
    fns["T0empty"] = _type0(b"", [3], 8, [0, 1], [0, 255])
    fns["T0short"] = _type0(bytes([100]), [3], 8, [0, 1], [0, 255])
    fns["T0dom"] = _type0(
        _pack([0, 40, 80, 120, 160], 8), [5], 8, [-2, 6], [0, 255]
    )
    fns["T01bit"] = _type0(_pack([0, 1, 1, 0], 1), [4], 1, [0, 1], [0, 1])
    fns["T02bit"] = _type0(_pack([0, 1, 2, 3], 2), [4], 2, [0, 1], [0, 3])
    fns["T024bit"] = _type0(_pack([0, 16777215], 24), [2], 24, [0, 1], [0, 1])
    fns["T032bit"] = _type0(_pack32([0, 4294967295]), [2], 32, [0, 1], [0, 1])
    return fns


def _build_bit32() -> dict[str, PDFunction]:
    fns: dict[str, PDFunction] = {}
    cases = {
        "T32_maxpos": [0, 0x7FFFFFFF],
        "T32_min": [0, 0x80000000],
        "T32_neg1": [0, 0xFFFFFFFF],
        "T32_bothneg": [0x80000000, 0xFFFFFFFF],
    }
    for name, codes in cases.items():
        fns[name] = _type0(_pack32(codes), [2], 32, [0, 1], [-2, 2])
    fns["T32_wide"] = _type0(_pack32([0, 0xFFFFFFFF]), [2], 32, [0, 1], [-5, 5])
    return fns


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
        outputs = [float(v) for v in tail.split()] if tail else []
        out.append((name, inputs, outputs))
    return out


def _check(probe: str, fns: dict[str, PDFunction]) -> None:
    expected = _parse(run_probe_text(probe))
    assert expected, f"probe {probe} produced no FUNC lines"
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
            if abs(g - e) > _TOL:
                mismatches.append(
                    f"{name} {inputs}[{j}]: py={g:.6f} != java={e:.6f}"
                )
    assert not mismatches, f"{probe} divergences:\n" + "\n".join(mismatches)
    assert covered == set(fns), f"{probe} battery drift: only-in-py={set(fns) - covered}"


@requires_oracle
def test_type0_degenerate_matches_pdfbox() -> None:
    _check("FunctionType0DegenerateProbe", _build_degenerate())


@requires_oracle
def test_type0_bit32_signed_cast_matches_pdfbox() -> None:
    _check("FunctionType0Bit32Probe", _build_bit32())
