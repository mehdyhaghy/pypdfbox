"""Live PDFBox differential fuzz parity for the Type 2 (exponential
interpolation) and Type 3 (stitching) functions (wave 1544, agent B).

Drives ``oracle/probes/FunctionType23FuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* COS specs and asserting each
``CASE`` line matches. Complements the existing Type2/Type3 fuzz probes
(FunctionType2FuzzProbe, FunctionType3FuzzProbe, FunctionType23EdgeProbe) with
NEW angles focused on the interpolation / stitching math and the
``/C0`` ``/C1`` ``/N`` (Type 2) and ``/Functions`` ``/Bounds`` ``/Encode``
(Type 3) array handling — see the probe header for the full corpus.

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR> [eval=<ERR | f0 f1 ...>]

Real bug fixed this wave so the probe matches byte-for-byte (see CHANGES.md,
Wave 1544): ``PDFunctionType2.eval`` read ``/C0`` / ``/C1`` via the *tolerant*
``COSArray.to_float_array`` (non-numeric entry -> ``0.0``); upstream reads them
via ``getC0().toFloatArray()`` whose ``COSNumber`` cast throws on a non-numeric
entry, so eval must now raise (``t2_c0_non_numeric`` / ``t2_c1_non_numeric``
=> eval ERR).
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
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-3


# ---------- COS builders (mirror FunctionType23FuzzProbe.java) ----------


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(float(v)))
    return arr


def _t2(
    c0: COSArray | None,
    c1: COSArray | None,
    n: float | None,
    domain: COSArray | None,
    range_: COSArray | None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    if domain is not None:
        d.set_item("Domain", domain)
    if c0 is not None:
        d.set_item("C0", c0)
    if c1 is not None:
        d.set_item("C1", c1)
    if n is not None:
        d.set_item("N", COSFloat(float(n)))
    if range_ is not None:
        d.set_item("Range", range_)
    return d


def _child(c0: float, c1: float) -> COSDictionary:
    """Simple Type 2 child f(x) = c0 + x * (c1 - c0) over Domain [0, 1]."""
    return _t2(_floats(c0), _floats(c1), 1.0, _floats(0, 1), None)


def _fns(*children: COSDictionary) -> COSArray:
    arr = COSArray()
    for c in children:
        arr.add(c)
    return arr


def _t3(
    functions: COSArray | None,
    bounds: COSArray | None,
    encode: COSArray | None,
    domain: COSArray | None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    if domain is not None:
        d.set_item("Domain", domain)
    if functions is not None:
        d.set_item("Functions", functions)
    if bounds is not None:
        d.set_item("Bounds", bounds)
    if encode is not None:
        d.set_item("Encode", encode)
    return d


def _t4_child(ps: str, range_: COSArray) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", _floats(0, 1))
    s.set_item("Range", range_)
    with s.create_output_stream() as out:
        out.write(ps.encode("us-ascii"))
    return s


def _build_cases() -> list[tuple[str, object, list[float]]]:
    """Return ordered (case_name, cos_spec, eval_input) mirroring the probe.

    A list (not a dict) because several cases share a name across multiple
    inputs (the probe emits a separate CASE line per input, same name)."""
    dom01 = _floats(0, 1)
    cases: list[tuple[str, object, list[float]]] = []

    # ================= Type 2 =================

    # /N non-numeric => getFloat default -1 => x^-1
    n_non_num = _t2(_floats(0), _floats(1), None, _floats(0, 1), None)
    n_non_num.set_item("N", COSName.get_pdf_name("bogus"))
    for x in (0.25, 0.5, 1.0):
        cases.append(("t2_n_non_numeric", n_non_num, [x]))

    cases.append(
        ("t2_n_huge_neg_x1", _t2(_floats(0), _floats(1), -1000.0, _floats(0, 1), None), [1.0])
    )
    cases.append(
        (
            "t2_n_huge_neg_xhalf",
            _t2(_floats(0), _floats(1), -1000.0, _floats(0, 1), None),
            [0.5],
        )
    )
    cases.append(
        ("t2_big_n_x2", _t2(_floats(0), _floats(1), 10.0, _floats(0, 4), None), [2.0])
    )

    c0bad = _floats(0, 0)
    c0bad.set(1, COSName.get_pdf_name("X"))
    cases.append(
        ("t2_c0_non_numeric", _t2(c0bad, _floats(1, 1), 1.0, _floats(0, 1), None), [0.5])
    )

    c1bad = _floats(1, 1)
    c1bad.set(0, COSString("oops"))
    cases.append(
        ("t2_c1_non_numeric", _t2(_floats(0, 0), c1bad, 1.0, _floats(0, 1), None), [0.5])
    )

    cases.append(
        (
            "t2_partial_range",
            _t2(_floats(0, 0), _floats(100, -100), 1.0, _floats(0, 1), _floats(0, 10)),
            [0.5],
        )
    )

    for x in (0.0, 0.5, 1.0):
        cases.append(("t2_rev_domain", _t2(_floats(0), _floats(8), 1.0, _floats(1, 0), None), [x]))

    cases.append(
        ("t2_odd_domain", _t2(_floats(0), _floats(5), 1.0, _floats(0, 1, 2), None), [0.4])
    )

    cases.append(
        (
            "t2_extra_inputs",
            _t2(_floats(0), _floats(10), 1.0, _floats(0, 1), None),
            [0.3, 0.9, 0.1],
        )
    )

    for x in (0.0, 0.5):
        cases.append(("t2_n0_neg", _t2(_floats(-5), _floats(-2), 0.0, _floats(0, 1), None), [x]))

    # ================= Type 3 =================

    four = _fns(_child(0, 10), _child(20, 30), _child(40, 50), _child(60, 70))
    b3 = _floats(0.25, 0.5, 0.75)
    enc4 = _floats(0, 1, 0, 1, 0, 1, 0, 1)
    for x in (0.1, 0.3, 0.6, 0.9):
        cases.append(("t3_four_fns", _t3(four, b3, enc4, dom01), [x]))

    cases.append(
        (
            "t3_nan_input",
            _t3(_fns(_child(0, 10), _child(100, 110)), _floats(0.5), _floats(0, 1, 0, 1), dom01),
            [math.nan],
        )
    )

    bnan = _floats(0.5)
    bnan.set(0, COSFloat(math.nan))
    cases.append(
        (
            "t3_nan_bound",
            _t3(_fns(_child(0, 10), _child(100, 110)), bnan, _floats(0, 1, 0, 1), dom01),
            [0.5],
        )
    )

    cases.append(
        (
            "t3_rev_encode_selected",
            _t3(_fns(_child(0, 10), _child(0, 100)), _floats(0.5), _floats(0, 1, 1, 0), dom01),
            [0.75],
        )
    )

    cases.append(
        (
            "t3_encode_overshoot_childclip",
            _t3(_fns(_child(0, 10), _child(0, 100)), _floats(0.5), _floats(0, 1, 0, 4), dom01),
            [0.9],
        )
    )

    enc_bad_upper = _floats(0, 1, 0, 1)
    enc_bad_upper.set(2, COSName.get_pdf_name("Q"))
    cases.append(
        (
            "t3_bad_encode_unreached",
            _t3(_fns(_child(0, 10), _child(100, 110)), _floats(0.5), enc_bad_upper, dom01),
            [0.25],
        )
    )

    enc_bad0 = _floats(0, 1)
    enc_bad0.set(0, COSName.get_pdf_name("Z"))
    cases.append(
        (
            "t3_single_bad_encode0",
            _t3(_fns(_child(0, 10)), COSArray(), enc_bad0, dom01),
            [0.5],
        )
    )

    cases.append(
        (
            "t3_bound_eq_dom_max",
            _t3(_fns(_child(0, 10), _child(100, 110)), _floats(1.0), _floats(0, 1, 0, 1), dom01),
            [1.0],
        )
    )

    cases.append(
        (
            "t3_bound_eq_dom_min",
            _t3(_fns(_child(3, 7), _child(0, 1)), _floats(0.0), _floats(0, 1, 0, 1), dom01),
            [0.0],
        )
    )

    with_t4 = COSArray()
    with_t4.add(_child(0, 5))
    with_t4.add(_t4_child("{ 2 mul 10 mul }", _floats(0, 100)))
    cases.append(
        ("t3_type4_child", _t3(with_t4, _floats(0.5), _floats(0, 1, 0, 1), dom01), [0.75])
    )

    bint = COSArray()
    bint.add(COSInteger.get(0))
    cases.append(
        (
            "t3_int_bound",
            _t3(_fns(_child(0, 10), _child(100, 110)), bint, _floats(0, 1, 0, 1), _floats(-1, 1)),
            [0.5],
        )
    )

    cases.append(
        (
            "t3_single_extra_keys",
            _t3(_fns(_child(0, 20)), _floats(0.3, 0.6), _floats(0, 1, 0, 1, 0, 1), dom01),
            [0.5],
        )
    )

    return cases


def _py_verdict(spec: object, eval_input: list[float]) -> str:
    """Reproduce the probe's CASE line for pypdfbox."""
    try:
        fn = PDFunction.create(spec)
    except Exception:  # noqa: BLE001 - mirror the probe's catch-all
        return "create=ERR"
    if fn is None:  # pragma: no cover - all specs here are dictionaries/streams
        return "create=none"
    try:
        out = fn.eval(eval_input)
    except Exception:  # noqa: BLE001
        return "create=ok eval=ERR"
    return "create=ok eval=" + " ".join(f"{v:.6f}" for v in out)


