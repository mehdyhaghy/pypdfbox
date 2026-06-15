"""Live PDFBox differential fuzz parity for the Type 3 stitching function
(wave 1523).

Drives ``oracle/probes/FunctionType3FuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* COS specs and asserting each
``CASE`` line matches. Complements FunctionEvalFuzzProbe's handful of Type 3
cases with a dedicated malformed-stitching battery: missing/empty/non-array
``/Functions``, single vs multi function dispatch, ``/Bounds`` length wrong
(not k-1), non-increasing / out-of-Domain ``/Bounds``, ``/Encode`` length wrong
(not 2k) or missing pairs, non-numeric ``/Bounds`` / ``/Encode`` entries, input
clamping below ``Domain[0]`` / above ``Domain[1]``, input exactly on an interior
bound, zero-width subdomain, malformed sub-function, and ``/Domain`` corners.

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR> [eval=<ERR | f0 f1 ...>]

Real bugs fixed this wave so the probe now matches byte-for-byte
(see CHANGES.md, Wave 1523):

* Single-subfunction dispatch must ignore ``/Bounds`` entirely (upstream's
  ``functionsArray.length == 1`` short-circuit) — pypdfbox used to reject a
  single function carrying any ``/Bounds`` via a length check.
* ``/Bounds`` length is *never* validated up front; an over/under-long
  ``/Bounds`` either dispatches the wrong interval or indexes past
  ``functionsArray`` (IndexError), exactly like upstream.
* ``/Encode`` access goes through ``PDRange.getMin/getMax`` (COSNumber cast),
  so an absent / too-short / non-numeric ``/Encode`` pair must raise rather
  than fall back to a defensive ``[0, 1]`` default.
* The input is clipped to ``/Domain`` with the *non-normalising* upstream
  ``clipToRange(float, float, float)``, so a reversed ``/Domain`` produces the
  same "partition not found" failure as upstream.
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
    COSString,
)
from pypdfbox.pdmodel.common.function import PDFunction
from tests.oracle.harness import requires_oracle, run_probe_text

_TOL = 1e-4


# ---------- COS builders (mirror FunctionType3FuzzProbe.java) ----------


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(float(v)))
    return arr


def _t2(c0: float, c1: float) -> COSDictionary:
    """f(x) = c0 + x * (c1 - c0) over Domain [0, 1] (N = 1)."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _floats(0, 1))
    d.set_item("N", COSFloat(1.0))
    d.set_item("C0", _floats(c0))
    d.set_item("C1", _floats(c1))
    return d


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


