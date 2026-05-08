"""Hand-written coverage for ``PDFunctionType2`` (exponential interpolation).

Complements the broader Type-2 coverage in ``test_pd_function.py`` and the
upstream-ported tests in ``upstream/test_pd_function_type_2.py``. Focuses
on the accessor/setter surface (including the ``COSArray``-returning
parity helpers ``get_c0_array`` / ``get_c1_array``), default-value
behaviour when ``/C0`` / ``/C1`` / ``/N`` are absent, and the eval-shape
contract (output dimension follows ``/C0``, ``/Range`` clipping when
present, exponent semantics for negative bases).
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionType2

# --------------------------------------------------------------------------
# Constructor / type
# --------------------------------------------------------------------------


def test_default_construction_starts_empty() -> None:
    fn = PDFunctionType2()
    assert isinstance(fn.get_cos_object(), COSDictionary)
    # Spec defaults — no keys present means C0=[0], C1=[1], N=1.
    assert fn.get_c0() == [0.0]
    assert fn.get_c1() == [1.0]
    assert fn.get_n() == pytest.approx(1.0)


def test_get_function_type_is_2() -> None:
    assert PDFunctionType2().get_function_type() == 2


def test_factory_dispatches_to_type2() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType2)


# --------------------------------------------------------------------------
# /C0
# --------------------------------------------------------------------------


def test_set_c0_with_list_round_trips() -> None:
    fn = PDFunctionType2()
    fn.set_c0([0.1, 0.2, 0.3])
    assert fn.get_c0() == pytest.approx([0.1, 0.2, 0.3])


def test_set_c0_with_tuple_round_trips() -> None:
    fn = PDFunctionType2()
    fn.set_c0((0.4, 0.5))
    assert fn.get_c0() == pytest.approx([0.4, 0.5])


def test_set_c0_with_cosarray_stores_in_place() -> None:
    """Passing a pre-built COSArray must store that exact object —
    parity with upstream ``setC0(COSArray)``."""
    fn = PDFunctionType2()
    arr = COSArray()
    arr.set_float_array([0.7, 0.8])
    fn.set_c0(arr)
    assert fn.get_c0_array() is arr


def test_get_c0_array_returns_cosarray() -> None:
    fn = PDFunctionType2()
    fn.set_c0([0.25, 0.5])
    arr = fn.get_c0_array()
    assert isinstance(arr, COSArray)
    assert arr.to_float_array() == pytest.approx([0.25, 0.5])


def test_get_c0_array_default_is_zero() -> None:
    """Absent /C0 must materialise as [0.0] per spec."""
    fn = PDFunctionType2()
    arr = fn.get_c0_array()
    assert isinstance(arr, COSArray)
    assert arr.to_float_array() == pytest.approx([0.0])


# --------------------------------------------------------------------------
# /C1
# --------------------------------------------------------------------------


def test_set_c1_with_list_round_trips() -> None:
    fn = PDFunctionType2()
    fn.set_c1([0.6, 0.7])
    assert fn.get_c1() == pytest.approx([0.6, 0.7])


def test_set_c1_with_cosarray_stores_in_place() -> None:
    fn = PDFunctionType2()
    arr = COSArray()
    arr.set_float_array([1.0, 2.0])
    fn.set_c1(arr)
    assert fn.get_c1_array() is arr


def test_get_c1_array_default_is_one() -> None:
    """Absent /C1 must materialise as [1.0] per spec."""
    fn = PDFunctionType2()
    arr = fn.get_c1_array()
    assert isinstance(arr, COSArray)
    assert arr.to_float_array() == pytest.approx([1.0])


# --------------------------------------------------------------------------
# /N
# --------------------------------------------------------------------------


def test_set_n_round_trips() -> None:
    fn = PDFunctionType2()
    fn.set_n(2.5)
    assert fn.get_n() == pytest.approx(2.5)


def test_get_n_default_is_one() -> None:
    fn = PDFunctionType2()
    assert fn.get_n() == pytest.approx(1.0)


def test_set_n_uses_cosfloat_storage() -> None:
    fn = PDFunctionType2()
    fn.set_n(3.0)
    stored = fn.get_cos_object().get_dictionary_object("N")
    assert isinstance(stored, COSFloat)


# --------------------------------------------------------------------------
# eval — basic shape
# --------------------------------------------------------------------------


def _make(
    c0: list[float],
    c1: list[float],
    n: float,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    c0_arr = COSArray()
    c0_arr.set_float_array(c0)
    raw.set_item("C0", c0_arr)
    c1_arr = COSArray()
    c1_arr.set_float_array(c1)
    raw.set_item("C1", c1_arr)
    raw.set_item("N", COSFloat(n))
    if domain is not None:
        d = COSArray()
        d.set_float_array(domain)
        raw.set_item("Domain", d)
    if rng is not None:
        r = COSArray()
        r.set_float_array(rng)
        raw.set_item("Range", r)
    return PDFunctionType2(raw)


def test_eval_at_zero_returns_c0_for_any_n() -> None:
    """x=0 → x**N=0 (for N>0) → result == C0."""
    for n in (0.5, 1.0, 2.0, 3.0):
        fn = _make([0.2, 0.4], [0.8, 1.0], n, domain=[0.0, 1.0])
        assert fn.eval([0.0]) == pytest.approx([0.2, 0.4]), f"failed for N={n}"


def test_eval_at_one_returns_c1_for_any_n() -> None:
    """x=1 → x**N=1 → result == C1."""
    for n in (0.5, 1.0, 2.0, 3.0):
        fn = _make([0.2, 0.4], [0.8, 1.0], n, domain=[0.0, 1.0])
        assert fn.eval([1.0]) == pytest.approx([0.8, 1.0]), f"failed for N={n}"


def test_eval_uses_only_first_input() -> None:
    """Type 2 has 1 input dimension by spec; trailing inputs are ignored."""
    fn = _make([0.0], [1.0], 1.0, domain=[0.0, 1.0, 0.0, 1.0])
    # Even with two domain pairs, Type 2 reads input[0].
    assert fn.eval([0.5, 99.0]) == pytest.approx([0.5])


def test_eval_output_dim_follows_min_of_c0_and_c1() -> None:
    """Output is sized by ``min(len(/C0), len(/C1))`` — upstream parity
    (PDFunctionType2.eval allocates ``new float[Math.min(c0.size(),
    c1.size())]``)."""
    # /C0 = [0,0,0]  /C1 = [1,1,1,1,1] — extra C1 entries get ignored.
    fn = _make([0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0, 1.0], 1.0, domain=[0.0, 1.0])
    out = fn.eval([0.5])
    assert len(out) == 3
    assert out == pytest.approx([0.5, 0.5, 0.5])


def test_eval_truncates_when_c1_shorter_than_c0() -> None:
    """Mirror upstream: when /C1 is shorter, output is sized by /C1
    (the smaller of the two), not padded out to /C0."""
    fn = _make([0.5, 0.5, 0.5], [1.0], 1.0, domain=[0.0, 1.0])
    # Sized by len(/C1) = 1 — only j=0 is evaluated.
    # j=0: 0.5 + 1.0*(1.0-0.5) = 1.0
    assert fn.eval([1.0]) == pytest.approx([1.0])


# --------------------------------------------------------------------------
# eval — exponent semantics
# --------------------------------------------------------------------------


def test_eval_exponent_quarter_at_half() -> None:
    """N=2 at x=0.5 → x**N = 0.25."""
    fn = _make([0.0], [1.0], 2.0, domain=[0.0, 1.0])
    assert fn.eval([0.5]) == pytest.approx([0.25])


def test_eval_exponent_eighth_at_half() -> None:
    """N=3 at x=0.5 → x**N = 0.125."""
    fn = _make([0.0], [1.0], 3.0, domain=[0.0, 1.0])
    assert fn.eval([0.5]) == pytest.approx([0.125])


def test_eval_fractional_exponent() -> None:
    """N=0.5 at x=0.25 → x**N = 0.5 → midpoint of C0..C1."""
    fn = _make([0.0], [1.0], 0.5, domain=[0.0, 1.0])
    assert fn.eval([0.25]) == pytest.approx([0.5])


def test_wave323_eval_fractional_exponent_negative_input_returns_nan() -> None:
    """Negative base with fractional /N stays in the float domain."""
    fn = _make([0.0], [1.0], 0.5, domain=[-1.0, 1.0], rng=[0.0, 1.0])

    out = fn.eval([-0.25])

    assert len(out) == 1
    assert math.isnan(out[0])


# --------------------------------------------------------------------------
# eval — clipping
# --------------------------------------------------------------------------


def test_eval_clips_input_to_domain() -> None:
    """Input above /Domain max gets clamped before exponent applies."""
    fn = _make([0.0], [1.0], 1.0, domain=[0.0, 0.5])
    # Input 5.0 clamps to 0.5 → result = 0 + 0.5*(1-0) = 0.5
    assert fn.eval([5.0]) == pytest.approx([0.5])


def test_eval_clips_input_below_domain() -> None:
    fn = _make([0.0], [1.0], 1.0, domain=[0.2, 1.0])
    # Input -1.0 clamps to 0.2 → result = 0 + 0.2*(1-0) = 0.2
    assert fn.eval([-1.0]) == pytest.approx([0.2])


def test_eval_clips_output_to_range() -> None:
    """Output above /Range max gets clamped (here C1=2 with range cap 1)."""
    fn = _make([0.0], [2.0], 1.0, domain=[0.0, 1.0], rng=[0.0, 1.0])
    assert fn.eval([1.0]) == pytest.approx([1.0])


def test_eval_clips_output_below_range_min() -> None:
    fn = _make([-1.0], [-2.0], 1.0, domain=[0.0, 1.0], rng=[0.0, 1.0])
    # Without clipping: 0+1*(-2- -1) = -2 → clamped to /Range min 0.
    assert fn.eval([1.0]) == pytest.approx([0.0])


def test_eval_no_range_no_clip() -> None:
    """When /Range is absent the raw eval result is returned unmodified."""
    fn = _make([0.0], [10.0], 1.0, domain=[0.0, 1.0])
    assert fn.eval([1.0]) == pytest.approx([10.0])


# --------------------------------------------------------------------------
# Defaults at eval time
# --------------------------------------------------------------------------


def test_eval_with_default_c0_c1_n_is_identity() -> None:
    """No /C0, /C1, or /N → defaults C0=[0], C1=[1], N=1 → eval(x) = [x]."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    fn = PDFunctionType2(raw)
    assert fn.eval([0.0]) == pytest.approx([0.0])
    assert fn.eval([0.5]) == pytest.approx([0.5])
    assert fn.eval([1.0]) == pytest.approx([1.0])


