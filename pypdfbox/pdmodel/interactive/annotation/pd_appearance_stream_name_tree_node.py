"""``/AP`` appearance-stream name-tree wrapper.

Mirrors the slot for an appearance-stream name tree referenced from the
catalog's ``/Names /AP`` entry. PDF 32000-1 §7.7.4 Table 31 lists ``/AP``
as a name tree mapping name strings to appearance streams; this surface
is most commonly populated by FDF round-trips where form-field appearance
dispatch is keyed by name.

Upstream PDFBox 3.x does not ship a typed wrapper for this name tree —
the only public accessor for ``/AP`` lives in the FDF reader, which
returns the raw ``COSDictionary``. We expose ``PDAppearanceStreamNameTreeNode``
as a strict ``PDNameTreeNode[PDAppearanceStream]`` so pypdfbox callers
get the same typed-leaf shape used by the rest of the name-tree wrappers
(``PDEmbeddedFilesNameTreeNode``, ``PDJavascriptNameTreeNode`` …).
Documented in ``CHANGES.md``.
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSStream
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)


class PDAppearanceStreamNameTreeNode(PDNameTreeNode[PDAppearanceStream]):
    """Name tree mapping names to appearance streams.

    The leaf values are ``PDAppearanceStream`` Form-XObject wrappers.
    Construction accepts a raw ``COSDictionary`` (the node dictionary)
    so callers reaching through ``PDDocumentNameDictionary.get_ap()``
    can wrap the existing storage without copying.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> PDAppearanceStream:
        if base is None or not isinstance(base, COSStream):
            msg = f"COSStream expected for appearance stream, got {base!r}"
            raise OSError(msg)
        return PDAppearanceStream(base)

    def convert_cos_to_pd(self, base: COSBase) -> PDAppearanceStream:
        """Mirror the typed factory used by sibling name-tree wrappers.

        The base class's :meth:`convert_cos_to_pd` shim delegates to
        :meth:`convert_cos_to_value`; we override here so the return type
        is pinned to ``PDAppearanceStream`` for callers and static
        analysers without going through the generic ``T``.
        """
        return self.convert_cos_to_value(base)

    def convert_value_to_cos(self, value: PDAppearanceStream) -> COSBase:
        return value.get_cos_object()

    def create_child_node(
        self, dic: COSDictionary
    ) -> PDAppearanceStreamNameTreeNode:
        return PDAppearanceStreamNameTreeNode(dic)


__all__ = ["PDAppearanceStreamNameTreeNode"]
