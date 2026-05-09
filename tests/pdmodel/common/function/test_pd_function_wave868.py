from __future__ import annotations

from . import test_pd_function as function_tests


def test_wave868_make_type0_sets_explicit_encode_and_decode_arrays() -> None:
    function = function_tests._make_type0(
        size=[2],
        bits=8,
        domain=[0.0, 1.0],
        rng=[0.0, 1.0],
        body=b"\x00\xff",
        encode=[1.0, 0.0],
        decode=[0.25, 0.75],
        order=3,
    )

    assert function.get_size() is not None
    assert function.get_size().to_float_array() == [2.0]
    assert function.get_encode() is not None
    assert function.get_encode().to_float_array() == [1.0, 0.0]
    assert function.get_decode() is not None
    assert function.get_decode().to_float_array() == [0.25, 0.75]
    assert function.get_order() == 3

