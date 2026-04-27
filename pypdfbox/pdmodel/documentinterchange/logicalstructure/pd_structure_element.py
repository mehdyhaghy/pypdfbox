from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_structure_node import PDStructureNode

_S: COSName = COSName.get_pdf_name("S")
_P: COSName = COSName.get_pdf_name("P")
_ID: COSName = COSName.get_pdf_name("ID")
_R: COSName = COSName.get_pdf_name("R")
_T: COSName = COSName.T  # type: ignore[attr-defined]
_LANG: COSName = COSName.get_pdf_name("Lang")
_ALT: COSName = COSName.get_pdf_name("Alt")
_E: COSName = COSName.get_pdf_name("E")
_ACTUAL_TEXT: COSName = COSName.get_pdf_name("ActualText")
_A: COSName = COSName.get_pdf_name("A")
_C: COSName = COSName.get_pdf_name("C")
_PG: COSName = COSName.get_pdf_name("Pg")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")

_STRUCT_ELEM_NAME: str = "StructElem"
_STRUCT_TREE_ROOT_NAME: str = "StructTreeRoot"

# Cap how far we follow a /RoleMap chain. PDF 32000-1 §14.7.4 doesn't pin a
# limit; upstream PDFBox uses the role-map dictionary itself as the cycle
# detector. We additionally cap the walk at 16 hops as belt-and-braces
# protection against pathological inputs.
_MAX_ROLE_MAP_DEPTH: int = 16

if TYPE_CHECKING:
    from .pd_attribute_object import PDAttributeObject
    from .revisions import Revisions


