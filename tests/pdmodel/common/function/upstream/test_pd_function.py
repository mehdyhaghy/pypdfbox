"""Upstream-style tests for ``PDFunction``.

Apache PDFBox does not ship a dedicated ``PDFunctionTest`` covering the
abstract base — only ``TestPDFunctionType4`` and the type4 sub-package
have direct upstream tests. The cases below exercise the abstract base
behaviour described in the upstream class javadoc and the public
contract that ``PDFunction.create()`` documents:

  - dispatching dictionary-backed and stream-backed functions to the
    correct concrete subtype,
  - rejecting non-dictionary / unsupported ``/FunctionType`` values
    with the ``IOException``-equivalent (``OSError`` per the project's
    Java-to-Python mapping; we surface ``ValueError``/``TypeError``
    today — see ``test_pd_function.py``),
  - the static ``interpolate`` helper (PDF 32000-1 §7.10.2),
  - the abstract ``toString()`` contract.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSObject, COSStream
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType3,
    PDFunctionType4,
    PDFunctionTypeIdentity,
)

# ---------- create() dispatch — mirrors the switch in PDFunction.java:134-146 ----------


def test_create_dispatches_to_type0_for_stream() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType0)
    assert fn.get_function_type() == 0


def test_create_dispatches_to_type2_for_dictionary() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType2)
    assert fn.get_function_type() == 2


def test_create_dispatches_to_type3_for_dictionary() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType3)
    assert fn.get_function_type() == 3


def test_create_dispatches_to_type4_for_stream() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType4)
    assert fn.get_function_type() == 4


def test_create_returns_identity_for_cos_name_identity() -> None:
    """Mirrors PDFunction.java:117-120 — the literal ``/Identity`` is
    recognised as a sentinel and yields a ``PDFunctionTypeIdentity``
    rather than going through the ``/FunctionType`` switch."""
    fn = PDFunction.create(COSName.get_pdf_name("Identity"))
    assert isinstance(fn, PDFunctionTypeIdentity)


def test_create_raises_for_unknown_function_type() -> None:
    """Mirrors PDFunction.java:144-145 (``throw new IOException``) —
    we surface ``ValueError`` so the call site can distinguish a
    missing function from an invalid one."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 99)
    with pytest.raises(ValueError):
        PDFunction.create(raw)


# ---------- get_cos_object — mirrors PDFunction.java:84-95 ----------


def test_get_cos_object_returns_dictionary_for_dict_backed() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunctionType2(raw)
    assert fn.get_cos_object() is raw


def test_get_cos_object_returns_stream_dictionary_for_stream_backed() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    fn = PDFunctionType0(raw)
    # The /Type entry is set on construction (PDFunction.java:58).
    assert fn.get_cos_object() is raw
    type_name = raw.get_dictionary_object("Type")
    assert isinstance(type_name, COSName)
    assert type_name.get_name() == "Function"


# ---------- get_pd_stream — mirrors PDFunction.java:101-104 ----------


def test_get_pd_stream_non_null_for_stream_backed() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.get_pd_stream() is not None


def test_get_pd_stream_null_for_dictionary_backed() -> None:
    fn = PDFunctionType2(COSDictionary())
    assert fn.get_pd_stream() is None


# ---------- getNumberOfInputParameters / getNumberOfOutputParameters ----------
# Mirrors PDFunction.java:159-174 and 209-217.


def test_number_of_input_parameters_counts_domain_pairs() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0, -2.0, 2.0, 0.0, 0.5])
    raw.set_item("Domain", domain)
    fn = PDFunctionType2(raw)
    assert fn.get_number_of_input_parameters() == 3


def test_number_of_output_parameters_counts_range_pairs() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    assert fn.get_number_of_output_parameters() == 2


def test_number_of_output_parameters_zero_when_range_absent() -> None:
    """Mirrors PDFunction.java:165-167 — ``rangeValues == null`` returns 0."""
    fn = PDFunctionType2(COSDictionary())
    assert fn.get_number_of_output_parameters() == 0


# ---------- getDomainForInput / getRangeForOutput pd_range wrappers ----------
# Mirrors PDFunction.java:185-189 and 228-232 — upstream returns ``PDRange``.


