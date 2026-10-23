from typing import Any, cast

from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.text import PDFTextStripper, TextPosition


class ExplodingFont(PDType1Font):
    def decode(self, _data: bytes) -> str:
        raise AssertionError("font decode should not run when CMap is active")


def test_wave944_decode_show_text_prefers_cmap_before_simple_font_decode() -> None:
    class FakeCMap:
        def read_code(self, stream: Any) -> int:
            value = stream.read(1)
            return value[0] if value else 0

        def to_unicode(self, code: int) -> str | None:
            return {65: "from-cmap"}.get(code)

    stripper = PDFTextStripper()
    stripper._active_cmap = cast("Any", FakeCMap())
    stripper._active_font = ExplodingFont()

    assert stripper._decode_show_text(b"A") == "from-cmap"


def test_wave944_word_break_uses_flipped_axis_previous_width() -> None:
    stripper = PDFTextStripper()
    stripper.set_should_flip_axes(True)
    prev = TextPosition(text="prev", x=100.0, y=10.0, font_size=8.0, width=6.0)
    close = TextPosition(text="close", x=104.1, y=27.9, font_size=8.0)
    far = TextPosition(text="far", x=104.1, y=28.1, font_size=8.0)

    assert stripper._is_line_break(close, prev) is True
    assert stripper._is_word_break(close, prev) is False
    assert stripper._is_word_break(far, prev) is True
