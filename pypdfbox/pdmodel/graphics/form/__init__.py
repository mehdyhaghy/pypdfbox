from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_form_x_object import PDFormXObject
    from .pd_transparency_group import PDTransparencyGroup
    from .pd_transparency_group_attributes import PDTransparencyGroupAttributes

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDFormXObject": ".pd_form_x_object",
        "PDTransparencyGroup": ".pd_transparency_group",
        "PDTransparencyGroupAttributes": ".pd_transparency_group_attributes",
    },
)

__all__ = [
    "PDFormXObject",
    "PDTransparencyGroup",
    "PDTransparencyGroupAttributes",
]
