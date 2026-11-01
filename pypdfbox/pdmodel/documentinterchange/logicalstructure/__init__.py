from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_attribute_object import PDAttributeObject
    from .pd_default_attribute_object import PDDefaultAttributeObject
    from .pd_mark_info import PDMarkInfo
    from .pd_marked_content_reference import PDMarkedContentReference
    from .pd_object_reference import PDObjectReference
    from .pd_parent_tree_value import PDParentTreeValue
    from .pd_structure_class_map import PDStructureClassMap
    from .pd_structure_element import PDStructureElement
    from .pd_structure_node import PDStructureNode
    from .pd_structure_tree_root import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from .revisions import Revisions

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDAttributeObject": ".pd_attribute_object",
        "PDDefaultAttributeObject": ".pd_default_attribute_object",
        "PDMarkInfo": ".pd_mark_info",
        "PDMarkedContentReference": ".pd_marked_content_reference",
        "PDObjectReference": ".pd_object_reference",
        "PDParentTreeValue": ".pd_parent_tree_value",
        "PDStructureClassMap": ".pd_structure_class_map",
        "PDStructureElement": ".pd_structure_element",
        "PDStructureNode": ".pd_structure_node",
        "PDStructureElementNumberTreeNode": ".pd_structure_tree_root",
        "PDStructureTreeRoot": ".pd_structure_tree_root",
        "Revisions": ".revisions",
    },
)

__all__ = [
    "PDAttributeObject",
    "PDDefaultAttributeObject",
    "PDMarkInfo",
    "PDMarkedContentReference",
    "PDObjectReference",
    "PDParentTreeValue",
    "PDStructureClassMap",
    "PDStructureElement",
    "PDStructureElementNumberTreeNode",
    "PDStructureNode",
    "PDStructureTreeRoot",
    "Revisions",
]