# --------------------------------------------------------------------------
# __str__ format mirrors upstream toString()
# --------------------------------------------------------------------------


def test_str_matches_upstream_format() -> None:
    """Upstream toString: ``"FunctionType2{C0: <c0> C1: <c1> N: <n>}"``."""
    fn = _make([0.25], [0.75], 2.0)
    rendered = str(fn)
    # Anchor on the structural markers — float reprs differ per platform but
    # the surrounding shape is stable.
    assert rendered.startswith("FunctionType2{")
    assert rendered.endswith("}")
    assert "C0:" in rendered
    assert "C1:" in rendered
    assert "N:" in rendered


def test_str_includes_default_c0_c1_n_when_keys_absent() -> None:
    """With no /C0 /C1 /N, the rendered string carries the spec defaults."""
    fn = PDFunctionType2()
    rendered = str(fn)
    assert "C0:" in rendered
    assert "C1:" in rendered
    # N defaults to 1.0 — accept either "1.0" or "1" in rendering.
    assert "N: 1" in rendered


# --------------------------------------------------------------------------
# Presence predicates: has_c0 / has_c1 / has_n
# --------------------------------------------------------------------------


def test_has_c0_false_when_key_absent() -> None:
    """An empty Type 2 dictionary advertises no explicit /C0 — the default
    materialised by ``get_c0`` is invisible to the predicate."""
    fn = PDFunctionType2()
    assert fn.has_c0() is False
    # Sanity: get_c0 still materialises the spec default.
    assert fn.get_c0() == [0.0]


