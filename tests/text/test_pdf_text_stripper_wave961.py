from __future__ import annotations

from pypdfbox.text import TextPosition
from tests.text.test_pdf_text_stripper_wave540 import RecordingStripper


def test_wave961_recording_stripper_dispatches_non_empty_run() -> None:
    stripper = RecordingStripper()
    sinked: list[str] = []
    positions = [TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)]

    stripper.write_string_with_positions("x", positions, sinked.append)

    assert stripper.calls == ["x"]
    assert sinked == ["x"]
