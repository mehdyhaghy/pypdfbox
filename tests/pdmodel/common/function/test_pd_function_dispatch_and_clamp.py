"""Wave 1369 — PDFunction.create dispatch matrix + clamping round-out.

Covers the structural dispatch of ``PDFunction.create`` across every
documented input shape (Type 0, 2, 3, 4, /Identity sentinel, indirect
COSObject reference, malformed dict, malformed name) and the base-class
``clip_input`` / ``clip_output`` clamping behaviour at /Domain and
/Range boundaries.

The existing ``test_pd_function.py`` and ``test_pd_function_create_wave303.py``
exercise the happy paths; this file rounds out the matrix systematically
and adds clamping edge cases that are common entry points for downstream
shading / soft-mask code.
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
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType3,
    PDFunctionType4,
    PDFunctionTypeIdentity,
)

# ---------- PDFunction.create dispatch matrix ----------


def _make_type(function_type: int, *, stream_backed: bool = False) -> COSDictionary | COSStream:
    cos: COSDictionary | COSStream = COSStream() if stream_backed else COSDictionary()
    cos.set_int("FunctionType", function_type)
    return cos


@pytest.mark.parametrize(
    ("function_type", "stream_backed", "expected_cls"),
    [
        (0, True, PDFunctionType0),
        (2, False, PDFunctionType2),
        (3, False, PDFunctionType3),
        (4, True, PDFunctionType4),
    ],
    ids=["type-0", "type-2", "type-3", "type-4"],
)
def test_create_dispatches_each_function_type(
    function_type: int, stream_backed: bool, expected_cls: type
) -> None:
    """``PDFunction.create`` must return the matching concrete subclass for
    each of the four documented /FunctionType codes."""
    raw = _make_type(function_type, stream_backed=stream_backed)
    fn = PDFunction.create(raw)
    assert isinstance(fn, expected_cls), (
        f"/FunctionType {function_type}: got {type(fn).__name__}, "
        f"want {expected_cls.__name__}"
    )


def test_create_dispatches_to_identity_for_cos_name() -> None:
    """The literal name ``/Identity`` is a sentinel — returns the
    pass-through PDFunctionTypeIdentity."""
    result = PDFunction.create(COSName.get_pdf_name("Identity"))
    assert isinstance(result, PDFunctionTypeIdentity)


def test_create_returns_none_for_none() -> None:
    assert PDFunction.create(None) is None


@pytest.mark.parametrize(
    "bad_type",
    [-1, 1, 5, 6, 7, 99],
    ids=[f"bad-type-{t}" for t in [-1, 1, 5, 6, 7, 99]],
)
def test_create_rejects_unsupported_function_type(bad_type: int) -> None:
    """Per PDF 32000-1, only /FunctionType in {0, 2, 3, 4} is valid. Any
    other integer must raise ValueError so the caller can distinguish a
    malformed dictionary from a missing /FunctionType entry."""
    raw = COSDictionary()
    raw.set_int("FunctionType", bad_type)
    with pytest.raises(ValueError, match="FunctionType"):
        PDFunction.create(raw)


def test_create_rejects_missing_function_type() -> None:
    """A dictionary with no /FunctionType key has ``get_int(..., -1) = -1``
    which falls into the unsupported branch."""
    raw = COSDictionary()
    with pytest.raises(ValueError, match="FunctionType"):
        PDFunction.create(raw)


def test_create_rejects_non_dict_non_stream_non_name() -> None:
    """A COSInteger / COSArray / random scalar is not a function."""
    with pytest.raises(TypeError, match="COSDictionary or COSStream"):
        PDFunction.create(COSInteger.get(42))


def test_create_rejects_non_identity_cos_name() -> None:
    """Only /Identity is a recognised name sentinel — other names raise."""
    other = COSName.get_pdf_name("NotIdentity")
    with pytest.raises(TypeError, match="COSDictionary or COSStream"):
        PDFunction.create(other)


def test_create_via_indirect_reference_resolves() -> None:
    """A COSObject wraps an indirect reference; create() must resolve it
    via ``get_object()`` before dispatching."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    obj = COSObject(1, 0, resolved=raw)
    fn = PDFunction.create(obj)
    assert isinstance(fn, PDFunctionType2)