class PDStructureElement(PDStructureNode):
    """
    A structure element (``/Type /StructElem`` dictionary). Mirrors PDFBox
    ``PDStructureElement``.

    This is the *lite* surface: typed attribute objects, class-name
    revisions, page (``/Pg``), ``/K`` typed kid dispatch, and role-map
    resolution are present; the typed-parent chain is deferred until later
    clusters land.
    """

    TYPE: str = "StructElem"

    def __init__(
        self,
        structure_element: COSDictionary | None = None,
        structure_type: str | None = None,
    ) -> None:
        super().__init__(structure_element if structure_element is not None else _STRUCT_ELEM_NAME)
        # Backwards-compat alias for callers / subclasses that referenced ``_element``.
        self._element: COSDictionary = self._dictionary
        if structure_type is not None:
            self.set_structure_type(structure_type)

    # ---------- /S structure type ----------

    def get_structure_type(self) -> str | None:
        return self._dictionary.get_name(_S)

    def set_structure_type(self, structure_type: str) -> None:
        self._dictionary.set_name(_S, structure_type)

    # ---------- /Pg page ----------

    def get_page(self) -> Any | None:
        """Return the typed ``PDPage`` for ``/Pg`` if present, else ``None``.

        Mirrors upstream ``PDStructureElement.getPage()``. The returned wrapper
        wraps the same underlying ``COSDictionary`` (no copy)."""
        from pypdfbox.pdmodel.pd_page import PDPage

        pg = self._dictionary.get_dictionary_object(_PG)
        if isinstance(pg, COSDictionary):
            return PDPage(pg)
        return None

    def set_page(self, page: Any | None) -> None:
        """Write ``/Pg``. ``None`` removes the entry."""
        if page is None:
            self._dictionary.remove_item(_PG)
            return
        cos = page.get_cos_object() if hasattr(page, "get_cos_object") else page
        self._dictionary.set_item(_PG, cos)

    # ---------- /S resolved through /RoleMap ----------

    def get_standard_structure_type(self) -> str | None:
        """Resolve this element's ``/S`` against the structure-tree-root
        ``/RoleMap`` until a standard PDF structure type is reached. Returns
        the resolved name, or ``None`` if ``/S`` is absent.

        Per PDF 32000-1 §14.7.4 a structure element's ``/S`` may be a
        non-standard name; the catalog's ``/StructTreeRoot/RoleMap`` maps it
        (potentially through several hops) to a standard structure type.
        """
        struct_type = self._dictionary.get_name(_S)
        if struct_type is None:
            return None

        role_map = self._find_role_map()
        if not role_map:
            return struct_type

        seen: set[str] = set()
        current = struct_type
        for _ in range(_MAX_ROLE_MAP_DEPTH):
            if current in seen:
                # Cycle — bail with the last value we resolved.
                return current
            seen.add(current)
            mapped = role_map.get(current)
            if mapped is None:
                return current
            current = mapped
        return current

    def _find_role_map(self) -> dict[str, str]:
        """Walk the ``/P`` parent chain to the ``StructTreeRoot`` and return
        its ``/RoleMap`` as a ``{name: name}`` dict. Returns an empty dict if
        no root or no role map is reachable."""
        node: COSDictionary | None = self._dictionary
        seen: set[int] = set()
        # Cap the parent walk too — defensive against malformed cyclic /P.
        for _ in range(_MAX_ROLE_MAP_DEPTH):
            if node is None or id(node) in seen:
                return {}
            seen.add(id(node))
            if node.get_name(_TYPE) == _STRUCT_TREE_ROOT_NAME:
                return _read_role_map(node)
            parent = node.get_dictionary_object(_P)
            node = parent if isinstance(parent, COSDictionary) else None
        return {}

    # ---------- /P parent (raw COSBase; typed PDStructureNode deferred) ----

    def get_parent(self) -> COSBase | None:
        return self._dictionary.get_dictionary_object(_P)

    def set_parent(self, parent: Any) -> None:
        if parent is None:
            self._dictionary.remove_item(_P)
            return
        cos = parent.get_cos_object() if hasattr(parent, "get_cos_object") else parent
        self._dictionary.set_item(_P, cos)

    # ---------- /ID ----------

    def get_id(self) -> str | None:
        return self._dictionary.get_string(_ID)

    def set_id(self, id_: str | None) -> None:
        self._dictionary.set_string(_ID, id_)

    # ---------- /R revision number ----------

    def get_revision_number(self) -> int:
        return self._dictionary.get_int(_R, 0)

    def set_revision_number(self, revision_number: int) -> None:
        if revision_number < 0:
            raise ValueError("The revision number shall be > -1")
        self._dictionary.set_int(_R, revision_number)

    # ---------- /T title ----------

    def get_title(self) -> str | None:
        return self._dictionary.get_string(_T)

    def set_title(self, title: str | None) -> None:
        self._dictionary.set_string(_T, title)

    # ---------- /Lang ----------

    def get_language(self) -> str | None:
        return self._dictionary.get_string(_LANG)

    def set_language(self, language: str | None) -> None:
        self._dictionary.set_string(_LANG, language)

    # ---------- /Alt ----------

    def get_alternate_description(self) -> str | None:
        return self._dictionary.get_string(_ALT)

    def set_alternate_description(self, alternate_description: str | None) -> None:
        self._dictionary.set_string(_ALT, alternate_description)

    # ---------- /E expanded form ----------

    def get_expanded_form(self) -> str | None:
        return self._dictionary.get_string(_E)

    def set_expanded_form(self, expanded_form: str | None) -> None:
        self._dictionary.set_string(_E, expanded_form)

    # ---------- /ActualText ----------

    def get_actual_text(self) -> str | None:
        return self._dictionary.get_string(_ACTUAL_TEXT)

    def set_actual_text(self, actual_text: str | None) -> None:
        self._dictionary.set_string(_ACTUAL_TEXT, actual_text)

    # ---------- /Alt convenience alias ----------

    def get_alt_text(self) -> str | None:
        """Convenience alias for ``get_alternate_description`` (``/Alt``).

        pypdfbox addition. Upstream PDFBox exposes only
        ``getAlternateDescription``; this short-name accessor mirrors
        common terminology used in PDF tagging tooling and is purely
        additive (no behavior change)."""
        return self.get_alternate_description()

    def set_alt_text(self, alt_text: str | None) -> None:
        """Convenience alias for ``set_alternate_description``."""
        self.set_alternate_description(alt_text)

    # ---------- /K kids ----------
    #
    # ``get_kids`` / ``set_kids`` / ``append_kid`` / ``remove_kid`` come from
    # PDStructureNode. The base node treats ``/K`` as a flat list of typed
    # structure-tree entries, preserving unknown values as raw COS fallback.

    # ---------- traversal helpers (pypdfbox additions) ----------
    #
    # Upstream PDFBox does not expose iter_descendants / find_by_role
    # directly; Java callers typically use the Stream API over getKids().
    # These helpers are pypdfbox conveniences and are purely additive.

    def iter_kids(self) -> Iterator[Any]:
        """Yield direct ``/K`` kids one at a time.

        Items are wrapped per :meth:`PDStructureNode.wrap_kid`:
        ``PDStructureElement`` / ``PDMarkedContentReference`` /
        ``PDObjectReference`` / ``int`` MCID, or raw COS fallback for
        unknown entries. This is a streaming view of :meth:`get_kids`.
        """
        for kid in self.get_kids():
            yield kid

    def iter_descendants(self) -> Iterator[PDStructureElement]:
        """Depth-first walk of the ``/K`` sub-tree.

        Yields every descendant ``PDStructureElement`` (not the node
        itself, and not marked-content references / object references /
        MCIDs). Order is pre-order DFS: each child element is yielded
        before its own descendants. Cycles in ``/K`` (malformed input)
        are guarded by an identity-set so the walk terminates.
        """
        seen: set[int] = {id(self._dictionary)}
        stack: list[PDStructureElement] = []
        # Push direct kids in reverse so pop() yields them in original order.
        direct = [k for k in self.get_kids() if isinstance(k, PDStructureElement)]
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
        """Yield every descendant element whose structure type matches
        ``role``.

        ``role`` is compared against the descendant's *resolved* standard
        structure type (i.e. after ``/RoleMap`` remap via
        :meth:`get_standard_structure_type`); falling back to the raw
        ``/S`` when no role-map is reachable. This means ``find_by_role
        ("H1")`` matches both elements whose ``/S`` is ``H1`` and elements
        whose ``/S`` maps to ``H1`` through a parent ``StructTreeRoot``'s
        ``/RoleMap``.
        """
        for descendant in self.iter_descendants():
            resolved = descendant.get_standard_structure_type()
            if resolved == role:
                yield descendant

    def find_first_by_role(self, role: str) -> PDStructureElement | None:
        """Return the first descendant matching ``role``, or ``None``.

        Equivalent to ``next(self.find_by_role(role), None)`` but spelled
        out for callers who prefer an explicit accessor."""
        for descendant in self.find_by_role(role):
            return descendant
        return None

    # ---------- /A attributes ----------

    def get_attributes(self) -> Revisions[PDAttributeObject]:
        from .pd_attribute_object import PDAttributeObject
        from .revisions import Revisions

        a = self._dictionary.get_dictionary_object(_A)
        if isinstance(a, COSArray):
            return Revisions(a)
        revs: Revisions[PDAttributeObject] = Revisions()
        if isinstance(a, COSDictionary):
            revs.add_object(PDAttributeObject(a), self.get_revision_number())
        return revs

    def set_attributes(self, attributes: Revisions[PDAttributeObject] | None) -> None:
        if attributes is None:
            self._dictionary.remove_item(_A)
            return
        self._dictionary.set_item(_A, attributes.to_cos_array())

    # ---------- /C class names ----------

    def get_class_names(self) -> Revisions[COSName]:
        from .revisions import Revisions

        c = self._dictionary.get_dictionary_object(_C)
        if isinstance(c, COSArray):
            return Revisions(c)
        revs: Revisions[COSName] = Revisions()
        if isinstance(c, COSName):
            revs.add_object(c, self.get_revision_number())
        return revs

    def set_class_names(self, class_names: Revisions[COSName] | None) -> None:
        if class_names is None:
            self._dictionary.remove_item(_C)
            return
        self._dictionary.set_item(_C, class_names.to_cos_array())


def _read_role_map(root: COSDictionary) -> dict[str, str]:
    """Extract ``/RoleMap`` from a structure-tree-root dict as a Python
    ``{name: name}`` map. Non-name values are skipped (they cannot resolve
    to a standard structure type in any meaningful way)."""
    rm = root.get_dictionary_object(_ROLE_MAP)
    if not isinstance(rm, COSDictionary):
        return {}
    out: dict[str, str] = {}
    for key, value in rm.entry_set():
        if isinstance(value, COSName):
            out[key.get_name()] = value.get_name()
    return out


__all__ = ["PDStructureElement"]
