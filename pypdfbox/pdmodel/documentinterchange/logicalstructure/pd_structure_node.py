from __future__ import annotations

from typing import Any, cast

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_K: COSName = COSName.get_pdf_name("K")
_STRUCT_TREE_ROOT_NAME: str = "StructTreeRoot"
_STRUCT_ELEM_NAME: str = "StructElem"


class PDStructureNode:
    """
    Base node in the logical-structure tree. Mirrors PDFBox
    ``PDStructureNode`` (the abstract parent of ``PDStructureTreeRoot`` and
    ``PDStructureElement``).

    Lite surface: typed kid dispatch (PDStructureElement /
    PDMarkedContentReference / PDObjectReference / int MCID), kid
    insertion/removal helpers, and cheap kid-count/emptiness predicates.
    Typed parent-chain helpers live on ``PDStructureElement``. Unknown
    ``/K`` entries are skipped, matching upstream ``createObject``.
    """

    #: ``/Type`` value identifying a :class:`PDStructureTreeRoot` dictionary.
    #: Mirrors upstream's literal ``"StructTreeRoot"`` (no upstream constant
    #: exists; lifted here so callers don't have to repeat the magic string).
    STRUCT_TREE_ROOT_TYPE: str = _STRUCT_TREE_ROOT_NAME

    #: ``/Type`` value identifying a :class:`PDStructureElement` dictionary.
    #: Mirrors upstream's ``PDStructureElement.TYPE`` and the literal
    #: ``"StructElem"`` checked by :meth:`create` / :meth:`create_object`.
    STRUCT_ELEM_TYPE: str = _STRUCT_ELEM_NAME

    def __init__(
        self,
        structure_type_for_create: str | COSDictionary | None = None,
    ) -> None:
        if isinstance(structure_type_for_create, COSDictionary):
            self._dictionary: COSDictionary = structure_type_for_create
        elif isinstance(structure_type_for_create, str):
            self._dictionary = COSDictionary()
            self._dictionary.set_name(_TYPE, structure_type_for_create)
        else:
            self._dictionary = COSDictionary()

    @staticmethod
    def create(node: COSDictionary) -> PDStructureNode:
        """
        Dispatch a ``COSDictionary`` to the matching typed wrapper:
        ``StructTreeRoot`` → ``PDStructureTreeRoot``;
        ``StructElem`` (or no ``/Type``) → ``PDStructureElement``.
        """
        if not isinstance(node, COSDictionary):
            raise TypeError(
                f"PDStructureNode.create expects COSDictionary, got {type(node).__name__}"
            )
        type_name = node.get_name_as_string(_TYPE)
        if type_name == _STRUCT_TREE_ROOT_NAME:
            from .pd_structure_tree_root import PDStructureTreeRoot

            return PDStructureTreeRoot(node)
        if type_name is None or type_name == _STRUCT_ELEM_NAME:
            from .pd_structure_element import PDStructureElement

            return PDStructureElement(node)
        raise ValueError(
            "Dictionary must not include a Type entry with a value that is "
            "neither StructTreeRoot nor StructElem."
        )

    @staticmethod
    def wrap_kid(kid: Any) -> Any:
        """Dispatch a /K kid entry to a typed wrapper based on /Type, or
        return the raw int / COSBase. Ints are MCIDs (marked content ids)."""
        from pypdfbox.cos import COSDictionary, COSInteger

        from .pd_marked_content_reference import PDMarkedContentReference
        from .pd_object_reference import PDObjectReference

        if isinstance(kid, COSInteger):
            return kid.value
        if isinstance(kid, COSDictionary):
            type_name = kid.get_name_as_string(_TYPE)
            if type_name == "MCR":
                return PDMarkedContentReference(kid)
            if type_name == "OBJR":
                return PDObjectReference(kid)
            if type_name == "StructElem":
                from .pd_structure_element import PDStructureElement

                return PDStructureElement(kid)
        return kid

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_type(self) -> str | None:
        return self._dictionary.get_name_as_string(_TYPE)

    def is_struct_tree_root(self) -> bool:
        """Return ``True`` when ``/Type`` is ``StructTreeRoot``.

        No upstream equivalent — added as a small typed predicate so callers
        don't have to compare against the magic string. Pairs with
        :meth:`is_struct_elem` and the public :attr:`STRUCT_TREE_ROOT_TYPE`
        constant.
        """
        return self.get_type() == _STRUCT_TREE_ROOT_NAME

    def is_struct_elem(self) -> bool:
        """Return ``True`` when ``/Type`` is ``StructElem`` (or absent).

        No upstream equivalent — added as a small typed predicate. Mirrors
        the dispatch rule used by :meth:`create` and :meth:`create_object`,
        where a missing ``/Type`` is treated as ``StructElem``.
        """
        type_name = self.get_type()
        return type_name is None or type_name == _STRUCT_ELEM_NAME

    # ---------- /K kids ----------

    def get_kids(self) -> list[Any]:
        """
        Returns the typed ``/K`` children. ``/K`` may be a single structure
        element dictionary, a single integer MCID, or a COSArray mixing
        dictionaries, integer MCIDs, and marked-content references. Known
        structure-tree dictionaries are wrapped; unknown entries are skipped.
        """
        k = self._dictionary.get_dictionary_object(_K)
        if k is None:
            return []
        if isinstance(k, COSArray):
            out: list[Any] = []
            for i in range(k.size()):
                base = k.get_object(i)
                value = self.create_object(base)
                if value is not None:
                    out.append(value)
            return out
        value = self.create_object(k)
        return [] if value is None else [value]

    def set_kids(self, kids: list[Any] | None) -> None:
        if not kids:
            self._dictionary.remove_item(_K)
            return
        arr = COSArray()
        for kid in kids:
            arr.add(_to_cos(kid))
        self._dictionary.set_item(_K, arr)

    def has_kids(self) -> bool:
        """Return ``True`` when ``/K`` is present and non-empty.

        Cheaper than ``len(get_kids()) > 0`` because we don't materialise
        the typed kid wrappers — we only inspect the raw ``/K`` entry. A
        single-kid (non-array) ``/K`` counts as having kids; an empty
        ``COSArray`` counts as no kids (matches :meth:`set_kids`'s
        behaviour, which removes ``/K`` when given an empty list).
        """
        k = self._dictionary.get_dictionary_object(_K)
        if k is None:
            return False
        if isinstance(k, COSArray):
            return k.size() > 0
        return True

    def is_kids_empty(self) -> bool:
        """Return ``True`` when ``/K`` is absent or an empty array.

        Inverse of :meth:`has_kids`. No upstream equivalent — added as a
        small predicate so callers can avoid building the full typed kid
        list when they only need an emptiness check.
        """
        return not self.has_kids()

    def get_kids_count(self) -> int:
        """Return the number of ``/K`` entries without materialising
        typed wrappers.

        Faster than ``len(get_kids())`` for nodes with many or
        unrecognised kids. A missing ``/K`` returns ``0``; a single-kid
        (non-array) ``/K`` returns ``1``; a ``COSArray`` returns its
        size. No upstream equivalent — added as a typed accessor.
        """
        k = self._dictionary.get_dictionary_object(_K)
        if k is None:
            return 0
        if isinstance(k, COSArray):
            return k.size()
        return 1

    def contains_kid(self, kid: Any) -> bool:
        """Return ``True`` when ``kid`` is currently present in ``/K``.

        Accepts a typed wrapper (anything exposing ``get_cos_object``), a
        raw ``COSBase``, or an ``int`` MCID — uses the same equality rules
        as :meth:`remove_kid`. No upstream equivalent — added as a small
        membership predicate so callers don't have to scan
        :meth:`get_kids` themselves. ``None`` returns ``False``.
        """
        if kid is None:
            return False
        cos_kid = _to_cos(kid)
        existing = self._dictionary.get_dictionary_object(_K)
        if existing is None:
            return False
        if isinstance(existing, COSArray):
            return any(
                _same_kid(existing.get_object(i), cos_kid)
                for i in range(existing.size())
            )
        return _same_kid(existing, cos_kid)

    def append_kid(self, kid: Any) -> None:
        if kid is None:
            return
        # Upstream: ``appendKid(int mcid)`` rejects negative MCID values
        # (PDStructureElement.java line 615), and ``appendKid(PDMarkedContent)``
        # rejects a wrapped marked-content sequence whose ``getMCID`` is
        # negative (line 635). Mirror both in this single dispatcher since
        # pypdfbox collapses the overloads.
        if isinstance(kid, bool):
            # bool is an int subclass in Python; reject it explicitly to
            # mirror the Java overload set (no ``appendKid(boolean)``).
            raise TypeError("appendKid does not accept bool")
        if isinstance(kid, int) and kid < 0:
            raise ValueError("MCID should not be negative")
        # Lazy import to avoid a cycle; PDMarkedContent isn't a transitive
        # import of this module.
        from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (  # noqa: PLC0415
            PDMarkedContent,
        )

        if isinstance(kid, PDMarkedContent):
            mcid = kid.get_mcid()
            if mcid < 0:
                raise ValueError("MCID is negative or doesn't exist")
            # Upstream stores the marked-content sequence as just its
            # MCID integer: ``appendKid(COSInteger.get(mcid))``
            # (PDStructureElement.java line 639).
            kid = mcid
        cos_kid = _to_cos(kid)
        existing = self._dictionary.get_dictionary_object(_K)
        if existing is None:
            self._dictionary.set_item(_K, cos_kid)
            _set_parent_if_structure_element(kid, self)
            return
        if isinstance(existing, COSArray):
            existing.add(cos_kid)
            _set_parent_if_structure_element(kid, self)
            return
        arr = COSArray()
        arr.add(existing)
        arr.add(cos_kid)
        self._dictionary.set_item(_K, arr)
        _set_parent_if_structure_element(kid, self)

    def create_object(self, kid: Any) -> Any:
        """Convert a single ``/K`` kid (a ``COSBase``) to its typed wrapper.

        Mirrors upstream protected ``PDStructureNode.createObject``:

        * ``COSDictionary`` (or a ``COSObject`` indirecting one) with
          ``/Type StructElem`` (or no ``/Type``) → :class:`PDStructureElement`.
        * ``/Type MCR`` → :class:`PDMarkedContentReference`.
        * ``/Type OBJR`` → :class:`PDObjectReference`.
        * ``COSInteger`` → ``int`` (the MCID value).
        * Anything else → ``None``.

        Differs from :meth:`wrap_kid` which preserves unknown COS objects
        as a raw fallback; ``create_object`` strictly returns ``None`` for
        unrecognized kids, matching upstream's contract.
        """
        from pypdfbox.cos import COSObject

        kid_dic: COSDictionary | None = None
        if isinstance(kid, COSDictionary):
            kid_dic = kid
        elif isinstance(kid, COSObject):
            base = kid.get_object()
            if isinstance(base, COSDictionary):
                kid_dic = base
        if kid_dic is not None:
            return self.create_object_from_dic(kid_dic)
        if isinstance(kid, COSInteger):
            return kid.value
        return None

    def create_object_from_dic(self, kid_dic: COSDictionary) -> Any:
        """Convert a ``/K`` dictionary kid to its typed wrapper.

        Mirrors upstream private ``PDStructureNode.createObjectFromDic``
        (Java line 395). Returns ``PDStructureElement`` for missing
        ``/Type`` or ``StructElem``, ``PDMarkedContentReference`` for
        ``MCR``, ``PDObjectReference`` for ``OBJR``, and ``None`` for any
        other ``/Type``. Unlike upstream this is exposed as a regular
        method so subclasses can override the dispatch (Python's
        ``protected`` convention).
        """
        from .pd_marked_content_reference import PDMarkedContentReference
        from .pd_object_reference import PDObjectReference

        type_name = kid_dic.get_name_as_string(_TYPE)
        if type_name is None or type_name == _STRUCT_ELEM_NAME:
            from .pd_structure_element import PDStructureElement

            return PDStructureElement(kid_dic)
        if type_name == "MCR":
            return PDMarkedContentReference(kid_dic)
        if type_name == "OBJR":
            return PDObjectReference(kid_dic)
        return None

    def append_objectable_kid(self, objectable: Any) -> None:
        """Append a ``COSObjectable``-style kid (anything exposing
        ``get_cos_object``). Mirrors upstream protected
        ``PDStructureNode.appendObjectableKid`` (Java line 161); ``None``
        is a no-op."""
        if objectable is None:
            return
        if hasattr(objectable, "get_cos_object"):
            self.append_kid(objectable.get_cos_object())
        else:
            self.append_kid(objectable)

    def remove_objectable_kid(self, objectable: Any) -> bool:
        """Remove a ``COSObjectable``-style kid. Mirrors upstream protected
        ``PDStructureNode.removeObjectableKid`` (Java line 297); returns
        ``False`` when the argument is ``None`` or the kid is absent."""
        if objectable is None:
            return False
        if hasattr(objectable, "get_cos_object"):
            return self.remove_kid(objectable.get_cos_object())
        return self.remove_kid(objectable)

    def insert_objectable_before(self, new_kid: Any, ref_kid: Any) -> bool:
        """Insert a ``COSObjectable``-style ``new_kid`` before ``ref_kid``.

        Mirrors upstream protected ``PDStructureNode.insertObjectableBefore``
        (Java line 220): ``new_kid`` is unwrapped via ``get_cos_object``
        when present, then the call is delegated to :meth:`insert_before`.
        ``None`` ``new_kid`` is a silent no-op (returns ``False``).
        """
        if new_kid is None:
            return False
        if hasattr(new_kid, "get_cos_object"):
            return self.insert_before(new_kid.get_cos_object(), ref_kid)
        return self.insert_before(new_kid, ref_kid)

    def insert_before(self, new_kid: Any, before_kid: Any) -> bool:
        """Insert ``new_kid`` immediately before ``before_kid`` in ``/K``.

        Mirrors upstream ``PDStructureNode.insertBefore``. Returns ``True``
        when ``before_kid`` is found and the insert happens; ``False`` when
        ``before_kid`` is missing (no insert performed). Promotes a
        single-entry ``/K`` to a ``COSArray`` when the insert turns it into
        two entries.
        """
        if new_kid is None or before_kid is None:
            return False
        cos_new = _to_cos(new_kid)
        cos_before = _to_cos(before_kid)
        existing = self._dictionary.get_dictionary_object(_K)
        if existing is None:
            return False
        if isinstance(existing, COSArray):
            for i in range(existing.size()):
                if _same_kid(existing.get_object(i), cos_before):
                    existing.add_at(i, cos_new)
                    return True
            return False
        if _same_kid(existing, cos_before):
            arr = COSArray()
            arr.add(cos_new)
            arr.add(existing)
            self._dictionary.set_item(_K, arr)
            return True
        return False

    def remove_kid(self, kid: Any) -> bool:
        if kid is None:
            return False
        cos_kid = _to_cos(kid)
        existing = self._dictionary.get_dictionary_object(_K)
        if existing is None:
            return False
        if isinstance(existing, COSArray):
            removed = _remove_array_kid(existing, cos_kid)
            if existing.size() == 1:
                only = existing.get_object(0)
                if only is not None:
                    self._dictionary.set_item(_K, only)
            if removed:
                _clear_parent_if_structure_element(kid)
            return removed
        if _same_kid(existing, cos_kid):
            self._dictionary.remove_item(_K)
            _clear_parent_if_structure_element(kid)
            return True
        return False


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return cast(COSBase, value.get_cos_object())
    if isinstance(value, int) and not isinstance(value, bool):
        return COSInteger.get(value)
    return cast(COSBase, value)


