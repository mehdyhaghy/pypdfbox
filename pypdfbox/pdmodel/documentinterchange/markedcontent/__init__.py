from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_artifact_marked_content import PDArtifactMarkedContent
    from .pd_marked_content import PDMarkedContent
    from .pd_property_list import PDPropertyList

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDArtifactMarkedContent": ".pd_artifact_marked_content",
        "PDMarkedContent": ".pd_marked_content",
        "PDPropertyList": ".pd_property_list",
    },
)

__all__ = [
    "PDArtifactMarkedContent",
    "PDMarkedContent",
    "PDPropertyList",
]
