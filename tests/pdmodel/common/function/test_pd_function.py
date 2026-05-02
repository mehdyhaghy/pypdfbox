from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSStream
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType3,
    PDFunctionType4,
    PDFunctionTypeIdentity,
)


# ---------- subtype identification ----------


def test_function_type0_identifies_itself() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.get_function_type() == 0


def test_function_type2_identifies_itself() -> None:
    fn = PDFunctionType2(COSDictionary())
    assert fn.get_function_type() == 2


def test_function_type3_identifies_itself() -> None:
    fn = PDFunctionType3(COSDictionary())
    assert fn.get_function_type() == 3


def test_function_type4_identifies_itself() -> None:
    fn = PDFunctionType4(COSStream())
    assert fn.get_function_type() == 4


def test_base_function_type_is_abstract() -> None:
    base = PDFunction()
    with pytest.raises(NotImplementedError):
        base.get_function_type()


# ---------- Type 2 round trip ----------


def test_type2_round_trip_c0_c1_n() -> None:
    fn = PDFunctionType2()
    fn.set_c0([0.1, 0.2])
    fn.set_c1([0.9, 0.8])
    fn.set_n(1.0)

    assert fn.get_c0() == pytest.approx([0.1, 0.2])
    assert fn.get_c1() == pytest.approx([0.9, 0.8])
    assert fn.get_n() == pytest.approx(1.0)


def test_type2_defaults_when_keys_absent() -> None:
    fn = PDFunctionType2(COSDictionary())
    # PDF defaults per §7.10.3
    assert fn.get_c0() == [0.0]
    assert fn.get_c1() == [1.0]


# ---------- Type 3 typed children ----------


def test_type3_get_functions_wraps_each_child() -> None:
    child2 = COSDictionary()
    child2.set_int("FunctionType", 2)
    child2.set_item("C0", COSArray([COSFloat(0.0)]))
    child2.set_item("C1", COSArray([COSFloat(1.0)]))
    child2.set_item("N", COSFloat(1.0))

    child3 = COSDictionary()
    child3.set_int("FunctionType", 2)
    child3.set_item("C0", COSArray([COSFloat(1.0)]))
    child3.set_item("C1", COSArray([COSFloat(0.0)]))
    child3.set_item("N", COSFloat(2.0))

    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    parent.set_item("Functions", COSArray([child2, child3]))

    fn3 = PDFunctionType3(parent)
    children = fn3.get_functions()
    assert len(children) == 2
    assert all(isinstance(c, PDFunctionType2) for c in children)
    assert children[0].get_c1() == pytest.approx([1.0])
    assert children[1].get_n() == pytest.approx(2.0)


def test_type3_get_functions_empty_when_key_missing() -> None:
    fn3 = PDFunctionType3(COSDictionary())
    assert fn3.get_functions() == []


# ---------- create() dispatch ----------


def test_create_dispatches_type0() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    assert isinstance(PDFunction.create(raw), PDFunctionType0)


def test_create_dispatches_type2() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    assert isinstance(PDFunction.create(raw), PDFunctionType2)


def test_create_dispatches_type3() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    assert isinstance(PDFunction.create(raw), PDFunctionType3)


def test_create_dispatches_type4() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    assert isinstance(PDFunction.create(raw), PDFunctionType4)


def test_create_returns_none_for_none_input() -> None:
    assert PDFunction.create(None) is None


def test_create_rejects_unsupported_function_type() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 7)
    with pytest.raises(ValueError):
        PDFunction.create(raw)


def test_create_rejects_non_dictionary_input() -> None:
    with pytest.raises(TypeError):
        PDFunction.create(COSInteger.get(2))


# ---------- domain / range ----------


def test_domain_round_trip_and_input_count() -> None:
    fn = PDFunctionType2()
    domain = COSArray()
    domain.set_float_array([0.0, 1.0, 0.0, 1.0])
    fn.set_domain(domain)
    assert fn.get_domain() is domain
    assert fn.get_number_of_input_parameters() == 2


