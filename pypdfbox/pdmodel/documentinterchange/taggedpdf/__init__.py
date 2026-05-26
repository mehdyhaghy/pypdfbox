from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .pd_export_format_attribute_object import PDExportFormatAttributeObject
from .pd_four_colours import PDFourColours
from .pd_layout_attribute_object import PDLayoutAttributeObject
from .pd_list_attribute_object import PDListAttributeObject
from .pd_print_field_attribute_object import PDPrintFieldAttributeObject
from .pd_standard_attribute_object import PDStandardAttributeObject
from .pd_table_attribute_object import PDTableAttributeObject
from .pd_user_attribute_object import PDUserAttributeObject
from .pd_user_property import PDUserProperty
from .standard_structure_types import StandardStructureTypes

# ``PDArtifactMarkedContent`` is exposed lazily via ``__getattr__`` to break a
# concurrent-edit-induced import cycle with the upstream-mirror re-export at
# ``pypdfbox.pdmodel.documentinterchange.markedcontent.pd_artifact_marked_content``,
# which imports the canonical class back from this package. Eager import would
# trigger a partial-module ImportError during package initialisation.

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .pd_artifact_marked_content import PDArtifactMarkedContent


def __getattr__(name: str) -> Any:
    if name == "PDArtifactMarkedContent":
        from .pd_artifact_marked_content import PDArtifactMarkedContent

        return PDArtifactMarkedContent
    raise AttributeError(
        "module 'pypdfbox.pdmodel.documentinterchange.taggedpdf' "
        f"has no attribute {name!r}"
    )


__all__ = [
    "PDArtifactMarkedContent",
    "PDExportFormatAttributeObject",
    "PDFourColours",
    "PDLayoutAttributeObject",
    "PDListAttributeObject",
    "PDPrintFieldAttributeObject",
    "PDStandardAttributeObject",
    "PDTableAttributeObject",
    "PDUserAttributeObject",
    "PDUserProperty",
    "StandardStructureTypes",
]
