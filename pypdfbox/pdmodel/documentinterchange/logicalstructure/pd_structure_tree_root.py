from __future__ import annotations

from typing import Any, Iterator

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode

from .pd_parent_tree_value import PDParentTreeValue
from .pd_structure_class_map import PDStructureClassMap
from .pd_structure_element import PDStructureElement
from .pd_structure_node import PDStructureNode

_ID_TREE: COSName = COSName.get_pdf_name("IDTree")
_PARENT_TREE: COSName = COSName.get_pdf_name("ParentTree")
_PARENT_TREE_NEXT_KEY: COSName = COSName.get_pdf_name("ParentTreeNextKey")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_CLASS_MAP: COSName = COSName.get_pdf_name("ClassMap")

_STRUCT_TREE_ROOT_NAME: str = "StructTreeRoot"

# Cap how far we follow a /RoleMap chain. PDF 32000-1 §14.7.4 doesn't pin a
# limit; upstream PDFBox uses the role-map dictionary itself as the cycle
# detector. We additionally cap the walk at 16 hops as belt-and-braces
# protection against pathological inputs (matches PDStructureElement).
_MAX_ROLE_MAP_DEPTH: int = 16

# PDF 32000-1 §14.8.4 standard structure types (subset). When ``ResolveRoleMap``
# walks the chain it stops at any name in this set; otherwise it follows the
# next mapping. The list mirrors upstream ``StandardStructureTypes`` constants
# that are recognised at the structure-tree root level. Keeping it inline
# avoids a circular import with the ``taggedpdf`` package.
_STANDARD_STRUCTURE_TYPES: frozenset[str] = frozenset(
    {
        "Document",
        "Part",
        "Art",
        "Sect",
        "Div",
        "BlockQuote",
        "Caption",
        "TOC",
        "TOCI",
        "Index",
        "NonStruct",
        "Private",
        "P",
        "H",
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
        "L",
        "LI",
        "Lbl",
        "LBody",
        "Table",
        "TR",
        "TH",
        "TD",
        "THead",
        "TBody",
        "TFoot",
        "Span",
        "Quote",
        "Note",
        "Reference",
        "BibEntry",
        "Code",
        "Link",
        "Annot",
        "Ruby",
        "RB",
        "RT",
        "RP",
        "Warichu",
        "WT",
        "WP",
        "Figure",
        "Formula",
        "Form",
    }
)


