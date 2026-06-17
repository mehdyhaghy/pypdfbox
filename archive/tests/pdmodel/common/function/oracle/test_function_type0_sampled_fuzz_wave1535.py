"""Live PDFBox differential parity for Type 0 (sampled) function eval over
MALFORMED dictionaries (wave 1535, agent D).

Where ``test_function_type0_order_oracle`` / ``..._degenerate_oracle`` and the
Bit32 probe cover valid bit-widths, degenerate shapes and the /Order no-op, this
pins the malformed-dictionary surfaces against the live PDFBox 3.0.7 jar:

  - /Size missing / wrong length / zero / negative / non-numeric (PDFBox errors;
    pypdfbox errors).
  - /BitsPerSample off-spec but readable (0, 3) — PDFBox does NOT validate
    against Table 38, it reads any width via ``readBits``; pypdfbox mirrors that
    for the determinate [0, 32] range, so 0/3 evaluate (not raise).
  - sample stream truncated / empty — per-sample zero-padding matches PDFBox.
  - /Encode missing (default), present-but-short (PDFBox NPEs → ERR; pypdfbox
    raises), /Decode missing / present-but-short likewise.
  - boundary vs interpolated inputs, 1-D vs 2-D shapes, Domain/Range clipping.

Two PINNED divergences (asserted both-sides, NOT as a match):
  - ``size_huge``: PDFBox eagerly allocates the full sample grid → OOM /
    NegativeArraySizeError (not an IOException, so it propagates) → ERR.
    pypdfbox reads samples lazily so it never allocates the grid and returns
    0.0. pypdfbox's lazy read is strictly more robust; matching PDFBox would
    mean deliberately allocating a billion-cell array.
  - ``bits64``: /BitsPerSample 33..64 is accepted by PDFBox but its output
    depends on a Java ``(int)`` long-truncation plus a stateful "first eval
    throws, the cached sample grid is left zeroed, later evals return 0" quirk
    that is not bit-reproducible in Python; pypdfbox raises for those widths.

The Java side is ``oracle/probes/FunctionType0SampledFuzzProbe.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-4

# Probe batteries whose PDFBox vs pypdfbox results intentionally differ — pinned
# both-sides (see module docstring). These are excluded from the strict-match
# loop and verified explicitly afterwards.
_PINNED = {"size_huge", "bits64"}


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
    """Mirror FunctionType0SampledFuzzProbe's function construction exactly."""
    b4 = bytes([0, 64, 192, 255])
    b22 = bytes([0, 100, 200, 255])
    b8 = bytes([0, 32, 64, 96, 128, 160, 192, 255])
    bad_size = COSArray()
    bad_size.add(COSName.get_pdf_name("X"))

    return {
        "size_missing": _t0(8, None, _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_len2": _t0(8, _ints(4, 4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_short2d": _t0(
            8, _ints(2), _floats(0, 1, 0, 1), _floats(0, 1), None, None, b4
        ),
        "size_zero": _t0(8, _ints(0), _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_neg": _t0(8, _ints(-4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "size_huge": _t0(
            8, _ints(1000000000), _floats(0, 1), _floats(0, 1), None, None, b4
        ),
        "bits0": _t0(0, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "bits3": _t0(3, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "bits64": _t0(64, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "trunc_body": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 1), None, None, bytes([0, 64])
        ),
        "empty_body": _t0(8, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b""),
        "enc_missing": _t0(8, _ints(4), _floats(0, 1), _floats(0, 1), None, None, b4),
        "enc_short": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 1), _floats(1), None, b4
        ),
        "enc_short2d": _t0(
            8,
            _ints(2, 2),
            _floats(0, 1, 0, 1),
            _floats(0, 255),
            _floats(0, 1),
            _floats(0, 255),
            b22,
        ),
        "dec_missing": _t0(8, _ints(4), _floats(0, 1), _floats(0, 10), None, None, b4),
        "dec_short": _t0(
            8, _ints(4), _floats(0, 1), _floats(0, 10), None, _floats(5), b4
        ),
        "grid8": _t0(8, _ints(8), _floats(0, 1), _floats(0, 1), None, None, b8),
        "bilin2d": _t0(
            8, _ints(2, 2), _floats(0, 1, 0, 1), _floats(0, 255), None, _floats(0, 255), b22
        ),
        "dom_edge": _t0(
            8, _ints(4), _floats(0.2, 0.8), _floats(0, 1), None, None, b4
        ),
        "range_clip": _t0(
            8, _ints(4), _floats(0, 1), _floats(0.25, 0.75), None, _floats(0, 1), b4
        ),
        "size_nonnum": _t0(8, bad_size, _floats(0, 1), _floats(0, 1), None, None, b4),
    }


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


def _eval_or_error(fn: PDFunction | None, inputs: list[float]) -> list[float] | None:
    """Return outputs, or None if pypdfbox errors (or the dict failed to build)."""
    if fn is None:
        return None
    try:
        return fn.eval(list(inputs))
    except Exception:
        return None


@requires_oracle
def test_type0_sampled_fuzz_matches_pdfbox() -> None:
    java_text = run_probe_text("FunctionType0SampledFuzzProbe")
    expected = _parse_probe_lines(java_text)
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
            # PDFBox errored — pypdfbox must error too.
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

    assert not mismatches, "Type 0 sampled-fuzz divergences vs PDFBox:\n" + "\n".join(
        mismatches
    )
    assert covered == set(fns), (
        f"probe / pypdfbox battery drift: only-in-py={set(fns) - covered}"
    )


@requires_oracle
def test_type0_size_huge_is_pinned_divergence() -> None:
    """PDFBox errors (eager full-grid allocation OOMs); pypdfbox reads lazily and
    returns 0.0. Pin BOTH sides so the divergence is documented, not silent."""
    java = {
        (name, tuple(inp)): out
        for name, inp, out in _parse_probe_lines(
            run_probe_text("FunctionType0SampledFuzzProbe")
        )
        if name == "size_huge"
    }
    assert java, "probe emitted no size_huge lines"
    for out in java.values():
        assert out is None, "expected PDFBox to ERR on /Size=1e9 (eager grid alloc)"

    fn = _build_functions()["size_huge"]
    assert fn is not None
    # pypdfbox does NOT allocate the grid — lazy per-sample read, never OOMs.
    assert fn.eval([0.0]) == pytest.approx([0.0])
    assert fn.eval([0.5]) == pytest.approx([0.0])


@requires_oracle
def test_type0_bits64_is_pinned_divergence() -> None:
    """PDFBox accepts 33..64-bit widths (returns 0.0 here via its stateful
    zeroed-cache quirk); pypdfbox raises ValueError because that width is past
    its determinate [0, 32] parity range. Pin BOTH sides."""
    java = {
        (name, tuple(inp)): out
        for name, inp, out in _parse_probe_lines(
            run_probe_text("FunctionType0SampledFuzzProbe")
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
