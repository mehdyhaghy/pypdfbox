from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDEmbeddedFilesNameTreeNode(PDNameTreeNode[PDComplexFileSpecification]):
    """
    Name tree of embedded file specifications. Mirrors PDFBox
    ``PDEmbeddedFilesNameTreeNode`` — concrete subclass of
    ``PDNameTreeNode<PDComplexFileSpecification>`` for the catalog's
    ``/Names /EmbeddedFiles`` entry.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> PDComplexFileSpecification:
        if base is not None and not isinstance(base, COSDictionary):
            raise OSError(f"dictionary expected here, but got {base!r}")
        return PDComplexFileSpecification(base)  # type: ignore[arg-type]

    def convert_value_to_cos(self, value: PDComplexFileSpecification) -> COSBase:
        return value.get_cos_object()

    def create_child_node(self, dic: COSDictionary) -> PDEmbeddedFilesNameTreeNode:
        return PDEmbeddedFilesNameTreeNode(dic)


__all__ = ["PDEmbeddedFilesNameTreeNode"]
