from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0


def _pack_samples(values: list[int], bits: int) -> bytes:
    total_bits = len(values) * bits
    packed = 0
    for value in values:
        packed = (packed << bits) | (value & ((1 << bits) - 1))
    padding = (-total_bits) % 8
    packed <<= padding
    byte_count = (total_bits + padding) // 8
    return packed.to_bytes(byte_count, "big") if byte_count else b""


def _float_array(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


def _size_array(values: list[int]) -> COSArray:
    return COSArray([COSInteger.get(value) for value in values])


def _build_type0(
    *,
    domain: list[float],
    range_: list[float],
    size: list[int],
    bits: int,
    samples: list[int],
    encode: list[float] | None = None,
    decode: list[float] | None = None,
) -> PDFunctionType0:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    raw.set_item("Domain", _float_array(domain))
    raw.set_item("Range", _float_array(range_))
    raw.set_item("Size", _size_array(size))
    raw.set_int("BitsPerSample", bits)
    if encode is not None:
        raw.set_item("Encode", _float_array(encode))
    if decode is not None:
        raw.set_item("Decode", _float_array(decode))
    raw.set_data(_pack_samples(samples, bits))
    return PDFunctionType0(raw)


def test_accessors_ignore_malformed_array_entries_and_keep_numeric_defaults() -> None:
    raw = COSStream()
    raw.set_item("Size", COSName.get_pdf_name("NotAnArray"))
    raw.set_item("Encode", COSName.get_pdf_name("NotAnArray"))
    raw.set_item("Decode", COSName.get_pdf_name("NotAnArray"))

    fn = PDFunctionType0(raw)

    assert fn.get_size() is None
    assert fn.get_encode() is None
    assert fn.get_decode() is None
    assert fn.get_bits_per_sample() == 0
    assert fn.get_order() == 1


def test_setters_round_trip_to_cos_stream_and_clear_optional_arrays() -> None:
    raw = COSStream()
    fn = PDFunctionType0(raw)
    size = _size_array([2, 3])
    encode = _float_array([0.0, 1.0, 2.0, 3.0])
    decode = _float_array([-1.0, 1.0])

    fn.set_size(size)
    fn.set_bits_per_sample(12)
    fn.set_order(3)
    fn.set_encode(encode)
    fn.set_decode(decode)

    assert raw.get_dictionary_object("Size") is size
    assert raw.get_int("BitsPerSample") == 12
    assert raw.get_int("Order") == 3
    assert raw.get_dictionary_object("Encode") is encode
    assert raw.get_dictionary_object("Decode") is decode

    fn.set_size(None)
    fn.set_encode_values(None)
    fn.set_decode_values(None)

    assert raw.contains_key("Size") is False
    assert raw.contains_key("Encode") is False
    assert raw.contains_key("Decode") is False


def test_partial_encode_defaults_missing_dimensions_to_size_minus_one() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4, 9],
        bits=8,
        samples=[0] * 36,
        encode=[10.0, 20.0],
    )

    assert fn.get_encode_for_parameter(0) == (10.0, 20.0)
    assert fn.get_encode_for_parameter(1) == (0.0, 8.0)


def test_partial_decode_defaults_missing_outputs_to_range_pairs() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[-1.0, 1.0, -2.0, 2.0],
        size=[2],
        bits=8,
        samples=[0, 0, 0, 0],
        decode=[10.0, 20.0],
    )

    assert fn.get_decode_for_parameter(0) == (10.0, 20.0)
    assert fn.get_decode_for_parameter(1) == (-2.0, 2.0)


def test_get_samples_cache_is_invalidated_when_bits_per_sample_changes() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    raw.set_item("Domain", _float_array([0.0, 1.0]))
    raw.set_item("Range", _float_array([0.0, 15.0]))
    raw.set_item("Size", _size_array([2]))
    raw.set_int("BitsPerSample", 8)
    raw.set_data(bytes([0x12, 0x34]))
    fn = PDFunctionType0(raw)

    assert fn.get_samples() == [[0x12], [0x34]]

    fn.set_bits_per_sample(4)

    assert fn.get_samples() == [[0x1], [0x2]]


@pytest.mark.parametrize(
    ("size", "match"),
    [
        ([2], "/Size missing or invalid"),
        ([0, 2], "/Size missing or invalid"),
    ],
)
def test_malformed_size_shape_raises_for_samples_and_eval(
    size: list[int],
    match: str,
) -> None:
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=size,
        bits=8,
        samples=[0, 255, 255, 0],
    )

    with pytest.raises(ValueError, match=match):
        fn.get_samples()
    with pytest.raises(ValueError, match=match):
        fn.eval([0.5, 0.5])


def test_non_numeric_size_entry_is_treated_as_invalid_shape() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    raw.set_item("Domain", _float_array([0.0, 1.0]))
    raw.set_item("Range", _float_array([0.0, 1.0]))
    raw.set_item("Size", COSArray([COSName.get_pdf_name("BadSize")]))
    raw.set_int("BitsPerSample", 8)
    raw.set_data(b"\x00\xff")
    fn = PDFunctionType0(raw)

    with pytest.raises(ValueError, match="/Size missing or invalid"):
        fn.get_samples()


def test_eval_function_for_type0_is_implemented_not_deferred() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 255],
    )

    assert fn.eval_function([0.25]) == pytest.approx([0.25])


def test_type0_eval_reports_validation_errors_not_notimplemented() -> None:
    fn = PDFunctionType0(COSStream())

    with pytest.raises(ValueError, match="/Domain and /Range"):
        fn.eval([0.0])