def test_has_c0_true_after_set_c0() -> None:
    fn = PDFunctionType2()
    fn.set_c0([0.1, 0.2])
    assert fn.has_c0() is True


def test_has_c0_true_when_dictionary_has_c0_already() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    arr = COSArray()
    arr.set_float_array([0.5])
    raw.set_item("C0", arr)
    fn = PDFunctionType2(raw)
    assert fn.has_c0() is True


def test_has_c1_false_when_key_absent() -> None:
    fn = PDFunctionType2()
    assert fn.has_c1() is False
    assert fn.get_c1() == [1.0]


def test_has_c1_true_after_set_c1() -> None:
    fn = PDFunctionType2()
    fn.set_c1([0.6, 0.7])
    assert fn.has_c1() is True


def test_has_n_false_when_key_absent() -> None:
    fn = PDFunctionType2()
    assert fn.has_n() is False
    # Default is documented at 1.0 in this port.
    assert fn.get_n() == pytest.approx(1.0)


def test_has_n_true_after_set_n() -> None:
    fn = PDFunctionType2()
    fn.set_n(2.0)
    assert fn.has_n() is True


def test_predicates_independent() -> None:
    """Setting one key does not mark the others as present — predicates
    must reflect each key's physical presence independently."""
    fn = PDFunctionType2()
    fn.set_n(2.5)
    assert fn.has_n() is True
    assert fn.has_c0() is False
    assert fn.has_c1() is False


