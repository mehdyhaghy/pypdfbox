from __future__ import annotations

from tests.filter.test_ccitt_fax_filter import _decode_params


def test_wave1221_decode_params_sets_boolean_value() -> None:
    params = _decode_params(BlackIs1=True)

    assert params.get_boolean("BlackIs1", False) is True
