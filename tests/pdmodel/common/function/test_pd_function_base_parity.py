from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType3,
    PDFunctionType4,
)
from pypdfbox.pdmodel.common.pd_range import PDRange

# ---------- get_domain_for_input / get_range_for_input ----------


def _type2_with_domain(domain: list[float]) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    raw.set_item("Domain", domain_arr)
    return PDFunctionType2(raw)


def test_get_domain_for_input_returns_first_pair() -> None:
    fn = _type2_with_domain([0.0, 1.0, -2.0, 2.0])
    assert fn.get_domain_for_input(0) == (0.0, 1.0)


def test_get_domain_for_input_returns_second_pair() -> None:
    fn = _type2_with_domain([0.0, 1.0, -2.0, 2.0])
    assert fn.get_domain_for_input(1) == (-2.0, 2.0)


def test_get_range_for_input_aliases_domain() -> None:
    fn = _type2_with_domain([0.25, 0.75])
    # Upstream typo: getRangeForInput actually returns the /Domain pair.
    assert fn.get_range_for_input(0) == fn.get_domain_for_input(0)
    assert fn.get_range_for_input(0) == (0.25, 0.75)


def test_get_domain_for_input_raises_when_out_of_range() -> None:
    fn = _type2_with_domain([0.0, 1.0])
    with pytest.raises(IndexError):
        fn.get_domain_for_input(5)


# ---------- get_range_for_output ----------


def test_get_range_for_output_returns_first_pair() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 0.5, -1.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    assert fn.get_range_for_output(0) == (0.0, 1.0)
    assert fn.get_range_for_output(1) == (0.0, 0.5)
    assert fn.get_range_for_output(2) == (-1.0, 1.0)


def test_get_range_for_output_raises_when_range_absent() -> None:
    fn = PDFunctionType2(COSDictionary())
    with pytest.raises(IndexError):
        fn.get_range_for_output(0)


# ---------- type predicates ----------


def test_is_function_type_2_true_for_type2() -> None:
    fn = PDFunctionType2(COSDictionary())
    assert fn.is_function_type_2() is True
    assert fn.is_function_type_0() is False
    assert fn.is_function_type_3() is False
    assert fn.is_function_type_4() is False


def test_is_function_type_0_true_for_type0() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.is_function_type_0() is True
    assert fn.is_function_type_2() is False


def test_is_function_type_3_true_for_type3() -> None:
    fn = PDFunctionType3(COSDictionary())
    assert fn.is_function_type_3() is True


def test_is_function_type_4_true_for_type4() -> None:
    fn = PDFunctionType4(COSStream())
    assert fn.is_function_type_4() is True


def test_type_predicates_all_false_for_abstract_base() -> None:
    base = PDFunction()
    assert base.is_function_type_0() is False
    assert base.is_function_type_2() is False
    assert base.is_function_type_3() is False
    assert base.is_function_type_4() is False


# ---------- eval_function alias ----------


def test_eval_function_delegates_to_eval() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(0.0)]))
    raw.set_item("C1", COSArray([COSFloat(1.0)]))
    raw.set_item("N", COSFloat(1.0))
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    fn = PDFunctionType2(raw)
    assert fn.eval_function([0.5]) == fn.eval([0.5])
    assert fn.eval_function([0.5]) == pytest.approx([0.5])


# ---------- to_array round trip ----------


def test_to_array_round_trip_floats() -> None:
    arr = PDFunction.to_array([0.0, 0.25, 0.5, 0.75, 1.0])
    assert isinstance(arr, COSArray)
    assert arr.size() == 5
    assert arr.to_float_array() == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_to_array_round_trip_empty() -> None:
    arr = PDFunction.to_array([])
    assert isinstance(arr, COSArray)
    assert arr.size() == 0


def test_to_array_round_trip_ints_promote_to_float() -> None:
    arr = PDFunction.to_array([1, 2, 3])
    assert arr.size() == 3
    assert arr.to_float_array() == pytest.approx([1.0, 2.0, 3.0])


def test_to_array_results_usable_as_domain() -> None:
    fn = PDFunctionType2(COSDictionary())
    fn.set_domain(PDFunction.to_array([0.0, 1.0, -1.0, 1.0]))
    assert fn.get_number_of_input_parameters() == 2
    assert fn.get_domain_for_input(1) == (-1.0, 1.0)


# ---------- /FunctionType code constants ----------


def test_function_type_constants_match_spec_values() -> None:
    """PDF 32000-1 §7.10.2 lists 0/2/3/4 — the constants must match
    so callers can branch on a named constant rather than a magic int."""
    assert PDFunction.FUNCTION_TYPE_SAMPLED == 0
    assert PDFunction.FUNCTION_TYPE_EXPONENTIAL == 2
    assert PDFunction.FUNCTION_TYPE_STITCHING == 3
    assert PDFunction.FUNCTION_TYPE_POSTSCRIPT == 4


