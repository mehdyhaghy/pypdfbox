from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .ccitt_factory import CCITTFactory
    from .custom_factory import CustomFactory
    from .jpeg_factory import JPEGFactory
    from .lossless_factory import LosslessFactory
    from .pd_image import PDImage
    from .pd_image_x_object import PDImageXObject
    from .pd_inline_image import PDInlineImage
    from .png_converter import (
        Chunk,
        PNGConverter,
    )
    from .predictor_encoder import PredictorEncoder
    from .sampled_image_reader import (
        MultipleInputStream,
        SampledImageReader,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CCITTFactory": ".ccitt_factory",
        "CustomFactory": ".custom_factory",
        "JPEGFactory": ".jpeg_factory",
        "LosslessFactory": ".lossless_factory",
        "PDImage": ".pd_image",
        "PDImageXObject": ".pd_image_x_object",
        "PDInlineImage": ".pd_inline_image",
        "Chunk": ".png_converter",
        "PNGConverter": ".png_converter",
        "PredictorEncoder": ".predictor_encoder",
        "MultipleInputStream": ".sampled_image_reader",
        "SampledImageReader": ".sampled_image_reader",
    },
)

__all__ = [
    "CCITTFactory",
    "Chunk",
    "CustomFactory",
    "JPEGFactory",
    "LosslessFactory",
    "MultipleInputStream",
    "PDImage",
    "PDImageXObject",
    "PDInlineImage",
    "PNGConverter",
    "PredictorEncoder",
    "SampledImageReader",
]
