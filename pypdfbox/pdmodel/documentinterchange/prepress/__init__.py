from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_box_style import PDBoxStyle

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDBoxStyle": ".pd_box_style",
    },
)

__all__ = ["PDBoxStyle"]