# --------------------------------------------------------------------------
# get_output_dimensions
# --------------------------------------------------------------------------


def test_get_output_dimensions_uses_range_when_present() -> None:
    """When /Range is set, output dimension count comes from /Range pairs."""
    fn = _make([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], 1.0,
               domain=[0.0, 1.0], rng=[0.0, 1.0, 0.0, 1.0])
    # /Range has 2 pairs even though C0/C1 have 3 entries — /Range wins.
    assert fn.get_output_dimensions() == 2


def test_get_output_dimensions_falls_back_to_min_of_c0_c1() -> None:
    """Without /Range, output dimension follows ``min(len(C0), len(C1))``,
    matching what eval actually allocates."""
    fn = _make([0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0, 1.0], 1.0,
               domain=[0.0, 1.0])
    assert fn.get_output_dimensions() == 3


def test_get_output_dimensions_with_shorter_c1() -> None:
    fn = _make([0.5, 0.5, 0.5], [1.0], 1.0, domain=[0.0, 1.0])
    assert fn.get_output_dimensions() == 1


def test_get_output_dimensions_with_defaults_is_one() -> None:
    """With no C0/C1 keys, both default to length-1 arrays per spec."""
    fn = PDFunctionType2()
    assert fn.get_output_dimensions() == 1


def test_get_output_dimensions_matches_eval_length() -> None:
    """The count returned must equal the actual eval output length —
    that's the contract documented in the docstring."""
    fn = _make([0.0, 0.0], [1.0, 1.0, 1.0, 1.0], 1.0, domain=[0.0, 1.0])
    expected = fn.get_output_dimensions()
    actual = len(fn.eval([0.5]))
    assert actual == expected
