from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .begin_inline_image import BeginInlineImage
    from .begin_inline_image_data import BeginInlineImageData
    from .end_inline_image import EndInlineImage

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BeginInlineImage": ".begin_inline_image",
        "BeginInlineImageData": ".begin_inline_image_data",
        "EndInlineImage": ".end_inline_image",
    },
)

__all__ = [
    "BeginInlineImage",
    "BeginInlineImageData",
    "EndInlineImage",
]