def _parse_probe(text: str) -> list[tuple[str, str]]:
    """Parse the probe stdout into an ordered list of (name, verdict)."""
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        name, _, verdict = rest.partition(" ")
        out.append((name, verdict))
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
        if math.isinf(va) or math.isinf(vb):
            if va != vb:
                return False
            continue
        if abs(va - vb) > _TOL * max(1.0, abs(va), abs(vb)):
            return False
    return True


@requires_oracle
def test_function_type23_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text("FunctionType23FuzzProbe"))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert len(cases) == len(probe), (
        f"case count mismatch: py={len(cases)} java={len(probe)}"
    )

    mismatches: list[str] = []
    for (py_name, spec, eval_input), (java_name, java) in zip(cases, probe, strict=True):
        assert py_name == java_name, f"order mismatch: py={py_name} java={java_name}"
        py = _py_verdict(spec, eval_input)
        if java.startswith("create=ok eval=") and py.startswith("create=ok eval="):
            jv = java[len("create=ok eval=") :]
            pv = py[len("create=ok eval=") :]
            if jv == "ERR" or pv == "ERR":
                if jv != pv:
                    mismatches.append(f"{py_name}({eval_input}): java={java!r} py={py!r}")
            elif not _floats_close(jv, pv):
                mismatches.append(f"{py_name}({eval_input}): java={java!r} py={py!r}")
        elif java != py:
            mismatches.append(f"{py_name}({eval_input}): java={java!r} py={py!r}")

    assert not mismatches, "type2/3 fuzz divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_probe_spans_new_surfaces() -> None:
    """Sanity: the corpus covers each NEW malformed surface this wave adds."""
    names = {n for n, _ in _parse_probe(run_probe_text("FunctionType23FuzzProbe"))}
    for key in (
        "t2_c0_non_numeric",
        "t2_n_non_numeric",
        "t2_rev_domain",
        "t3_four_fns",
        "t3_nan_input",
        "t3_type4_child",
        "t3_bound_eq_dom_max",
    ):
        assert key in names, f"missing surface: {key}"


