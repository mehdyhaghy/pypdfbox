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


def _kids_array(node: COSDictionary) -> COSArray | None:
    kids = node.get_dictionary_object(_KIDS)
    return kids if isinstance(kids, COSArray) else None


class PDPageTree:
    """
    Iterable view of the document's page tree rooted at ``/Pages``.
    Mirrors ``org.apache.pdfbox.pdmodel.PDPageTree``.

    Cluster #1 supports:
      - iteration in document order;
      - ``len()`` via ``/Count`` (with a walk-fallback);
      - 0-based and negative indexing;
      - ``index_of(page)`` / ``index_of_page(page)`` lookup;
      - ``add(page)`` / ``remove(page|int)`` / ``insert_before`` /
        ``insert_after``;
      - ``get_root()`` — top ``/Pages`` node;
      - ``iterator()`` — Java-style alias for ``__iter__``;
      - the ``get_inheritable_attribute`` static helper.
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
                wrapper.set_item(_KIDS, kids)
                wrapper.set_int(_COUNT, 1)
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

        kids = _kids_array(node)
        if kids is None:
            return
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if isinstance(entry, COSDictionary):
                yield from self._walk(entry, seen)

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
        return len(self)

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

    @staticmethod
    def _sanitize_type(dictionary: COSDictionary) -> None:
        """Normalize the ``/Type`` entry of a leaf page dictionary.

        Mirrors upstream ``PDPageTree.sanitizeType``:
        - missing ``/Type`` is set to ``/Page`` (defensive against
          malformed PDFs that omit the entry on otherwise-valid pages);
        - any ``/Type`` other than ``/Page`` raises ``ValueError`` (upstream
          throws ``IllegalStateException``)."""
        type_name = dictionary.get_dictionary_object(_TYPE)
        if type_name is None:
            dictionary.set_item(_TYPE, _PAGE)
            return
        if isinstance(type_name, COSName) and type_name != _PAGE:
            raise ValueError(f"Expected 'Page' but found {type_name}")

    def get(self, index: int) -> PDPage:
        """0-based accessor — matches upstream's ``get(int)``."""
        return self[index]

    def index_of(self, page: PDPage | COSDictionary) -> int:
        """Return the 0-based document-order index of ``page``.

        Mirrors upstream ``indexOf(PDPage)``: returns ``-1`` when the page
        is not part of this page tree. Comparison is by the underlying
        ``COSDictionary`` identity so callers can pass a fresh ``PDPage``
        wrapper around an existing page dictionary.
        """
        page_dict = _unwrap_page_dict(page)
        for index, candidate in enumerate(self):
            if candidate.get_cos_object() is page_dict:
                return index
        return -1

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
        parent = page_dict.get_dictionary_object(_PARENT)
        if not isinstance(parent, COSDictionary):
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

    def insert_before(
        self, new_page: PDPage | COSDictionary, target: PDPage | COSDictionary
    ) -> None:
        """Insert ``new_page`` directly before ``target`` in ``target``'s
        parent's ``/Kids``."""
        target_dict = _unwrap_page_dict(target)
        new_dict = _unwrap_page_dict(new_page)
        parent = target_dict.get_dictionary_object(_PARENT)
        if not isinstance(parent, COSDictionary):
            parent = self._root
        kids = _kids_array(parent)
        if kids is None:
            raise ValueError("target page has no /Kids parent array")
        index = self._index_of_kid(kids, target_dict)
        if index < 0:
            raise ValueError("target page is not in its declared parent's /Kids")
        kids.add_at(index, new_dict)
        new_dict.set_item(_PARENT, parent)
        self._increment_count(parent, +1)

    def insert_after(
        self, new_page: PDPage | COSDictionary, target: PDPage | COSDictionary
    ) -> None:
        target_dict = _unwrap_page_dict(target)
        new_dict = _unwrap_page_dict(new_page)
        parent = target_dict.get_dictionary_object(_PARENT)
        if not isinstance(parent, COSDictionary):
            parent = self._root
        kids = _kids_array(parent)
        if kids is None:
            raise ValueError("target page has no /Kids parent array")
        index = self._index_of_kid(kids, target_dict)
        if index < 0:
            raise ValueError("target page is not in its declared parent's /Kids")
        kids.add_at(index + 1, new_dict)
        new_dict.set_item(_PARENT, parent)
        self._increment_count(parent, +1)

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
            parent = cursor.get_dictionary_object(_PARENT)
            cursor = parent if isinstance(parent, COSDictionary) else None
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
            parent = cursor.get_dictionary_object(_PARENT)
            cursor = parent if isinstance(parent, COSDictionary) else None