class PDStructureTreeRoot(PDStructureNode):
    """
    Root of a PDF logical-structure tree (``/StructTreeRoot`` dictionary).
    Mirrors PDFBox ``PDStructureTreeRoot``.

    Lite surface: ``/K`` returns typed children where known, preserving raw
    COS fallback; ``/ParentTree`` returns a typed number-tree wrapper with raw
    COS values; ``/ClassMap`` returns a :class:`PDStructureClassMap` typed
    wrapper exposing ``PDAttributeObject``-typed entries.
    """

    def __init__(self, struct_tree_root: COSDictionary | None = None) -> None:
        super().__init__(
            struct_tree_root if struct_tree_root is not None else _STRUCT_TREE_ROOT_NAME
        )
        # Backwards-compat alias for callers / subclasses that referenced ``_root``.
        self._root: COSDictionary = self._dictionary

    # ---------- /K kids ----------
    #
    # PDStructureNode provides ``get_kids`` / ``set_kids`` / ``append_kid`` /
    # ``remove_kid``; we keep no override here.

    # ---------- /RoleMap ----------

    def get_role_map(self) -> dict[str, str]:
        """
        Returns a Python dict mapping non-standard structure-type names to
        standard structure types. Entries that are not ``/Name`` values
        are skipped (upstream returns the underlying mixed map; we narrow
        to string-to-string for the lite scaffold).
        """
        rm = self._dictionary.get_dictionary_object(_ROLE_MAP)
        out: dict[str, str] = {}
        if not isinstance(rm, COSDictionary):
            return out
        for key, value in rm.entry_set():
            if isinstance(value, COSName):
                out[key.get_name()] = value.get_name()
        return out

    def set_role_map(self, role_map: dict[str, str] | None) -> None:
        if role_map is None:
            self._dictionary.remove_item(_ROLE_MAP)
            return
        rm = COSDictionary()
        for key, value in role_map.items():
            rm.set_name(key, value)
        self._dictionary.set_item(_ROLE_MAP, rm)

    # ---------- /ClassMap ----------

    def get_class_map(self) -> PDStructureClassMap | None:
        """
        Returns the ``/ClassMap`` as a :class:`PDStructureClassMap` typed
        wrapper, or ``None`` when the entry is absent.

        Mirrors upstream ``PDStructureTreeRoot.getClassMap`` semantics; we
        return a typed wrapper instead of a raw ``Map<String,Object>``.
        """
        cm = self._dictionary.get_dictionary_object(_CLASS_MAP)
        if not isinstance(cm, COSDictionary):
            return None
        return PDStructureClassMap(cm)

    def set_class_map(
        self, class_map: PDStructureClassMap | dict[str, Any] | None
    ) -> None:
        """Write the ``/ClassMap`` entry.

        Accepts a :class:`PDStructureClassMap`, a raw ``dict`` whose values
        are :class:`PDAttributeObject` (or lists of them) or raw COS
        dictionaries / arrays, or ``None``/empty to remove the entry."""
        if class_map is None:
            self._dictionary.remove_item(_CLASS_MAP)
            return
        if isinstance(class_map, PDStructureClassMap):
            if class_map.is_empty():
                self._dictionary.remove_item(_CLASS_MAP)
                return
            self._dictionary.set_item(_CLASS_MAP, class_map.get_cos_object())
            return
        if not class_map:
            self._dictionary.remove_item(_CLASS_MAP)
            return
        cm = COSDictionary()
        for name, value in class_map.items():
            if isinstance(value, list):
                arr = COSArray()
                for entry in value:
                    arr.add(_to_cos(entry))
                cm.set_item(name, arr)
            else:
                cm.set_item(name, _to_cos(value))
        self._dictionary.set_item(_CLASS_MAP, cm)

    # ---------- /IDTree ----------

    def get_id_tree(self) -> PDNameTreeNode[PDStructureElement] | None:
        id_tree = self._dictionary.get_dictionary_object(_ID_TREE)
        if not isinstance(id_tree, COSDictionary):
            return None
        return PDStructureElementNameTreeNode(id_tree)

    def set_id_tree(self, id_tree: Any) -> None:
        if id_tree is None:
            self._dictionary.remove_item(_ID_TREE)
            return
        cos = id_tree.get_cos_object() if hasattr(id_tree, "get_cos_object") else id_tree
        self._dictionary.set_item(_ID_TREE, cos)

    # ---------- /ParentTree ----

    def get_parent_tree(self) -> PDStructureElementNumberTreeNode | None:
        """Return the ``/ParentTree`` as a typed number-tree wrapper.

        Mirrors upstream ``PDStructureTreeRoot.getParentTree()``. Values are
        exposed as raw COS entries (either a structure-element
        :class:`COSDictionary` or a :class:`COSArray` indexed by MCID) — use
        :meth:`get_parent_tree_value` for a :class:`PDParentTreeValue`-typed
        convenience lookup.
        """
        parent_tree = self._dictionary.get_dictionary_object(_PARENT_TREE)
        if not isinstance(parent_tree, COSDictionary):
            return None
        return PDStructureElementNumberTreeNode(parent_tree)

    def set_parent_tree(self, parent_tree: PDNumberTreeNode[Any] | Any) -> None:
        """Set the ``/ParentTree`` entry. Accepts a :class:`PDNumberTreeNode`,
        a raw :class:`COSDictionary`, anything with ``get_cos_object``, or
        ``None`` to remove. Mirrors upstream
        ``PDStructureTreeRoot.setParentTree(PDNumberTreeNode)``."""
        if parent_tree is None:
            self._dictionary.remove_item(_PARENT_TREE)
            return
        cos = (
            parent_tree.get_cos_object()
            if hasattr(parent_tree, "get_cos_object")
            else parent_tree
        )
        self._dictionary.set_item(_PARENT_TREE, cos)

    def get_parent_tree_value(self, key: int) -> PDParentTreeValue | None:
        """Look up a ``/ParentTree`` entry by integer key and return it as a
        :class:`PDParentTreeValue` wrapper, or ``None`` when the parent tree
        is absent or the key is unknown.

        Per PDF 32000-1 §14.7.4.4 the value is either a structure-element
        dictionary (annotations / XObjects) or an array indexed by MCID
        (page objects / content streams); :class:`PDParentTreeValue` keeps
        either shape addressable as a single typed wrapper.
        """
        parent_tree = self.get_parent_tree()
        if parent_tree is None:
            return None
        value = parent_tree.get_value(key)
        if not isinstance(value, (COSArray, COSDictionary)):
            return None
        return PDParentTreeValue(value)

    # ---------- /ParentTreeNextKey ----------

    def get_parent_tree_next_key(self) -> int:
        """Return ``/ParentTreeNextKey`` (the next-available integer key for
        the parent tree). Defaults to ``0`` when the entry is absent.
        Mirrors upstream ``PDStructureTreeRoot.getParentTreeNextKey()``."""
        return self._dictionary.get_int(_PARENT_TREE_NEXT_KEY, 0)

    def set_parent_tree_next_key(self, key: int) -> None:
        """Set ``/ParentTreeNextKey``. Mirrors upstream
        ``PDStructureTreeRoot.setParentTreeNextKey(int)``."""
        self._dictionary.set_int(_PARENT_TREE_NEXT_KEY, key)

    # ---------- convenience lookups ----------

    def get_struct_element_for_id(self, id_string: str) -> PDStructureElement | None:
        """Look up a ``PDStructureElement`` by ``/ID`` via the ``/IDTree``.
        Returns ``None`` when the ``/IDTree`` is absent or the id is not found.
        Mirrors upstream ``PDStructureTreeRoot.getStructElementForID``."""
        if id_string is None:
            return None
        id_tree = self.get_id_tree()
        if id_tree is None:
            return None
        return id_tree.get_value(id_string)

    def get_struct_element_for_mcid(
        self, page: Any, mcid: int
    ) -> PDStructureElement | None:
        """Look up the ``PDStructureElement`` that owns the marked-content
        sequence with id ``mcid`` on ``page``. Resolves via
        ``/StructParents`` → ``/ParentTree`` → array indexed by mcid.
        Returns ``None`` when any link is missing.
        Mirrors upstream ``PDStructureTreeRoot.getStructElementForMCID``."""
        if page is None:
            return None
        struct_parents = page.get_struct_parents()
        if struct_parents < 0:
            return None
        parent_tree = self.get_parent_tree()
        if parent_tree is None:
            return None
        entry = parent_tree.get_value(struct_parents)
        if not isinstance(entry, COSArray):
            return None
        if mcid < 0 or mcid >= entry.size():
            return None
        target = entry.get_object(mcid)
        if not isinstance(target, COSDictionary):
            return None
        return PDStructureElement(target)

    # ---------- /K traversal helpers (pypdfbox additions) ----------

    def iter_descendants(self) -> Iterator[PDStructureElement]:
        """Depth-first walk of every ``PDStructureElement`` reachable from
        ``/K``. Skips marked-content references, object references, and bare
        MCID integers. Cycles in ``/K`` are guarded by an identity-set so
        the walk terminates.
        """
        seen: set[int] = {id(self._dictionary)}
        stack: list[PDStructureElement] = []
        direct = [
            k for k in self.get_kids() if isinstance(k, PDStructureElement)
        ]
        stack.extend(reversed(direct))
        while stack:
            node = stack.pop()
            node_id = id(node.get_cos_object())
            if node_id in seen:
                continue
            seen.add(node_id)
            yield node
            children = [
                k for k in node.get_kids() if isinstance(k, PDStructureElement)
            ]
            stack.extend(reversed(children))

    def find_by_role(self, role: str) -> Iterator[PDStructureElement]:
        """Yield every descendant element whose *resolved* (role-map normalized)
        structure type matches ``role``. Mirrors the existing
        :meth:`PDStructureElement.find_by_role` API but rooted at the tree
        root rather than a structure element."""
        for descendant in self.iter_descendants():
            resolved = descendant.get_standard_structure_type()
            if resolved == role:
                yield descendant

    def find_first_by_role(self, role: str) -> PDStructureElement | None:
        """Return the first descendant matching ``role``, or ``None``."""
        for hit in self.find_by_role(role):
            return hit
        return None

    # ---------- /RoleMap resolve ----------

    def resolve_role_map(self, structure_type: str | None) -> str | None:
        """Resolve ``structure_type`` against ``/RoleMap`` until it lands on
        a standard PDF structure type (or runs out of mappings).

        Mirrors upstream ``getStandardStructureType`` semantics applied at
        the tree-root level. Returns the input unchanged when no role-map
        exists, when the input is already a standard type, or when no
        mapping matches. Cycles are broken by visiting each name at most
        once.
        """
        if structure_type is None:
            return None
        role_map = self.get_role_map()
        if not role_map:
            return structure_type
        seen: set[str] = set()
        current: str = structure_type
        for _ in range(_MAX_ROLE_MAP_DEPTH):
            if current in _STANDARD_STRUCTURE_TYPES:
                return current
            if current in seen:
                return current
            seen.add(current)
            mapped = role_map.get(current)
            if mapped is None:
                return current
            current = mapped
        return current

    # ---------- /ParentTree construction ----------

    def build_parent_tree(self, pages: Any) -> PDStructureElementNumberTreeNode:
        """Construct ``/ParentTree`` from the supplied iterable of
        :class:`PDPage`-likes (anything exposing ``get_struct_parents`` and
        ``get_cos_object``).

        The resulting number tree maps each page's ``/StructParents`` integer
        to a :class:`COSArray` indexed by MCID. Existing per-page entries
        already present in the tree are reused (callers rebuilding from
        scratch should pass in a fresh ``PDStructureTreeRoot``).

        Mirrors the upstream "StructParents → ParentTree" wiring that lives
        inline in ``PDFMergerUtility`` / ``LayerUtility``; the helper is a
        pypdfbox convenience that lifts it onto :class:`PDStructureTreeRoot`.

        Returns the resulting :class:`PDStructureElementNumberTreeNode`. Pages
        without a ``/StructParents`` entry (or with a negative value) are
        skipped; the caller is expected to set ``/StructParents`` on each
        page before invoking this builder.
        """
        existing = self.get_parent_tree()
        if existing is None:
            tree = PDStructureElementNumberTreeNode()
        else:
            tree = existing
        # Read existing numbers as a dict to make merging deterministic.
        existing_numbers = tree.get_numbers() or {}
        nums: dict[int, COSBase] = dict(existing_numbers)
        max_key = max(nums.keys()) if nums else -1
        for page in pages or []:
            sp = page.get_struct_parents()
            if sp is None or sp < 0:
                continue
            if sp not in nums:
                # Empty per-page array; callers populate it through
                # ``/MCID`` ordering when they wire structure elements.
                nums[sp] = COSArray()
            if sp > max_key:
                max_key = sp
        tree.set_numbers(nums)
        self.set_parent_tree(tree)
        if max_key >= 0:
            self.set_parent_tree_next_key(max_key + 1)
        return tree

    # ---------- /K append ----------

    def append_kid(self, kid: Any) -> None:  # noqa: D401 - mirrors upstream
        """Append ``kid`` to the root's ``/K``. Wires ``/P`` for
        :class:`PDStructureElement` kids so they back-reference this root,
        mirroring upstream's ``appendKid(PDStructureElement)`` plumbing.
        """
        if kid is None:
            return
        super().append_kid(kid)
        if isinstance(kid, PDStructureElement):
            kid.set_parent(self)