# ---------- oracle-free frozen regressions ----------


def test_type2_non_numeric_c0_raises_oracle_free() -> None:
    """Frozen copy of the wave-1544 fix: a non-numeric ``/C0`` entry makes eval
    raise (upstream ``getC0().toFloatArray()`` COSNumber-cast parity), rather
    than tolerantly mapping the bad entry to ``0.0``."""
    c0 = _floats(0, 0)
    c0.set(1, COSName.get_pdf_name("X"))
    fn = PDFunction.create(_t2(c0, _floats(1, 1), 1.0, _floats(0, 1), None))
    with pytest.raises(ValueError, match="non-numeric"):
        fn.eval([0.5])


def test_type2_non_numeric_c1_raises_oracle_free() -> None:
    """Frozen copy: a non-numeric ``/C1`` entry makes eval raise."""
    c1 = _floats(1, 1)
    c1.set(0, COSString("oops"))
    fn = PDFunction.create(_t2(_floats(0, 0), c1, 1.0, _floats(0, 1), None))
    with pytest.raises(ValueError, match="non-numeric"):
        fn.eval([0.5])


def test_type2_reversed_domain_no_input_clip_oracle_free() -> None:
    """Frozen copy: Type 2 eval reads ``input[0]`` directly (no /Domain clip),
    so a reversed /Domain [1,0] does not alter the result — f(0)=0, f(1)=8."""
    fn = PDFunction.create(_t2(_floats(0), _floats(8), 1.0, _floats(1, 0), None))
    assert fn.eval([0.0]) == pytest.approx([0.0], abs=_TOL)
    assert fn.eval([1.0]) == pytest.approx([8.0], abs=_TOL)


def test_type2_empty_c0_still_defaults_oracle_free() -> None:
    """Frozen copy: an empty (but present) /C0 still materialises [0.0] in eval
    (constructor default), unchanged by the strict-reader fix."""
    fn = PDFunction.create(_t2(COSArray(), _floats(5), 1.0, _floats(0, 1), None))
    assert fn.eval([0.5]) == pytest.approx([2.5], abs=_TOL)


def test_type3_four_function_dispatch_oracle_free() -> None:
    """Frozen copy: a four-subfunction / three-bound stitcher dispatches each
    input into the matching interval and child."""
    dom01 = _floats(0, 1)
    four = _fns(_child(0, 10), _child(20, 30), _child(40, 50), _child(60, 70))
    b3 = _floats(0.25, 0.5, 0.75)
    enc4 = _floats(0, 1, 0, 1, 0, 1, 0, 1)
    fn = PDFunction.create(_t3(four, b3, enc4, dom01))
    assert fn.eval([0.1]) == pytest.approx([4.0], abs=_TOL)
    assert fn.eval([0.9]) == pytest.approx([66.0], abs=_TOL)