def test_range_round_trip_and_output_count() -> None:
    fn = PDFunctionType2()
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    fn.set_range(rng)
    assert fn.get_range() is rng
    assert fn.get_number_of_output_parameters() == 3


def test_output_count_zero_when_range_absent() -> None:
    fn = PDFunctionType2()
    assert fn.get_range() is None
    assert fn.get_number_of_output_parameters() == 0


# ---------- Type 0 accessors ----------


def test_type0_accessors() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    raw.set_item("Size", COSArray([COSInteger.get(4), COSInteger.get(4)]))
    raw.set_int("BitsPerSample", 8)
    raw.set_int("Order", 3)
    raw.set_item("Encode", COSArray([COSFloat(0.0), COSFloat(3.0)]))
    raw.set_item("Decode", COSArray([COSFloat(0.0), COSFloat(1.0)]))

    fn = PDFunctionType0(raw)
    size = fn.get_size()
    assert size is not None and size.size() == 2
    assert fn.get_bits_per_sample() == 8
    assert fn.get_order() == 3
    encode = fn.get_encode()
    assert encode is not None and encode.size() == 2
    decode = fn.get_decode()
    assert decode is not None and decode.size() == 2


def test_type0_order_defaults_to_one() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.get_order() == 1


# ---------- evaluation ----------


def _make_type2(c0: list[float], c1: list[float], n: float,
                domain: list[float] | None = None,
                rng: list[float] | None = None) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(v) for v in c0]))
    raw.set_item("C1", COSArray([COSFloat(v) for v in c1]))
    raw.set_item("N", COSFloat(n))
    if domain is not None:
        domain_arr = COSArray()
        domain_arr.set_float_array(domain)
        raw.set_item("Domain", domain_arr)
    if rng is not None:
        range_arr = COSArray()
        range_arr.set_float_array(rng)
        raw.set_item("Range", range_arr)
    return PDFunctionType2(raw)


def test_base_eval_is_abstract() -> None:
    base = PDFunction()
    with pytest.raises(NotImplementedError):
        base.eval([0.0])


def test_type2_eval_at_zero_returns_c0() -> None:
    fn = _make_type2([0.1, 0.2, 0.3], [0.9, 0.8, 0.7], 1.0, domain=[0.0, 1.0])
    assert fn.eval([0.0]) == pytest.approx([0.1, 0.2, 0.3])


def test_type2_eval_at_one_returns_c1() -> None:
    fn = _make_type2([0.1, 0.2, 0.3], [0.9, 0.8, 0.7], 1.0, domain=[0.0, 1.0])
    assert fn.eval([1.0]) == pytest.approx([0.9, 0.8, 0.7])


def test_type2_eval_at_half_with_n1_returns_midpoint() -> None:
    fn = _make_type2([0.0, 0.0], [1.0, 0.5], 1.0, domain=[0.0, 1.0])
    assert fn.eval([0.5]) == pytest.approx([0.5, 0.25])


def test_type2_eval_at_half_with_n2_returns_quarter() -> None:
    # x**N = 0.5**2 = 0.25
    fn = _make_type2([0.0, 1.0], [1.0, 0.0], 2.0, domain=[0.0, 1.0])
    # y[0] = 0 + 0.25*(1-0) = 0.25
    # y[1] = 1 + 0.25*(0-1) = 0.75
    assert fn.eval([0.5]) == pytest.approx([0.25, 0.75])


def test_type2_eval_clips_output_when_range_present() -> None:
    fn = _make_type2(
        [0.0], [2.0], 1.0, domain=[0.0, 1.0], rng=[0.0, 1.0]
    )
    # Without clipping y(1.0) = 2.0; clipped to /Range upper bound 1.0.
    assert fn.eval([1.0]) == pytest.approx([1.0])


def test_clip_input_clamps_below_min() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, domain=[0.2, 0.8])
    assert fn.clip_input([-5.0]) == pytest.approx([0.2])


def test_clip_input_clamps_above_max() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, domain=[0.2, 0.8])
    assert fn.clip_input([5.0]) == pytest.approx([0.8])


