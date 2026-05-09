from __future__ import annotations

from .test_pd_function_type0_wave407 import _stream_function


def test_wave1149_stream_function_sets_optional_decode_array() -> None:
    fn = _stream_function(
        range_=[0.0, 1.0],
        decode=[10.0, 20.0],
        samples=[0, 255],
    )

    assert fn.get_decode_for_parameter(0) == (10.0, 20.0)
