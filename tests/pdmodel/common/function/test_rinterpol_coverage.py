"""Coverage tests for :mod:`pypdfbox.pdmodel.common.function.rinterpol`.

These tests target the branch step path (``self._rinterpol`` when
``step < len(self._in) - 1``) and the public ``calc_sample_index`` /
``get_samples`` accessors that the wave 1280 baseline left uncovered.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0, Rinterpol


def _stub_2d_function() -> PDFunctionType0:
    """Build a 2D function (2x2 grid) with 1 output value per cell.

    Samples laid out per upstream ``calcSampleIndex`` convention:
    first input dim varies fastest. Values are 0, 10, 20, 30 (8-bit).
    """
    cos = COSStream()
    cos.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(0))
    size = COSArray()
    size.add(COSInteger.get(2))
    size.add(COSInteger.get(2))
    cos.set_item(COSName.get_pdf_name("Size"), size)
    cos.set_item(COSName.get_pdf_name("BitsPerSample"), COSInteger.get(8))
    domain = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0):
        domain.add(COSFloat(v))
    cos.set_item(COSName.get_pdf_name("Domain"), domain)
    rng = COSArray()
    rng.add(COSFloat(0.0))
    rng.add(COSFloat(255.0))
    cos.set_item(COSName.get_pdf_name("Range"), rng)
    cos.set_raw_data(bytes([0, 10, 20, 30]))
    return PDFunctionType0(cos)


def test_rinterpol_2d_branch_recurses_when_prev_equals_next() -> None:
    """Branch step where ``in_prev == in_next`` for the leading axis
    forces the recursive descent without averaging two grid points.
    """
    func = _stub_2d_function()
    r = Rinterpol(func, [0.0, 0.5], [0, 0], [0, 1])
    out = r.rinterpolate()
    # axis0 collapsed to 0; axis1 fractional halfway between sample 0 (=0)
    # and sample 2 (=20) -> 10.
    assert len(out) == 1
    assert abs(out[0] - 10.0) < 1e-3


def test_rinterpol_2d_branch_with_two_axes_interpolated() -> None:
    """Both axes fractional; exercises the inner ``self._function.interpolate``
    blend on the branch step (lines 91-98).
    """
    func = _stub_2d_function()
    r = Rinterpol(func, [0.5, 0.5], [0, 0], [1, 1])
    out = r.rinterpolate()
    # Bilinear interpolation over [0, 10, 20, 30] at (0.5, 0.5) -> 15.
    assert abs(out[0] - 15.0) < 1e-3


def test_rinterpol_2d_branch_with_distinct_prev_next() -> None:
    """Top corner: every axis interpolated end-to-end."""
    func = _stub_2d_function()
    r = Rinterpol(func, [1.0, 1.0], [0, 0], [1, 1])
    out = r.rinterpolate()
    assert abs(out[0] - 30.0) < 1e-3


def test_calc_sample_index_2d_layout_matches_upstream() -> None:
    """Public ``calc_sample_index`` (line 113-118) computes a flat
    index with first axis varying fastest.
    """
    func = _stub_2d_function()
    r = Rinterpol(func, [0.0, 0.0], [0, 0], [0, 0])
    # (0,0) -> 0, (1,0) -> 1, (0,1) -> 2, (1,1) -> 3.
    assert r.calc_sample_index([0, 0]) == 0
    assert r.calc_sample_index([1, 0]) == 1
    assert r.calc_sample_index([0, 1]) == 2
    assert r.calc_sample_index([1, 1]) == 3


def test_get_samples_proxies_function() -> None:
    """``Rinterpol.get_samples`` (line 125) delegates to the parent
    function's decoded sample table.
    """
    func = _stub_2d_function()
    r = Rinterpol(func, [0.0, 0.0], [0, 0], [0, 0])
    samples = r.get_samples()
    assert samples == func.get_samples()
    # 2x2 grid -> 4 cells, each with 1 output dim.
    assert len(samples) == 4
    assert all(len(row) == 1 for row in samples)


def test_underscore_alias_matches_public_calc_sample_index() -> None:
    """``_calc_sample_index`` is the underscore alias preserved for
    in-module callers (line 121)."""
    func = _stub_2d_function()
    r = Rinterpol(func, [0.0, 0.0], [0, 0], [0, 0])
    assert r._calc_sample_index([1, 1]) == r.calc_sample_index([1, 1])