def test_get_ranges_for_inputs_pairs_domain() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, domain=[0.0, 1.0, -2.0, 2.0])
    assert fn.get_ranges_for_inputs() == [(0.0, 1.0), (-2.0, 2.0)]


def test_get_ranges_for_outputs_pairs_range() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, rng=[0.0, 1.0, 0.0, 0.5])
    assert fn.get_ranges_for_outputs() == [(0.0, 1.0), (0.0, 0.5)]


def _make_type0(
    size: list[int],
    bits: int,
    domain: list[float],
    rng: list[float],
    body: bytes,
    encode: list[float] | None = None,
    decode: list[float] | None = None,
    order: int | None = None,
) -> PDFunctionType0:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    size_arr = COSArray()
    for s in size:
        size_arr.add(COSInteger.get(s))
    raw.set_item("Size", size_arr)
    raw.set_int("BitsPerSample", bits)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    raw.set_item("Domain", domain_arr)
    range_arr = COSArray()
    range_arr.set_float_array(rng)
    raw.set_item("Range", range_arr)
    if encode is not None:
        encode_arr = COSArray()
        encode_arr.set_float_array(encode)
        raw.set_item("Encode", encode_arr)
    if decode is not None:
        decode_arr = COSArray()
        decode_arr.set_float_array(decode)
        raw.set_item("Decode", decode_arr)
    if order is not None:
        raw.set_int("Order", order)
    raw.set_raw_data(body)
    return PDFunctionType0(raw)


def test_type0_eval_1d_endpoints_and_midpoint() -> None:
    fn = _make_type0(
        size=[3],
        bits=8,
        domain=[0.0, 1.0],
        rng=[0.0, 1.0],
        body=bytes([0x00, 0x80, 0xFF]),
    )
    assert fn.eval([0.0]) == pytest.approx([0.0])
    # 0x80/0xFF = 128/255 ≈ 0.5019607
    assert fn.eval([0.5]) == pytest.approx([0x80 / 0xFF])
    assert fn.eval([1.0]) == pytest.approx([1.0])


def test_type0_eval_2d_corners_and_center() -> None:
    # 2x2 grid, samples laid out with the first dim varying fastest:
    #   (0,0)=0x00  (1,0)=0xFF  (0,1)=0xFF  (1,1)=0x00
    fn = _make_type0(
        size=[2, 2],
        bits=8,
        domain=[0.0, 1.0, 0.0, 1.0],
        rng=[0.0, 1.0],
        body=bytes([0x00, 0xFF, 0xFF, 0x00]),
    )
    assert fn.eval([0.0, 0.0]) == pytest.approx([0.0])
    assert fn.eval([1.0, 0.0]) == pytest.approx([1.0])
    assert fn.eval([0.0, 1.0]) == pytest.approx([1.0])
    assert fn.eval([1.0, 1.0]) == pytest.approx([0.0])
    # Center: 4-corner average = (0 + 255 + 255 + 0) / 4 / 255 = 0.5
    assert fn.eval([0.5, 0.5]) == pytest.approx([0.5])


def test_type0_order3_1d_exact_at_sample_points() -> None:
    """Catmull-Rom hits each sample exactly at the integer encoded position."""
    # Samples [0, 0.25, 0.5, 0.75, 1.0] over /Domain [0, 4] map encoded
    # positions 0..4 to those exact floats via /Decode = /Range = [0, 1].
    fn = _make_type0(
        size=[5],
        bits=8,
        domain=[0.0, 4.0],
        rng=[0.0, 1.0],
        body=bytes([0x00, 0x40, 0x80, 0xC0, 0xFF]),
        order=3,
    )
    assert fn.eval([0.0]) == pytest.approx([0x00 / 0xFF])
    assert fn.eval([1.0]) == pytest.approx([0x40 / 0xFF])
    assert fn.eval([2.0]) == pytest.approx([0x80 / 0xFF])
    assert fn.eval([3.0]) == pytest.approx([0xC0 / 0xFF])
    assert fn.eval([4.0]) == pytest.approx([0xFF / 0xFF])