def test_create_via_indirect_reference_to_none_returns_none() -> None:
    """A COSObject whose target is None passes through as None."""
    obj = COSObject(1, 0, resolved=None)
    assert PDFunction.create(obj) is None


# ---------- get_function_type identity per concrete class ----------


@pytest.mark.parametrize(
    ("cls", "expected_code"),
    [
        (PDFunctionType0, 0),
        (PDFunctionType2, 2),
        (PDFunctionType3, 3),
        (PDFunctionType4, 4),
    ],
    ids=["type0-code", "type2-code", "type3-code", "type4-code"],
)
def test_get_function_type_per_class(cls: type, expected_code: int) -> None:
    """Each concrete subclass advertises its own /FunctionType code via
    ``get_function_type``."""
    fn = cls()
    assert fn.get_function_type() == expected_code


@pytest.mark.parametrize(
    ("cls", "predicate_index"),
    [
        (PDFunctionType0, 0),
        (PDFunctionType2, 2),
        (PDFunctionType3, 3),
        (PDFunctionType4, 4),
    ],
    ids=["pred-type0", "pred-type2", "pred-type3", "pred-type4"],
)
def test_is_function_type_predicate_matches(cls: type, predicate_index: int) -> None:
    """Each subclass's matching ``is_function_type_N`` predicate is True;
    all others are False."""
    fn = cls()
    predicates = {
        0: fn.is_function_type_0(),
        2: fn.is_function_type_2(),
        3: fn.is_function_type_3(),
        4: fn.is_function_type_4(),
    }
    for k, v in predicates.items():
        if k == predicate_index:
            assert v is True, f"{cls.__name__} self-predicate {k} is False"
        else:
            assert v is False, f"{cls.__name__} cross-predicate {k} is True"


# ---------- /Domain clipping ----------


def _make_type2_with_clip(
    *, domain: list[float], range_: list[float] | None = None
) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    c0 = COSArray()
    c0.set_float_array([0.0])
    raw.set_item("C0", c0)
    c1 = COSArray()
    c1.set_float_array([1.0])
    raw.set_item("C1", c1)
    raw.set_item("N", COSFloat(1.0))
    d = COSArray()
    d.set_float_array(domain)
    raw.set_item("Domain", d)
    if range_ is not None:
        r = COSArray()
        r.set_float_array(range_)
        raw.set_item("Range", r)
    return PDFunctionType2(raw)


@pytest.mark.parametrize(
    ("domain", "input_x", "expected_y"),
    [
        # /Domain = [0, 1]; ±inf flow through unclamped (no /Range here)
        ([0.0, 1.0], math.inf, math.inf),
        ([0.0, 1.0], -math.inf, -math.inf),
        ([0.0, 1.0], 0.5, 0.5),
        # Normal /Domain [0, 1], in-range
        ([0.0, 1.0], 0.0, 0.0),
        ([0.0, 1.0], 1.0, 1.0),
        ([0.0, 1.0], -0.1, -0.1),  # NOT clipped
        ([0.0, 1.0], 1.1, 1.1),  # NOT clipped
        # Non-trivial /Domain — input still not clipped
        ([-2.0, 2.0], -3.0, -3.0),
        ([-2.0, 2.0], 3.0, 3.0),
        ([-2.0, 2.0], 0.0, 0.0),
        # Inverted /Domain — input still not clipped
        ([1.0, 0.0], -1.0, -1.0),
        ([1.0, 0.0], 5.0, 5.0),
    ],
    ids=[
        "inf-up", "inf-dn", "in-range-mid",
        "in-range-lo", "in-range-hi", "below-lo", "above-hi",
        "neg-domain-below", "neg-domain-above", "neg-domain-zero",
        "inverted-domain-below", "inverted-domain-above",
    ],
)
def test_type2_eval_does_not_clip_input_to_domain(
    domain: list[float], input_x: float, expected_y: float
) -> None:
    """Type 2 eval does NOT clip its input to /Domain.

    Apache PDFBox 3.0.7 ``PDFunctionType2.eval`` reads ``input[0]`` directly
    (PDFunctionType2.java:90-104) — confirmed against the ShadingFuncProbe
    oracle. With C0=0, C1=1, N=1 the function is the identity, so the output
    equals the (unclamped) input. /Domain governs how *consumers* (e.g.
    shadings) sample the function, not how eval treats out-of-range inputs.
    """
    fn = _make_type2_with_clip(domain=domain)
    out = fn.eval([input_x])[0]
    if math.isinf(expected_y):
        assert out == expected_y
    else:
        assert math.isclose(out, expected_y, rel_tol=1e-9, abs_tol=1e-9), (
            f"/Domain={domain} input={input_x}: got {out} want {expected_y}"
        )