def _build_cases() -> dict[str, tuple[object, list[float]]]:
    """Return {case_name: (cos_spec, eval_input)} mirroring the probe."""
    dom01 = _floats(0, 1)
    cases: dict[str, tuple[object, list[float]]] = {}

    # ---- /Functions shape ----
    cases["fns_missing"] = (_t3(None, COSArray(), _floats(0, 1), dom01), [0.5])
    cases["fns_empty"] = (_t3(COSArray(), COSArray(), _floats(0, 1), dom01), [0.5])
    not_arr = _t3(None, COSArray(), _floats(0, 1), dom01)
    not_arr.set_item("Functions", _t2(0, 1))
    cases["fns_not_array"] = (not_arr, [0.5])

    # ---- single function (Bounds ignored) ----
    cases["single_basic"] = (_t3(_fns(_t2(0, 1)), COSArray(), _floats(0, 1), dom01), [0.5])
    cases["single_with_bound"] = (
        _t3(_fns(_t2(0, 1)), _floats(0.5), _floats(0, 1), dom01),
        [0.5],
    )
    cases["single_rev_encode"] = (
        _t3(_fns(_t2(0, 10)), COSArray(), _floats(1, 0), dom01),
        [0.25],
    )
    cases["single_encode_missing"] = (
        _t3(_fns(_t2(0, 1)), COSArray(), None, dom01),
        [0.5],
    )
    cases["single_encode_short"] = (
        _t3(_fns(_t2(0, 1)), COSArray(), _floats(0), dom01),
        [0.5],
    )

    # ---- two functions, well-formed ----
    def _two(inp: float) -> tuple[COSDictionary, list[float]]:
        return (
            _t3(_fns(_t2(0, 10), _t2(100, 110)), _floats(0.5), _floats(0, 1, 0, 1), dom01),
            [inp],
        )

    cases["two_low"] = _two(0.25)
    cases["two_high"] = _two(0.75)
    cases["two_on_bound"] = _two(0.5)
    cases["two_at_dom_max"] = _two(1.0)
    cases["two_at_dom_min"] = _two(0.0)

    # ---- input clamping ----
    cases["clamp_over"] = _two(5.0)
    cases["clamp_under"] = _two(-5.0)

    # ---- /Bounds length wrong ----
    cases["bounds_too_few"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), COSArray(), _floats(0, 1, 0, 1), dom01),
        [0.75],
    )
    cases["bounds_too_many"] = (
        _t3(
            _fns(_t2(0, 10), _t2(100, 110)),
            _floats(0.3, 0.6),
            _floats(0, 1, 0, 1, 0, 1),
            dom01,
        ),
        [0.75],
    )
    cases["three_mid"] = (
        _t3(
            _fns(_t2(0, 10), _t2(50, 60), _t2(100, 110)),
            _floats(0.33, 0.66),
            _floats(0, 1, 0, 1, 0, 1),
            dom01,
        ),
        [0.5],
    )

    # ---- /Bounds non-increasing / out of Domain ----
    cases["bounds_reversed"] = (
        _t3(
            _fns(_t2(0, 10), _t2(50, 60), _t2(100, 110)),
            _floats(0.7, 0.3),
            _floats(0, 1, 0, 1, 0, 1),
            dom01,
        ),
        [0.5],
    )
    cases["bound_below_domain"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), _floats(-0.5), _floats(0, 1, 0, 1), dom01),
        [0.5],
    )
    cases["bound_above_domain"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), _floats(1.5), _floats(0, 1, 0, 1), dom01),
        [0.5],
    )

    # ---- zero-width subdomain ----
    cases["zero_width_mid"] = (
        _t3(
            _fns(_t2(0, 10), _t2(50, 60), _t2(100, 110)),
            _floats(0.5, 0.5),
            _floats(0, 1, 0, 1, 0, 1),
            dom01,
        ),
        [0.5],
    )

    # ---- /Encode length wrong / non-numeric ----
    cases["encode_short_multi"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), _floats(0.5), _floats(0, 1), dom01),
        [0.75],
    )
    cases["encode_oversized"] = (
        _t3(
            _fns(_t2(0, 10), _t2(100, 110)),
            _floats(0.5),
            _floats(0, 1, 0, 1, 0, 1),
            dom01,
        ),
        [0.75],
    )
    bad_enc = _floats(0, 1, 0, 1)
    bad_enc.set(2, COSName.get_pdf_name("X"))
    cases["encode_non_numeric"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), _floats(0.5), bad_enc, dom01),
        [0.75],
    )

    # ---- non-numeric /Bounds entry ----
    bad_bounds = _floats(0.5)
    bad_bounds.set(0, COSString("oops"))
    cases["bounds_non_numeric"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), bad_bounds, _floats(0, 1, 0, 1), dom01),
        [0.5],
    )

    # ---- malformed sub-function ----
    bad_child = COSDictionary()
    bad_child.set_int("FunctionType", 99)
    with_bad = COSArray()
    with_bad.add(_t2(0, 10))
    with_bad.add(bad_child)
    cases["subfn_malformed"] = (
        _t3(with_bad, _floats(0.5), _floats(0, 1, 0, 1), dom01),
        [0.75],
    )
    with_int = COSArray()
    with_int.add(_t2(0, 10))
    with_int.add(COSInteger.get(7))
    cases["subfn_not_dict"] = (
        _t3(with_int, _floats(0.5), _floats(0, 1, 0, 1), dom01),
        [0.75],
    )

    # ---- /Domain malformed ----
    cases["domain_missing"] = (
        _t3(_fns(_t2(0, 10), _t2(100, 110)), _floats(0.5), _floats(0, 1, 0, 1), None),
        [0.5],
    )
    cases["domain_reversed"] = (
        _t3(
            _fns(_t2(0, 10), _t2(100, 110)),
            _floats(0.5),
            _floats(0, 1, 0, 1),
            _floats(1, 0),
        ),
        [0.5],
    )
    cases["domain_wide"] = (
        _t3(
            _fns(_t2(0, 10), _t2(100, 110)),
            _floats(0),
            _floats(0, 1, 0, 1),
            _floats(-10, 10),
        ),
        [5.0],
    )

    # ---- encode interpolation at interval edges ----
    cases["edge_at_lower"] = (
        _t3(_fns(_t2(0, 10), _t2(0, 100)), _floats(0.5), _floats(0, 1, 0, 1), dom01),
        [0.5],
    )
    cases["edge_encode_overshoot"] = (
        _t3(_fns(_t2(0, 10), _t2(0, 100)), _floats(0.5), _floats(0, 1, 0, 4), dom01),
        [0.75],
    )

    return cases


