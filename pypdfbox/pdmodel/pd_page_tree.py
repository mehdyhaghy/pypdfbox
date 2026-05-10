from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
)

from .pd_page import PDPage, _unwrap_page_dict

if TYPE_CHECKING:
    from .pd_document import PDDocument


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PAGE: COSName = COSName.PAGE  # type: ignore[attr-defined]
_PAGES: COSName = COSName.PAGES  # type: ignore[attr-defined]
_KIDS: COSName = COSName.KIDS  # type: ignore[attr-defined]
_COUNT: COSName = COSName.COUNT  # type: ignore[attr-defined]
_PARENT: COSName = COSName.PARENT  # type: ignore[attr-defined]
# Legacy single-letter alias for /Parent — upstream PDFBox falls back to
# ``COSName.P`` whenever ``/Parent`` is absent (see every
# ``getCOSDictionary(COSName.PARENT, COSName.P)`` call in PDPageTree.java).
_P: COSName = COSName.get_pdf_name("P")


def _resolve_parent(node: COSDictionary) -> COSDictionary | None:
    """Return ``node``'s ancestor following the upstream
    ``/Parent`` → ``/P`` fallback semantics."""
    parent = node.get_dictionary_object(_PARENT)
    if isinstance(parent, COSDictionary):
        return parent
    parent = node.get_dictionary_object(_P)
    return parent if isinstance(parent, COSDictionary) else None


def _is_page_dict(node: COSDictionary) -> bool:
    """``/Type /Page`` leaf — but tolerate dicts that lack ``/Type``
    altogether and just look like a page (have ``/Contents`` / ``/MediaBox``
    but no ``/Kids``). Matches upstream's lenient detection."""
    type_name = node.get_dictionary_object(_TYPE)
    if isinstance(type_name, COSName):
        if type_name == _PAGE:
            return True
        if type_name == _PAGES:
            return False
    # No /Type — fall back to /Kids presence.
    return not node.contains_key(_KIDS)


def _is_page_tree_node(node: COSDictionary | None) -> bool:
    """Return True when ``node`` is a page-tree intermediate (``/Type
    /Pages`` *or* a node carrying a ``/Kids`` array). Mirrors upstream's
    private ``isPageTreeNode`` helper — some files (PDFBOX-2250-229205.pdf)
    omit ``/Type /Pages`` and rely on the ``/Kids`` presence heuristic."""
    if node is None:
        return False
    type_name = node.get_dictionary_object(_TYPE)
    if isinstance(type_name, COSName) and type_name == _PAGES:
        return True
    return node.contains_key(_KIDS)


def _kids_array(node: COSDictionary) -> COSArray | None:
    kids = node.get_dictionary_object(_KIDS)
    return kids if isinstance(kids, COSArray) else None


class _SearchContext:
    """State holder threaded through :meth:`PDPageTree.find_page`.

    Mirrors upstream's private ``SearchContext`` inner class (PDPageTree.java
    L429-L445): tracks the running 0-based page index and flips ``found``
    when the dictionary identity matches the page being searched for.
    """

    __slots__ = ("searched", "index", "found")

    def __init__(self, page: PDPage | COSDictionary) -> None:
        self.searched: COSDictionary = _unwrap_page_dict(page)
        self.index: int = -1
        self.found: bool = False

    def visit_page(self, current: COSDictionary) -> None:
        self.index += 1
        if self.searched is current:
            self.found = True