def test_type0_order3_1d_midpoint_uses_cubic_hermite() -> None:
    """At t=0.5 between two interior samples the Catmull-Rom value matches
    the closed-form Hermite combination of the four bracketing samples."""
    samples = [0x00, 0x40, 0x80, 0xC0, 0xFF]
    fn = _make_type0(
        size=[5],
        bits=8,
        domain=[0.0, 4.0],
        rng=[-10.0, 10.0],  # wide range so cubic doesn't get clipped
        body=bytes(samples),
        order=3,
    )
    # Encoded position 1.5 → floor=1, frac=0.5; stencil samples are
    # s0=samples[0], s1=samples[1], s2=samples[2], s3=samples[3].
    # h00=0.5, h10=0.125, h01=0.5, h11=-0.125 at t=0.5.
    # m1 = (s2 - s0)/2, m2 = (s3 - s1)/2.
    s0, s1, s2, s3 = samples[0], samples[1], samples[2], samples[3]
    m1 = 0.5 * (s2 - s0)
    m2 = 0.5 * (s3 - s1)
    interp = 0.5 * s1 + 0.125 * m1 + 0.5 * s2 + (-0.125) * m2
    expected = interp * (10.0 - (-10.0)) / 0xFF + (-10.0)
    assert fn.eval([1.5]) == pytest.approx([expected])


def test_type0_order3_2d_smoke_4x4_grid() -> None:
    """Cubic 2D interpolation over a 4x4 grid: integer corners exact, mid-
    grid points stay inside the convex hull of neighbour samples."""
    # Diagonal ramp: cell (i, j) holds value (i + 4*j) * (255 / 15).
    body = bytes(int((i + 4 * j) * 255 / 15) for j in range(4) for i in range(4))
    fn = _make_type0(
        size=[4, 4],
        bits=8,
        domain=[0.0, 3.0, 0.0, 3.0],
        rng=[0.0, 1.0],
        body=body,
        order=3,
    )
    # Exact at integer-encoded corners.
    assert fn.eval([0.0, 0.0]) == pytest.approx([0.0])
    assert fn.eval([3.0, 3.0]) == pytest.approx([1.0])
    # Smoke: a center sample produces a value strictly in (0, 1).
    mid = fn.eval([1.5, 1.5])
    assert len(mid) == 1
    assert 0.0 < mid[0] < 1.0


def test_type0_order2_falls_back_to_linear() -> None:
    """/Order values other than 1 or 3 fall back to linear interpolation,
    behaviorally identical to the /Order = 1 result."""
    common = dict(
        size=[3],
        bits=8,
        domain=[0.0, 1.0],
        rng=[0.0, 1.0],
        body=bytes([0x00, 0x80, 0xFF]),
    )
    linear = _make_type0(**common)
    quadratic = _make_type0(**common, order=2)
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert quadratic.eval([x]) == pytest.approx(linear.eval([x]))


def test_type0_order3_boundary_clamps_no_index_error() -> None:
    """Cubic neighbour lookups at the /Domain edges must clamp to the valid
    sample range — no negative-index lookups, no IndexError."""
    fn = _make_type0(
        size=[3],
        bits=8,
        domain=[0.0, 1.0],
        rng=[0.0, 1.0],
        body=bytes([0x00, 0x80, 0xFF]),
        order=3,
    )
    # Edges of /Domain — should hit the first/last sample exactly via clamp.
    assert fn.eval([0.0]) == pytest.approx([0.0])
    assert fn.eval([1.0]) == pytest.approx([1.0])
    # Just inside each edge — exercises the (-1) and (+2) stencil offsets
    # through the clamp without crashing.
    near_lo = fn.eval([0.01])
    near_hi = fn.eval([0.99])
    assert 0.0 <= near_lo[0] <= 1.0
    assert 0.0 <= near_hi[0] <= 1.0


