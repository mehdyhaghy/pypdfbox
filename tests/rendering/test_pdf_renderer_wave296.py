from __future__ import annotations

from pypdfbox.rendering import ImageType, RenderDestination


def test_rendering_public_enums_keep_pdfbox_parity_values() -> None:
    assert ImageType.BGR.pil_mode == "RGB"
    assert ImageType.BGR.to_buffered_image_type() == 5
    assert RenderDestination.PRINT.value == "Print"
