from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType0, Rinterpol


def _stub_function() -> PDFunctionType0:
    # Build a 1D function with 4 samples covering domain [0,1] → range [0,1].
    from pypdfbox.cos import COSInteger, COSName, COSStream

    cos = COSStream()
    cos.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(0))
    size = COSArray()
    size.add(COSInteger.get(4))
    cos.set_item(COSName.get_pdf_name("Size"), size)
    bits = COSInteger.get(8)
    cos.set_item(COSName.get_pdf_name("BitsPerSample"), bits)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    cos.set_item(COSName.get_pdf_name("Domain"), domain)
    rng = COSArray()
    rng.add(COSFloat(0.0))
    rng.add(COSFloat(1.0))
    cos.set_item(COSName.get_pdf_name("Range"), rng)
    # Sample bytes: 0, 85, 170, 255 (~0, 1/3, 2/3, 1 in 8-bit).
    cos.set_raw_data(bytes([0, 85, 170, 255]))
    func = PDFunctionType0(cos)
    return func


def test_rinterpolate_endpoint() -> None:
    func = _stub_function()
    r = Rinterpol(func, [0.0], [0], [0])
    out = r.rinterpolate()
    assert len(out) == 1
    assert abs(out[0] - 0.0) < 1e-6


def test_rinterpolate_midpoint() -> None:
    func = _stub_function()
    r = Rinterpol(func, [0.5], [0], [1])
    out = r.rinterpolate()
    assert len(out) == 1
    # interpolating between sample[0]=0 and sample[1]=85, in=0.5, prev=0, next=1
    # -> linear blend = 42.5
    assert abs(out[0] - 42.5) < 1e-3


def test_rinterpolate_top_sample() -> None:
    func = _stub_function()
    r = Rinterpol(func, [3.0], [3], [3])
    out = r.rinterpolate()
    assert abs(out[0] - 255.0) < 1e-6


def test_class_attributes() -> None:
    func = _stub_function()
    r = Rinterpol(func, [1.0], [1], [1])
    assert r._number_of_input_values == 1
    assert r._number_of_output_values == 1
