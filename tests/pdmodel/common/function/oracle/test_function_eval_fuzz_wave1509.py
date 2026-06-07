"""Live PDFBox differential fuzz parity for PDF function construction +
evaluation (wave 1509).

Drives ``oracle/probes/FunctionEvalFuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* COS specs and asserting each
``CASE`` line matches. Complements the existing eval oracles (which assume a
well-formed spec) by fuzzing the construction-leniency contract and the
malformed-spec eval corners.

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR> [eval=<ERR | f0 f1 ...>]

Semantics:
  - ``create=ERR`` — upstream ``PDFunction.create`` threw.
  - ``create=ok eval=ERR`` — construction succeeded, ``eval`` threw.
  - ``create=ok eval=<floats>`` — both succeeded.

Where pypdfbox *intentionally* diverges from upstream's construction contract
(documented in CHANGES.md, wave 1509), the case is listed in
``_CONSTRUCT_DIVERGENCES`` with the pypdfbox-side expectation and a citation.
For every other case the probe's behaviour is the contract pypdfbox must meet.

Key fix pinned this wave: pypdfbox's Type 4 parser previously rejected several
malformed brace shapes (missing close, stray close, trailing tokens, absent
outer wrapper) that upstream ``InstructionSequenceBuilder`` tolerates. Wave 1509
aligned the parser with upstream's lenient stack semantics, so the ``t4_*``
brace-corner cases below now match Java byte-for-byte.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-4


# ---------- COS builders (mirror FunctionEvalFuzzProbe.java) ----------


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    arr.set_float_array([float(v) for v in vals])
    return arr


def _ints(*vals: int) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSInteger.get(v))
    return arr


def _pack(bits_per_sample: int, *samples: int) -> bytes:
    bits = bits_per_sample * len(samples)
    nbytes = (bits + 7) // 8
    out = bytearray(nbytes)
    pos = 0
    for sample in samples:
        for k in range(bits_per_sample - 1, -1, -1):
            if (sample >> k) & 1:
                out[pos >> 3] |= 0x80 >> (pos & 7)
            pos += 1
    return bytes(out)


def _t0(
    bits_per_sample: int,
    size: COSArray,
    domain: COSArray,
    rng: COSArray,
    encode: COSArray | None,
    decode: COSArray | None,
    samples: bytes,
) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 0)
    s.set_int("BitsPerSample", bits_per_sample)
    s.set_item("Size", size)
    s.set_item("Domain", domain)
    s.set_item("Range", rng)
    if encode is not None:
        s.set_item("Encode", encode)
    if decode is not None:
        s.set_item("Decode", decode)
    s.set_data(samples)
    return s


def _t2(
    n: float | None,
    c0: COSArray | None,
    c1: COSArray | None,
    domain: tuple[float, float] = (0.0, 1.0),
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _floats(*domain))
    if n is not None:
        d.set_item("N", COSFloat(float(n)))
    if c0 is not None:
        d.set_item("C0", c0)
    if c1 is not None:
        d.set_item("C1", c1)
    return d


def _t4(ps: str) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", _floats(0, 1))
    s.set_item("Range", _floats(-1000, 1000))
    s.set_data(ps.encode("ascii"))
    return s


def _t3_single() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    d.set_item("Domain", _floats(0, 1))
    fns = COSArray()
    fns.add(_t2(1.0, _floats(0), _floats(1)))
    d.set_item("Functions", fns)
    d.set_item("Bounds", COSArray())
    d.set_item("Encode", _floats(0, 1))
    return d


def _t3_two() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    d.set_item("Domain", _floats(0, 1))
    fns = COSArray()
    fns.add(_t2(1.0, _floats(0), _floats(10)))
    fns.add(_t2(1.0, _floats(10), _floats(20)))
    d.set_item("Functions", fns)
    d.set_item("Bounds", _floats(0.5))
    d.set_item("Encode", _floats(0, 1, 0, 1))
    return d


def _t3_rev_encode() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    d.set_item("Domain", _floats(0, 1))
    fns = COSArray()
    fns.add(_t2(1.0, _floats(0), _floats(10)))
    fns.add(_t2(1.0, _floats(0), _floats(10)))
    d.set_item("Functions", fns)
    d.set_item("Bounds", _floats(0.5))
    d.set_item("Encode", _floats(1, 0, 1, 0))
    return d


def _t3_zero_width() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    d.set_item("Domain", _floats(0, 1))
    fns = COSArray()
    fns.add(_t2(1.0, _floats(0), _floats(10)))
    fns.add(_t2(1.0, _floats(10), _floats(20)))
    fns.add(_t2(1.0, _floats(20), _floats(30)))
    d.set_item("Functions", fns)
    d.set_item("Bounds", _floats(0.5, 0.5))
    d.set_item("Encode", _floats(0, 1, 0, 1, 0, 1))
    return d


def _build_cases() -> dict[str, tuple[object, list[float] | None]]:
    """Return {case_name: (cos_spec, eval_input_or_None)} mirroring the probe.

    ``eval_input_or_None`` is ``None`` for construction-only cases (probe emits
    no ``eval=`` token).
    """
    cases: dict[str, tuple[object, list[float] | None]] = {}

    # ---- construction-leniency contract ----
    cases["create_null"] = (None, None)
    cases["create_name_identity"] = (
        COSName.get_pdf_name("Identity"),
        [0.3, 0.7],
    )
    cases["create_name_identity2"] = (COSName.get_pdf_name("Identity"), [0.5])
    cases["create_obj_identity"] = (
        COSObject(0, 0, resolved=COSName.get_pdf_name("Identity")),
        None,
    )
    cases["create_name_other"] = (COSName.get_pdf_name("Foo"), None)
    cases["create_array"] = (_floats(1, 2, 3), None)
    cases["create_int"] = (COSInteger.get(5), None)

    no_type = COSDictionary()
    no_type.set_item("Domain", _floats(0, 1))
    cases["create_no_functiontype"] = (no_type, None)

    type1 = COSDictionary()
    type1.set_int("FunctionType", 1)
    cases["create_functiontype1"] = (type1, None)

    type5 = COSDictionary()
    type5.set_int("FunctionType", 5)
    cases["create_functiontype5"] = (type5, None)

    type_neg = COSDictionary()
    type_neg.set_int("FunctionType", -3)
    cases["create_functiontype_neg"] = (type_neg, None)

    t2dict = COSDictionary()
    t2dict.set_int("FunctionType", 2)
    t2dict.set_item("Domain", _floats(0, 1))
    t2dict.set_item("N", COSInteger.get(1))
    cases["create_obj_type2"] = (COSObject(0, 0, resolved=t2dict), [0.5])

    # ---- Type 0 BitsPerSample sweep ----
    for bps in (1, 2, 4, 8, 12, 16, 24, 32):
        mx = (2**31 - 1) if bps >= 31 else (1 << bps) - 1
        cases[f"t0_bps{bps}_at0"] = (
            _t0(bps, _ints(2), _floats(0, 1), _floats(0, 1), None, None, _pack(bps, 0, mx)),
            [0.0],
        )
        cases[f"t0_bps{bps}_at1"] = (
            _t0(bps, _ints(2), _floats(0, 1), _floats(0, 1), None, None, _pack(bps, 0, mx)),
            [1.0],
        )
        cases[f"t0_bps{bps}_mid"] = (
            _t0(bps, _ints(2), _floats(0, 1), _floats(0, 1), None, None, _pack(bps, 0, mx)),
            [0.5],
        )

    cases["t0_truncated"] = (
        _t0(8, _ints(4), _floats(0, 1), _floats(0, 1), None, None, _pack(8, 0, 255)),
        [1.0],
    )
    _oversized = _pack(8, 0, 128, 255, 64, 32, 16)
    cases["t0_oversized"] = (
        _t0(8, _ints(2), _floats(0, 1), _floats(0, 1), None, None, _oversized),
        [1.0],
    )
    cases["t0_empty_stream"] = (
        _t0(8, _ints(2), _floats(0, 1), _floats(0, 1), None, None, b""),
        [0.0],
    )
    cases["t0_size1"] = (
        _t0(8, _ints(1), _floats(0, 1), _floats(0, 1), None, None, _pack(8, 200)),
        [0.5],
    )
    cases["t0_encode_inv"] = (
        _t0(8, _ints(2), _floats(0, 1), _floats(0, 1), _floats(1, 0), None, _pack(8, 0, 255)),
        [0.0],
    )
    cases["t0_decode"] = (
        _t0(8, _ints(2), _floats(0, 1), _floats(0, 1), None, _floats(0, 100), _pack(8, 0, 255)),
        [1.0],
    )
    cases["t0_input_over"] = (
        _t0(8, _ints(2), _floats(0, 1), _floats(0, 1), None, None, _pack(8, 0, 255)),
        [5.0],
    )
    cases["t0_input_under"] = (
        _t0(8, _ints(2), _floats(0, 1), _floats(0, 1), None, None, _pack(8, 0, 255)),
        [-5.0],
    )

    # ---- Type 2 corners ----
    cases["t2_n_missing"] = (_t2(None, None, None), [0.5])
    cases["t2_n0"] = (_t2(0.0, None, None), [0.5])
    cases["t2_n_frac"] = (_t2(0.5, None, None), [0.25])
    cases["t2_n_neg"] = (_t2(-1.0, _floats(1, 2), _floats(3, 4)), [0.5])
    cases["t2_c0c1"] = (_t2(2.0, _floats(0, 10), _floats(1, 20)), [0.5])
    cases["t2_c0c1_mismatch"] = (_t2(1.0, _floats(0), _floats(1, 2)), [0.5])
    cases["t2_negbase_frac"] = (
        _t2(0.5, _floats(-1), _floats(-2), domain=(-1.0, 1.0)),
        [0.5],
    )
    cases["t2_oob_input"] = (_t2(2.0, None, None, domain=(-2.0, 2.0)), [1.5])

    # ---- Type 3 degenerate Bounds ----
    cases["t3_single"] = (_t3_single(), [0.5])
    cases["t3_at_bound"] = (_t3_two(), [0.5])
    cases["t3_reversed_encode"] = (_t3_rev_encode(), [0.5])
    cases["t3_zero_width"] = (_t3_zero_width(), [0.5])
    cases["t3_input_at_domain_max"] = (_t3_two(), [1.0])

    # ---- Type 4 operator / error corners ----
    cases["t4_add"] = (_t4("{ 2 add }"), [0.25])
    cases["t4_div0"] = (_t4("{ pop 1 0 div }"), [0.0])
    cases["t4_idiv0"] = (_t4("{ pop 1 0 idiv }"), [0.0])
    cases["t4_mod0"] = (_t4("{ pop 1 0 mod }"), [0.0])
    cases["t4_underflow"] = (_t4("{ pop add }"), [0.0])
    cases["t4_type_idiv_real"] = (_t4("{ pop 7.5 2 idiv }"), [0.0])
    cases["t4_unknown_op"] = (_t4("{ pop 1 frobnicate }"), [0.0])
    cases["t4_unbalanced"] = (_t4("{ pop 1 2 add"), [0.0])
    cases["t4_nested_if"] = (_t4("{ pop 1 { 2 { 3 } if } if }"), [0.0])
    cases["t4_ifelse"] = (_t4("{ pop true { 10 } { 20 } ifelse }"), [0.0])
    cases["t4_deep_nest"] = (_t4("{ pop { { { 5 } if } if } pop 5 }"), [0.0])
    cases["t4_sqrt_neg"] = (_t4("{ pop -1 sqrt }"), [0.0])
    cases["t4_empty_prog"] = (_t4("{ }"), [0.5])

    return cases


# Cases where pypdfbox *intentionally* diverges from upstream's construction
# contract (documented in CHANGES.md, wave 1509). Maps case name -> the
# pypdfbox-side outcome marker: "none" (create returns None), or
# "identity" (create returns the Identity sentinel). Everything not listed
# must match the probe's create/eval verdict exactly.
_CONSTRUCT_DIVERGENCES = {
    # Upstream: create(null) -> IOException ("Function must be a Dictionary,
    # but is (null)"). pypdfbox returns None so call sites that pass a missing
    # /Function entry don't need to null-guard before create (upstream callers
    # all null-check first). Robustness divergence — pre-wave-1509, documented.
    "create_null": "none",
    # Upstream: a COSObject wrapping the /Identity name is dereferenced to a
    # COSName, which is not a COSDictionary -> IOException (the IDENTITY check
    # is a by-reference test on the *raw* arg, before deref). pypdfbox
    # dereferences first then value-matches the name, so it returns the
    # Identity sentinel. Lenient robustness divergence — pinned both sides.
    "create_obj_identity": "identity",
}


def _py_verdict(name: str, spec: object, eval_input: list[float] | None) -> str:
    """Reproduce the probe's CASE line for pypdfbox."""
    try:
        fn = PDFunction.create(spec)
    except Exception:  # noqa: BLE001 - mirror the probe's catch-all
        return "create=ERR"
    if fn is None:
        # pypdfbox-only outcome (upstream would have raised). The caller maps
        # this via _CONSTRUCT_DIVERGENCES.
        return "create=none"
    if eval_input is None:
        return "create=ok"
    try:
        out = fn.eval(eval_input)
    except Exception:  # noqa: BLE001
        return "create=ok eval=ERR"
    return "create=ok eval=" + " ".join(f"{v:.6f}" for v in out)


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        name, _, verdict = rest.partition(" ")
        out[name] = verdict
    return out


