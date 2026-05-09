from __future__ import annotations

from tests.pdmodel.font.test_font_encoding_remaining_wave753 import _RecordingMapper


def test_wave753_recording_mapper_null_font_fallbacks() -> None:
    mapper = _RecordingMapper()

    assert mapper.get_true_type_font("Helvetica", None) is None
    assert mapper.get_open_type_font("Helvetica", None) is None

