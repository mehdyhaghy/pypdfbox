from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.image import JPEGFactory


def test_wave313_create_from_byte_array_rejects_unreadable_image_data() -> None:
    with pytest.raises(ValueError, match="expected JPEG image"):
        JPEGFactory.create_from_byte_array(None, b"not an image")

