"""Hand-written tests for ``pypdfbox.debugger.ui.ImageUtil``."""

import pytest

from pypdfbox.debugger.ui import ImageUtil

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402  (after importorskip)


def _checker(w: int = 4, h: int = 3) -> Image.Image:
    img = Image.new("RGB", (w, h), (0, 0, 0))
    for x in range(w):
        for y in range(h):
            img.putpixel((x, y), (x * 50, y * 80, 0))
    return img


def test_zero_rotation_returns_same_object() -> None:
    img = _checker()
    assert ImageUtil.get_rotated_image(img, 0) is img


def test_180_rotation_preserves_size() -> None:
    img = _checker(4, 3)
    rotated = ImageUtil.get_rotated_image(img, 180)
    assert rotated.size == (4, 3)
    # opposite corners should swap
    assert rotated.getpixel((0, 0)) == img.getpixel((3, 2))


def test_90_rotation_swaps_dimensions() -> None:
    img = _checker(4, 3)
    rotated = ImageUtil.get_rotated_image(img, 90)
    assert rotated.size == (3, 4)


def test_270_rotation_swaps_dimensions() -> None:
    img = _checker(4, 3)
    rotated = ImageUtil.get_rotated_image(img, 270)
    assert rotated.size == (3, 4)


def test_negative_rotation_normalises() -> None:
    img = _checker(4, 3)
    rotated = ImageUtil.get_rotated_image(img, -90)
    # -90 normalises to 270, which swaps dimensions.
    assert rotated.size == (3, 4)


def test_non_multiple_of_90_raises() -> None:
    with pytest.raises(ValueError):
        ImageUtil.get_rotated_image(_checker(), 45)


def test_constructor_is_blocked() -> None:
    with pytest.raises(TypeError):
        ImageUtil()
