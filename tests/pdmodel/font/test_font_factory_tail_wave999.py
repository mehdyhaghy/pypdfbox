from __future__ import annotations

from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from tests.pdmodel.font.test_font_factory_tail_wave798 import _RecordingMapper


def test_wave798_recording_mapper_null_font_fallbacks() -> None:
    mapper = _RecordingMapper()
    descriptor = PDFontDescriptor()

    assert mapper.get_true_type_font("WaveTailFont", descriptor) is None
    assert mapper.get_open_type_font("WaveTailFont", descriptor) is None