def test_type3_eval_routes_to_first_subfunction() -> None:
    # Subfunction 0: C0=[0], C1=[1], N=1 over encoded [0,1]
    sub0 = COSDictionary()
    sub0.set_int("FunctionType", 2)
    sub0.set_item("C0", COSArray([COSFloat(0.0)]))
    sub0.set_item("C1", COSArray([COSFloat(1.0)]))
    sub0.set_item("N", COSFloat(1.0))
    sub0_domain = COSArray()
    sub0_domain.set_float_array([0.0, 1.0])
    sub0.set_item("Domain", sub0_domain)

    # Subfunction 1: C0=[1], C1=[0], N=1 over encoded [0,1]
    sub1 = COSDictionary()
    sub1.set_int("FunctionType", 2)
    sub1.set_item("C0", COSArray([COSFloat(1.0)]))
    sub1.set_item("C1", COSArray([COSFloat(0.0)]))
    sub1.set_item("N", COSFloat(1.0))
    sub1_domain = COSArray()
    sub1_domain.set_float_array([0.0, 1.0])
    sub1.set_item("Domain", sub1_domain)

    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    parent_domain = COSArray()
    parent_domain.set_float_array([0.0, 1.0])
    parent.set_item("Domain", parent_domain)
    parent.set_item("Functions", COSArray([sub0, sub1]))
    parent.set_item("Bounds", COSArray([COSFloat(0.5)]))
    parent.set_item(
        "Encode",
        COSArray([COSFloat(0.0), COSFloat(1.0), COSFloat(0.0), COSFloat(1.0)]),
    )

    fn3 = PDFunctionType3(parent)
    # x = 0.25 falls in sub0's interval [0, 0.5]; mapped to 0.5 in encoded
    # [0,1]; sub0 (linear ramp 0->1) returns 0.5.
    assert fn3.eval([0.25]) == pytest.approx([0.5])
    # x = 0.75 falls in sub1's interval [0.5, 1.0]; mapped to 0.5; sub1
    # (linear ramp 1->0) returns 0.5.
    assert fn3.eval([0.75]) == pytest.approx([0.5])


# ---------- Type 4 PostScript-calculator eval ----------


def _make_type4(body: str, *,
                domain: list[float] | None = None,
                rng: list[float] | None = None) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    if domain is not None:
        domain_arr = COSArray()
        domain_arr.set_float_array(domain)
        raw.set_item("Domain", domain_arr)
    if rng is not None:
        range_arr = COSArray()
        range_arr.set_float_array(rng)
        raw.set_item("Range", range_arr)
    raw.set_data(body.encode("ascii"))
    return PDFunctionType4(raw)


def test_type4_eval_empty_body_echoes_input() -> None:
    fn = _make_type4("{ }", domain=[0.0, 10.0])
    assert fn.eval([1.0]) == pytest.approx([1.0])


def test_type4_eval_dup_mul_squares_input() -> None:
    fn = _make_type4("{ dup mul }", domain=[-10.0, 10.0])
    assert fn.eval([3.0]) == pytest.approx([9.0])


def test_type4_eval_exch_sub_abs() -> None:
    fn = _make_type4("{ exch sub abs }", domain=[0.0, 10.0, 0.0, 10.0])
    assert fn.eval([5.0, 3.0]) == pytest.approx([2.0])


def test_type4_eval_geometric_mean_of_squares() -> None:
    fn = _make_type4(
        "{ dup mul exch dup mul add 0.5 mul }",
        domain=[-10.0, 10.0, -10.0, 10.0],
    )
    assert fn.eval([3.0, 4.0]) == pytest.approx([12.5])


def test_type4_eval_if_branch_taken() -> None:
    # abs(x) via if: dup 0 lt {neg} if  — dup so the comparison doesn't
    # consume the value being abs'd.
    fn = _make_type4("{ dup 0 lt {neg} if }", domain=[-10.0, 10.0])
    assert fn.eval([-5.0]) == pytest.approx([5.0])


def test_type4_eval_if_branch_not_taken() -> None:
    fn = _make_type4("{ dup 0 lt {neg} if }", domain=[-10.0, 10.0])
    assert fn.eval([5.0]) == pytest.approx([5.0])


