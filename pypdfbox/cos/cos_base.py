from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .i_cos_visitor import ICOSVisitor

if TYPE_CHECKING:
    from .cos_object_key import COSObjectKey


class COSBase(ABC):
    """
    Abstract root of every COS object. Carries the metadata shared by all
    COS types: indirect-vs-direct status (whether this object is referenced
    via the xref table) and the ``needs_to_be_updated`` flag the writer
    consults during incremental save.
    """

    def __init__(self) -> None:
        self._direct: bool = False
        self._needs_to_be_updated: bool = False
        self._key: COSObjectKey | None = None

    @abstractmethod
    def accept(self, visitor: ICOSVisitor) -> Any:
        """Double-dispatch entry point — concrete subclasses call the
        matching ``visit_from_*`` on the visitor."""

    def get_cos_object(self) -> COSBase:
        """Return the underlying COS object — ``self`` for native COS types.

        Mirrors PDFBox ``COSBase.getCOSObject`` (Java line 47), which
        satisfies the ``COSObjectable`` contract. ``COSObjectable``
        wrappers in ``pdmodel`` override this to return the wrapped
        ``COSDictionary``/``COSArray``.
        """
        return self

    def is_direct(self) -> bool:
        """``True`` if this object is written inline (not via an indirect
        reference). Mirrors PDFBox's direct/indirect distinction."""
        return self._direct

    def set_direct(self, direct: bool) -> None:
        self._direct = direct

    def is_needs_to_be_updated(self) -> bool:
        """Used by the incremental writer to decide whether this object
        must be re-emitted in the appended xref."""
        return self._needs_to_be_updated

    def set_needs_to_be_updated(self, value: bool) -> None:
        self._needs_to_be_updated = value

    def get_key(self) -> COSObjectKey | None:
        """Return the indirect-object ``COSObjectKey`` of this object, or
        ``None`` when it is direct / unkeyed.

        Mirrors PDFBox ``COSBase.getKey`` (Java line 86). The xref
        reconstruction pass populates this so writers can later cross-
        reference a resolved payload back to its indirect identity.
        """
        return self._key

    def set_key(self, key: COSObjectKey | None) -> None:
        """Record the indirect-object ``COSObjectKey`` for this object.

        Mirrors PDFBox ``COSBase.setKey`` (Java line 96).
        """
        self._key = key
