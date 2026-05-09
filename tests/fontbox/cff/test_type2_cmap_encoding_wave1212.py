from __future__ import annotations

from tests.fontbox.cff import test_type2_cmap_encoding_wave730


def test_wave1212_dummy_encoding_name_helper() -> None:
    assert test_type2_cmap_encoding_wave730._DummyEncoding().get_encoding_name() == "Dummy"
