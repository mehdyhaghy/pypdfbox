from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from tests.pdmodel.graphics.image.upstream import test_lossless_factory as lossless_mod


class _ImageWithColorSpace:
    def __init__(self, color_space: object) -> None:
        self._color_space = color_space

    def get_bits_per_component(self) -> int:
        return 8

    def get_width(self) -> int:
        return 2

    def get_height(self) -> int:
        return 3

    def get_color_space_cos_object(self) -> object:
        return self._color_space


def test_wave886_validate_accepts_array_color_space_name() -> None:
    color_space = COSArray()
    color_space.add(COSName.get_pdf_name("Indexed"))
    image = _ImageWithColorSpace(color_space)

    lossless_mod._validate(image, 8, 2, 3, "Indexed")  # noqa: SLF001


def test_wave886_validate_rejects_array_without_name_entry() -> None:
    color_space = COSArray()
    color_space.add(COSString(b"Indexed"))
    image = _ImageWithColorSpace(color_space)

    with pytest.raises(AssertionError):
        lossless_mod._validate(image, 8, 2, 3, "Indexed")  # noqa: SLF001


def test_wave886_validate_rejects_unexpected_color_space_object() -> None:
    image = _ImageWithColorSpace(object())

    with pytest.raises(AssertionError, match="unexpected /ColorSpace type"):
        lossless_mod._validate(image, 8, 2, 3, "Indexed")  # noqa: SLF001
