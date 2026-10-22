from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_abstract_pattern import PDAbstractPattern
    from .pd_shading_pattern import PDShadingPattern
    from .pd_tiling_pattern import PDTilingPattern

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDAbstractPattern": ".pd_abstract_pattern",
        "PDShadingPattern": ".pd_shading_pattern",
        "PDTilingPattern": ".pd_tiling_pattern",
    },
)

__all__ = [
    "PDAbstractPattern",
    "PDShadingPattern",
    "PDTilingPattern",
]
