from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_field import PDField

_logger = logging.getLogger(__name__)


class PDFieldTree(Sequence["PDField"]):
    """Iterable view over an AcroForm's field tree.

    Mirrors PDFBox ``PDFieldTree`` as a read-side wrapper: iteration walks
    root fields first, then each non-terminal field's descendants in ``/Kids``
    order. ``Sequence`` methods are provided for Python callers that used the
    previous list-returning ``PDAcroForm.get_field_tree`` surface.
    """

    def __init__(self, acro_form: PDAcroForm) -> None:
        if acro_form is None:
            raise ValueError("root cannot be null")
        self._acro_form = acro_form

    def __iter__(self) -> Iterator[PDField]:
        return self.iterator()

    def iterator(self) -> Iterator[PDField]:
        """Return an iterator which walks all fields in the tree, in order."""
        return _FieldIterator(self._acro_form)

    def __len__(self) -> int:
        return len(self._as_list())

    def __getitem__(self, index: int | slice) -> PDField | list[PDField]:
        return self._as_list()[index]

    def is_empty(self) -> bool:
        """Predicate — ``True`` when the underlying AcroForm has no fields.

        Pypdfbox-only convenience: equivalent to ``len(tree) == 0`` but cheaper
        because it short-circuits on the first field encountered instead of
        walking the entire tree.
        """
        return next(iter(self), None) is None

    def __bool__(self) -> bool:
        return not self.is_empty()

    def __contains__(self, item: object) -> bool:
        """Short-circuiting membership check.

        Walks the tree comparing each :class:`PDField` against ``item`` and
        stops on the first match — avoids the full traversal that
        :class:`Sequence`'s default ``__contains__`` would perform via
        :meth:`__getitem__`. Two fields wrapping the same underlying
        ``COSDictionary`` compare as equal even when they are distinct Python
        instances (consistent with PDFBox's ``COSDictionary`` identity-based
        ``equals``).
        """
        from .pd_field import PDField

        if not isinstance(item, PDField):
            return False
        target = id(item.get_cos_object())
        return any(id(f.get_cos_object()) == target for f in self)

    def to_list(self) -> list[PDField]:
        """Materialise the tree as a fresh ``list[PDField]``.

        Pypdfbox-only convenience mirroring Java's ``Stream.toList()`` /
        ``StreamSupport.stream(spliterator, false).collect(...)`` idiom that
        upstream callers reach for. Equivalent to ``list(tree)`` but reads
        more idiomatically alongside other typed accessors. Each call
        materialises a new list — callers that mutate the result do not
        affect the underlying tree.
        """
        return self._as_list()

    def _as_list(self) -> list[PDField]:
        return list(iter(self))


class _FieldIterator(Iterator["PDField"]):
    """PDFBox-style field iterator with COSDictionary identity cycle guard."""

    def __init__(self, form: PDAcroForm) -> None:
        self._queue: deque[PDField] = deque()
        self._seen: set[int] = set()
        for field in form.get_fields():
            self._enqueue_kids(field)

    def __next__(self) -> PDField:
        if not self._queue:
            raise StopIteration
        return self._queue.popleft()

    def has_next(self) -> bool:
        return bool(self._queue)

    def next(self) -> PDField:
        return self.__next__()

    def remove(self) -> None:
        raise NotImplementedError("remove")

    def _enqueue_kids(self, node: PDField) -> None:
        self._queue.append(node)
        self._seen.add(id(node.get_cos_object()))
        if node.is_terminal():
            return

        from .pd_non_terminal_field import PDNonTerminalField

        if not isinstance(node, PDNonTerminalField):
            return
        for child in node.get_children():
            if id(child.get_cos_object()) in self._seen:
                _logger.error(
                    "Child of field '%s' already exists elsewhere, ignored to avoid recursion",
                    node.get_fully_qualified_name(),
                )
            else:
                self._enqueue_kids(child)


__all__ = ["PDFieldTree"]
