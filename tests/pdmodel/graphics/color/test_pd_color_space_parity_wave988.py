from __future__ import annotations

from tests.pdmodel.graphics.color import test_pd_color_space_parity


def test_wave988_base_decode_stub_exposes_name_and_initial_color() -> None:
    test_pd_color_space_parity.test_base_get_default_decode_returns_zero_one_per_component()
    stub_class = test_pd_color_space_parity._BASE_DECODE_STUB_CLASS
    assert stub_class is not None
    stub = stub_class()

    color = stub.get_initial_color()

    assert stub.get_name() == "Stub"
    assert color.get_components() == [0.0, 0.0]
    assert color.get_color_space() is stub
