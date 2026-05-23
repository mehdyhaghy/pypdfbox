from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

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

# PDF 32000-1 §14.8.4 categorises standard structure types into four buckets:
# grouping, block-level, inline-level, illustration. The split below mirrors
# that section's tables. Used by ``is_block_level`` / ``is_inline_level`` /
# ``is_grouping_level`` / ``is_illustration_level`` predicates (pypdfbox
# additions — upstream callers compose these manually). All four buckets
# resolve against the *standard* (post-RoleMap) name so non-standard
# elements wired through /RoleMap categorise correctly.
_GROUPING_TYPES: frozenset[str] = frozenset(
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
    }
)

_BLOCK_LEVEL_TYPES: frozenset[str] = frozenset(
    {
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
    }
)

_INLINE_LEVEL_TYPES: frozenset[str] = frozenset(
    {
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
    }
)

_ILLUSTRATION_TYPES: frozenset[str] = frozenset(
    {
        "Figure",
        "Formula",
        "Form",
    }
)

# PDF 32000-1 §14.8.4 standard structure types. Mirrors upstream
# ``StandardStructureTypes`` constants. Kept inline (rather than imported from
# ``taggedpdf``) to avoid a circular import — the taggedpdf package imports
# from logicalstructure already.
_STANDARD_STRUCTURE_TYPES: frozenset[str] = frozenset(
    {
        # Grouping elements
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
        # Block-level structure elements
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
        # Inline-level structure elements
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
        # Illustration elements
        "Figure",
        "Formula",
        "Form",
    }
)

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

    # ---------- /S standard-structure-type constants ----------
    #
    # Mirror upstream ``StandardStructureTypes`` constants (PDF 32000-1
    # §14.8.4). These are exposed as class attributes on
    # :class:`PDStructureElement` so callers can write
    # ``elem.set_structure_type(PDStructureElement.H1)`` without a separate
    # import. The full ``StandardStructureTypes`` shim lives in the
    # ``taggedpdf`` package; keeping the names here avoids the round-trip
    # for the most common call-site pattern.
    #
    # Grouping elements
    DOCUMENT: str = "Document"
    PART: str = "Part"
    ART: str = "Art"
    SECT: str = "Sect"
    DIV: str = "Div"
    BLOCK_QUOTE: str = "BlockQuote"
    CAPTION: str = "Caption"
    TOC: str = "TOC"
    TOCI: str = "TOCI"
    INDEX: str = "Index"
    NON_STRUCT: str = "NonStruct"
    PRIVATE: str = "Private"
    # Block-level structure elements
    P: str = "P"
    H: str = "H"
    H1: str = "H1"
    H2: str = "H2"
    H3: str = "H3"
    H4: str = "H4"
    H5: str = "H5"
    H6: str = "H6"
    L: str = "L"
    LI: str = "LI"
    LBL: str = "Lbl"
    L_BODY: str = "LBody"
    TABLE: str = "Table"
    TR: str = "TR"
    TH: str = "TH"
    TD: str = "TD"
    T_HEAD: str = "THead"
    T_BODY: str = "TBody"
    T_FOOT: str = "TFoot"
    # Inline-level structure elements
    SPAN: str = "Span"
    QUOTE: str = "Quote"
    NOTE: str = "Note"
    REFERENCE: str = "Reference"
    BIB_ENTRY: str = "BibEntry"
    CODE: str = "Code"
    LINK: str = "Link"
    ANNOT: str = "Annot"
    RUBY: str = "Ruby"
    RB: str = "RB"
    RT: str = "RT"
    RP: str = "RP"
    WARICHU: str = "Warichu"
    WT: str = "WT"
    WP: str = "WP"
    # Illustration elements
    FIGURE: str = "Figure"
    FORMULA: str = "Formula"
    FORM: str = "Form"

    def __init__(
        self,
        structure_element: COSDictionary | str | None = None,
        structure_type: str | PDStructureNode | None = None,
    ) -> None:
        """Three upstream-compatible overloads collapsed into one form:

        - ``PDStructureElement()`` — fresh ``/Type StructElem`` dictionary.
        - ``PDStructureElement(COSDictionary)`` — wrap an existing dictionary.
        - ``PDStructureElement(structureType: str, parent: PDStructureNode)``
          — upstream's primary constructor (``PDStructureElement.java``
          line 49). ``parent`` may be ``None``. Sets ``/Type = StructElem``
          and ``/S = structureType`` and links ``/P`` when ``parent`` is
          provided.

        The legacy ``structure_type=...`` keyword form is still accepted
        for callers that bypass positional invocation.
        """
        # Detect the upstream-shape `(structureType: str, parent)` call:
        # the first positional argument is the /S name (a string), the
        # second is the optional parent node. In that case, build a fresh
        # /Type StructElem dictionary then stamp /S and /P.
        if isinstance(structure_element, str):
            parent: PDStructureNode | None = (
                structure_type if isinstance(structure_type, PDStructureNode) else None
            )
            super().__init__(_STRUCT_ELEM_NAME)
            self._element: COSDictionary = self._dictionary
            self.set_structure_type(structure_element)
            if parent is not None:
                self.set_parent(parent)
            return

        super().__init__(structure_element if structure_element is not None else _STRUCT_ELEM_NAME)
        # Backwards-compat alias for callers / subclasses that referenced ``_element``.
        self._element = self._dictionary
        if isinstance(structure_type, str):
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

    def get_parent_node(self) -> PDStructureNode | None:
        """Return ``/P`` dispatched to a typed :class:`PDStructureNode`
        (either :class:`PDStructureTreeRoot` or :class:`PDStructureElement`).
        Mirrors upstream ``PDStructureElement.getParent()``'s typed dispatch
        via ``PDStructureNode.create``. Returns ``None`` when ``/P`` is
        absent or not a dictionary."""
        parent = self._dictionary.get_dictionary_object(_P)
        if not isinstance(parent, COSDictionary):
            return None
        return PDStructureNode.create(parent)

    def get_structure_tree_root(self) -> Any | None:
        """Walk the ``/P`` parent chain to the owning
        :class:`PDStructureTreeRoot`. Returns ``None`` when no root is
        reachable. Mirrors upstream's private
        ``PDStructureElement.getStructureTreeRoot()`` (lifted to a public
        accessor — pypdfbox callers commonly need root-level role-map /
        class-map traversal from a leaf element)."""
        from .pd_structure_tree_root import PDStructureTreeRoot

        node: COSDictionary | None = self._dictionary
        seen: set[int] = set()
        for _ in range(_MAX_ROLE_MAP_DEPTH):
            if node is None or id(node) in seen:
                return None
            seen.add(id(node))
            if node.get_name(_TYPE) == _STRUCT_TREE_ROOT_NAME:
                return PDStructureTreeRoot(node)
            parent = node.get_dictionary_object(_P)
            node = parent if isinstance(parent, COSDictionary) else None
        return None

    # ---------- /ID ----------

    def get_id(self) -> str | None:
        return self._dictionary.get_string(_ID)

    def set_id(self, id_: str | None) -> None:
        self._dictionary.set_string(_ID, id_)

    def get_element_identifier(self) -> str | None:
        """Return the element identifier (``/ID``).

        Upstream-spelled accessor for ``/ID`` (mirrors PDFBox
        ``getElementIdentifier``); :meth:`get_id` is the shorter pypdfbox
        spelling and remains an alias for the same slot.
        """
        return self._dictionary.get_string(_ID)

    def set_element_identifier(self, identifier: str | None) -> None:
        """Set the element identifier (``/ID``).

        Upstream-spelled mutator (mirrors PDFBox ``setElementIdentifier``).
        """
        self._dictionary.set_string(_ID, identifier)

    # ---------- /R revision number ----------

    def get_revision_number(self) -> int:
        return self._dictionary.get_int(_R, 0)

    def set_revision_number(self, revision_number: int) -> None:
        if revision_number < 0:
            raise ValueError("The revision number shall be > -1")
        self._dictionary.set_int(_R, revision_number)

    def increment_revision_number(self) -> None:
        """Bump ``/R`` by one. Mirrors upstream ``incrementRevisionNumber``."""
        self.set_revision_number(self.get_revision_number() + 1)

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

    # ---------- presence predicates (pypdfbox additions) ----------
    #
    # Upstream PDFBox callers write ``elem.getElementIdentifier() != null``
    # at every call site. These short ``has_*`` predicates mirror common
    # PDF tagging-tooling spelling and avoid the ``is None`` boilerplate.

    def has_id(self) -> bool:
        """Return ``True`` when ``/ID`` is present and non-empty."""
        value = self._dictionary.get_string(_ID)
        return value is not None and value != ""

    def has_page(self) -> bool:
        """Return ``True`` when ``/Pg`` is present and is a dictionary."""
        return isinstance(self._dictionary.get_dictionary_object(_PG), COSDictionary)

    def has_title(self) -> bool:
        """Return ``True`` when ``/T`` is present and non-empty."""
        value = self._dictionary.get_string(_T)
        return value is not None and value != ""

    def has_language(self) -> bool:
        """Return ``True`` when ``/Lang`` is present and non-empty."""
        value = self._dictionary.get_string(_LANG)
        return value is not None and value != ""

    def has_alternate_description(self) -> bool:
        """Return ``True`` when ``/Alt`` is present and non-empty."""
        value = self._dictionary.get_string(_ALT)
        return value is not None and value != ""

    def has_expanded_form(self) -> bool:
        """Return ``True`` when ``/E`` is present and non-empty."""
        value = self._dictionary.get_string(_E)
        return value is not None and value != ""

    def has_actual_text(self) -> bool:
        """Return ``True`` when ``/ActualText`` is present and non-empty."""
        value = self._dictionary.get_string(_ACTUAL_TEXT)
        return value is not None and value != ""

    def has_structure_type(self) -> bool:
        """Return ``True`` when ``/S`` is present (any name)."""
        return self._dictionary.get_name(_S) is not None

    def has_parent(self) -> bool:
        """Return ``True`` when ``/P`` is present and is a dictionary."""
        return isinstance(self._dictionary.get_dictionary_object(_P), COSDictionary)

    def is_root_attached(self) -> bool:
        """Return ``True`` when this element's ``/P`` chain reaches a
        :class:`PDStructureTreeRoot`.

        pypdfbox addition: upstream PDFBox exposes the root walk only as
        the private ``getStructureTreeRoot`` helper. Callers commonly want
        to know whether the element is *attached* to a tree at all (e.g.
        before queueing it for tagged-PDF validation); this predicate is
        ``self.get_structure_tree_root() is not None``.
        """
        return self.get_structure_tree_root() is not None

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
        yield from self.get_kids()

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

    def get_attribute_objects(self) -> list[PDAttributeObject]:
        """Return the ``/A`` entries as a flat list of typed
        :class:`PDAttributeObject` (every owner subclass dispatched through
        :meth:`PDAttributeObject.create`).

        pypdfbox addition: upstream callers reach for ``getAttributes()``
        and unpack the :class:`Revisions` wrapper. The flat-list shape is a
        common convenience and lets ``PDStructureElement`` callers compose
        with ``/ClassMap`` lookups without going through the revision API.
        """
        from .pd_attribute_object import PDAttributeObject

        out: list[PDAttributeObject] = []
        a = self._dictionary.get_dictionary_object(_A)
        if isinstance(a, COSDictionary):
            out.append(PDAttributeObject.create(a))
            return out
        if isinstance(a, COSArray):
            for i in range(a.size()):
                item = a.get_object(i)
                if isinstance(item, COSDictionary):
                    out.append(PDAttributeObject.create(item))
        return out

    def has_attribute_owner(self, owner: str) -> bool:
        """Return ``True`` when at least one ``/A`` entry's ``/O`` owner
        equals ``owner``. Convenience wrapper around
        :meth:`get_attribute_objects`."""
        if owner is None:
            return False
        return any(attr.get_owner() == owner for attr in self.get_attribute_objects())

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
            revs.add_object(c, 0)
        return revs

    def set_class_names(self, class_names: Revisions[COSName] | None) -> None:
        if class_names is None:
            self._dictionary.remove_item(_C)
            return
        if class_names.size() == 1 and class_names.get_revision_number_at(0) == 0:
            class_name = class_names.get_object_at(0)
            if isinstance(class_name, COSName):
                self._dictionary.set_item(_C, class_name)
            else:
                self._dictionary.set_name(_C, str(class_name))
            return
        self._dictionary.set_item(_C, class_names.to_cos_array())

    def get_class_names_as_strings(self) -> list[str]:
        """Return the ``/C`` class-name entries as plain Python ``str``.

        Mirrors upstream's ``Revisions<String>``-typed ``getClassNames``;
        this convenience helper is the pypdfbox-typed shape (the underlying
        Revisions store wraps :class:`COSName` for round-trip fidelity).

        Single-name and array shapes both decode the same way; non-name
        entries (e.g. integer revision markers) are skipped.
        """
        revs = self.get_class_names()
        out: list[str] = []
        for i in range(revs.size()):
            entry = revs.get_object_at(i)
            if isinstance(entry, COSName):
                out.append(entry.get_name())
            elif isinstance(entry, str):
                out.append(entry)
        return out

    def has_class(self, class_name: str | None) -> bool:
        """Return ``True`` when ``class_name`` is one of this element's
        ``/C`` class names. Mirrors PDF tagging-tooling convention; not a
        direct upstream method but a thin wrapper over :meth:`Revisions.contains`
        that callers commonly write inline."""
        if class_name is None:
            return False
        return class_name in self.get_class_names_as_strings()

    # ---------- /S standard-structure-type alias ----------

    def get_standard_structure_type_name(self) -> str | None:
        """Alias for :meth:`get_standard_structure_type`. Some upstream
        documentation refers to the resolved name as the "standard structure
        type"; pypdfbox keeps both spellings additive."""
        return self.get_standard_structure_type()

    def set_standard_structure_type(self, structure_type: str) -> None:
        """Mirror upstream ``setStandardStructureType``.

        Writes ``structure_type`` to ``/S``. Upstream does not enforce a
        whitelist either — the standard-structure-types check is exposed
        separately via :meth:`is_standard_structure_type`.
        """
        if structure_type is None:
            raise ValueError("standard structure type shall not be null")
        self.set_structure_type(structure_type)

    @staticmethod
    def is_standard_structure_type(structure_type: str | None) -> bool:
        """Return ``True`` when ``structure_type`` is one of the PDF 32000-1
        §14.8.4 standard structure types.

        pypdfbox addition: upstream PDFBox exposes the type list as a public
        ``StandardStructureTypes.types`` constant; the membership check is a
        common predicate at call sites, so we expose it directly. ``None``
        returns ``False`` (matches upstream's ``Collections.contains(null)``
        on a non-null-tolerant ``ArrayList``).
        """
        if structure_type is None:
            return False
        return structure_type in _STANDARD_STRUCTURE_TYPES

    def is_resolved_structure_type_standard(self) -> bool:
        """Return ``True`` when this element's *resolved* structure type
        (after walking the parent chain's ``/RoleMap``) is a PDF 32000-1
        standard structure type.

        pypdfbox addition: the resolved-type check is what callers actually
        want when validating a tagged PDF, but it requires composing
        :meth:`get_standard_structure_type` with
        :meth:`is_standard_structure_type` on every call site. Inlining the
        composition keeps the predicate one method call away.
        """
        return self.is_standard_structure_type(self.get_standard_structure_type())

    def is_grouping_level(self) -> bool:
        """Return ``True`` when this element resolves to a standard
        grouping structure type (PDF 32000-1 §14.8.4)."""
        return self.get_standard_structure_type() in _GROUPING_TYPES

    def is_block_level(self) -> bool:
        """Return ``True`` when this element resolves to a standard
        block-level structure type (PDF 32000-1 §14.8.4)."""
        return self.get_standard_structure_type() in _BLOCK_LEVEL_TYPES

    def is_inline_level(self) -> bool:
        """Return ``True`` when this element resolves to a standard
        inline-level structure type (PDF 32000-1 §14.8.4)."""
        return self.get_standard_structure_type() in _INLINE_LEVEL_TYPES

    def is_illustration_level(self) -> bool:
        """Return ``True`` when this element resolves to a standard
        illustration structure type (PDF 32000-1 §14.8.4)."""
        return self.get_standard_structure_type() in _ILLUSTRATION_TYPES

    # ---------- typed /K append overloads ----------
    #
    # Upstream PDFBox exposes overloads for ``appendKid`` keyed on the kid
    # kind: ``PDStructureElement`` (sets the kid's ``/P`` parent pointer),
    # ``PDMarkedContentReference``, ``PDObjectReference``, and ``int`` (raw
    # MCID). The base ``append_kid`` accepts any kid; these typed wrappers
    # add the parent-pointer plumbing that upstream performs as a side
    # effect. Per PRD §3 we keep both inheritance and behavior intact.

    def append_kid_element(self, structure_element: PDStructureElement) -> None:
        """Append a ``PDStructureElement`` kid and set its ``/P`` parent
        pointer to this element.

        Mirrors upstream ``appendKid(PDStructureElement)``."""
        if structure_element is None:
            return
        self.append_kid(structure_element)
        structure_element.set_parent(self)

    def append_kid_marked_content(
        self, marked_content_reference: Any
    ) -> None:
        """Append a ``PDMarkedContentReference`` kid.

        Mirrors upstream ``appendKid(PDMarkedContentReference)``."""
        if marked_content_reference is None:
            return
        self.append_kid(marked_content_reference)

    def append_kid_object_reference(self, object_reference: Any) -> None:
        """Append a ``PDObjectReference`` kid.

        Mirrors upstream ``appendKid(PDObjectReference)``."""
        if object_reference is None:
            return
        self.append_kid(object_reference)

    def append_kid_mcid(self, mcid: int) -> None:
        """Append a marked-content identifier (raw integer ``/K`` entry).

        Mirrors upstream ``appendKid(int)``. Upstream rejects negative
        values; we mirror that with ``ValueError``.
        """
        if mcid < 0:
            raise ValueError("MCID is negative")
        self.append_kid(mcid)

    def append_kid_marked_content_object(self, marked_content: Any) -> None:
        """Append the ``MCID`` of a :class:`PDMarkedContent` as a kid.

        Mirrors upstream ``appendKid(PDMarkedContent)``: pulls the
        marked-content sequence's ``MCID`` and appends it as an integer
        ``/K`` entry. ``None`` is a silent no-op (matches upstream's
        null-guard); a missing or negative ``MCID`` raises
        ``ValueError`` (upstream throws ``IllegalArgumentException``).
        """
        if marked_content is None:
            return
        mcid = marked_content.get_mcid()
        if mcid < 0:
            raise ValueError("MCID is negative or doesn't exist")
        self.append_kid(mcid)

    # ---------- typed /K remove + insert overloads ----------

    def remove_kid_element(self, structure_element: PDStructureElement) -> bool:
        """Remove a ``PDStructureElement`` kid and clear its ``/P`` parent
        pointer when the removal succeeds.

        Mirrors upstream ``removeKid(PDStructureElement)`` (PDStructureNode
        ancestor): the base ``remove_kid`` only updates ``/K``; this
        overload additionally clears the kid's parent back-pointer when
        the kid was actually present, matching upstream's contract.
        Returns ``True`` when the kid was removed, ``False`` otherwise.
        """
        if structure_element is None:
            return False
        removed = self.remove_kid(structure_element)
        if removed:
            structure_element.set_parent(None)
        return removed

    def insert_before_element(
        self, new_kid: PDStructureElement, before_kid: Any
    ) -> bool:
        """Insert a ``PDStructureElement`` before ``before_kid`` in ``/K``.

        Mirrors upstream ``insertBefore(PDStructureElement, Object)`` —
        a thin typed alias over :meth:`PDStructureNode.insert_before` that
        documents the upstream overload's contract.
        """
        if new_kid is None or before_kid is None:
            return False
        return self.insert_before(new_kid, before_kid)

    def insert_before_mcid(self, mcid: int, before_kid: Any) -> bool:
        """Insert a marked-content identifier (integer) before ``before_kid``.

        Mirrors upstream ``insertBefore(COSInteger, Object)``: a typed
        alias for inserting a raw integer MCID into ``/K``. Returns
        ``False`` when ``before_kid`` is missing (no insert performed) or
        either argument is ``None``.
        """
        if before_kid is None:
            return False
        return self.insert_before(mcid, before_kid)

    # ---------- typed /K remove overloads (mcr / objr / mcid) ----------

    def remove_kid_mcid(self, mcid: int) -> bool:
        """Remove a marked-content identifier from ``/K``.

        Mirrors upstream ``removeKid(COSInteger)``: a typed alias over
        :meth:`PDStructureNode.remove_kid`. Returns ``True`` when the
        integer was present and removed.
        """
        return self.remove_kid(mcid)

    def remove_kid_marked_content(self, marked_content_reference: Any) -> bool:
        """Remove a ``PDMarkedContentReference`` kid from ``/K``.

        Mirrors upstream ``removeKid(PDMarkedContentReference)`` — a typed
        alias over :meth:`PDStructureNode.remove_kid`. ``None`` is a
        silent no-op returning ``False``.
        """
        if marked_content_reference is None:
            return False
        return self.remove_kid(marked_content_reference)

    def remove_kid_object_reference(self, object_reference: Any) -> bool:
        """Remove a ``PDObjectReference`` kid from ``/K``.

        Mirrors upstream ``removeKid(PDObjectReference)`` — a typed alias
        over :meth:`PDStructureNode.remove_kid`. ``None`` is a silent
        no-op returning ``False``.
        """
        if object_reference is None:
            return False
        return self.remove_kid(object_reference)

    # ---------- /A attribute object maintenance ----------

    def add_attribute(self, attribute_object: Any) -> None:
        """Append ``attribute_object`` to ``/A`` at the current revision and
        wire its structure-element back-pointer.

        Mirrors upstream ``addAttribute(PDAttributeObject)``: the new
        attribute object's revision is the structure element's current
        ``/R`` value (defaulting to ``0``); the back-pointer is set so
        :meth:`PDAttributeObject.notify_change` can locate this element.
        """
        if attribute_object is None:
            return
        revision = self.get_revision_number()
        attribute_object.set_structure_element(self)
        revs: Revisions[PDAttributeObject] = self.get_attributes()
        revs.add_object(attribute_object, revision)
        # ``Revisions`` shares the underlying COSArray on the ``/A`` slot
        # only when ``/A`` was already an array; for the bare-dict and empty
        # cases we have to write the array back.
        existing = self._dictionary.get_dictionary_object(_A)
        if not isinstance(existing, COSArray):
            self._dictionary.set_item(_A, revs.to_cos_array())

    def remove_attribute(self, attribute_object: Any) -> None:
        """Remove ``attribute_object`` from ``/A`` and clear its
        structure-element back-pointer.

        Mirrors upstream ``removeAttribute(PDAttributeObject)``. Silently
        returns when the attribute isn't present.
        """
        if attribute_object is None:
            return
        revs: Revisions[PDAttributeObject] = self.get_attributes()
        idx = revs.index_of(attribute_object)
        if idx == -1:
            return
        revs.remove_at(idx)
        if revs.is_empty():
            self._dictionary.remove_item(_A)
        else:
            # Always rewrite the slot — the underlying array may have shrunk
            # below the bare-dict heuristic upstream uses.
            self._dictionary.set_item(_A, revs.to_cos_array())
        if attribute_object.get_structure_element() is self:
            attribute_object.set_structure_element(None)

    def attribute_changed(self, attribute_object: Any) -> None:
        """Mark ``attribute_object`` as changed at the current revision.

        Mirrors upstream ``attributeChanged(PDAttributeObject)``: bumps the
        attribute object's revision to match the structure element's
        current ``/R``. Silently returns when the attribute isn't present
        in ``/A``.
        """
        if attribute_object is None:
            return
        revision = self.get_revision_number()
        revs: Revisions[PDAttributeObject] = self.get_attributes()
        idx = revs.index_of(attribute_object)
        if idx == -1:
            return
        revs.set_revision_number_at(idx, revision)
        existing = self._dictionary.get_dictionary_object(_A)
        if not isinstance(existing, COSArray):
            self._dictionary.set_item(_A, revs.to_cos_array())

    # ---------- /C class-name maintenance ----------

    def add_class_name(self, class_name: str | None) -> None:
        """Append ``class_name`` to ``/C`` at the current revision.

        Mirrors upstream ``addClassName(String)``. ``None`` is a silent
        no-op (matches upstream's null-guard).
        """
        if class_name is None:
            return
        revision = self.get_revision_number()
        revs: Revisions[COSName] = self.get_class_names()
        revs.add_object(COSName.get_pdf_name(class_name), revision)
        existing = self._dictionary.get_dictionary_object(_C)
        if not isinstance(existing, COSArray):
            self._dictionary.set_item(_C, revs.to_cos_array())

    def remove_class_name(self, class_name: str | None) -> None:
        """Remove ``class_name`` from ``/C``.

        Mirrors upstream ``removeClassName(String)``. Silently returns
        when the name isn't present.
        """
        if class_name is None:
            return
        target = COSName.get_pdf_name(class_name)
        revs: Revisions[COSName] = self.get_class_names()
        idx = revs.index_of(target)
        if idx == -1:
            return
        revs.remove_at(idx)
        if revs.is_empty():
            self._dictionary.remove_item(_C)
        else:
            self._dictionary.set_item(_C, revs.to_cos_array())

    def class_name_changed(self, class_name: str | None) -> None:
        """Mark ``class_name`` as changed at the current revision.

        Mirrors upstream ``classNameChanged(String)``: bumps the class
        name's revision to match the structure element's current ``/R``.
        Silently returns when the name isn't present in ``/C``.
        """
        if class_name is None:
            return
        target = COSName.get_pdf_name(class_name)
        revision = self.get_revision_number()
        revs: Revisions[COSName] = self.get_class_names()
        idx = revs.index_of(target)
        if idx == -1:
            return
        revs.set_revision_number_at(idx, revision)
        existing = self._dictionary.get_dictionary_object(_C)
        if not isinstance(existing, COSArray):
            self._dictionary.set_item(_C, revs.to_cos_array())

    # ---------- marked-content reference enumeration ----------

    def iter_object_references(self) -> Iterator[Any]:
        """Yield direct ``/K`` kids that are :class:`PDObjectReference`
        (``/Type /OBJR``) typed wrappers. Upstream's ``getKids`` returns a
        mixed list; this is a convenience filter for callers that only
        care about annotation/XObject back-pointers."""
        from .pd_object_reference import PDObjectReference

        for kid in self.get_kids():
            if isinstance(kid, PDObjectReference):
                yield kid

    def iter_kid_elements(self) -> Iterator[PDStructureElement]:
        """Yield direct ``/K`` kids that are :class:`PDStructureElement`.

        pypdfbox addition: complements :meth:`iter_object_references` and
        :meth:`get_marked_content_references` so callers can filter the
        mixed ``/K`` list by kind without writing the ``isinstance`` check
        themselves. Non-recursive — use :meth:`iter_descendants` for the
        full sub-tree.
        """
        for kid in self.get_kids():
            if isinstance(kid, PDStructureElement):
                yield kid

    # ---------- /K convenience helpers (pypdfbox additions) ----------

    def count_kids(self) -> int:
        """Return the number of direct ``/K`` kids.

        pypdfbox addition: thin wrapper over ``len(get_kids())`` for callers
        that prefer an accessor over the list-builder. Mirrors common Java
        ``size()`` idioms without forcing the kid list to be materialised
        twice on the caller side.
        """
        return len(self.get_kids())

    def clear_kids(self) -> None:
        """Remove the ``/K`` entry entirely.

        pypdfbox addition: ``set_kids(None)`` is the upstream-aligned way
        to drop the slot, but calling it ``clear_kids`` reads better at
        call sites that are unsetting (rather than replacing) the kid
        list. Purely additive — delegates to :meth:`set_kids`.
        """
        self.set_kids(None)

    def get_role_map(self) -> dict[str, str]:
        """Return the structure tree root's ``/RoleMap`` reachable from
        this element as a ``{name: name}`` dict.

        Mirrors upstream ``PDStructureElement.getRoleMap()`` (private in
        Java; lifted to public here because pypdfbox callers commonly
        want to inspect the role map without re-walking the parent
        chain themselves). Returns an empty dict when no
        ``StructTreeRoot`` ancestor is reachable or it has no
        ``/RoleMap``.
        """
        return self._find_role_map()

    def get_marked_content_references(self) -> list[Any]:
        """Return the direct marked-content references of this element.

        Mirrors upstream ``getMarkedContentReferences()``: collects every
        ``/K`` kid that is either a raw integer MCID or a typed
        :class:`PDMarkedContentReference`. Structure-element kids and
        object-reference kids are skipped (callers wanting a recursive
        walk should compose with :meth:`iter_descendants`).
        """
        from .pd_marked_content_reference import PDMarkedContentReference

        out: list[Any] = []
        for kid in self.get_kids():
            if (
                isinstance(kid, int)
                and not isinstance(kid, bool)
                or isinstance(kid, PDMarkedContentReference)
            ):
                out.append(kid)
        return out


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
