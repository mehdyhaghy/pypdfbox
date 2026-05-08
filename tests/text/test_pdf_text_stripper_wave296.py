from __future__ import annotations

from collections.abc import Callable

from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.text_position import TextPosition


def test_format_positions_uses_position_aware_write_string_hook() -> None:
    class PositionAwareStripper(PDFTextStripper):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[list[TextPosition]] = []

        def write_string_with_positions(
            self,
            text: str,
            text_positions: list[TextPosition],
            sink: Callable[[str], None],
        ) -> None:
            self.seen.append(text_positions)
            sink(f"<{text}>")

    position = TextPosition(text="A", x=10.0, y=20.0, font_size=12.0)
    stripper = PositionAwareStripper()

    assert stripper._format_positions([position]) == "<A>"
    assert stripper.seen == [[position]]
