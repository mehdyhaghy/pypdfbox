from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cos_array import COSArray
    from .cos_base import COSBase
    from .cos_dictionary import COSDictionary
    from .cos_object import COSObject
    from .cos_update_info import COSUpdateInfo


class COSIncrement:
    """Traversal helper that collects updates beneath a ``COSUpdateInfo``
    so the incremental writer knows which objects to emit.

    Mirrors upstream ``org.apache.pdfbox.cos.COSIncrement`` (Java line 33).
    Walks the seed's children, tracking direct vs indirect descendants
    and respecting the document-state origin so cross-document references
    are forced into the increment.
    """

    def __init__(self, increment_origin: COSUpdateInfo | None) -> None:
        # LinkedHashSet equivalent — Python dicts preserve insertion order.
        self._objects: dict[int, COSBase] = {}
        self._excluded: set[int] = set()
        self._processed_objects: set[int] = set()
        self._increment_origin: COSUpdateInfo | None = increment_origin
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def contains(self, base: COSBase | None) -> bool:
        """``True`` if ``base`` has already been collected or processed.

        Mirrors upstream ``COSIncrement.contains`` (Java line 242).
        """
        # Local import dodges a module-load cycle.
        from .cos_object import COSObject  # noqa: PLC0415

        if base is None:
            return False
        if id(base) in self._objects:
            return True
        return isinstance(base, COSObject) and id(base) in self._processed_objects

    def exclude(self, *base: COSBase | None) -> COSIncrement:
        """Mark the given bases as excluded from the increment.

        Mirrors upstream ``COSIncrement.exclude`` (Java line 306).
        """
        for entry in base:
            if entry is not None:
                self._excluded.add(id(entry))
        return self

    def get_objects(self) -> list[COSBase]:
        """Return all indirect bases scheduled to be written on this
        increment. Triggers lazy collection on first call.

        Mirrors upstream ``COSIncrement.getObjects`` (Java line 336).
        """
        if not self._initialized and self._increment_origin is not None:
            self._collect(self._increment_origin.get_cos_object())
            self._initialized = True
        return list(self._objects.values())

    def __iter__(self) -> Iterator[COSBase]:
        return iter(self.get_objects())

    def iterator(self) -> Iterator[COSBase]:
        """Return an iterator over the collected objects.

        Mirrors upstream ``COSIncrement.iterator`` (Java line 352).
        """
        return iter(self)

    # ------------------------------------------------------------------
    # Public-name aliases for the private collection helpers so the
    # upstream method surface is reachable from outside.
    # ------------------------------------------------------------------

    def collect(self, base: COSBase | None) -> bool:
        """Public alias for :meth:`_collect`.

        Mirrors upstream ``COSIncrement.collect(COSBase)`` (Java line
        83, private).
        """
        return self._collect(base)

    def add(self, obj: COSBase | None) -> None:
        """Public alias for :meth:`_add`.

        Mirrors upstream ``COSIncrement.add(COSBase)`` (Java line 274,
        private).
        """
        self._add(obj)

    def add_processed_object(self, base: COSBase | None) -> None:
        """Mark ``base`` as already processed.

        Mirrors upstream ``COSIncrement.addProcessedObject`` (Java line
        290, private).
        """
        if base is not None:
            self._processed_objects.add(id(base))

    def is_excluded(self, base: COSBase) -> bool:
        """``True`` if ``base`` has been excluded via :meth:`exclude`.

        Mirrors upstream ``COSIncrement.isExcluded`` (Java line 324,
        private).
        """
        return self._is_excluded(base)

    def update_different_origin(self, update_state: object) -> None:
        """If ``update_state`` originates from a different document,
        force it to be marked updated so it joins this increment.

        Mirrors upstream ``COSIncrement.updateDifferentOrigin`` (Java
        line 257, private).
        """
        self._update_different_origin(update_state)

    # ------------------------------------------------------------------
    # Internals — match upstream private methods 1:1
    # ------------------------------------------------------------------

    def _collect(self, base: COSBase | None) -> bool:
        from .cos_array import COSArray  # noqa: PLC0415
        from .cos_dictionary import COSDictionary  # noqa: PLC0415
        from .cos_object import COSObject  # noqa: PLC0415

        if base is None or self.contains(base):
            return False
        if isinstance(base, COSDictionary):
            return self._collect_dictionary(base)
        if isinstance(base, COSObject):
            self._collect_object(base)
            return False
        if isinstance(base, COSArray):
            return self._collect_array(base)
        return False

    def _collect_dictionary(self, dictionary: COSDictionary) -> bool:
        update_state = dictionary.get_update_state()
        if (
            not self._is_excluded(dictionary)
            and not self.contains(dictionary)
            and update_state.is_updated()
        ):
            self._add(dictionary)
        child_demands_parent_update = False
        for entry in dictionary.values():
            if not self._is_update_info(entry) or self.contains(entry):
                continue
            entry_state = entry.get_update_state()
            self._update_different_origin(entry_state)
            from .cos_array import COSArray  # noqa: PLC0415
            from .cos_object import COSObject  # noqa: PLC0415

            if entry.is_need_to_be_updated() and (
                (not isinstance(entry, COSObject) and entry.is_direct())
                or isinstance(entry, COSArray)
            ):
                self.exclude(entry)
                child_demands_parent_update = True
            child_demands_parent_update = (
                self._collect(entry) or child_demands_parent_update
            )
        if self._is_excluded(dictionary):
            return child_demands_parent_update
        if child_demands_parent_update and not self.contains(dictionary):
            self._add(dictionary)
        return False

    def _collect_array(self, array: COSArray) -> bool:
        update_state = array.get_update_state()
        child_demands_parent_update = update_state.is_updated()
        for entry in array:
            if not self._is_update_info(entry) or self.contains(entry):
                continue
            entry_state = entry.get_update_state()
            self._update_different_origin(entry_state)
            child_demands_parent_update = (
                self._collect(entry) or child_demands_parent_update
            )
        return child_demands_parent_update

    def _collect_object(self, obj: COSObject) -> None:
        if self.contains(obj):
            return
        self._processed_objects.add(id(obj))
        update_state = obj.get_update_state()
        self._update_different_origin(update_state)
        actual = None
        if update_state.is_updated() or obj.is_dereferenced():
            base = obj.get_object()
            if self._is_update_info(base):
                actual = base
        if actual is None or self.contains(actual.get_cos_object()):
            return
        child_demands_parent_update = False
        actual_state = actual.get_update_state()
        if actual_state.is_updated():
            child_demands_parent_update = True
        self.exclude(actual.get_cos_object())
        child_demands_parent_update = (
            self._collect(actual.get_cos_object()) or child_demands_parent_update
        )
        if update_state.is_updated() or child_demands_parent_update:
            self._add(actual.get_cos_object())

    def _update_different_origin(self, update_state: object) -> None:
        origin = self._increment_origin
        if origin is None or update_state is None:
            return
        own_origin = origin.get_update_state().get_origin_document_state()
        get_origin = getattr(update_state, "get_origin_document_state", None)
        if get_origin is None:
            return
        if own_origin is not get_origin():
            update_state.update()  # type: ignore[attr-defined]

    def _add(self, obj: COSBase | None) -> None:
        if obj is not None:
            self._objects[id(obj)] = obj

    def _is_excluded(self, base: COSBase) -> bool:
        return id(base) in self._excluded

    @staticmethod
    def _is_update_info(entry: object) -> bool:
        # ``COSUpdateInfo`` is an ABC; concrete COS types extend it. The
        # cheap check is for the ``get_update_state`` method to avoid
        # importing the ABC here (circular).
        return entry is not None and hasattr(entry, "get_update_state")