# ---------- /Range clipping ----------


@pytest.mark.parametrize(
    ("range_", "raw_output", "expected_clipped"),
    [
        # /Range = [0, 1]
        ([0.0, 1.0], 0.5, 0.5),
        ([0.0, 1.0], -0.5, 0.0),
        ([0.0, 1.0], 1.5, 1.0),
        ([0.0, 1.0], math.inf, 1.0),
        ([0.0, 1.0], -math.inf, 0.0),
        # Negative /Range
        ([-2.0, 2.0], 3.0, 2.0),
        ([-2.0, 2.0], -3.0, -2.0),
        # Inverted /Range
        ([1.0, 0.0], 5.0, 1.0),
        ([1.0, 0.0], -5.0, 0.0),
    ],
    ids=[
        "in-range", "below-min", "above-max", "inf-up", "inf-dn",
        "neg-above", "neg-below", "inverted-above", "inverted-below",
    ],
)
def test_range_clipping_via_clip_output(
    range_: list[float], raw_output: float, expected_clipped: float
) -> None:
    """``clip_output`` clamps each output to its /Range pair (normalised
    for inverted pairs).
    """
    fn = _make_type2_with_clip(domain=[0.0, 1.0], range_=range_)
    out = fn.clip_output([raw_output])[0]
    assert math.isclose(out, expected_clipped, rel_tol=1e-9, abs_tol=1e-9), (
        f"/Range={range_} raw={raw_output}: got {out} want {expected_clipped}"
    )


def test_clip_output_passes_through_when_range_absent() -> None:
    """Without /Range, clip_output returns inputs unchanged — Type 2 and
    Type 3 allow this since /Range is optional for them."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunctionType2(raw)
    assert fn.clip_output([100.0, -50.0]) == pytest.approx([100.0, -50.0], abs=1e-9)


def test_clip_input_passes_excess_through_unchanged() -> None:
    """Inputs beyond the declared /Domain dimension count are returned
    unchanged (no clamping happens)."""
    fn = _make_type2_with_clip(domain=[0.0, 1.0])
    # /Domain has 1 pair; input has 3 values — only the first is clamped.
    out = fn.clip_input([0.5, 999.0, -999.0])
    assert math.isclose(out[0], 0.5, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(out[1], 999.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(out[2], -999.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Identity sentinel passes through unchanged ----------


def test_identity_eval_passes_through() -> None:
    """The /Identity sentinel returns its input unchanged regardless of
    shape — single, multi-dim, even a 4-vector."""
    fn = PDFunctionTypeIdentity()
    assert fn.eval([0.5]) == pytest.approx([0.5], abs=1e-9)
    assert fn.eval([0.1, 0.2, 0.3, 0.4]) == pytest.approx(
        [0.1, 0.2, 0.3, 0.4], abs=1e-9
    )
    assert fn.eval([]) == []
