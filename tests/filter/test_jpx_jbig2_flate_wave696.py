from __future__ import annotations

import io
import sys
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger
from pypdfbox.filter import JBIG2Decode
from pypdfbox.filter import flate_decode as flate_module
from pypdfbox.filter import jbig2_decode as jbig2_module
from pypdfbox.filter.jpx_decode import _mode_components_and_bpc


def test_jpx_mode_helper_reports_four_component_modes() -> None:
    assert _mode_components_and_bpc("RGBA", ("R", "G", "B", "A")) == (4, 8)
    assert _mode_components_and_bpc("CMYK", ("C", "M", "Y", "K")) == (4, 8)


def test_jpx_mode_helper_reports_one_bit_and_fallback_modes() -> None:
    assert _mode_components_and_bpc("1", ("1",)) == (1, 1)
    assert _mode_components_and_bpc("P", ("P",)) == (1, 8)


def test_jbig2_decode_params_array_out_of_range_returns_empty_dict() -> None:
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", COSArray())

    resolved = jbig2_module._resolve_decode_params(stream_dict, 1)

    assert resolved.is_empty()


def test_jbig2_decode_params_array_non_dictionary_entry_returns_empty_dict() -> None:
    array = COSArray()
    array.add(COSInteger.get(9))
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", array)

    resolved = jbig2_module._resolve_decode_params(stream_dict, 0)

    assert resolved.is_empty()


def test_jbig2_decode_wraps_invalid_parser_png_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_parser = SimpleNamespace(parse_jbig2=lambda _data: b"not a png")
    monkeypatch.setitem(sys.modules, "jbig2_parser", fake_parser)

    with pytest.raises(OSError, match="post-decode PNG handoff failed"):
        JBIG2Decode().decode(io.BytesIO(b"jbig2 bytes"), io.BytesIO())


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
