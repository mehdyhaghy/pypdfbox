from __future__ import annotations

import io
from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSInteger
from pypdfbox.filter import CCITTFaxDecode, DCTDecode
from pypdfbox.filter import ccitt_fax_decode as ccitt_module
from pypdfbox.filter import dct_decode as dct_module


def _decode_params(**values: int | bool) -> COSDictionary:
    params = COSDictionary()
    for key, value in values.items():
        if isinstance(value, bool):
            params.set_boolean(key, value)
        else:
            params.set_int(key, value)
    return params


def test_ccitt_decode_params_array_out_of_range_returns_empty_dict() -> None:
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", COSArray())

    resolved = ccitt_module._resolve_decode_params(stream_dict, 2)

    assert resolved.is_empty()


def test_ccitt_decode_params_array_non_dictionary_entry_returns_empty_dict() -> None:
    array = COSArray()
    array.add(COSInteger.get(7))
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", array)

    resolved = ccitt_module._resolve_decode_params(stream_dict, 0)

    assert resolved.is_empty()


def test_ccitt_ifd_entry_rejects_unsupported_tiff_type() -> None:
    with pytest.raises(ValueError, match="unsupported TIFF entry type"):
        ccitt_module._ifd_entry(256, 99, 1, 8)


def test_ccitt_t4_wrapper_sets_two_dimensional_option_for_positive_k() -> None:
    wrapper = ccitt_module._build_tiff_wrapper(
        b"\x00",
        columns=8,
        rows=1,
        k=1,
        photometric=1,
        encoded_byte_align=False,
    )

    with Image.open(io.BytesIO(wrapper)) as image:
        assert image.tag_v2[ccitt_module._TIFF_COMPRESSION] == ccitt_module._COMPRESSION_T4
        assert image.tag_v2[ccitt_module._TIFF_T4_OPTIONS] & ccitt_module._T4_TWO_DIMENSIONAL


def test_ccitt_encode_wraps_libtiff_frombytes_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_frombytes(*_args: Any, **_kwargs: Any) -> Image.Image:
        raise RuntimeError("cannot build image")

    monkeypatch.setattr(ccitt_module.Image, "frombytes", fail_frombytes)
    params = _decode_params(K=-1, Columns=8, Rows=1)

    with pytest.raises(OSError, match="libtiff encode failed"):
        CCITTFaxDecode().encode(io.BytesIO(b"\xff"), io.BytesIO(), params)


def test_ccitt_encode_wraps_tiff_strip_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(*_args: Any, **_kwargs: Any) -> Image.Image:
        raise RuntimeError("cannot parse strip")

    monkeypatch.setattr(ccitt_module.Image, "open", fail_open)
    params = _decode_params(K=-1, Columns=8, Rows=1)

    with pytest.raises(OSError, match="failed to parse TIFF strip"):
        CCITTFaxDecode().encode(io.BytesIO(b"\xff"), io.BytesIO(), params)


def test_ccitt_estimate_rows_clamps_invalid_columns_to_one() -> None:
    assert ccitt_module._estimate_rows(b"\x00\x01", 0) == 1


def test_dct_decode_empty_input_reuses_supplied_parameters() -> None:
    params = COSDictionary()
    out = io.BytesIO()

    result = DCTDecode().decode(io.BytesIO(b""), out, params)

    assert result.parameters is params
    assert result.bytes_written == 0
    assert out.getvalue() == b""


def test_dct_decode_invalid_jpeg_raises_oserror() -> None:
    with pytest.raises(OSError, match="JPEG decode failed"):
        DCTDecode().decode(io.BytesIO(b"not a jpeg"), io.BytesIO())


def test_dct_decode_cmyk_jpeg_reports_four_components() -> None:
    image = Image.new("CMYK", (1, 1), color=(0, 10, 20, 30))
    encoded = io.BytesIO()
    image.save(encoded, format="JPEG")

    result = DCTDecode().decode(io.BytesIO(encoded.getvalue()), io.BytesIO())

    assert result.parameters.get_int("ColorComponents") == 4
    assert result.parameters.get_int("BitsPerComponent") == 8


def test_dct_decode_uses_band_count_for_unmapped_pillow_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeImage:
        mode = "P"
        size = (2, 1)

        def __enter__(self) -> FakeImage:
            return self

        def __exit__(self, *_exc_info: object) -> None:
            return None

        def load(self) -> None:
            return None

        def tobytes(self) -> bytes:
            return b"\x01\x02"

        def getbands(self) -> tuple[str, ...]:
            return ("P",)

    def fake_open(_stream: io.BytesIO) -> FakeImage:
        return FakeImage()

    monkeypatch.setattr(dct_module.Image, "open", fake_open)

    out = io.BytesIO()
    result = DCTDecode().decode(io.BytesIO(b"fake jpeg"), out)

    assert out.getvalue() == b"\x01\x02"
    assert result.parameters.get_int("Width") == 2
    assert result.parameters.get_int("ColorComponents") == 1
