from __future__ import annotations

from collections.abc import Iterable

from .cos_base import COSBase
from .cos_document_state import COSDocumentState


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
        if self._origin_document_state is not None or origin_document_state is None:
            return
        self._origin_document_state = origin_document_state
        if not dereferencing:
            self.update()
        self._propagate_origin_to_children(dereferencing=dereferencing)

    def setOriginDocumentState(  # noqa: N802 - upstream Java name
        self,
        origin_document_state: COSDocumentState | None,
    ) -> None:
        self.set_origin_document_state(origin_document_state)

    def get_origin_document_state(self) -> COSDocumentState | None:
        return self._origin_document_state

    def getOriginDocumentState(self) -> COSDocumentState | None:  # noqa: N802
        return self.get_origin_document_state()

    def is_accepting_updates(self) -> bool:
        return (
            self._origin_document_state is not None
            and self._origin_document_state.is_accepting_updates()
        )

    def isAcceptingUpdates(self) -> bool:  # noqa: N802
        return self.is_accepting_updates()

    def is_updated(self) -> bool:
        return self._updated

    def isUpdated(self) -> bool:  # noqa: N802
        return self.is_updated()

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

    def dereferenceChild(self, child: COSBase | None) -> None:  # noqa: N802
        self.dereference_child(child)

    def _link_child(self, child: COSBase) -> None:
        state = getattr(child, "get_update_state", None)
        if state is not None:
            state().set_origin_document_state(self._origin_document_state)

    def _propagate_origin_to_children(self, *, dereferencing: bool) -> None:
        # Local imports avoid hard module cycles at import time.
        from .cos_array import COSArray  # noqa: PLC0415
        from .cos_dictionary import COSDictionary  # noqa: PLC0415
        from .cos_object import COSObject  # noqa: PLC0415

        update_info = self._update_info
        if isinstance(update_info, COSDictionary):
            for child in update_info.values():
                self._set_child_origin(child, dereferencing=dereferencing)
        elif isinstance(update_info, COSArray):
            for child in update_info:
                self._set_child_origin(child, dereferencing=dereferencing)
        elif isinstance(update_info, COSObject) and update_info.is_dereferenced():
            self._set_child_origin(
                update_info.get_object(),
                dereferencing=dereferencing,
            )

    def _set_child_origin(
        self,
        child: COSBase | None,
        *,
        dereferencing: bool,
    ) -> None:
        if child is None:
            return
        state = getattr(child, "get_update_state", None)
        if state is not None:
            state().set_origin_document_state(
                self._origin_document_state,
                dereferencing=dereferencing,
            )