def test_function_type_constants_align_with_subclasses() -> None:
    type0 = PDFunctionType0(COSStream()).get_function_type()
    type2 = PDFunctionType2(COSDictionary()).get_function_type()
    type3 = PDFunctionType3(COSDictionary()).get_function_type()
    type4 = PDFunctionType4(COSStream()).get_function_type()
    assert type0 == PDFunction.FUNCTION_TYPE_SAMPLED
    assert type2 == PDFunction.FUNCTION_TYPE_EXPONENTIAL
    assert type3 == PDFunction.FUNCTION_TYPE_STITCHING
    assert type4 == PDFunction.FUNCTION_TYPE_POSTSCRIPT


def test_function_type_constants_usable_in_branching() -> None:
    """Smoke: the constants compose with the predicate accessors."""
    fn = PDFunctionType2(COSDictionary())
    triggered = fn.get_function_type() == PDFunction.FUNCTION_TYPE_EXPONENTIAL
    assert triggered is True


# ---------- is_stream_backed ----------


def test_is_stream_backed_true_for_type0() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.is_stream_backed() is True
    assert fn.get_pd_stream() is not None


def test_is_stream_backed_true_for_type4() -> None:
    fn = PDFunctionType4(COSStream())
    assert fn.is_stream_backed() is True


def test_is_stream_backed_false_for_type2() -> None:
    fn = PDFunctionType2(COSDictionary())
    assert fn.is_stream_backed() is False
    assert fn.get_pd_stream() is None


def test_is_stream_backed_false_for_type3() -> None:
    fn = PDFunctionType3(COSDictionary())
    assert fn.is_stream_backed() is False


def test_is_stream_backed_false_for_default_constructor() -> None:
    """``PDFunction()`` allocates a fresh dictionary — never stream-backed."""
    base = PDFunction()
    assert base.is_stream_backed() is False


# ---------- get_pd_range_for_input ----------


def test_get_pd_range_for_input_returns_pd_range_first_pair() -> None:
    fn = _type2_with_domain([0.0, 1.0, -2.0, 2.0])
    rng = fn.get_pd_range_for_input(0)
    assert isinstance(rng, PDRange)
    assert rng.get_min() == pytest.approx(0.0)
    assert rng.get_max() == pytest.approx(1.0)


def test_get_pd_range_for_input_returns_pd_range_second_pair() -> None:
    fn = _type2_with_domain([0.0, 1.0, -2.0, 2.0])
    rng = fn.get_pd_range_for_input(1)
    assert rng.get_min() == pytest.approx(-2.0)
    assert rng.get_max() == pytest.approx(2.0)


def test_get_pd_range_for_input_raises_when_domain_missing() -> None:
    """Without /Domain the upstream NPEs; we raise a deterministic
    ``ValueError`` so the call site can distinguish the two."""
    fn = PDFunctionType2(COSDictionary())
    with pytest.raises(ValueError):
        fn.get_pd_range_for_input(0)


def test_get_pd_range_for_input_aliases_tuple_accessor() -> None:
    """The PDRange wrapper and the tuple accessor must report identical
    bounds — they're two views over the same /Domain pair."""
    fn = _type2_with_domain([0.25, 0.75, -1.0, 1.0])
    rng0 = fn.get_pd_range_for_input(0)
    assert (rng0.get_min(), rng0.get_max()) == fn.get_domain_for_input(0)


# ---------- get_pd_range_for_output ----------


def test_get_pd_range_for_output_returns_pd_range_first_pair() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, -1.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    pd = fn.get_pd_range_for_output(0)
    assert isinstance(pd, PDRange)
    assert pd.get_min() == pytest.approx(0.0)
    assert pd.get_max() == pytest.approx(1.0)


def test_get_pd_range_for_output_indexes_into_array() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, -1.0, 1.0, -5.0, 5.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    pd = fn.get_pd_range_for_output(2)
    assert pd.get_min() == pytest.approx(-5.0)
    assert pd.get_max() == pytest.approx(5.0)


def test_get_pd_range_for_output_raises_when_range_missing() -> None:
    fn = PDFunctionType2(COSDictionary())
    with pytest.raises(ValueError):
        fn.get_pd_range_for_output(0)


def test_get_pd_range_for_output_aliases_tuple_accessor() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 0.5, -2.0, 2.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    pd = fn.get_pd_range_for_output(1)
    assert (pd.get_min(), pd.get_max()) == fn.get_range_for_output(1)


def test_get_pd_range_for_output_share_backing_array() -> None:
    """Mutating the wrapper writes through to the backing /Range array —
    confirms the wrapper is a live view, not a copy."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    pd = fn.get_pd_range_for_output(0)
    pd.set_max(0.5)
    # Re-read via the tuple accessor — the new bound should be visible.
    assert fn.get_range_for_output(0) == (0.0, 0.5)
