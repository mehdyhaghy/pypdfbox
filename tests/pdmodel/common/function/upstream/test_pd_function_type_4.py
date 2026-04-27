"""Tests ported from upstream PDFBox 3.0
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/TestPDFunctionType4.java``.

The upstream class exercises the higher-level wrapper (factory creation,
domain/range round-tripping, end-to-end eval against a hand-rolled
PostScript body). Per-operator coverage lives in
``upstream/test_pd_function_type4.py`` (ported from
``type4/TestOperators.java``); this file complements it.

Skipped:
* Java type-distinction assertions (``instanceof Float``) — pypdfbox
  collapses to ``float`` on the way out.
* Logger / IOException-message text checks — Python error surface differs.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionType4


def _build_stream(body: str, domain: list[float], rng: list[float]) -> COSStream:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    d = COSArray()
    d.set_float_array(domain)
    raw.set_item("Domain", d)
    r = COSArray()
    r.set_float_array(rng)
    raw.set_item("Range", r)
    raw.set_data(body.encode("ascii"))
    return raw


# --------------------------------------------------------------------------
# Wrapper / factory
# --------------------------------------------------------------------------


def test_function_type_is_4() -> None:
    raw = _build_stream("{ }", [0.0, 1.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.get_function_type() == 4


def test_pdfunction_create_dispatches_to_type4() -> None:
    """Upstream: ``PDFunction.create`` returns a ``PDFunctionType4`` for
    ``/FunctionType 4`` streams."""
    raw = _build_stream("{ dup mul }", [-1.0, 1.0], [0.0, 1.0])
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType4)


def test_get_pd_stream_present() -> None:
    raw = _build_stream("{ }", [0.0, 1.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.get_pd_stream() is not None


# --------------------------------------------------------------------------
# Eval pipeline
# --------------------------------------------------------------------------


def test_eval_squaring_program() -> None:
    """Upstream: ``{ dup mul }`` over ``/Domain [-1, 1]`` is the canonical
    squaring tint transform."""
    raw = _build_stream("{ dup mul }", [-1.0, 1.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.eval([0.0]) == pytest.approx([0.0])
    assert fn.eval([0.5]) == pytest.approx([0.25])
    assert fn.eval([1.0]) == pytest.approx([1.0])
    assert fn.eval([-1.0]) == pytest.approx([1.0])


def test_eval_input_clipped_to_domain() -> None:
    """Upstream: Eval clips inputs through ``/Domain`` before running the
    program. Input 5.0 with /Domain [0, 1] clamps to 1.0."""
    raw = _build_stream("{ dup mul }", [0.0, 1.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.eval([5.0]) == pytest.approx([1.0])  # clamped to 1, then 1*1


def test_eval_output_clipped_to_range() -> None:
    """Upstream: Eval clips outputs through ``/Range`` after running.
    Result 25.0 (5*5) with /Range [0, 10] clamps to 10."""
    raw = _build_stream("{ dup mul }", [-100.0, 100.0], [0.0, 10.0])
    fn = PDFunctionType4(raw)
    assert fn.eval([5.0]) == pytest.approx([10.0])


def test_eval_two_input_program() -> None:
    """Upstream: a two-input function (mul of inputs) — exercises
    /Domain pair sizing."""
    raw = _build_stream("{ mul }", [-10.0, 10.0, -10.0, 10.0], [-1e9, 1e9])
    fn = PDFunctionType4(raw)
    assert fn.eval([3.0, 4.0]) == pytest.approx([12.0])


def test_eval_constant_program() -> None:
    """Upstream: a program that ignores its input and pushes a constant."""
    raw = _build_stream("{ pop 0.5 }", [0.0, 1.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.eval([0.0]) == pytest.approx([0.5])
    assert fn.eval([0.7]) == pytest.approx([0.5])
    assert fn.eval([1.0]) == pytest.approx([0.5])


# --------------------------------------------------------------------------
# Domain / Range round-trip
# --------------------------------------------------------------------------


def test_get_domain_round_trips() -> None:
    raw = _build_stream("{ }", [0.0, 1.0, -2.0, 3.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    domain = fn.get_domain()
    assert domain is not None
    assert domain.to_float_array() == pytest.approx([0.0, 1.0, -2.0, 3.0])


def test_get_range_round_trips() -> None:
    raw = _build_stream("{ }", [0.0, 1.0], [-5.0, 5.0, 0.0, 1.0])
    fn = PDFunctionType4(raw)
    rng = fn.get_range()
    assert rng is not None
    assert rng.to_float_array() == pytest.approx([-5.0, 5.0, 0.0, 1.0])


def test_get_number_of_input_parameters() -> None:
    raw = _build_stream("{ }", [0.0, 1.0, 0.0, 1.0, 0.0, 1.0], [0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.get_number_of_input_parameters() == 3


def test_get_number_of_output_parameters() -> None:
    raw = _build_stream("{ }", [0.0, 1.0], [0.0, 1.0, 0.0, 1.0])
    fn = PDFunctionType4(raw)
    assert fn.get_number_of_output_parameters() == 2
