from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0


def _arr(values: list[float]) -> COSArray:
    out = COSArray()
    out.set_float_array(values)
    return out


def _size(values: list[int]) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(COSFloat(float(value)))
    return out


def _pack(values: list[int], bits: int) -> bytes:
    total_bits = len(values) * bits
    big = 0
    for value in values:
        big = (big << bits) | (value & ((1 << bits) - 1))
    pad = (-total_bits) % 8
    big <<= pad
    return big.to_bytes((total_bits + pad) // 8, "big") if total_bits else b""


def _stream_function(
    *,
    domain: list[float] | None = None,
    range_: list[float] | None = None,
    size: list[int] | None = None,
    bits: int = 8,
    samples: list[int] | None = None,
    encode: list[float] | None = None,
    decode: list[float] | None = None,
) -> PDFunctionType0:
    domain = [0.0, 1.0] if domain is None else domain
    range_ = [0.0, 1.0] if range_ is None else range_
    size = [2] if size is None else size
    samples = [0, 255] if samples is None else samples

    raw = COSStream()
    raw.set_item("Domain", _arr(domain))
    raw.set_item("Range", _arr(range_))
    raw.set_item("Size", _size(size))
    raw.set_int("BitsPerSample", bits)
    if encode is not None:
        raw.set_item("Encode", _arr(encode))
    if decode is not None:
        raw.set_item("Decode", _arr(decode))
    raw.set_data(_pack(samples, bits))
    return PDFunctionType0(raw)


def test_dictionary_backed_function_uses_empty_sample_body() -> None:
    raw = COSDictionary()
    raw.set_item("Domain", _arr([0.0, 1.0]))
    raw.set_item("Range", _arr([0.0, 1.0]))
    raw.set_item("Size", _size([2]))
    raw.set_int("BitsPerSample", 8)

    assert PDFunctionType0(raw).get_samples() == [[0], [0]]


def test_get_size_list_treats_non_numeric_entries_as_zero() -> None:
    fn = PDFunctionType0(COSStream())
    raw_size = COSArray()
    raw_size.add(COSName.get_pdf_name("NotANumber"))
    raw_size.add(COSFloat(3.0))
    fn.set_size(raw_size)

    assert fn._get_size_list() == [0, 3]


def test_encode_parameter_returns_none_when_domain_declares_more_than_size() -> None:
    fn = PDFunctionType0(COSDictionary())
    fn.set_domain(_arr([0.0, 1.0]))

    assert fn.get_encode_for_parameter(0) is None


def test_decode_parameter_returns_none_when_range_pairs_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fn = PDFunctionType0(COSDictionary())
    monkeypatch.setattr(fn, "get_number_of_output_parameters", lambda: 1)
    monkeypatch.setattr(fn, "get_ranges_for_outputs", lambda: [])

    assert fn.get_decode_for_parameter(0) is None


def test_eval_raises_for_partial_encode_missing_trailing_pairs() -> None:
    # /Encode present but too short for the 2nd input dim: upstream PDFBox does
    # NOT default-fill a partial /Encode — getEncodeForParameter(1) is null and
    # eval NPEs. pypdfbox raises ValueError to mirror that hard failure
    # (wave-1535 sampled-fuzz oracle).
    fn = _stream_function(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[2, 2],
        samples=[0, 10, 20, 30],
        encode=[0.0, 1.0],
    )

    with pytest.raises(ValueError, match="/Encode"):
        fn.eval([1.0, 1.0])


def test_decode_pairs_raise_when_decode_present_but_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A present-but-short /Decode is NOT default-filled (upstream returns it
    # verbatim; getDecodeForParameter is null past its length). _get_decode_pairs
    # therefore raises for the missing output dims rather than padding from
    # /Range / zero (wave-1535 sampled-fuzz oracle).
    fn = PDFunctionType0(COSDictionary())
    fn.set_decode(_arr([10.0, 20.0]))
    monkeypatch.setattr(
        fn, "get_ranges_for_outputs", lambda: [(-1.0, 1.0), (-2.0, 2.0)]
    )

    with pytest.raises(ValueError, match="/Decode"):
        fn._get_decode_pairs(3)


def test_decode_sample_grid_rejects_out_of_range_bits_and_invalid_size() -> None:
    # bits=33 is past pypdfbox's [0, 32] parity range (off-spec widths 0..32 are
    # now accepted like upstream; 33..64 are pinned-divergent — CHANGES.md Wave
    # 1535), so decode_sample_grid must raise on it.
    bad_bits = _stream_function(bits=33)
    with pytest.raises(ValueError, match="BitsPerSample"):
        bad_bits.decode_sample_grid()

    bad_size = _stream_function(size=[0])
    with pytest.raises(ValueError, match="/Size missing or invalid"):
        bad_size.decode_sample_grid()


def test_interpolate_linear_clamps_coordinates_and_folds_multiple_outputs() -> None:
    fn = _stream_function(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0, 0.0, 255.0],
        size=[2, 2],
        samples=[0, 100, 10, 110, 20, 120, 40, 140],
    )
    body = fn._get_sample_bytes()

    assert fn._interpolate_linear(
        [-2.0, 0.5],
        [2, 2],
        2,
        8,
        body,
    ) == pytest.approx([10.0, 110.0])
    assert fn._interpolate_linear(
        [1.0, 5.0],
        [2, 2],
        2,
        8,
        body,
    ) == pytest.approx([40.0, 140.0])


def test_eval_degenerate_domain_and_encoded_clamps() -> None:
    degenerate = _stream_function(
        domain=[1.0, 1.0],
        range_=[0.0, 255.0],
        encode=[1.0, 1.0],
        samples=[10, 200],
    )
    assert degenerate.eval([1.0]) == pytest.approx([200.0])

    below = _stream_function(range_=[0.0, 255.0], encode=[-5.0, -2.0], samples=[7, 9])
    assert below.eval([0.5]) == pytest.approx([7.0])

    above = _stream_function(range_=[0.0, 255.0], encode=[5.0, 9.0], samples=[7, 9])
    assert above.eval([0.5]) == pytest.approx([9.0])
