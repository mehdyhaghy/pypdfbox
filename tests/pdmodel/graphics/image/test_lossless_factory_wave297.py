from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.image import LosslessFactory


def test_create_from_image_rejects_non_pil_image_wave297() -> None:
    with pytest.raises(TypeError, match="image must be a PIL.Image.Image"):
        LosslessFactory.create_from_image(None, b"not an image")  # type: ignore[arg-type]
