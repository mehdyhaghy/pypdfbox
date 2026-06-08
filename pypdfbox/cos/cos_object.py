from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .cos_base import COSBase
from .cos_update_state import COSUpdateState
from .i_cos_visitor import ICOSVisitor

_LOG = logging.getLogger(__name__)


class COSObject(COSBase):
    """
    Indirect-reference holder. Carries the (object_number, generation_number)
    pair that points into the document's xref, plus a lazy loader callback
    that the parser/document supplies to resolve the actual object.

    Until ``get_object()`` is first called, the resolved value is ``None``.
    Repeated calls return the cached value.
    """

    def __init__(
        self,
        object_number: int,
        generation_number: int = 0,
        *,
        loader: Callable[[COSObject], COSBase | None] | None = None,
        resolved: COSBase | None = None,
    ) -> None:
        super().__init__()
        if object_number < 0:
            raise ValueError("object_number must be non-negative")
        if generation_number < 0:
            raise ValueError("generation_number must be non-negative")
        self._object_number = object_number
        self._generation_number = generation_number
        self._loader = loader
        self._object: COSBase | None = resolved
        # Whether a load attempt has run. Distinct from ``_object is None``:
        # an unresolvable reference (free xref entry) leaves ``_object`` at
        # ``None`` *after* the loader ran, which still counts as
        # dereferenced. Mirrors upstream ``isDereferenced`` semantics.
        self._dereferenced: bool = resolved is not None
        self._update_state = COSUpdateState(self)

    @property
    def object_number(self) -> int:
        return self._object_number

    @property
    def generation_number(self) -> int:
        return self._generation_number

    def get_object_number(self) -> int:
        return self._object_number

    def get_generation_number(self) -> int:
        return self._generation_number

    def get_object(self) -> COSBase | None:
        """Resolve and cache the referenced object, invoking the loader on
        first access. Returns ``None`` if the reference cannot be resolved
        (e.g., free entry in the xref)."""
        if not self._dereferenced and self._loader is not None:
            # Mark dereferenced *before* invoking the loader so a recursive
            # call (object graph cycles) doesn't re-enter and loop forever.
            # Mirrors upstream ``COSObject.getObject``.
            self._dereferenced = True
            try:
                self._object = self._loader(self)
                self._update_state.dereference_child(self._object)
            except OSError:
                # PDFBox catches parser IOExceptions here: a malformed xref
                # target resolves to null and is not retried.
                _LOG.error("Can't dereference %s", self, exc_info=True)
            finally:
                # Upstream drops the parser callback after success, an
                # IOException, or an unchecked exception.
                self._loader = None
        return self._object

    def set_object(self, value: COSBase | None) -> None:
        """Manually attach a resolved object (used by the parser when it
        loads xref entries eagerly)."""
        self._object = value
        self._dereferenced = True
        self._update_state.dereference_child(value)

    def set_loader(self, loader: Callable[[COSObject], COSBase | None] | None) -> None:
        """Attach (or replace) the lazy loader. ``None`` removes any loader.
        Used by ``PDFParser`` after the xref has been resolved to wire up
        every pool entry to a body-parsing callback."""
        self._loader = loader

    def is_object_loaded(self) -> bool:
        return self._object is not None

    def is_dereferenced(self) -> bool:
        """Return ``True`` once a load attempt has been made (whether it
        produced a value or not). Mirrors upstream ``isDereferenced``."""
        return self._dereferenced

    def get_update_state(self) -> COSUpdateState:
        return self._update_state

    def is_needs_to_be_updated(self) -> bool:
        return self._update_state.is_updated()

    def set_needs_to_be_updated(self, value: bool) -> None:
        self._update_state.update(value)

    def is_object_null(self) -> bool:
        """Return ``True`` when no resolved object is attached. Mirrors
        upstream ``isObjectNull`` — a free xref entry shows up as a
        dereferenced object whose base is still null."""
        return self._object is None

    def set_to_null(self) -> None:
        """Pin the referenced object to ``COSNull.NULL`` and drop the
        loader so it can't replace it on next access. Mirrors upstream
        ``setToNull``."""
        # Local import to avoid a hard cos→cos_null cycle at module load.
        from .cos_null import COSNull  # noqa: PLC0415

        self._object = COSNull.NULL
        self._loader = None
        self._dereferenced = True

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_object(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSObject):
            return (
                self._object_number == other._object_number
                and self._generation_number == other._generation_number
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._object_number, self._generation_number))

    def __repr__(self) -> str:
        return f"COSObject({self._object_number} {self._generation_number} R)"

    def __str__(self) -> str:
        """Mirrors upstream ``COSObject.toString`` (``COSObject.java``
        line 149): ``COSObject{<num> <gen> R}``. The inner ``<num> <gen>
        R`` payload matches ``COSObjectKey.toString``.
        """
        return f"COSObject{{{self._object_number} {self._generation_number} R}}"

    def to_string(self) -> str:
        """Snake-case wrapper around :meth:`__str__` mirroring
        upstream ``COSObject.toString`` (``COSObject.java`` line 149).
        Lets callers porting Java code keep the ``obj.toString()`` shape.
        """
        return self.__str__()
