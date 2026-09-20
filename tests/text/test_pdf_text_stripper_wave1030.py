from pypdfbox.text import PDFTextStripper
from tests.text.test_pdf_text_stripper_wave944 import ExplodingFont


def test_wave1030_decode_show_text_falls_back_when_simple_font_decode_fails() -> None:
    stripper = PDFTextStripper()
    stripper._active_font = ExplodingFont()

    assert stripper._decode_show_text(b"fallback") == "fallback"