def test_type4_eval_true_false_and() -> None:
    fn = _make_type4("{ true false and }")
    # bools coerce to 0.0/1.0 in the returned float list
    assert fn.eval([]) == pytest.approx([0.0])


def test_type4_eval_stack_underflow_raises() -> None:
    fn = _make_type4("{ pop }")
    with pytest.raises(OSError):
        fn.eval([])


def test_type4_eval_ifelse_picks_branch() -> None:
    # |x| via ifelse: dup 0 lt {neg}{} ifelse
    fn = _make_type4("{ dup 0 lt {neg}{} ifelse }", domain=[-10.0, 10.0])
    assert fn.eval([-7.0]) == pytest.approx([7.0])
    assert fn.eval([4.0]) == pytest.approx([4.0])


def test_type4_eval_unknown_operator_raises() -> None:
    fn = _make_type4("{ banana }")
    with pytest.raises(OSError):
        fn.eval([1.0])


def test_type4_eval_clips_input_and_output() -> None:
    fn = _make_type4("{ dup mul }", domain=[-2.0, 2.0], rng=[0.0, 4.0])
    # input 5.0 clipped to 2.0 -> 4.0; output stays at 4.0
    assert fn.eval([5.0]) == pytest.approx([4.0])
    # input -10.0 clipped to -2.0 -> 4.0
    assert fn.eval([-10.0]) == pytest.approx([4.0])


# ---------- interpolate static helper ----------


def test_interpolate_maps_endpoints() -> None:
    assert PDFunction.interpolate(0.0, 0.0, 1.0, 10.0, 20.0) == pytest.approx(10.0)
    assert PDFunction.interpolate(1.0, 0.0, 1.0, 10.0, 20.0) == pytest.approx(20.0)


def test_interpolate_maps_midpoint() -> None:
    assert PDFunction.interpolate(0.5, 0.0, 1.0, 10.0, 20.0) == pytest.approx(15.0)


def test_interpolate_degenerate_x_range_returns_y_min() -> None:
    """PDFBOX-5593: when xMax == xMin, return yMin instead of dividing by zero."""
    assert PDFunction.interpolate(0.5, 1.0, 1.0, 10.0, 20.0) == pytest.approx(10.0)


def test_interpolate_inverted_y_range() -> None:
    # Interpolating over an inverted output range still respects the
    # straight-line formula (y_max < y_min just yields a downward ramp).
    assert PDFunction.interpolate(0.5, 0.0, 1.0, 1.0, 0.0) == pytest.approx(0.5)


# ---------- clip_to_range / clip_value_to_range upstream-named aliases ----------


def test_clip_to_range_alias_uses_range() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, rng=[0.0, 0.5])
    assert fn.clip_to_range([1.0]) == pytest.approx([0.5])


def test_clip_value_to_range_clamps_below_above() -> None:
    assert PDFunction.clip_value_to_range(-1.0, 0.0, 1.0) == pytest.approx(0.0)
    assert PDFunction.clip_value_to_range(2.0, 0.0, 1.0) == pytest.approx(1.0)
    assert PDFunction.clip_value_to_range(0.5, 0.0, 1.0) == pytest.approx(0.5)


def test_clip_value_to_range_swapped_bounds() -> None:
    # Tolerate min > max — normalise then clamp.
    assert PDFunction.clip_value_to_range(0.5, 1.0, 0.0) == pytest.approx(0.5)
    assert PDFunction.clip_value_to_range(2.0, 1.0, 0.0) == pytest.approx(1.0)


# ---------- __str__ matches upstream ----------


def test_str_reports_function_type_number() -> None:
    # Type 4 keeps the base-class ``__str__`` ("FunctionType<n>") since the
    # subclass does not override toString upstream either. Type 2 has its
    # own override (see test_pd_function_type_2.py for that format).
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    fn = PDFunction.create(raw)
    assert str(fn) == "FunctionType4"


# ---------- /Type = /Function set on stream construction ----------


