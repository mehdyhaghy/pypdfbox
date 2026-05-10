from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary


class PDParentTreeValue:
    """
    A value held in the ``ParentTree`` (number tree) on the structure tree
    root. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDParentTreeValue``.

    Per PDF 32000-1 §14.7.4.4 the parent-tree maps each marked-content
    parent identifier (``StructParent`` / ``StructParents``) to either:

    - a single structure-element dictionary (annotations, XObjects), or
    - an array of structure-element references indexed by ``MCID``
      (page objects, content streams).

    This class keeps the underlying ``COSArray`` or ``COSDictionary``
    addressable as a single typed wrapper. ``get_cos_object`` returns the
    raw underlying COS value, matching upstream's ``COSObjectable`` hook.
    """

    __slots__ = ("_obj",)

    def __init__(self, obj: COSArray | COSDictionary) -> None:
        if not isinstance(obj, (COSArray, COSDictionary)):
            raise TypeError(
                "PDParentTreeValue expects a COSArray or COSDictionary, got "
                f"{type(obj).__name__}"
            )
        self._obj: COSArray | COSDictionary = obj

    def get_cos_object(self) -> COSBase:
        return self._obj

    def __repr__(self) -> str:
        return repr(self._obj)

    def to_string(self) -> str:
        """Mirror upstream ``PDParentTreeValue.toString()``
        (``PDParentTreeValue.java`` lines 53-57): delegates to the
        underlying ``COSArray`` / ``COSDictionary``'s string form."""
        return str(self._obj)

    def __str__(self) -> str:
        """Mirror upstream ``PDParentTreeValue.toString()`` which delegates to
        the underlying ``COSArray``/``COSDictionary``'s ``toString``."""
        return self.to_string()


__all__ = ["PDParentTreeValue"]
