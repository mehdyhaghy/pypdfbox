"""Live PDFBox differential fuzz parity for PDF function CONSTRUCTION +
DISPATCH (wave 1515, agent C).

Drives ``oracle/probes/FunctionCreateFuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* COS graphs and asserting each
``CASE`` line matches. This complements
``test_function_eval_fuzz_wave1509.py`` (which fuzzes the create→eval pipeline
with a Type-4 emphasis): THIS module never calls ``eval`` — it isolates the
``PDFunction.create`` dispatch contract and the per-type construction-time
leniency across all four function types.

Probe line grammar (one per case, corpus order)::

    CASE <name> ftype=<n|ERR> class=<simpleName|null|ERR> domain=<arity|ERR> \
        range=<arity|ERR> nout=<n|ERR> extra=<type-specific|ERR>

Semantics:
  - ``ftype`` — raw ``/FunctionType`` int as ``getInt`` sees it (-1 when
    absent / non-int).
  - ``class`` — ``create()``'s result simple class name, ``null`` when create
    returns null, ``ERR`` when create throws. What matters for a dispatch
    leniency audit is *whether* construction succeeds, not the Java exception
    class, so both sides collapse any throw to ``ERR``.
  - ``domain`` / ``range`` / ``nout`` — pair counts of /Domain, /Range, and
    ``getNumberOfOutputParameters`` again; ``ERR`` on throw, ``-`` when create
    yielded no function.
  - ``extra`` — type-specific construction-readable summary; ``ERR`` on throw,
    ``-`` otherwise. The PostScript body parses lazily on the pypdfbox side
    (see divergences), so Type 4's ``extra`` is the literal ``type4``.

Where pypdfbox *intentionally* diverges from upstream's construction contract
(documented in CHANGES.md, wave 1515), the case is listed in
``_DIVERGENCES`` with the pypdfbox-side expectation and a citation. For every
other case the probe's behaviour is the contract pypdfbox must meet.

Bug fixed this wave (now matches Java byte-for-byte): pypdfbox
``PDFunctionType0.get_bits_per_sample`` defaulted to 0 for an absent
``/BitsPerSample``; upstream's single-arg ``getInt`` default is -1. The
``t0_no_bps`` case below pins the corrected value.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionTypeIdentity,
)
from pypdfbox.pdmodel.common.function.pd_function_type0 import PDFunctionType0
from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2
from pypdfbox.pdmodel.common.function.pd_function_type3 import PDFunctionType3
from tests.oracle.harness import requires_oracle, run_probe_text

_IDENTITY = COSName.get_pdf_name("Identity")


# ---------- COS builders (mirror FunctionCreateFuzzProbe.java) ----------


def _ints(*vals: int) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSInteger.get(v))
    return a


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _dict(function_type: int) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", function_type)
    return d


def _stream(function_type: int, body: bytes | None) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", function_type)
    if body is not None:
        s.set_data(body)
    return s


# ---------- projection (mirror the probe's grammar exactly) ----------


def _fmt(v: float) -> str:
    if v != v:  # NaN
        return "NaN"
    if v == float("inf"):
        return "Infinity"
    if v == float("-inf"):
        return "-Infinity"
    return f"{v:.6f}"


def _raw_type(base: object) -> str:
    b = base
    if isinstance(b, COSObject):
        b = b.get_object()
    if isinstance(b, COSDictionary):
        return str(b.get_int("FunctionType", -1))
    return "-1"


def _extra(fn: PDFunction) -> str:
    if isinstance(fn, PDFunctionType0):
        bps = fn.get_bits_per_sample()
        size = fn.get_size()
        sz = -1 if size is None else size.size()
        return f"bps={bps} size={sz}"
    if isinstance(fn, PDFunctionType2):
        n = fn.get_n()
        c0 = fn.get_c0_array()
        c1 = fn.get_c1_array()
        n0 = -1 if c0 is None else c0.size()
        n1 = -1 if c1 is None else c1.size()
        return f"N={_fmt(n)} c0={n0} c1={n1}"
    if isinstance(fn, PDFunctionType3):
        fns = fn.get_functions_array()
        bounds = fn.get_bounds()
        enc = fn.get_encode()
        nf = -1 if fns is None else fns.size()
        nb = -1 if bounds is None else bounds.size()
        ne = -1 if enc is None else enc.size()
        return f"fns={nf} bounds={nb} enc={ne}"
    return "type4"


def _safe_extra(fn: PDFunction) -> str:
    try:
        return _extra(fn)
    except Exception:
        return "ERR"


def _project(name: str, base: object) -> str:
    parts = [f"CASE {name}"]

    try:
        parts.append(f"ftype={_raw_type(base)}")
    except Exception:
        parts.append("ftype=ERR")

    try:
        fn = PDFunction.create(base)
    except Exception:
        parts.append("class=ERR domain=- range=- nout=- extra=-")
        return " ".join(parts)

    if fn is None:
        parts.append("class=null domain=- range=- nout=- extra=-")
        return " ".join(parts)

    parts.append(f"class={type(fn).__name__}")

    try:
        parts.append(f"domain={fn.get_number_of_input_parameters()}")
    except Exception:
        parts.append("domain=ERR")

    try:
        parts.append(f"range={fn.get_number_of_output_parameters()}")
    except Exception:
        parts.append("range=ERR")

    try:
        parts.append(f"nout={fn.get_number_of_output_parameters()}")
    except Exception:
        parts.append("nout=ERR")

    parts.append(f"extra={_safe_extra(fn)}")
    return " ".join(parts)


# ---------- the corpus (mirror FunctionCreateFuzzProbe.corpus()) ----------


def _corpus() -> list[tuple[str, object]]:
    cases: list[tuple[str, object]] = []

    # dispatch: missing / unknown / out-of-range / non-int type
    cases.append(("null_base", None))
    cases.append(("dict_no_type", COSDictionary()))
    cases.append(("type_1_unknown", _dict(1)))
    cases.append(("type_5_unknown", _dict(5)))
    cases.append(("type_neg", _dict(-3)))

    type_name = COSDictionary()
    type_name.set_item("FunctionType", COSName.get_pdf_name("Foo"))
    cases.append(("type_is_name", type_name))

    type_str = COSDictionary()
    type_str.set_item("FunctionType", COSString("2"))
    cases.append(("type_is_string", type_str))

    type_real = COSDictionary()
    type_real.set_item("FunctionType", COSFloat(2.0))
    cases.append(("type_is_real_2", type_real))

    type_real3 = COSDictionary()
    type_real3.set_item("FunctionType", COSFloat(2.7))
    cases.append(("type_is_real_2_7", type_real3))

    # identity sentinel + COSObject unwrap
    cases.append(("identity_name", _IDENTITY))
    cases.append(("plain_name", COSName.get_pdf_name("Foo")))

    t2inner = _dict(2)
    t2inner.set_item("Domain", _floats(0, 1))
    cases.append(("cosobject_wraps_t2", COSObject(1, resolved=t2inner)))

    cases.append(("cosobject_unresolved", COSObject(2)))

    # non-dict bases (dictionary-required branch)
    cases.append(("base_integer", COSInteger.get(2)))
    cases.append(("base_string", COSString("hi")))
    cases.append(("base_bool", COSBoolean.TRUE))
    cases.append(("base_array", _ints(0, 1)))

    # Type 0 as plain dict vs stream
    t0dict = _dict(0)
    t0dict.set_item("Domain", _floats(0, 1))
    t0dict.set_item("Range", _floats(0, 1))
    t0dict.set_item("Size", _ints(2))
    t0dict.set_int("BitsPerSample", 8)
    cases.append(("t0_plain_dict", t0dict))

    t0stream = _stream(0, bytes([0, 255]))
    t0stream.set_item("Domain", _floats(0, 1))
    t0stream.set_item("Range", _floats(0, 1))
    t0stream.set_item("Size", _ints(2))
    t0stream.set_int("BitsPerSample", 8)
    cases.append(("t0_stream_ok", t0stream))

    t0nodom = _stream(0, bytes([0, 255]))
    t0nodom.set_item("Range", _floats(0, 1))
    t0nodom.set_item("Size", _ints(2))
    t0nodom.set_int("BitsPerSample", 8)
    cases.append(("t0_no_domain", t0nodom))

    t0norange = _stream(0, bytes([0, 255]))
    t0norange.set_item("Domain", _floats(0, 1))
    t0norange.set_item("Size", _ints(2))
    t0norange.set_int("BitsPerSample", 8)
    cases.append(("t0_no_range", t0norange))

    t0odd = _stream(0, bytes([0, 255]))
    t0odd.set_item("Domain", _floats(0, 1, 2))
    t0odd.set_item("Range", _floats(0, 1))
    t0odd.set_item("Size", _ints(2))
    t0odd.set_int("BitsPerSample", 8)
    cases.append(("t0_odd_domain", t0odd))

    t0nobps = _stream(0, bytes([0, 255]))
    t0nobps.set_item("Domain", _floats(0, 1))
    t0nobps.set_item("Range", _floats(0, 1))
    t0nobps.set_item("Size", _ints(2))
    cases.append(("t0_no_bps", t0nobps))

    for bps in (1, 2, 4, 8, 12, 16, 24, 32, 3, 0, 64):
        s = _stream(0, bytes([0, 255]))
        s.set_item("Domain", _floats(0, 1))
        s.set_item("Range", _floats(0, 1))
        s.set_item("Size", _ints(2))
        s.set_int("BitsPerSample", bps)
        cases.append((f"t0_bps_{bps}", s))

    t0nosize = _stream(0, bytes([0, 255]))
    t0nosize.set_item("Domain", _floats(0, 1))
    t0nosize.set_item("Range", _floats(0, 1))
    t0nosize.set_int("BitsPerSample", 8)
    cases.append(("t0_no_size", t0nosize))

    t0sizename = _stream(0, bytes([0, 255]))
    t0sizename.set_item("Domain", _floats(0, 1))
    t0sizename.set_item("Range", _floats(0, 1))
    t0sizename.set_item("Size", COSName.get_pdf_name("X"))
    t0sizename.set_int("BitsPerSample", 8)
    cases.append(("t0_size_is_name", t0sizename))

    # Type 2: C0/C1 arity, /N corners
    t2bare = _dict(2)
    t2bare.set_item("Domain", _floats(0, 1))
    cases.append(("t2_bare", t2bare))

    t2non = _dict(2)
    t2non.set_item("Domain", _floats(0, 1))
    t2non.set_item("C0", _floats(0, 0, 0))
    t2non.set_item("C1", _floats(1, 1, 1))
    cases.append(("t2_no_n", t2non))

    t2neg = _dict(2)
    t2neg.set_item("Domain", _floats(0, 1))
    t2neg.set_item("N", COSFloat(-2.0))
    cases.append(("t2_neg_n", t2neg))

    t2namen = _dict(2)
    t2namen.set_item("Domain", _floats(0, 1))
    t2namen.set_item("N", COSName.get_pdf_name("X"))
    cases.append(("t2_name_n", t2namen))

    t2mis = _dict(2)
    t2mis.set_item("Domain", _floats(0, 1))
    t2mis.set_item("N", COSFloat(1.0))
    t2mis.set_item("C0", _floats(0, 0))
    t2mis.set_item("C1", _floats(1, 1, 1))
    cases.append(("t2_c0_c1_mismatch", t2mis))

    t2nodom = _dict(2)
    t2nodom.set_item("N", COSFloat(1.0))
    cases.append(("t2_no_domain", t2nodom))

    t2stream = _stream(2, None)
    t2stream.set_item("Domain", _floats(0, 1))
    t2stream.set_item("N", COSFloat(1.0))
    cases.append(("t2_as_stream", t2stream))

    # Type 3: /Functions, /Bounds, /Encode
    t3nf = _dict(3)
    t3nf.set_item("Domain", _floats(0, 1))
    cases.append(("t3_no_functions", t3nf))

    t3ea = _dict(3)
    t3ea.set_item("Domain", _floats(0, 1))
    t3ea.set_item("Functions", COSArray())
    t3ea.set_item("Bounds", COSArray())
    t3ea.set_item("Encode", COSArray())
    cases.append(("t3_empty_functions", t3ea))

    sub2a = _dict(2)
    sub2a.set_item("Domain", _floats(0, 1))
    sub2a.set_item("N", COSFloat(1.0))
    sub2b = _dict(2)
    sub2b.set_item("Domain", _floats(0, 1))
    sub2b.set_item("N", COSFloat(1.0))

    t3two = _dict(3)
    t3two.set_item("Domain", _floats(0, 1))
    subs = COSArray()
    subs.add(sub2a)
    subs.add(sub2b)
    t3two.set_item("Functions", subs)
    t3two.set_item("Bounds", _floats(0.5))
    t3two.set_item("Encode", _floats(0, 1, 0, 1))
    cases.append(("t3_two_subs", t3two))

    t3bad = _dict(3)
    t3bad.set_item("Domain", _floats(0, 1))
    bad = COSArray()
    bad.add(COSInteger.get(7))
    bad.add(COSString("x"))
    t3bad.set_item("Functions", bad)
    cases.append(("t3_bad_members", t3bad))

    t3fnsname = _dict(3)
    t3fnsname.set_item("Domain", _floats(0, 1))
    t3fnsname.set_item("Functions", COSName.get_pdf_name("X"))
    cases.append(("t3_functions_is_name", t3fnsname))

    t3ba = _dict(3)
    t3ba.set_item("Domain", _floats(0, 1))
    subs2 = COSArray()
    subs2.add(sub2a)
    subs2.add(sub2b)
    t3ba.set_item("Functions", subs2)
    t3ba.set_item("Bounds", _floats(0.3, 0.6, 0.9))
    t3ba.set_item("Encode", _floats(0, 1))
    cases.append(("t3_bounds_encode_arity", t3ba))

    # Type 4: malformed PostScript body (construction)
    t4ok = _stream(4, b"{ 2 mul }")
    t4ok.set_item("Domain", _floats(0, 1))
    t4ok.set_item("Range", _floats(0, 1000))
    cases.append(("t4_ok_body", t4ok))

    t4bad = _stream(4, b"{ 2 mul ")
    t4bad.set_item("Domain", _floats(0, 1))
    t4bad.set_item("Range", _floats(0, 1000))
    cases.append(("t4_unbalanced_body", t4bad))

    t4garbage = _stream(4, b"this is not postscript")
    t4garbage.set_item("Domain", _floats(0, 1))
    t4garbage.set_item("Range", _floats(0, 1000))
    cases.append(("t4_garbage_body", t4garbage))

    t4nobody = _stream(4, None)
    t4nobody.set_item("Domain", _floats(0, 1))
    t4nobody.set_item("Range", _floats(0, 1000))
    cases.append(("t4_no_body", t4nobody))

    t4nodom = _stream(4, b"{ 2 mul }")
    t4nodom.set_item("Range", _floats(0, 1000))
    cases.append(("t4_no_domain", t4nodom))

    t4dict = _dict(4)
    t4dict.set_item("Domain", _floats(0, 1))
    t4dict.set_item("Range", _floats(0, 1000))
    cases.append(("t4_plain_dict", t4dict))

    return cases


# ---------- documented intentional divergences (CHANGES.md, wave 1515) ----------
#
# Each entry maps a case name to the pypdfbox-side projected line that REPLACES
# the upstream probe line. Every divergence is a *robustness* difference where
# pypdfbox is more lenient than upstream's accidental NPE / eager-construction
# faults; the underlying valid-input contract is unchanged.
_DIVERGENCES: dict[str, str] = {
    # --- null base ---
    # Upstream create(null): null is not COSName.IDENTITY, not a COSObject,
    # and not instanceof COSDictionary → IOException "Function must be a
    # Dictionary, but is (null)" (class=ERR). pypdfbox's create() returns None
    # for a None base by documented contract (the common "no function present"
    # case), which is the more useful caller signal → class=null.
    "null_base": (
        "CASE null_base ftype=-1 class=null domain=- range=- nout=- extra=-"
    ),
    # --- /FunctionType as a real with no /Domain ---
    # getInt truncates the COSFloat to 2 (both sides), so dispatch reaches
    # PDFunctionType2; the dict carries no /Domain, hitting the same
    # getNumberOfInputParameters NPE divergence pinned below.
    "type_is_real_2": (
        "CASE type_is_real_2 ftype=2 class=PDFunctionType2 "
        "domain=0 range=0 nout=0 extra=N=-1.000000 c0=1 c1=1"
    ),
    "type_is_real_2_7": (
        "CASE type_is_real_2_7 ftype=2 class=PDFunctionType2 "
        "domain=0 range=0 nout=0 extra=N=-1.000000 c0=1 c1=1"
    ),
    # --- absent /Domain → getNumberOfInputParameters ---
    # Upstream PDFunction.getNumberOfInputParameters() does NOT null-check the
    # /Domain array (unlike getNumberOfOutputParameters, which guards /Range),
    # so an absent /Domain throws NullPointerException → probe reports
    # domain=ERR. pypdfbox guards the lookup and returns 0 (and the rest of
    # the projection then proceeds). The pypdfbox lines below carry domain=0
    # plus the remaining fields that upstream never reached (it aborts the
    # whole projection at the domain slot, emitting domain=- ... no — the
    # probe catches the throw per-slot, so upstream keeps range/nout/extra).
    "t0_no_domain": (
        "CASE t0_no_domain ftype=0 class=PDFunctionType0 "
        "domain=0 range=1 nout=1 extra=bps=8 size=1"
    ),
    "t2_no_domain": (
        "CASE t2_no_domain ftype=2 class=PDFunctionType2 "
        "domain=0 range=0 nout=0 extra=N=1.000000 c0=1 c1=1"
    ),
    "t4_no_domain": (
        "CASE t4_no_domain ftype=4 class=PDFunctionType4 "
        "domain=0 range=1 nout=1 extra=type4"
    ),
    # identity sentinel: PDFunctionTypeIdentity has no /Domain; upstream's
    # getNumberOfInputParameters NPEs (domain=ERR). pypdfbox returns 0.
    "identity_name": (
        "CASE identity_name ftype=-1 class=PDFunctionTypeIdentity "
        "domain=0 range=0 nout=0 extra=type4"
    ),
    # --- COSObject wrapping a free/unresolved reference ---
    # Upstream create() unwraps the COSObject; getObject() returns null; null
    # is not instanceof COSDictionary → IOException (class=ERR). pypdfbox's
    # create() returns None for an unresolved COSObject (graceful) → class=null.
    "cosobject_unresolved": (
        "CASE cosobject_unresolved ftype=-1 class=null "
        "domain=- range=- nout=- extra=-"
    ),
    # --- Type 4 lazy vs eager construction ---
    # Upstream PDFunctionType4's CONSTRUCTOR eagerly reads the stream body and
    # parses it (getPDStream().toByteArray() → InstructionSequenceBuilder.parse),
    # so a Type-4 spec with no stream body (no createOutputStream call) or given
    # as a plain dict throws at create() (class=ERR). pypdfbox parses the body
    # lazily on first eval (cached), so construction succeeds. The malformed-body
    # contract is therefore exercised at eval (see test_function_eval_fuzz_*),
    # not at create. These two cases pin the lenient construction.
    "t4_no_body": (
        "CASE t4_no_body ftype=4 class=PDFunctionType4 "
        "domain=1 range=1 nout=1 extra=type4"
    ),
    "t4_plain_dict": (
        "CASE t4_plain_dict ftype=4 class=PDFunctionType4 "
        "domain=1 range=1 nout=1 extra=type4"
    ),
}


@requires_oracle
def test_function_create_dispatch_matches_pdfbox() -> None:
    cases = _corpus()
    java_lines = [
        ln for ln in run_probe_text("FunctionCreateFuzzProbe").splitlines() if ln.strip()
    ]
    assert len(java_lines) == len(cases), (
        f"probe emitted {len(java_lines)} lines for {len(cases)} cases"
    )

    mismatches: list[str] = []
    for (name, base), java_line in zip(cases, java_lines, strict=True):
        assert java_line.startswith(f"CASE {name} "), (
            f"probe/corpus order skew: expected '{name}', got '{java_line}'"
        )
        py_line = _project(name, base)
        expected = _DIVERGENCES.get(name, java_line)
        if py_line != expected:
            mismatches.append(
                f"\n  case   : {name}"
                f"\n  java   : {java_line}"
                f"\n  pypdf  : {py_line}"
                f"\n  expect : {expected}"
            )

    assert not mismatches, "construction/dispatch divergences:" + "".join(mismatches)


@requires_oracle
def test_divergences_are_real() -> None:
    """Guard: every name in ``_DIVERGENCES`` must actually differ from the
    probe (so a future upstream/pypdfbox change that re-converges the
    behaviour fails loudly instead of silently masking a regression)."""
    cases = {name: base for name, base in _corpus()}
    java = {
        ln.split()[1]: ln
        for ln in run_probe_text("FunctionCreateFuzzProbe").splitlines()
        if ln.strip()
    }
    for name, pinned in _DIVERGENCES.items():
        assert name in cases, f"stale divergence pin: {name}"
        assert java[name] != pinned, (
            f"divergence '{name}' no longer diverges from upstream — re-pin or drop"
        )
        assert _project(name, cases[name]) == pinned, (
            f"divergence '{name}' pypdfbox projection drifted from its pin"
        )


def test_identity_and_dispatch_smoke() -> None:
    """Oracle-free smoke: core dispatch invariants that must hold regardless
    of the live jar (frozen from the wave-1515 oracle run)."""
    assert PDFunction.create(None) is None
    assert isinstance(PDFunction.create(_IDENTITY), PDFunctionTypeIdentity)

    t2 = _dict(2)
    t2.set_item("Domain", _floats(0, 1))
    assert isinstance(PDFunction.create(t2), PDFunctionType2)

    # absent /BitsPerSample → -1 (upstream parity, fixed wave 1515).
    t0 = _stream(0, bytes([0, 255]))
    t0.set_item("Domain", _floats(0, 1))
    t0.set_item("Range", _floats(0, 1))
    t0.set_item("Size", _ints(2))
    fn0 = PDFunction.create(t0)
    assert isinstance(fn0, PDFunctionType0)
    assert fn0.get_bits_per_sample() == -1
