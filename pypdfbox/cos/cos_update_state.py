from __future__ import annotations

from collections.abc import Iterable

from .cos_base import COSBase
from .cos_document_state import COSDocumentState
from .cos_increment import COSIncrement

# COSArray / COSDictionary / COSObject, bound on first use: those modules
# import this one, so a module-level import would be circular.
_COS_TYPES: tuple[type, type, type] | None = None


def _bind_cos_types() -> None:
    global _COS_TYPES
    from .cos_array import COSArray
    from .cos_dictionary import COSDictionary
    from .cos_object import COSObject

    _COS_TYPES = (COSArray, COSDictionary, COSObject)


class COSUpdateState:
    """Document-state-gated update tracker for COS update-info objects.

    Mirrors PDFBox's ``COSUpdateState``: a dictionary, array, stream, or
    object wrapper ignores update marks until it is linked to a document
    state whose parser phase has completed.
    """

    def __init__(self, update_info: COSBase) -> None:
        self._update_info = update_info
        self._origin_document_state: COSDocumentState | None = None
        self._updated = False

    def set_origin_document_state(
        self,
        origin_document_state: COSDocumentState | None,
        *,
        dereferencing: bool = False,
    ) -> None:
        """Link this state and every reachable substructure to
        ``origin_document_state``.

        Mirrors upstream ``COSUpdateState#setOriginDocumentState``. Already
        linked states are skipped (and so is their subtree). Unless
        ``dereferencing``, each newly linked state is also marked updated.

        PDFBOX-6200: the structure is traversed with an explicit stack instead
        of recursion, as it may be nested deeper than the call stack allows.
        """
        if origin_document_state is None:
            return
        pending: list[COSUpdateState] = [self]
        while pending:
            state = pending.pop()
            if state._origin_document_state is not None:
                continue
            state._origin_document_state = origin_document_state
            if not dereferencing:
                state.update()
            state._push_substructures(pending)

    def get_origin_document_state(self) -> COSDocumentState | None:
        return self._origin_document_state

    def is_accepting_updates(self) -> bool:
        return (
            self._origin_document_state is not None
            and self._origin_document_state.is_accepting_updates()
        )

    def is_updated(self) -> bool:
        return self._updated

    def update(
        self,
        updated: bool = True,
        child: COSBase | None = None,
        children: Iterable[COSBase | None] | None = None,
    ) -> None:
        if self.is_accepting_updates():
            self._updated = updated
        if child is not None:
            self._link_child(child)
        if children is not None:
            for item in children:
                if item is not None:
                    self._link_child(item)

    def dereference_child(self, child: COSBase | None) -> None:
        if child is None:
            return
        state = getattr(child, "get_update_state", None)
        if state is None:
            return
        state().set_origin_document_state(
            self._origin_document_state,
            dereferencing=True,
        )

    def to_increment(self) -> COSIncrement:
        """Create a :class:`COSIncrement` seeded with the managed update-info.

        Mirrors upstream ``COSUpdateState#toIncrement()`` (Java line 254).
        """
        # Imported lazily-safe at module top; ``COSIncrement`` wants a
        # ``COSUpdateInfo`` (an object that exposes ``get_cos_object`` +
        # ``get_update_state``). ``self._update_info`` satisfies both
        # since every concrete COS update-info type does.
        return COSIncrement(self._update_info)  # type: ignore[arg-type]

    def _link_child(self, child: COSBase) -> None:
        state = getattr(child, "get_update_state", None)
        if state is not None:
            state().set_origin_document_state(self._origin_document_state)

    def _push_substructures(self, pending: list[COSUpdateState]) -> None:
        if _COS_TYPES is None:
            _bind_cos_types()
        cos_array, cos_dictionary, cos_object = _COS_TYPES  # type: ignore[misc]
        update_info = self._update_info
        if isinstance(update_info, cos_dictionary):
            for entry in update_info.values():
                self._push_update_state(pending, entry)
        elif isinstance(update_info, cos_array):
            for entry in update_info:
                self._push_update_state(pending, entry)
        elif isinstance(update_info, cos_object) and update_info.is_dereferenced():
            self._push_update_state(pending, update_info.get_object())

    @staticmethod
    def _push_update_state(
        pending: list[COSUpdateState], base: COSBase | None
    ) -> None:
        if base is None:
            return
        state = getattr(base, "get_update_state", None)
        if state is not None:
            pending.append(state())
