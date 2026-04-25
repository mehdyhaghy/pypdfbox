from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


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
        if self._object is None and self._loader is not None:
            self._object = self._loader(self)
        return self._object

    def set_object(self, value: COSBase | None) -> None:
        """Manually attach a resolved object (used by the parser when it
        loads xref entries eagerly)."""
        self._object = value

    def is_object_loaded(self) -> bool:
        return self._object is not None

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