def _py_verdict(spec: object, eval_input: list[float]) -> str:
    """Reproduce the probe's CASE line for pypdfbox."""
    try:
        fn = PDFunction.create(spec)
    except Exception:  # noqa: BLE001 - mirror the probe's catch-all
        return "create=ERR"
    if fn is None:  # pragma: no cover - all Type 3 specs here are dictionaries
        return "create=none"
    try:
        out = fn.eval(eval_input)
    except Exception:  # noqa: BLE001
        return "create=ok eval=ERR"
    return "create=ok eval=" + " ".join(f"{v:.6f}" for v in out)


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
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
def test_function_type3_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text("FunctionType3FuzzProbe"))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, (spec, eval_input) in cases.items():
        java = probe[name]
        py = _py_verdict(spec, eval_input)
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

    assert not mismatches, "type3 fuzz divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_probe_spans_type3_surfaces() -> None:
    """Sanity: the corpus covers each malformed-stitching surface."""
    probe = _parse_probe(run_probe_text("FunctionType3FuzzProbe"))
    for key in (
        "fns_missing",
        "single_with_bound",
        "bounds_too_few",
        "bounds_too_many",
        "encode_non_numeric",
        "domain_reversed",
        "zero_width_mid",
    ):
        assert key in probe, f"missing surface: {key}"


# ---------- oracle-free frozen regressions (the wave-1523 fixes) ----------


def test_single_function_ignores_bounds_oracle_free() -> None:
    """Frozen copy: a single-subfunction stitcher dispatches to function[0] and
    encodes over the whole /Domain, ignoring any /Bounds present."""
    dom01 = _floats(0, 1)
    fn = PDFunction.create(_t3(_fns(_t2(0, 1)), _floats(0.5), _floats(0, 1), dom01))
    assert fn.eval([0.5]) == pytest.approx([0.5], abs=_TOL)


def test_absent_encode_raises_oracle_free() -> None:
    """Frozen copy: an absent /Encode pair must raise (no [0, 1] default)."""
    dom01 = _floats(0, 1)
    fn = PDFunction.create(_t3(_fns(_t2(0, 1)), COSArray(), None, dom01))
    with pytest.raises(ValueError, match="Encode"):
        fn.eval([0.5])


def test_reversed_domain_partition_not_found_oracle_free() -> None:
    """Frozen copy: a reversed /Domain clamps via the non-normalising
    clipToRange, leaving the input outside every partition -> raise."""
    fn = PDFunction.create(
        _t3(
            _fns(_t2(0, 10), _t2(100, 110)),
            _floats(0.5),
            _floats(0, 1, 0, 1),
            _floats(1, 0),
        )
    )
    with pytest.raises(ValueError, match="partition not found"):
        fn.eval([0.5])
