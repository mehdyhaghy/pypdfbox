from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_document_outline import PDDocumentOutline
    from .pd_outline_item import PDOutlineItem
    from .pd_outline_node import (
        PDOutlineItemIterator,
        PDOutlineNode,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDDocumentOutline": ".pd_document_outline",
        "PDOutlineItem": ".pd_outline_item",
        "PDOutlineItemIterator": ".pd_outline_node",
        "PDOutlineNode": ".pd_outline_node",
    },
)

__all__ = [
    "PDDocumentOutline",
    "PDOutlineItem",
    "PDOutlineItemIterator",
    "PDOutlineNode",
]
