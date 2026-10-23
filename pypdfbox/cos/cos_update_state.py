from __future__ import annotations

from collections.abc import Iterable

from .cos_base import COSBase
from .cos_document_state import COSDocumentState
from .cos_increment import COSIncrement

# COSArray / COSDictionary / COSObject, bound on first use: those modules
# import this one, so a module-level import would be circular.
_COS_TYPES: tuple[type, type, type] | None = None

# Exact classes whose update state is the plain ``_update_state`` attribute
# (none of them overrides ``get_update_state``), and exact leaf classes that
# carry no update state at all. Both are bound with ``_COS_TYPES``. Any other
# class, including subclasses of these, takes the generic
# ``get_update_state`` lookup, so the sets are only a dispatch shortcut.
_TRACKED_TYPES: frozenset[type] = frozenset()
_LEAF_TYPES: frozenset[type] = frozenset()


def _bind_cos_types() -> None:
    global _COS_TYPES, _TRACKED_TYPES, _LEAF_TYPES
    from .cos_array import COSArray
    from .cos_boolean import COSBoolean
    from .cos_dictionary import COSDictionary
    from .cos_float import COSFloat
    from .cos_integer import COSInteger
    from .cos_name import COSName
    from .cos_null import COSNull
    from .cos_object import COSObject
    from .cos_stream import COSStream
    from .cos_string import COSString

    _TRACKED_TYPES = frozenset((COSArray, COSDictionary, COSObject, COSStream))
    _LEAF_TYPES = frozenset(
        (COSBoolean, COSFloat, COSInteger, COSName, COSNull, COSString, type(None))
    )
    _COS_TYPES = (COSArray, COSDictionary, COSObject)


def _child_state(child: object) -> COSUpdateState | None:
    """Return ``child``'s update state, or ``None`` when it has none."""
    cls = child.__class__
    if cls in _TRACKED_TYPES:
        return child._update_state  # type: ignore[attr-defined]
    if cls in _LEAF_TYPES:
        return None
    state = getattr(child, "get_update_state", None)
    return state() if state is not None else None


class COSUpdateState:
    """Document-state-gated update tracker for COS update-info objects.

    Mirrors PDFBox's ``COSUpdateState``: a dictionary, array, stream, or
    object wrapper ignores update marks until it is linked to a document
    state whose parser phase has completed.

    Performance note: while a state has no origin document state (every
    object the parser is still building, every freshly constructed object)
    :meth:`update` and :meth:`dereference_child` are exact no-ops, so the
    COS containers skip calling them in that case.
    """

    __slots__ = ("_origin_document_state", "_update_info", "_updated")

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
        if origin_document_state is None or self._origin_document_state is not None:
            return
        if _COS_TYPES is None:
            _bind_cos_types()
        cos_array, cos_dictionary, cos_object = _COS_TYPES  # type: ignore[misc]
        tracked = _TRACKED_TYPES
        leaf = _LEAF_TYPES
        # ``update()`` on a freshly linked state sets the flag exactly when
        # the (shared) origin accepts updates; evaluate that once.
        mark = not dereferencing and origin_document_state.is_accepting_updates()
        pending: list[COSUpdateState] = [self]
        pop = pending.pop
        push = pending.append
        while pending:
            state = pop()
            if state._origin_document_state is not None:
                continue
            state._origin_document_state = origin_document_state
            if mark:
                state._updated = True
            update_info = state._update_info
            if isinstance(update_info, cos_dictionary):
                entries = update_info.values()
            elif isinstance(update_info, cos_array):
                entries = update_info
            elif isinstance(update_info, cos_object) and update_info.is_dereferenced():
                entries = (update_info.get_object(),)
            else:
                continue
            for entry in entries:
                cls = entry.__class__
                if cls in tracked:
                    child_state = entry._update_state
                    # An already linked state would be skipped on pop anyway
                    # (most entries are pool references the document linked).
                    if child_state._origin_document_state is None:
                        push(child_state)
                elif cls not in leaf:
                    get_state = getattr(entry, "get_update_state", None)
                    if get_state is not None:
                        push(get_state())

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
        origin = self._origin_document_state
        if origin is None:
            # Not accepting updates, and linking a child to a ``None``
            # origin is a no-op.
            return
        if origin.is_accepting_updates():
            self._updated = updated
        if _COS_TYPES is None:
            _bind_cos_types()
        if child is not None:
            state = _child_state(child)
            if state is not None:
                state.set_origin_document_state(origin)
        if children is not None:
            for item in children:
                if item is not None:
                    state = _child_state(item)
                    if state is not None:
                        state.set_origin_document_state(origin)

    def dereference_child(self, child: COSBase | None) -> None:
        origin = self._origin_document_state
        if child is None or origin is None:
            return
        if _COS_TYPES is None:
            _bind_cos_types()
        state = _child_state(child)
        if state is not None:
            state.set_origin_document_state(origin, dereferencing=True)

    def to_increment(self) -> COSIncrement:
        """Create a :class:`COSIncrement` seeded with the managed update-info.

        Mirrors upstream ``COSUpdateState#toIncrement()`` (Java line 254).
        """
        # Imported lazily-safe at module top; ``COSIncrement`` wants a
        # ``COSUpdateInfo`` (an object that exposes ``get_cos_object`` +
        # ``get_update_state``). ``self._update_info`` satisfies both
        # since every concrete COS update-info type does.
        return COSIncrement(self._update_info)  # type: ignore[arg-type]

    @staticmethod
    def _push_update_state(
        pending: list[COSUpdateState], base: COSBase | None
    ) -> None:
        if base is None:
            return
        state = getattr(base, "get_update_state", None)
        if state is not None:
            pending.append(state())
