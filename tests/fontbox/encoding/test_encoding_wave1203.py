from __future__ import annotations

from tests.fontbox.encoding.test_encoding_wave294 import _Wave294Encoding


def test_wave294_encoding_name_helper() -> None:
    assert _Wave294Encoding().get_encoding_name() == "Wave294"