class PDStructureElementNameTreeNode(PDNameTreeNode[PDStructureElement]):
    """
    Concrete name-tree node used for ``/IDTree``. Mirrors upstream
    ``org.apache.pdfbox.pdmodel.PDStructureElementNameTreeNode`` (kept
    private to this module — the upstream class lives directly in
    ``pdmodel``; we colocate here until callers need a public symbol).
    """

    def convert_cos_to_value(self, base: COSBase) -> PDStructureElement:
        if not isinstance(base, COSDictionary):
            raise TypeError(
                f"IDTree value must be COSDictionary, got {type(base).__name__}"
            )
        return PDStructureElement(base)

    def convert_value_to_cos(self, value: PDStructureElement) -> COSBase:
        return value.get_cos_object()

    def create_child_node(self, dic: COSDictionary) -> PDStructureElementNameTreeNode:
        return PDStructureElementNameTreeNode(dic)


class PDStructureElementNumberTreeNode(PDNumberTreeNode[COSBase]):
    """
    Concrete number-tree node used for ``/ParentTree``. Values are exposed as
    raw COS entries because parent-tree leaves may be either a structure
    element dictionary or an array indexed by MCID.
    """

    def convert_cos_to_value(self, base: COSBase) -> COSBase:
        return base

    def convert_value_to_cos(self, value: COSBase) -> COSBase:
        return _to_cos(value)

    def create_child_node(self, dic: COSDictionary) -> PDStructureElementNumberTreeNode:
        return PDStructureElementNumberTreeNode(dic)


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return value.get_cos_object()
    return value


__all__ = [
    "PDStructureClassMap",
    "PDStructureElementNameTreeNode",
    "PDStructureElementNumberTreeNode",
    "PDStructureTreeRoot",
]