def test_stream_construction_sets_type_function() -> None:
    raw = COSStream()
    PDFunctionType0(raw)
    type_name = raw.get_dictionary_object("Type")
    assert isinstance(type_name, COSName)
    assert type_name.get_name() == "Function"


# ---------- Identity sentinel handling ----------


def test_create_returns_identity_for_cos_name_identity() -> None:
    result = PDFunction.create(COSName.get_pdf_name("Identity"))
    assert isinstance(result, PDFunctionTypeIdentity)


def test_identity_eval_returns_input_unchanged() -> None:
    fn = PDFunctionTypeIdentity()
    assert fn.eval([0.1, 0.2, 0.3]) == [0.1, 0.2, 0.3]


def test_identity_str_matches_upstream() -> None:
    assert str(PDFunctionTypeIdentity()) == "FunctionTypeIdentity"


def test_identity_get_range_is_none() -> None:
    assert PDFunctionTypeIdentity().get_range() is None


def test_identity_get_function_type_raises() -> None:
    fn = PDFunctionTypeIdentity()
    with pytest.raises(NotImplementedError):
        fn.get_function_type()


def test_identity_constructor_accepts_optional_cos_base() -> None:
    """Mirrors upstream ``PDFunctionTypeIdentity(COSBase function)`` — the
    argument is discarded but exists so Java call sites translate cleanly."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 99)  # arbitrary — must be ignored
    fn = PDFunctionTypeIdentity(raw)
    # Discarded: the wrapper still behaves like the no-arg form.
    assert fn.eval([0.5, 0.7]) == [0.5, 0.7]
    assert fn.get_range() is None


def test_identity_constructor_accepts_none_for_java_null_calls() -> None:
    """Java port pattern: ``new PDFunctionTypeIdentity(null)`` — must work."""
    fn = PDFunctionTypeIdentity(None)
    assert fn.eval([1.0]) == [1.0]


def test_identity_get_range_values_returns_none() -> None:
    """Mirrors the protected ``PDFunctionTypeIdentity.getRangeValues()``
    override which returns ``null`` so base ``clipToRange`` is a no-op."""
    assert PDFunctionTypeIdentity().get_range_values() is None


# ---------- *_values upstream-named aliases ----------


def test_get_domain_values_alias_returns_underlying_array() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    fn = PDFunction.create(raw)
    assert fn.get_domain_values() is domain


def test_get_domain_values_alias_returns_none_when_absent() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunction.create(raw)
    assert fn.get_domain_values() is None


def test_get_range_values_alias_returns_underlying_array() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([-2.0, 2.0])
    raw.set_item("Range", rng)
    fn = PDFunction.create(raw)
    assert fn.get_range_values() is rng


def test_get_range_values_alias_returns_none_when_absent() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunction.create(raw)
    assert fn.get_range_values() is None


def test_set_domain_values_alias_round_trips() -> None:
    fn = PDFunctionType2()
    domain = COSArray()
    domain.set_float_array([0.0, 0.5])
    fn.set_domain_values(domain)
    assert fn.get_domain() is domain
    # Numeric round-trip via the typed accessor.
    assert fn.get_domain_for_input(0) == pytest.approx((0.0, 0.5))


def test_set_domain_values_alias_with_none_removes_entry() -> None:
    fn = PDFunctionType2()
    arr = COSArray()
    arr.set_float_array([0.0, 1.0])
    fn.set_domain_values(arr)
    fn.set_domain_values(None)
    assert fn.get_domain() is None


def test_set_range_values_alias_round_trips() -> None:
    fn = PDFunctionType2()
    rng = COSArray()
    rng.set_float_array([-1.0, 1.0, -2.0, 2.0])
    fn.set_range_values(rng)
    assert fn.get_range() is rng
    assert fn.get_number_of_output_parameters() == 2


def test_set_range_values_alias_with_none_removes_entry() -> None:
    fn = PDFunctionType2()
    arr = COSArray()
    arr.set_float_array([0.0, 1.0])
    fn.set_range_values(arr)
    fn.set_range_values(None)
    assert fn.get_range() is None
