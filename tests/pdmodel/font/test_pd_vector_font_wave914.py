from __future__ import annotations

from pypdfbox.pdmodel.font import PDVectorFont
from tests.pdmodel.font import test_pd_vector_font as vector_tests


def test_missing_has_glyph_stub_methods_are_executable() -> None:
    stub = vector_tests._MissingHasGlyph()

    assert stub.get_path(65) is None
    assert stub.get_normalized_path(65) is None
    assert not isinstance(stub, PDVectorFont)


def test_minimal_vector_font_default_glyph_set_and_extension_method() -> None:
    class ExtendedVectorFont(vector_tests._MinimalVectorFont):
        def extra(self) -> str:
            return "extra"

    font = ExtendedVectorFont()

    assert font.has_glyph(65) is True
    assert font.has_glyph(68) is False
    assert font.extra() == "extra"
    assert isinstance(font, PDVectorFont)
