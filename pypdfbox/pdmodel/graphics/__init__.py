from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .blend_mode import BlendMode
    from .pd_x_object import PDXObject

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BlendMode": ".blend_mode",
        "PDXObject": ".pd_x_object",
    },
)

__all__ = [
    "BlendMode",
    "PDXObject",
]