class PDPageTree:
    """
    Iterable view of the document's page tree rooted at ``/Pages``.
    Mirrors ``org.apache.pdfbox.pdmodel.PDPageTree``.

    Supports document-order iteration, count/index access, membership
    predicates, page insertion/removal, collection clearing, Java-style
    aliases, and helpers for the malformed page-tree shapes PDFBox accepts
    in the wild.
    """

    def __init__(
        self,
        root: COSDictionary | None = None,
        document: PDDocument | None = None,
    ) -> None:
        if root is None:
            root = COSDictionary()
            root.set_item(_TYPE, _PAGES)
            root.set_item(_KIDS, COSArray())
            root.set_int(_COUNT, 0)
        else:
            # Repair bad PDFs which contain a Page dict directly as the page
            # tree root instead of a /Pages intermediate node (PDFBOX-3154).
            # Wrap the lone page in a synthetic /Pages node with a single-kid
            # /Kids array and /Count 1 so iteration and indexing still work.
            type_name = root.get_dictionary_object(_TYPE)
            if isinstance(type_name, COSName) and type_name == _PAGE:
                kids = COSArray()
                kids.add(root)
                wrapper = COSDictionary()
                wrapper.set_item(_TYPE, _PAGES)
                wrapper.set_item(_KIDS, kids)
                wrapper.set_int(_COUNT, 1)
                root.set_item(_PARENT, wrapper)
                root = wrapper
        self._root = root
        self._document = document

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._root

    def get_root(self) -> COSDictionary:
        """Return the top ``/Pages`` node backing this tree.

        Mirrors upstream ``PDPageTree.getCOSObject()`` — exposed as
        ``get_root`` for callers that want an explicit accessor instead
        of the generic COS-object getter.
        """
        return self._root

    def get_document(self) -> PDDocument | None:
        """Return the owning ``PDDocument`` if this tree was constructed
        with one, else ``None``. Mirrors upstream ``getDocument()``."""
        return self._document

    # ---------- iteration ----------

    def __iter__(self) -> Iterator[PDPage]:
        yield from self._walk(self._root, set())

    def iterator(self) -> Iterator[PDPage]:
        """Java-style alias for ``__iter__``. Mirrors upstream
        ``PDPageTree.iterator()``."""
        return iter(self)

    def _walk(
        self, node: COSDictionary, seen: set[int]
    ) -> Iterator[PDPage]:
        """Depth-first traversal yielding leaf ``/Type /Page`` nodes."""
        if id(node) in seen:
            return
        seen.add(id(node))

        if _is_page_dict(node):
            yield PDPage(node)
            return

        for kid in self.get_kids(node):
            yield from self._walk(kid, seen)

    # ---------- Python protocols ----------

    def __len__(self) -> int:
        # Prefer the explicit /Count when present and sane, fall back to
        # walking the tree (matches upstream's tolerance for missing /Count
        # on synthesised page trees).
        count = self._root.get_dictionary_object(_COUNT)
        if isinstance(count, COSInteger) and count.value >= 0:
            walked = sum(1 for _ in self)
            if walked == count.value:
                return count.value
            # /Count is wrong — fall through to the actual walk count.
            return walked
        return sum(1 for _ in self)

    def get_count(self) -> int:
        """Return the ``/Count`` entry of the root ``/Pages`` dict.

        Mirrors upstream ``PDPageTree.getCount()`` literally —
        ``root.getInt(COSName.COUNT, 0)`` — so this is O(1) and reports the
        stored count even when it disagrees with a tree walk. Use
        ``len(self)`` (the Python protocol) for a walk-validated count."""
        count = self._root.get_dictionary_object(_COUNT)
        if isinstance(count, COSInteger):
            return count.value
        return 0

    def __getitem__(self, index: int) -> PDPage:
        if not isinstance(index, int):
            raise TypeError(f"PDPageTree indices must be int, got {type(index).__name__}")
        n = len(self)
        if index < 0:
            index += n
        if index < 0 or index >= n:
            raise IndexError(f"page index out of range: {index}")
        for i, page in enumerate(self):
            if i == index:
                self._sanitize_type(page.get_cos_object())
                return page
        raise IndexError(f"page index out of range: {index}")  # pragma: no cover

    def __contains__(self, page: object) -> bool:
        """Return ``True`` when ``page`` (a :class:`PDPage` or its backing
        ``COSDictionary``) is reachable from this tree's root.

        Pypdfbox extension — upstream Java's ``PDPageTree`` does not expose a
        membership predicate, but ``page in tree`` is the natural Pythonic
        spelling of ``indexOf(page) != -1`` and avoids re-walking the tree
        twice when the caller only cares whether the page is present.
        """
        if not isinstance(page, (PDPage, COSDictionary)):
            return False
        return self.index_of(page) >= 0

    def __bool__(self) -> bool:
        """Truthiness mirrors ``len(self) > 0`` — a tree with zero pages is
        falsy. Pypdfbox extension; upstream relies on Java's identity-based
        ``Object`` truthiness which is irrelevant in Python."""
        return len(self) > 0

    # ---------- predicates ----------

    def is_empty(self) -> bool:
        """Return ``True`` when this tree contains no pages.

        Pypdfbox extension that mirrors the ``Collection.isEmpty()`` idiom
        familiar from Java; equivalent to ``len(self) == 0`` but reads
        nicer at call sites that already treat the tree as a collection.
        """
        return len(self) == 0

    def has_pages(self) -> bool:
        """Return ``True`` when this tree contains at least one page."""
        return not self.is_empty()

    def has_page(self, page: PDPage | COSDictionary) -> bool:
        """Return ``True`` when ``page`` is a member of this page tree.

        Predicate alias for ``index_of(page) >= 0``; complements the
        ``__contains__`` protocol with a name-based call site for callers
        porting Java-style ``contains``/``hasPage`` checks. Matches the
        ``has_*`` predicate pattern already used across pypdfbox
        (e.g. ``PDTextField.has_value``, ``PDVariableText.has_q``).
        """
        return self.index_of(page) >= 0

    @staticmethod
    def sanitize_type(dictionary: COSDictionary) -> None:
        """Normalize the ``/Type`` entry of a leaf page dictionary.

        Mirrors upstream ``PDPageTree.sanitizeType`` (PDPageTree.java
        L284-L296):
        - missing ``/Type`` is set to ``/Page`` (defensive against
          malformed PDFs that omit the entry on otherwise-valid pages);
        - malformed non-name ``/Type`` values are also replaced with
          ``/Page`` because upstream reads the value with ``getCOSName``;
        - any ``/Type`` other than ``/Page`` raises ``ValueError`` (upstream
          throws ``IllegalStateException``).

        Upstream keeps this private; pypdfbox publicises it because the
        ``/Type`` repair is useful to callers that synthesise pages from
        raw COS dictionaries before handing them to the tree.
        """
        type_name = dictionary.get_dictionary_object(_TYPE)
        if type_name is None or not isinstance(type_name, COSName):
            dictionary.set_item(_TYPE, _PAGE)
            return
        if type_name != _PAGE:
            raise ValueError(f"Expected 'Page' but found {type_name}")

    # Legacy private alias retained for backwards compatibility with the
    # internal call sites that predate the public ``sanitize_type``.
    _sanitize_type = sanitize_type

    def get(self, index: int) -> PDPage:
        """0-based accessor — matches upstream's ``get(int)``."""
        return self[index]

    def index_of(self, page: PDPage | COSDictionary) -> int:
        """Return the 0-based document-order index of ``page``.

        Mirrors upstream ``indexOf(PDPage)``: returns ``-1`` when the page
        is not part of this page tree. Comparison is by the underlying
        ``COSDictionary`` identity so callers can pass a fresh ``PDPage``
        wrapper around an existing page dictionary. Delegates to
        :meth:`find_page` to reuse the upstream depth-first search.
        """
        page_dict = _unwrap_page_dict(page)
        context = _SearchContext(page_dict)
        if self.find_page(context, self._root):
            return context.index
        return -1

    @classmethod
    def find_page(
        cls, context: _SearchContext, node: COSDictionary
    ) -> bool:
        """Depth-first search the kid tree rooted at ``node`` for the
        page recorded on ``context.searched``.

        Mirrors upstream's private ``findPage`` (PDPageTree.java L409-L427):
        recurses into intermediate ``/Pages`` children and increments the
        context index on each leaf page until ``context.found`` flips true.
        Returns ``context.found`` so callers can distinguish "ran out of
        kids" from "located the page". Pypdfbox publicises this helper so
        callers porting upstream's ``indexOf`` plumbing have a named entry
        point alongside :class:`_SearchContext`.
        """
        for kid in cls.get_kids(node):
            if context.found:
                break
            if _is_page_tree_node(kid):
                cls.find_page(context, kid)
            else:
                context.visit_page(kid)
        return context.found

    def index_of_page(self, page: PDPage | COSDictionary) -> int:
        """Alias for ``index_of`` for callers porting page-index helpers."""
        return self.index_of(page)

    # ---------- mutation ----------

    def add(self, page: PDPage | COSDictionary) -> None:
        """Append ``page`` to the root's ``/Kids`` array and bump every
        ancestor's ``/Count``. Upstream walks parents recursively; for our
        single-rooted tree the only ancestor is ``self._root``."""
        page_dict = _unwrap_page_dict(page)
        page_dict.set_item(_PARENT, self._root)
        kids = self._get_or_create_kids()
        kids.add(page_dict)
        self._increment_count(self._root, +1)

    def remove(self, page: PDPage | COSDictionary) -> bool:
        """Remove ``page`` from its parent's ``/Kids`` and decrement
        ``/Count`` up the chain. Returns True if removal occurred."""
        page_dict = _unwrap_page_dict(page)
        parent = _resolve_parent(page_dict)
        if parent is None:
            parent = self._root
        kids = _kids_array(parent)
        if kids is None:
            return False
        index = self._index_of_kid(kids, page_dict)
        if index < 0:
            return False
        kids.remove_at(index)
        self._decrement_count_chain(parent, 1)
        return True

    def remove_at(self, index: int) -> PDPage:
        """Remove the page at zero-based ``index`` and return it.

        Mirrors upstream ``PDPageTree.remove(int)`` (renamed because
        Python can't overload the single-arg ``remove`` already bound to
        the by-page variant). Raises :class:`IndexError` when ``index``
        is out of range, which matches Python list semantics; upstream
        throws ``IndexOutOfBoundsException`` for the same condition.
        """
        page = self[index]
        # ``self.remove`` takes care of /Kids splice + /Count decrement
        # along the parent chain.
        self.remove(page)
        return page

    def clear(self) -> None:
        """Remove all pages from the root node and reset its ``/Count``.

        Collection-style pypdfbox helper. If ``/Kids`` is missing or
        malformed, the root is repaired to carry an empty ``COSArray``.
        """
        kids = _kids_array(self._root)
        if kids is None:
            self._root.set_item(_KIDS, COSArray())
        else:
            kids.clear()
        self._root.set_int(_COUNT, 0)

    def insert_before(
        self, new_page: PDPage | COSDictionary, target: PDPage | COSDictionary
    ) -> None:
        """Insert ``new_page`` directly before ``target`` in ``target``'s
        parent's ``/Kids``."""
        target_dict = _unwrap_page_dict(target)
        new_dict = _unwrap_page_dict(new_page)
        parent = _resolve_parent(target_dict)
        if parent is None:
            parent = self._root
        kids = _kids_array(parent)
        if kids is None:
            raise ValueError("target page has no /Kids parent array")
        index = self._index_of_kid(kids, target_dict)
        if index < 0:
            raise ValueError("target page is not in its declared parent's /Kids")
        kids.add_at(index, new_dict)
        new_dict.set_item(_PARENT, parent)
        self.increase_parents(parent)

    def insert_after(
        self, new_page: PDPage | COSDictionary, target: PDPage | COSDictionary
    ) -> None:
        target_dict = _unwrap_page_dict(target)
        new_dict = _unwrap_page_dict(new_page)
        parent = _resolve_parent(target_dict)
        if parent is None:
            parent = self._root
        kids = _kids_array(parent)
        if kids is None:
            raise ValueError("target page has no /Kids parent array")
        index = self._index_of_kid(kids, target_dict)
        if index < 0:
            raise ValueError("target page is not in its declared parent's /Kids")
        kids.add_at(index + 1, new_dict)
        new_dict.set_item(_PARENT, parent)
        self.increase_parents(parent)

    @staticmethod
    def increase_parents(parent_dict: COSDictionary | None) -> None:
        """Walk up the ``/Parent`` chain starting at ``parent_dict`` and
        increment each ancestor's ``/Count`` by one.

        Mirrors upstream's private ``increaseParents`` (PDPageTree.java
        L599-L608): used by ``insert_before``/``insert_after`` after a
        ``/Kids`` splice so every ancestor's stored page count stays in
        sync with the actual tree size. Cycle-safe via an identity-set
        guard (upstream's loop just trusts the chain to be acyclic, but
        pypdfbox already hardens equivalent walks elsewhere — see
        ``get_inheritable_attribute``).
        """
        cursor = parent_dict
        seen: set[int] = set()
        while cursor is not None and id(cursor) not in seen:
            seen.add(id(cursor))
            current = cursor.get_dictionary_object(_COUNT)
            base = current.value if isinstance(current, COSInteger) else 0
            cursor.set_int(_COUNT, base + 1)
            cursor = _resolve_parent(cursor)

    # ---------- node classification ----------

    @staticmethod
    def is_page_tree_node(node: COSDictionary | None) -> bool:
        """Return ``True`` when ``node`` is a page-tree intermediate
        (``/Type /Pages``) **or** a dict carrying a ``/Kids`` array.

        Mirrors upstream's private ``isPageTreeNode`` heuristic — some
        non-conformant PDFs omit ``/Type /Pages`` on intermediate nodes
        but still keep ``/Kids``, so the predicate is deliberately lenient
        on the second clause (see PDFBOX-2250-229205.pdf).
        """
        return _is_page_tree_node(node)

    @staticmethod
    def is_page_dict(node: COSDictionary | None) -> bool:
        """Return ``True`` when ``node`` looks like a leaf ``/Type /Page``
        dictionary (rather than a ``/Pages`` intermediate).

        Mirrors upstream's lenient detection: ``/Type /Page`` wins; ``/Type
        /Pages`` returns ``False``; otherwise (no ``/Type`` at all) the node
        is treated as a leaf when it carries no ``/Kids`` array. Pypdfbox
        publicises this helper so callers porting upstream's free-floating
        ``COSName.PAGE.equals(node.getCOSName(COSName.TYPE))`` checks have a
        named entrypoint that matches ``is_page_tree_node``.
        """
        if node is None:
            return False
        return _is_page_dict(node)

    @staticmethod
    def get_parent(node: COSDictionary) -> COSDictionary | None:
        """Return ``node``'s parent dictionary, following the upstream
        ``/Parent`` → ``/P`` fallback (``getCOSDictionary(PARENT, P)``).

        Returns ``None`` when neither key resolves to a dictionary. Matches
        the same fallback used by upstream's ``getInheritableAttribute``,
        ``remove``, ``insertBefore``, and ``insertAfter`` paths so callers
        traversing the page tree can centralise the lookup instead of
        repeating the two-key dance.
        """
        return _resolve_parent(node)

    @staticmethod
    def get_kids(node: COSDictionary) -> list[COSDictionary]:
        """Return the ``/Kids`` of ``node`` as a list of ``COSDictionary``.

        Mirrors upstream's ``getKids`` helper: missing/non-array ``/Kids``
        yields the empty list, non-dictionary entries are skipped, and
        ``null`` entries are repaired in place by injecting a fresh empty
        ``/Type /Page`` dictionary so iteration stays well-formed (matches
        upstream's ``"replaced null entry with an empty page"`` warning
        path in PDPageTree.java).
        """
        kids = _kids_array(node)
        if kids is None:
            return []
        result: list[COSDictionary] = []
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if isinstance(entry, COSDictionary):
                result.append(entry)
                continue
            if entry is None:
                # Repair-in-place: empty /Type /Page placeholder.
                empty_page = COSDictionary()
                empty_page.set_item(_TYPE, _PAGE)
                empty_page.set_item(_PARENT, node)
                kids.set(i, empty_page)
                result.append(empty_page)
        return result

    # ---------- inheritable attribute lookup ----------

    @staticmethod
    def get_inheritable_attribute(
        node: COSDictionary, key: COSName
    ) -> COSBase | None:
        """Walk the ``/Parent`` chain looking for ``key``. Returns ``None``
        if no ancestor (including ``node``) carries it. Mirrors upstream's
        ``getInheritableAttribute``; protects against parent cycles."""
        cursor: COSDictionary | None = node
        seen: set[int] = set()
        while cursor is not None and id(cursor) not in seen:
            seen.add(id(cursor))
            value = cursor.get_dictionary_object(key)
            if value is not None:
                return value
            cursor = _resolve_parent(cursor)
        return None

    # ---------- internals ----------

    def _get_or_create_kids(self) -> COSArray:
        kids = _kids_array(self._root)
        if kids is None:
            kids = COSArray()
            self._root.set_item(_KIDS, kids)
        return kids

    @staticmethod
    def _index_of_kid(kids: COSArray, target: COSDictionary) -> int:
        """Locate ``target`` inside ``kids``. ``kids`` may hold the dict
        directly or via a ``COSObject`` indirect ref."""
        for i in range(kids.size()):
            entry = kids.get(i)
            if entry is target:
                return i
            if isinstance(entry, COSObject) and entry.get_object() is target:
                return i
        return -1

    @staticmethod
    def _increment_count(node: COSDictionary, delta: int) -> None:
        current = node.get_dictionary_object(_COUNT)
        new_value = (current.value if isinstance(current, COSInteger) else 0) + delta
        node.set_int(_COUNT, max(new_value, 0))

    @classmethod
    def _decrement_count_chain(cls, node: COSDictionary, delta: int) -> None:
        cursor: COSDictionary | None = node
        seen: set[int] = set()
        while cursor is not None and id(cursor) not in seen:
            seen.add(id(cursor))
            cls._increment_count(cursor, -delta)
            cursor = _resolve_parent(cursor)
