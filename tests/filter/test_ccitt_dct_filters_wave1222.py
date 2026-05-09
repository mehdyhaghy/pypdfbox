from __future__ import annotations

from tests.filter.test_ccitt_dct_filters_wave695 import _decode_params


def test_wave1222_decode_params_sets_boolean_value() -> None:
    params = _decode_params(EncodedByteAlign=True)

    assert params.get_boolean("EncodedByteAlign", False) is True