def _floats_close(a: str, b: str) -> bool:
    fa = a.split()
    fb = b.split()
    if len(fa) != len(fb):
        return False
    for sa, sb in zip(fa, fb, strict=True):
        if sa == sb:
            continue
        try:
            va, vb = float(sa), float(sb)
        except ValueError:
            return False
        if math.isnan(va) and math.isnan(vb):
            continue
        if abs(va - vb) > _TOL:
            return False
    return True


@requires_oracle
def test_function_eval_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text("FunctionEvalFuzzProbe"))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    # Every probe case must be reproduced here (and vice versa).
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, (spec, eval_input) in cases.items():
        java = probe[name]
        py = _py_verdict(name, spec, eval_input)

        if name in _CONSTRUCT_DIVERGENCES:
            mode = _CONSTRUCT_DIVERGENCES[name]
            if mode == "none" and (java != "create=ERR" or py != "create=none"):
                # Upstream raised; pypdfbox returns None.
                mismatches.append(f"{name}: java={java!r} py={py!r} (expected none)")
            elif mode == "identity" and (
                java != "create=ERR" or not py.startswith("create=ok")
            ):
                # Upstream raised; pypdfbox builds Identity and evals it.
                mismatches.append(f"{name}: java={java!r} py={py!r} (expected identity)")
            continue

        # Non-divergent cases: verdict must match. For eval-with-floats lines,
        # compare numerically within tolerance; otherwise compare verbatim.
        if java.startswith("create=ok eval=") and py.startswith("create=ok eval="):
            jv = java[len("create=ok eval=") :]
            pv = py[len("create=ok eval=") :]
            if jv == "ERR" or pv == "ERR":
                if jv != pv:
                    mismatches.append(f"{name}: java={java!r} py={py!r}")
            elif not _floats_close(jv, pv):
                mismatches.append(f"{name}: java={java!r} py={py!r}")
        elif java != py:
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "function fuzz divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_probe_covers_all_function_types() -> None:
    """Sanity: the corpus spans Type 0/2/3/4 + the construction battery."""
    probe = _parse_probe(run_probe_text("FunctionEvalFuzzProbe"))
    assert any(k.startswith("t0_") for k in probe)
    assert any(k.startswith("t2_") for k in probe)
    assert any(k.startswith("t3_") for k in probe)
    assert any(k.startswith("t4_") for k in probe)
    assert any(k.startswith("create_") for k in probe)
    # Lenient brace-corner regression guard (the wave-1509 fix).
    assert probe["t4_unbalanced"] == "create=ok eval=3.000000"


def test_unbalanced_brace_is_lenient_oracle_free() -> None:
    """Oracle-free frozen copy of the wave-1509 fix: a Type 4 program with a
    missing closing brace must still evaluate (upstream-faithful lenient
    parser), not raise."""
    fn = PDFunction.create(_t4("{ pop 1 2 add"))
    assert fn.eval([0.0]) == pytest.approx([3.0], abs=_TOL)


def test_trailing_tokens_after_outer_brace_are_lenient_oracle_free() -> None:
    """Frozen copy: tokens after the outer ``}`` stay in the main sequence
    (upstream ``InstructionSequenceBuilder`` semantics)."""
    fn = PDFunction.create(_t4("{ 1 } 99"))
    assert fn.eval([0.0]) == pytest.approx([99.0], abs=_TOL)