def _remove_array_kid(array: COSArray, cos_kid: COSBase) -> bool:
    if array.remove_object(cos_kid):
        return True
    for i in range(array.size()):
        if _same_kid(array.get_object(i), cos_kid):
            array.remove_at(i)
            return True
    return False


def _same_kid(left: Any, right: Any) -> bool:
    if left is right:
        return True
    if isinstance(left, COSInteger) and isinstance(right, COSInteger):
        return left.value == right.value
    if isinstance(left, COSInteger) and isinstance(right, int) and not isinstance(right, bool):
        return left.value == right
    if isinstance(left, int) and not isinstance(left, bool) and isinstance(right, COSInteger):
        return left == right.value
    if left == right:
        return True
    # Mirror upstream insertBefore / removeKid: also peek through a COSObject
    # indirection so an indirect-reference kid compares equal to the dereferenced
    # COSBase the caller passed in (Java lines 260-264, 340-344).
    from pypdfbox.cos import COSObject

    if isinstance(left, COSObject):
        inner = left.get_object()
        if inner is not None and inner == right:
            return True
    if isinstance(right, COSObject):
        inner = right.get_object()
        if inner is not None and left == inner:
            return True
    return False


def _set_parent_if_structure_element(kid: Any, parent: PDStructureNode) -> None:
    from .pd_structure_element import PDStructureElement

    if isinstance(kid, PDStructureElement):
        kid.set_parent(parent)


def _clear_parent_if_structure_element(kid: Any) -> None:
    from .pd_structure_element import PDStructureElement

    if isinstance(kid, PDStructureElement):
        kid.set_parent(None)


__all__ = ["PDStructureNode"]
