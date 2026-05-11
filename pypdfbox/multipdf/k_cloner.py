"""Structure-tree ``/K`` cloner used by ``Splitter``.

Mirrors the private inner class ``Splitter.KCloner`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/multipdf/Splitter.java`` lines
355-503). Upstream nests it inside ``Splitter`` to access two private
maps (``pageDictMap``, ``structDictMap``); we host it as a top-level
module so it can be reused outside Splitter.

The Python ``Splitter`` implementation keeps the cloning logic in
``Splitter._k_create_clone`` for backward-compatibility with prior waves.
This class is a thin adapter that delegates to that method, preserving
upstream's API surface (``KCloner(dst_page_tree).create_clone(...)``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName

if TYPE_CHECKING:
    from pypdfbox.multipdf.splitter import Splitter
    from pypdfbox.pdmodel.pd_page_tree import PDPageTree


class KCloner:
    """Clone a structure-tree ``/K`` payload into a destination page tree."""

    def __init__(
        self,
        dst_page_tree: PDPageTree,
        splitter: Splitter | None = None,
        page_dict_map: dict[int, COSDictionary] | None = None,
        struct_dict_map: dict[int, COSDictionary] | None = None,
    ) -> None:
        self._dst_page_tree = dst_page_tree
        self._splitter = splitter
        self._page_dict_map = page_dict_map if page_dict_map is not None else {}
        self._struct_dict_map = struct_dict_map if struct_dict_map is not None else {}

    def create_clone(
        self,
        src: COSBase | None,
        dst_parent: COSBase | None,
        current_page_dict: COSDictionary | None,
    ) -> COSBase | None:
        """Clone ``src`` into the destination page tree.

        Returns ``None`` if ``src`` belongs to no destination page (matches
        upstream semantics).
        """
        if self._splitter is not None and hasattr(self._splitter, "_k_create_clone"):
            # Sync the cloner state into the splitter so its existing
            # algorithm picks the right map snapshots.
            self._splitter._page_dict_map = self._page_dict_map  # type: ignore[attr-defined]
            self._splitter._struct_dict_map = self._struct_dict_map  # type: ignore[attr-defined]
            return self._splitter._k_create_clone(
                src, dst_parent, current_page_dict, self._dst_page_tree
            )
        if src is None:
            return None
        if isinstance(src, COSArray):
            return self.create_array_clone(src, dst_parent, current_page_dict)
        if isinstance(src, COSDictionary):
            return self.create_dictionary_clone(src, dst_parent, current_page_dict)
        return src

    def create_array_clone(
        self,
        src: COSArray,
        dst_parent: COSBase | None,
        current_page_dict: COSDictionary | None,
    ) -> COSBase | None:
        """Clone a structure-tree ``/K`` array. Mirrors upstream's private
        ``createArrayClone`` (Splitter.java line 390)."""
        if self._splitter is not None and hasattr(self._splitter, "_k_create_clone"):
            return self.create_clone(src, dst_parent, current_page_dict)
        result = COSArray()
        for element in src:
            cloned = self.create_clone(element, dst_parent, current_page_dict)
            if cloned is not None:
                result.add(cloned)
        return result if result.size() > 0 else None

    def create_dictionary_clone(
        self,
        src: COSDictionary,
        dst_parent: COSBase | None,
        current_page_dict: COSDictionary | None,
    ) -> COSBase | None:
        """Clone a structure-tree ``/K`` dictionary. Mirrors upstream's
        private ``createDictionaryClone`` (Splitter.java line 413)."""
        if self._splitter is not None and hasattr(self._splitter, "_k_create_clone"):
            return self.create_clone(src, dst_parent, current_page_dict)
        # Splitter-less fallback: passthrough so the dictionary is not lost.
        return src

    def has_mci_ds(self, kid: COSBase | None) -> bool:
        """Return ``True`` when ``kid`` references at least one MCID. Mirrors
        upstream's private ``hasMCIDs`` (Splitter.java line 535)."""
        if kid is None:
            return False
        if isinstance(kid, COSDictionary):
            value = kid.get_dictionary_object(COSName.get_pdf_name("K"))
            from pypdfbox.cos.cos_integer import COSInteger

            if isinstance(value, COSInteger):
                return True
            if isinstance(value, COSArray):
                return any(self.has_mci_ds(v) for v in value)
            if isinstance(value, COSDictionary):
                return self.has_mci_ds(value)
            return False
        if isinstance(kid, COSArray):
            return any(self.has_mci_ds(v) for v in kid)
        # Bare COSInteger means an MCID.
        from pypdfbox.cos.cos_integer import COSInteger

        return isinstance(kid, COSInteger)

    def remove_possible_orphan_annotation(
        self,
        src_obj: COSDictionary,
        src_dict: COSDictionary,
        annotations: object | None = None,
    ) -> None:
        """Drop an annotation reference from the destination page when its
        owning structure element ends up in a different page. Mirrors
        upstream's private ``removePossibleOrphanAnnotation``
        (Splitter.java line 555)."""
        if self._splitter is not None and hasattr(
            self._splitter, "_remove_possible_orphan_annotation"
        ):
            self._splitter._remove_possible_orphan_annotation(  # type: ignore[attr-defined]
                src_obj, src_dict, annotations
            )
            return
        # Splitter-less fallback: clear the /Obj reference defensively.
        obj_name = COSName.get_pdf_name("Obj")
        if src_dict.contains_key(obj_name):
            src_dict.remove_item(obj_name)


__all__ = ["KCloner"]
