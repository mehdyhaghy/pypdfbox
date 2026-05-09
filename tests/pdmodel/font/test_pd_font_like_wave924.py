from __future__ import annotations

from pypdfbox.pdmodel.font import PDFontLike
from tests.pdmodel.font.test_pd_font_like import _MissingMethods


class _WrongSigFontLike:
    def get_name(self):
        return 1

    def get_font_descriptor(self):
        return 0

    def get_font_matrix(self):
        return None

    def get_bounding_box(self):
        return None

    def get_position_vector(self, code):
        return None

    def get_height(self, code):
        return ""

    def get_width(self, code):
        return ""

    def has_explicit_width(self, code):
        return ""

    def get_width_from_font(self, code):
        return ""

    def is_embedded(self):
        return ""

    def is_damaged(self):
        return ""

    def get_average_font_width(self):
        return ""


class _ExtendedFontLike:
    def get_name(self) -> str:
        return "Extended"

    def get_font_descriptor(self):
        return None

    def get_font_matrix(self):
        return []

    def get_bounding_box(self):
        return ()

    def get_position_vector(self, code: int):
        return (code, 0)

    def get_height(self, code: int) -> float:
        return float(code)

    def get_width(self, code: int) -> float:
        return float(code)

    def has_explicit_width(self, code: int) -> bool:
        return code == 65

    def get_width_from_font(self, code: int) -> float:
        return float(code)

    def is_embedded(self) -> bool:
        return False

    def is_damaged(self) -> bool:
        return False

    def get_average_font_width(self) -> float:
        return 0.0

    def extra(self) -> str:
        return "extra"


def test_wave924_incomplete_stub_name_accessor_remains_callable() -> None:
    partial = _MissingMethods()

    assert partial.get_name() == "Partial"
    assert not isinstance(partial, PDFontLike)


def test_wave924_runtime_protocol_does_not_consume_methods() -> None:
    font = _WrongSigFontLike()

    assert isinstance(font, PDFontLike)
    assert font.get_name() == 1


def test_wave924_extended_protocol_stub_extra_method_body_runs() -> None:
    font = _ExtendedFontLike()

    assert isinstance(font, PDFontLike)
    assert font.extra() == "extra"
