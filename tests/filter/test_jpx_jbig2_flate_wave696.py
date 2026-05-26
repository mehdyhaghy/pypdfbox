from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger
from pypdfbox.filter import JBIG2Decode
from pypdfbox.filter import flate_decode as flate_module
from pypdfbox.filter.jpx_decode import _mode_components_and_bpc


def test_jpx_mode_helper_reports_four_component_modes() -> None:
    assert _mode_components_and_bpc("RGBA", ("R", "G", "B", "A")) == (4, 8)
    assert _mode_components_and_bpc("CMYK", ("C", "M", "Y", "K")) == (4, 8)


def test_jpx_mode_helper_reports_one_bit_and_fallback_modes() -> None:
    assert _mode_components_and_bpc("1", ("1",)) == (1, 1)
    assert _mode_components_and_bpc("P", ("P",)) == (1, 8)


def test_jbig2_decode_garbage_raises_oserror_with_decode_parms_array() -> None:
    # JBIG2 decoding is now supported via the first-party pure-Python
    # decoder; a /DecodeParms array (filter at index 1, no usable
    # /JBIG2Globals entry) is resolved fine, but garbage codestream
    # bytes surface a decode failure as OSError.
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", COSArray())

    with pytest.raises(OSError):
        JBIG2Decode().decode(io.BytesIO(b"jbig2 bytes"), io.BytesIO(), stream_dict, 1)


def test_flate_decode_params_dict_under_decode_parms_is_returned() -> None:
    decode_params = COSDictionary()
    decode_params.set_int("Predictor", 12)
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", decode_params)

    assert flate_module._get_decode_params(stream_dict, 0) is decode_params


def test_flate_decode_params_array_out_of_range_returns_empty_dict() -> None:
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", COSArray())

    resolved = flate_module._get_decode_params(stream_dict, 4)

    assert resolved.is_empty()


def test_flate_decode_params_array_non_dictionary_entry_returns_empty_dict() -> None:
    array = COSArray()
    array.add(COSInteger.get(3))
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", array)

    resolved = flate_module._get_decode_params(stream_dict, 0)

    assert resolved.is_empty()