def test_get_pd_range_for_input_returns_pd_range_wrapper() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain = COSArray()
    domain.set_float_array([0.25, 0.75])
    raw.set_item("Domain", domain)
    fn = PDFunctionType2(raw)
    pd = fn.get_pd_range_for_input(0)
    assert pd.get_min() == pytest.approx(0.25)
    assert pd.get_max() == pytest.approx(0.75)


def test_get_pd_range_for_output_returns_pd_range_wrapper() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([-1.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    pd = fn.get_pd_range_for_output(0)
    assert pd.get_min() == pytest.approx(-1.0)
    assert pd.get_max() == pytest.approx(1.0)


# ---------- setDomainValues / setRangeValues — PDFunction.java:196-200, 239-243 ----------


def test_set_range_values_writes_through_to_dictionary() -> None:
    fn = PDFunctionType2(COSDictionary())
    rng = COSArray()
    rng.set_float_array([0.0, 1.0])
    fn.set_range_values(rng)
    assert fn.get_cos_object().get_dictionary_object("Range") is rng


def test_set_domain_values_writes_through_to_dictionary() -> None:
    fn = PDFunctionType2(COSDictionary())
    domain = COSArray()
    domain.set_float_array([0.0, 1.0, 0.0, 1.0])
    fn.set_domain_values(domain)
    assert fn.get_cos_object().get_dictionary_object("Domain") is domain


# ---------- clipToRange variants — PDFunction.java:293-335 ----------


def test_clip_to_range_clamps_each_output_to_its_range_pair() -> None:
    """Vector ``clipToRange(float[])`` — clamps each output to its
    ``/Range`` pair. Excess outputs (beyond range pairs) pass through."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, -1.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    # 5.0 clamps to 1.0; -2.0 clamps to -1.0; third value passes through.
    assert fn.clip_to_range([5.0, -2.0, 0.5]) == pytest.approx([1.0, -1.0, 0.5])


def test_clip_to_range_passes_through_when_range_absent() -> None:
    """Mirrors PDFunction.java:307-311 — when ``rangeValues == null`` the
    result is the input vector unchanged."""
    fn = PDFunctionType2(COSDictionary())
    assert fn.clip_to_range([3.14, -7.0]) == pytest.approx([3.14, -7.0])


def test_clip_value_to_range_below_min_returns_min() -> None:
    """Scalar ``clipToRange(float, float, float)`` — PDFunction.java:324-335."""
    assert PDFunction.clip_value_to_range(-5.0, 0.0, 1.0) == pytest.approx(0.0)


def test_clip_value_to_range_above_max_returns_max() -> None:
    assert PDFunction.clip_value_to_range(5.0, 0.0, 1.0) == pytest.approx(1.0)


def test_clip_value_to_range_in_range_returns_unchanged() -> None:
    assert PDFunction.clip_value_to_range(0.5, 0.0, 1.0) == pytest.approx(0.5)


# ---------- interpolate — PDFunction.java:349-357 ----------


def test_interpolate_at_x_min_returns_y_min() -> None:
    assert PDFunction.interpolate(0.0, 0.0, 1.0, 10.0, 20.0) == pytest.approx(10.0)


def test_interpolate_at_x_max_returns_y_max() -> None:
    assert PDFunction.interpolate(1.0, 0.0, 1.0, 10.0, 20.0) == pytest.approx(20.0)


def test_interpolate_at_midpoint_returns_y_midpoint() -> None:
    assert PDFunction.interpolate(0.5, 0.0, 1.0, 10.0, 20.0) == pytest.approx(15.0)


def test_interpolate_pdfbox_5593_degenerate_x_range() -> None:
    """Mirrors PDFunction.java:351-355 (PDFBOX-5593 / PR #162) —
    when ``xRangeMax == xRangeMin`` return ``yRangeMin`` rather than
    dividing by zero."""
    assert PDFunction.interpolate(0.5, 1.0, 1.0, 10.0, 20.0) == pytest.approx(10.0)


# ---------- toString — PDFunction.java:362-366 ----------


def test_to_string_reports_function_type_number() -> None:
    """Direct port of ``PDFunction.toString()`` — ``"FunctionType<n>"``."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunction.create(raw)
    assert fn.to_string() == "FunctionType2"


def test_to_string_aligns_with_str_dunder() -> None:
    """``__str__`` and ``to_string`` must return the same string so call
    sites translated from ``fn.toString()`` and Pythonic ``str(fn)``
    hit the same value."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    fn = PDFunction.create(raw)
    assert fn.to_string() == str(fn) == "FunctionType4"


def test_to_string_for_each_concrete_subtype() -> None:
    assert PDFunctionType0(COSStream()).to_string() == "FunctionType0"
    assert PDFunctionType2(COSDictionary()).to_string() == "FunctionType2"
    assert PDFunctionType3(COSDictionary()).to_string() == "FunctionType3"
    assert PDFunctionType4(COSStream()).to_string() == "FunctionType4"


def test_to_string_identity_subclass_returns_stable_label() -> None:
    """Identity has no ``/FunctionType`` — the override returns the
    stable label rather than the abstract-base ``"FunctionType?"`` fallback."""
    assert PDFunctionTypeIdentity().to_string() == "FunctionTypeIdentity"


# ---------- eval contract — PDFunction.java:257 (abstract) ----------


def test_base_eval_is_abstract() -> None:
    """``PDFunction.eval`` is abstract upstream — calling it on the
    bare base must raise rather than return a default vector."""
    base = PDFunction()
    with pytest.raises(NotImplementedError):
        base.eval([0.0])


def test_eval_uses_clip_to_range_in_subclasses() -> None:
    """Smoke: a Type2 with a ``/Range`` clamps its output via the
    inherited ``clipToRange``. Mirrors the Java-side expectation that
    subclasses delegate to the base helper rather than re-implementing."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(0.0)]))
    raw.set_item("C1", COSArray([COSFloat(2.0)]))
    raw.set_item("N", COSFloat(1.0))
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    # Without /Range clip the un-clipped output would be 2.0.
    assert fn.eval([1.0]) == pytest.approx([1.0])


# ---------- private cache fields — PDFunction.java:42-45 ----------
# Upstream caches ``domain`` / ``range`` (resolved COSArray) and
# ``numberOfInputValues`` / ``numberOfOutputValues`` (computed pair counts)
# as private fields with a ``-1`` / ``null`` sentinel. The tests below assert
# that pypdfbox's port has the same observable caching behaviour.


def test_set_range_values_updates_cached_array_reference() -> None:
    """Upstream ``setRangeValues`` (line 196-200) writes both the
    dictionary entry AND the private ``range`` cache. Subsequent
    ``getRangeValues`` must observe the new array without re-reading
    the dictionary."""
    fn = PDFunctionType2(COSDictionary())
    rng = COSArray()
    rng.set_float_array([0.0, 1.0])
    fn.set_range_values(rng)
    # First read primes the cache; second read returns the same instance.
    first = fn.get_range_values()
    second = fn.get_range_values()
    assert first is second is rng


def test_set_domain_values_updates_cached_array_reference() -> None:
    """Same contract as range — ``setDomainValues`` (line 239-243)
    primes the private ``domain`` cache."""
    fn = PDFunctionType2(COSDictionary())
    domain = COSArray()
    domain.set_float_array([0.0, 1.0, 0.0, 1.0])
    fn.set_domain_values(domain)
    first = fn.get_domain_values()
    second = fn.get_domain_values()
    assert first is second is domain


def test_input_parameter_count_uses_cached_value() -> None:
    """Mirrors PDFunction.java:211-216 — the count is computed once
    and stored in ``numberOfInputValues``. Two consecutive calls must
    return the identical value."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    raw.set_item("Domain", domain)
    fn = PDFunctionType2(raw)
    assert fn.get_number_of_input_parameters() == 3
    assert fn.get_number_of_input_parameters() == 3


def test_output_parameter_count_uses_cached_value() -> None:
    """Mirrors PDFunction.java:161-172 — the count is computed once
    and stored in ``numberOfOutputValues``."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    assert fn.get_number_of_output_parameters() == 2
    assert fn.get_number_of_output_parameters() == 2


def test_set_domain_values_invalidates_input_count_cache() -> None:
    """Upstream ``setDomainValues`` (line 241) updates the cached
    ``domain`` reference; the next ``getNumberOfInputParameters``
    call recomputes off the new array (its ``numberOfInputValues``
    sentinel is reset implicitly via the upstream contract)."""
    fn = PDFunctionType2(COSDictionary())
    one_dim = COSArray()
    one_dim.set_float_array([0.0, 1.0])
    fn.set_domain_values(one_dim)
    assert fn.get_number_of_input_parameters() == 1
    two_dim = COSArray()
    two_dim.set_float_array([0.0, 1.0, 0.0, 1.0])
    fn.set_domain_values(two_dim)
    assert fn.get_number_of_input_parameters() == 2


def test_set_range_values_invalidates_output_count_cache() -> None:
    """Same contract for ``/Range`` — replacing the array via
    ``setRangeValues`` flushes the cached output-pair count."""
    fn = PDFunctionType2(COSDictionary())
    one_dim = COSArray()
    one_dim.set_float_array([0.0, 1.0])
    fn.set_range_values(one_dim)
    assert fn.get_number_of_output_parameters() == 1
    three_dim = COSArray()
    three_dim.set_float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    fn.set_range_values(three_dim)
    assert fn.get_number_of_output_parameters() == 3


# ---------- create() unwraps COSObject indirect references ----------
# Mirrors PDFunction.java:122-126 — when a COSObject is passed in, it
# is dereferenced first; the inner value drives the type dispatch.


def test_create_unwraps_cos_object_indirect_reference_to_type2() -> None:
    """An indirect-reference object (``COSObject``) wrapping a Type-2
    dictionary must dispatch via the resolved underlying object — not
    raise on the wrapper type. Mirrors the ``base = ((COSObject) function)
    .getObject()`` line in upstream ``create``."""
    inner = COSDictionary()
    inner.set_int("FunctionType", 2)
    indirect = COSObject(1, 0, resolved=inner)
    fn = PDFunction.create(indirect)
    assert isinstance(fn, PDFunctionType2)


def test_create_unwraps_cos_object_indirect_reference_to_type3() -> None:
    """Same indirection as Type-2 — verifies the unwrap path is not
    branched on subtype."""
    inner = COSDictionary()
    inner.set_int("FunctionType", 3)
    indirect = COSObject(2, 0, resolved=inner)
    fn = PDFunction.create(indirect)
    assert isinstance(fn, PDFunctionType3)


def test_create_unwraps_cos_object_with_unresolved_reference_returns_none() -> None:
    """A ``COSObject`` whose ``getObject()`` resolves to ``None`` mirrors
    upstream's branch where the unwrap yields ``null`` and the
    ``IOException`` is thrown for "must be a Dictionary, but is (null)".
    pypdfbox treats the ``None`` resolution as the same case as
    ``create(None)`` — it returns ``None`` rather than raising, so the
    caller can distinguish missing from invalid."""
    indirect = COSObject(3, 0, resolved=None)
    indirect.set_object(None)  # explicit dereference, no inner value
    assert PDFunction.create(indirect) is None


# ---------- get_function_type abstract — PDFunction.java:78 ----------


def test_function_type_for_each_concrete_subtype_matches_upstream() -> None:
    """Mirrors the upstream ``getFunctionType()`` overrides in each
    concrete subclass — the int returned must match the spec values
    listed in PDFunction.java:67-77 (0, 2, 3, 4)."""
    assert PDFunctionType0(COSStream()).get_function_type() == 0
    assert PDFunctionType2(COSDictionary()).get_function_type() == 2
    assert PDFunctionType3(COSDictionary()).get_function_type() == 3
    assert PDFunctionType4(COSStream()).get_function_type() == 4


# ---------- stream constructor sets /Type /Function — PDFunction.java:55-58 ----------


def test_stream_constructor_sets_type_function_when_absent() -> None:
    """Mirrors ``functionStream.getCOSObject().setItem(COSName.TYPE,
    COSName.FUNCTION)`` — the stream variant always advertises
    ``/Type /Function`` so external introspection can recognise it
    without having to load the full PD wrapper."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    PDFunctionType4(raw)
    type_name = raw.get_dictionary_object("Type")
    assert isinstance(type_name, COSName)
    assert type_name.get_name() == "Function"


def test_stream_constructor_overwrites_existing_type_entry() -> None:
    """If the stream dictionary already carried a ``/Type`` value (rare
    but legal — e.g. a copy from an unrelated dictionary), upstream
    unconditionally overwrites it. Verify pypdfbox does the same."""
    raw = COSStream()
    raw.set_item("Type", COSName.get_pdf_name("XObject"))  # foreign value
    raw.set_int("FunctionType", 0)
    PDFunctionType0(raw)
    type_name = raw.get_dictionary_object("Type")
    assert isinstance(type_name, COSName)
    assert type_name.get_name() == "Function"


def test_dictionary_constructor_does_not_set_type_entry() -> None:
    """Mirrors PDFunction.java:60-63 — dictionary-backed functions go
    through the ``functionDictionary = (COSDictionary) function`` branch
    which deliberately does NOT touch ``/Type``."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    PDFunctionType2(raw)
    assert raw.get_dictionary_object("Type") is None


# ---------- get_pd_stream identity — PDFunction.java:101-104 ----------


def test_get_pd_stream_wraps_underlying_cos_stream() -> None:
    """Mirrors the upstream ``functionStream`` field — the stored
    ``PDStream`` references the same backing ``COSStream`` so changes
    flow through both views."""
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    fn = PDFunctionType0(raw)
    pd_stream = fn.get_pd_stream()
    assert pd_stream is not None
    # The wrapper exposes the same dictionary as the function itself.
    assert pd_stream.get_cos_object() is raw


# ---------- range values absent for Type 2 — PDFunction.java:264-271 ----------


def test_get_range_values_returns_none_for_dictionary_without_range() -> None:
    """``/Range`` is optional for Type 2 / 3 (legal per PDF 32000-1
    §7.10.3). Upstream returns ``null``; pypdfbox returns ``None``."""
    fn = PDFunctionType2(COSDictionary())
    assert fn.get_range_values() is None


# ---------- clipToRange empty array short-circuit — PDFunction.java:297 ----------


def test_clip_to_range_passes_through_when_range_array_is_empty() -> None:
    """Upstream guards ``rangesArray != null && rangesArray.size() > 0``
    — a present-but-empty ``/Range`` short-circuits the same as a
    missing one, returning the input vector unchanged."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("Range", COSArray())  # present but empty
    fn = PDFunctionType2(raw)
    assert fn.clip_to_range([3.14, -7.0]) == pytest.approx([3.14, -7.0])


# ---------- create() rejects non-dictionary base — PDFunction.java:127-131 ----------


def test_create_rejects_non_dictionary_cos_base_with_typed_error() -> None:
    """Mirrors ``throw new IOException("Error: Function must be a
    Dictionary, but is " + ...)``. pypdfbox surfaces ``TypeError`` so
    the call site can distinguish the malformed-input case from a
    missing function (``None`` input)."""
    with pytest.raises(TypeError):
        PDFunction.create(COSInteger.get(2))


# ---------- interpolate is callable on instances — PDFunction.java:349 ----------


def test_interpolate_callable_on_instance() -> None:
    """Upstream ``interpolate`` is a ``protected`` instance method, so
    subclasses dispatch via ``this.interpolate(...)``. pypdfbox exposes
    it as a static helper but must remain reachable through an instance
    so call sites translated from Java keep compiling."""
    fn = PDFunctionType2(COSDictionary())
    assert fn.interpolate(0.5, 0.0, 1.0, 10.0, 20.0) == pytest.approx(15.0)


# ---------- /Type /Function pre-existing — PDFunction.java:58 ----------


def test_stream_constructor_idempotent_when_type_already_function() -> None:
    """Constructing a stream-backed function over a stream that already
    has ``/Type /Function`` is a no-op — the value remains the same
    PDF name object."""
    raw = COSStream()
    raw.set_item("Type", COSName.get_pdf_name("Function"))
    raw.set_int("FunctionType", 0)
    PDFunctionType0(raw)
    type_name = raw.get_dictionary_object("Type")
    assert isinstance(type_name, COSName)
    assert type_name.get_name() == "Function"


# ---------- get_cos_object identity for stream — PDFunction.java:85-94 ----------


def test_get_cos_object_round_trip_returns_same_stream_dictionary() -> None:
    """Two calls to ``get_cos_object`` return the same dictionary
    instance — upstream returns ``functionStream.getCOSObject()`` which
    is a stable reference, not a fresh copy."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    fn = PDFunctionType4(raw)
    assert fn.get_cos_object() is fn.get_cos_object() is raw


def test_get_cos_object_round_trip_returns_same_dictionary() -> None:
    """Same identity guarantee for the dictionary-backed branch."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    fn = PDFunctionType2(raw)
    assert fn.get_cos_object() is fn.get_cos_object() is raw
