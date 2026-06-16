"""Live PDFBox differential parity for Type 0 (sampled) function eval — wave
1540, agent A. Focus: the NON-NORMALISING clip surfaces.

The wave-1539 Type 4 audit established that ``PDFunctionType4.eval`` clips with
the scalar ``clipToRange(F,F,F)`` (no min/max swap), not the base normalising
array clip. Disassembling ``PDFunctionType0.eval`` (jar 3.0.7) confirmed the
same: it clips inputs (to ``/Domain``), the encoded coordinate (to
``[0, Size-1]``) and outputs (to ``/Range``) with ``clipToRange(F,F,F)`` —
``if x < min -> min; if x > max -> max; else x`` — never swapping a reversed
pair. pypdfbox's ``PDFunctionType0.eval`` previously routed input/output through
the base ``clip_input`` / ``clip_output``, which DO swap a reversed ``(min,max)``
pair, so a reversed ``/Domain`` or ``/Range`` produced different output than
Java. Wave 1540 added a local non-normalising clip (mirroring the Type 3 / Type 4
overrides) and this test pins the corrected behaviour against the live jar.

Surfaces fuzzed (35 batteries):
  - reversed /Domain, /Range, /Encode, /Decode (alone and combined).
  - clamping exactly at / beyond Domain & Range edges.
  - empty / odd-length / non-numeric /Domain /Range /Encode /Decode; over-long
    /Encode.
  - /Size zero / negative / non-numeric / wrong-arity.
  - /BitsPerSample sweep 1,2,4,8,12,16,24,32 + off-spec 0,3 + invalid 64.
  - sample stream too short / too long.
  - nearest vs linear at grid points and between.
  - multi-input multi-output sampling; reversed Domain on a second axis.
  - getNumberOfOutputParameters projected per battery (NOUT lines).

PINNED divergences (asserted both-sides, NOT as a match):
  - ``bits64``: /BitsPerSample 33..64 is accepted by PDFBox (its readBits throws
    EOFException, the cached grid is left zeroed, eval returns 0.0); pypdfbox
    raises ValueError because that width is past its determinate [0, 32] parity
    range (same divergence pinned in wave 1535).
  - ``dom_nonnum`` / ``range_nonnum`` / ``enc_nonnum`` / ``dec_nonnum``: a
    /Domain /Range /Encode /Decode array carrying a non-numeric entry (a COSName)
    makes PDFBox throw (``COSArray.toFloatArray`` / PDRange does
    ``(COSNumber) obj`` -> ClassCastException) -> ERR. pypdfbox's
    ``COSArray.to_float_array`` is intentionally lenient (non-numeric -> 0.0, a
    repo-wide design choice shared by every numeric COS accessor), so eval
    proceeds and produces a number. This is a pre-existing global divergence
    rooted in the shared COS layer, not in PDFunctionType0; fixing it would mean
    making every numeric COSArray accessor strict, which is out of this surface's
    scope. Pinned both-sides so the gap is documented, not silent.

The Java side is ``oracle/probes/FunctionType0FuzzWave1540Probe.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-4

# Batteries whose PDFBox vs pypdfbox eval results intentionally differ — pinned
# both-sides (see module docstring), excluded from the strict-match loop.
_PINNED = {"bits64", "dom_nonnum", "range_nonnum", "enc_nonnum", "dec_nonnum"}

# The non-numeric batteries: PDFBox throws on the COSName-in-array, pypdfbox
# evaluates (lenient to_float_array). Verified both-sides below.
_NONNUM = {"dom_nonnum", "range_nonnum", "enc_nonnum", "dec_nonnum"}


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
    size: COSArray | None,
    domain: COSArray,
    rng: COSArray,
    encode: COSArray | None,
    decode: COSArray | None,
    body: bytes,
) -> PDFunction | None:
    s = COSStream()
    s.set_int("FunctionType", 0)
    s.set_item("Domain", domain)
    s.set_item("Range", rng)
    if size is not None:
        s.set_item("Size", size)
    s.set_int("BitsPerSample", bits)
    if encode is not None:
        s.set_item("Encode", encode)
    if decode is not None:
        s.set_item("Decode", decode)
    s.set_data(body)
    try:
        return PDFunction.create(s)
    except Exception:
        return None


def _build_functions() -> dict[str, PDFunction | None]:
    """Mirror FunctionType0FuzzWave1540Probe's construction exactly."""
    b4 = bytes([0, 64, 192, 255])

    dom_bad = COSArray()
    dom_bad.add(COSName.get_pdf_name("X"))
    dom_bad.add(COSInteger.get(1))

    range_bad = COSArray()
    range_bad.add(COSInteger.get(0))
    range_bad.add(COSName.get_pdf_name("Y"))

    enc_bad = COSArray()
    enc_bad.add(COSName.get_pdf_name("E"))
    enc_bad.add(COSInteger.get(3))

    dec_bad = COSArray()
    dec_bad.add(COSInteger.get(0))
    dec_bad.add(COSName.get_pdf_name("D"))

    size_bad = COSArray()
    size_bad.add(COSName.get_pdf_name("S"))

    b1 = bytes([0b10110010])
    b2 = bytes([0x1B])
    b4w = bytes([0x0F, 0xA5])
    b12 = bytes([0x00, 0x0F, 0xFF])
    b16 = bytes([0x00, 0x00, 0xFF, 0xFF])
    b24 = bytes([0, 0, 0, 0xFF, 0xFF, 0xFF])
    b32 = bytes([0, 0, 0, 0, 0xFF, 0xFF, 0xFF, 0xFF])
    b8 = bytes([0, 32, 64, 96, 128, 160, 192, 255])
    mio = bytes([0, 255, 64, 192, 128, 32, 200, 16])

    return {
        "dom_rev": _t0(8, _ints(4), _floats(1, 0), _floats(0, 1), None, None, b4),
        "range_rev": _t0(
            8, _ints(4), _floats(0, 1), _floats(1, 0), None, _floats(0, 1), b4
        ),
        "enc_rev": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 1), _floats(3, 0), None, b4
        ),
        "dec_rev": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 1), None, _floats(1, 0), b4
        ),
        "dom_range_rev": _t0(
            8, _ints(4), _floats(0.8, 0.2), _floats(1, 0), None, _floats(0, 1), b4
        ),
        "dom_clamp": _t0(
            8, _ints(4), _floats(0.2, 0.8), _floats(0, 1), None, None, b4
        ),
        "range_clamp": _t0(
            8, _ints(4), _floats(0, 1), _floats(0.25, 0.75), None, _floats(0, 1), b4
        ),
        "dom_empty": _t0(8, _ints(4), _floats(), _floats(0, 1), None, None, b4),
        "dom_odd": _t0(8, _ints(4), _floats(0, 1, 2), _floats(0, 1), None, None, b4),
        "range_empty": _t0(8, _ints(4), _floats(0, 1), _floats(), None, None, b4),
        "range_odd": _t0(8, _ints(4), _floats(0, 1), _floats(0, 1, 2), None, None, b4),
        "dom_nonnum": _t0(8, _ints(4), dom_bad, _floats(0, 1), None, None, b4),
        "range_nonnum": _t0(8, _ints(4), _floats(0, 1), range_bad, None, None, b4),
        "enc_nonnum": _t0(8, _ints(4), _floats(0, 1), _floats(0, 1), enc_bad, None, b4),
        "dec_nonnum": _t0(8, _ints(4), _floats(0, 1), _floats(0, 1), None, dec_bad, b4),
        "enc_long": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 1), _floats(0, 3, 9, 9), None, b4
        ),
        "size_zero": _t0(8, _ints(0), _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_neg": _t0(8, _ints(-4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_nonnum": _t0(8, size_bad, _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_arity": _t0(8, _ints(4, 4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "bits1": _t0(1, _ints(8), _floats(0, 1), _floats(0, 1), None, None, b1),
        "bits2": _t0(2, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b2),
        "bits4": _t0(4, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4w),
        "bits12": _t0(12, _ints(2), _floats(0, 1), _floats(0, 1), None, None, b12),
        "bits16": _t0(16, _ints(2), _floats(0, 1), _floats(0, 1), None, None, b16),
        "bits24": _t0(24, _ints(2), _floats(0, 1), _floats(0, 1), None, None, b24),
        "bits32": _t0(32, _ints(2), _floats(0, 1), _floats(0, 1), None, None, b32),
        "bits0": _t0(0, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "bits3": _t0(3, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "bits64": _t0(64, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "body_short": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 1), None, None, bytes([0, 64])
        ),
        "body_long": _t0(
            8,
            _ints(4),
            _floats(0, 1),
            _floats(0, 1),
            None,
            None,
            bytes([0, 64, 192, 255, 1, 2, 3, 4]),
        ),
        "grid8": _t0(8, _ints(8), _floats(0, 1), _floats(0, 1), None, None, b8),
        "mio_2x2": _t0(
            8,
            _ints(2, 2),
            _floats(0, 1, 0, 1),
            _floats(0, 1, 0, 1),
            None,
            _floats(0, 255, 0, 255),
            mio,
        ),
        "mio_dom_rev": _t0(
            8,
            _ints(2, 2),
            _floats(0, 1, 1, 0),
            _floats(0, 1),
            None,
            _floats(0, 1),
            bytes([0, 100, 200, 255]),
        ),
    }


def _parse_func_lines(
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
            out.append((name, inputs, None))
        else:
            outputs = [float(v) for v in tail.split()] if tail else []
            out.append((name, inputs, outputs))
    return out


def _parse_nout_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("NOUT "):
            _, name, val = line.split()
            out[name] = val
    return out


def _eval_or_error(fn: PDFunction | None, inputs: list[float]) -> list[float] | None:
    if fn is None:
        return None
    try:
        return fn.eval(list(inputs))
    except Exception:
        return None


@requires_oracle
def test_type0_fuzz_wave1540_matches_pdfbox() -> None:
    java_text = run_probe_text("FunctionType0FuzzWave1540Probe")
    expected = _parse_func_lines(java_text)
    assert expected, "probe produced no FUNC lines"

    fns = _build_functions()
    mismatches: list[str] = []
    covered: set[str] = set()

    for name, inputs, exp_out in expected:
        assert name in fns, f"no pypdfbox function built for probe entry {name!r}"
        covered.add(name)
        if name in _PINNED:
            continue
        got = _eval_or_error(fns[name], inputs)
        if exp_out is None:
            if got is not None:
                mismatches.append(
                    f"{name} {inputs}: java=ERR py={[round(v, 6) for v in got]}"
                )
            continue
        if got is None:
            mismatches.append(f"{name} {inputs}: java={exp_out} py=ERR")
            continue
        if len(got) != len(exp_out):
            mismatches.append(
                f"{name} {inputs}: arity {len(got)} != java {len(exp_out)}"
            )
            continue
        for j, (g, e) in enumerate(zip(got, exp_out, strict=True)):
            if abs(g - e) > _TOL:
                mismatches.append(f"{name} {inputs}[{j}]: py={g:.6f} != java={e:.6f}")

    assert not mismatches, "Type 0 wave-1540 fuzz divergences vs PDFBox:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), (
        f"probe / pypdfbox battery drift: only-in-py={set(fns) - covered}"
    )


@requires_oracle
def test_type0_fuzz_wave1540_reversed_domain_non_normalising() -> None:
    """Pin the wave-1540 fix: a reversed /Domain is NOT swapped — eval clips
    with the non-normalising scalar clipToRange, so input 0.0 maps to the LOW
    sample (0.0) and input 1.0 to the HIGH sample (1.0), exactly as Java does.
    Before the fix the base normalising clip_input swapped [1,0]->[0,1] and
    produced the inverted result."""
    fn = _build_functions()["dom_rev"]
    assert fn is not None
    assert fn.eval([0.0]) == pytest.approx([0.0])
    assert fn.eval([1.0]) == pytest.approx([1.0])
    # Reversed /Range likewise honoured (output collapses to lower max).
    rng = _build_functions()["range_rev"]
    assert rng is not None
    assert rng.eval([0.0]) == pytest.approx([1.0])
    assert rng.eval([1.0]) == pytest.approx([0.0])


@requires_oracle
def test_type0_fuzz_wave1540_num_output_parameters() -> None:
    """getNumberOfOutputParameters() projection matches PDFBox per battery."""
    java_text = run_probe_text("FunctionType0FuzzWave1540Probe")
    java_nout = _parse_nout_lines(java_text)
    assert java_nout, "probe emitted no NOUT lines"

    fns = _build_functions()
    mismatches: list[str] = []
    for name, fn in fns.items():
        assert name in java_nout, f"probe missing NOUT for {name!r}"
        exp = java_nout[name]
        if fn is None:
            got = "ERR"
        else:
            try:
                got = str(fn.get_number_of_output_parameters())
            except Exception:
                got = "ERR"
        if got != exp:
            mismatches.append(f"{name}: py={got} != java={exp}")
    assert not mismatches, "NOUT divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_type0_fuzz_wave1540_nonnumeric_array_pinned_divergence() -> None:
    """A non-numeric (COSName) entry in /Domain /Range /Encode /Decode makes
    PDFBox throw -> ERR, while pypdfbox's lenient COSArray.to_float_array treats
    it as 0.0 and evaluates. Pin BOTH sides: Java must ERR on every input, and
    pypdfbox must return a (finite) result on at least the mid input."""
    java = _parse_func_lines(run_probe_text("FunctionType0FuzzWave1540Probe"))
    fns = _build_functions()
    for battery in _NONNUM:
        java_outs = [out for name, _inp, out in java if name == battery]
        assert java_outs, f"probe emitted no {battery} lines"
        assert all(out is None for out in java_outs), (
            f"expected PDFBox to ERR on every {battery} input"
        )
        fn = fns[battery]
        assert fn is not None
        # pypdfbox evaluates (does not raise) — lenient numeric coercion.
        result = fn.eval([0.5])
        assert result is not None


@requires_oracle
def test_type0_fuzz_wave1540_bits64_pinned_divergence() -> None:
    """PDFBox accepts 33..64-bit widths (readBits EOFs, zeroed cache -> 0.0);
    pypdfbox raises ValueError (past its determinate [0,32] parity range). Pin
    BOTH sides (same divergence as wave 1535)."""
    java = {
        tuple(inp): out
        for name, inp, out in _parse_func_lines(
            run_probe_text("FunctionType0FuzzWave1540Probe")
        )
        if name == "bits64"
    }
    assert java, "probe emitted no bits64 lines"
    for out in java.values():
        assert out == pytest.approx([0.0]), "expected PDFBox bits=64 -> 0.0"

    fn = _build_functions()["bits64"]
    assert fn is not None
    with pytest.raises(ValueError, match="BitsPerSample"):
        fn.eval([0.5])
