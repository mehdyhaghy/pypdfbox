from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from .i_cos_visitor import ICOSVisitor

if TYPE_CHECKING:
    from .cos_object_key import COSObjectKey


def _compute_abstract_methods(cls: type) -> frozenset[str]:
    """Return the abstract method names of ``cls`` the way ``ABCMeta`` does:
    names declared abstract in its own namespace plus inherited abstract
    names it does not override with a concrete attribute."""
    abstracts = {
        name
        for name, value in cls.__dict__.items()
        if getattr(value, "__isabstractmethod__", False)
    }
    for base in cls.__bases__:
        for name in getattr(base, "__abstractmethods__", ()):
            if getattr(getattr(cls, name, None), "__isabstractmethod__", False):
                abstracts.add(name)
    return frozenset(abstracts)


class COSBase:
    """
    Abstract root of every COS object. Carries the metadata shared by all
    COS types: indirect-vs-direct status (whether this object is referenced
    via the xref table) and the ``needs_to_be_updated`` flag the writer
    consults during incremental save.

    Performance note: this deliberately does not use ``ABCMeta``. Every
    ``isinstance(x, SomeCOSType)`` check that fails would otherwise run
    ``ABCMeta.__instancecheck__`` (several times slower than the plain type
    check), and the parser, writer and pdmodel layers do millions of them.
    Abstract-method enforcement is kept: ``__init_subclass__`` computes
    ``__abstractmethods__`` exactly like ``ABCMeta``, so instantiating a
    class with an unimplemented abstract method still raises ``TypeError``.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.__abstractmethods__ = _compute_abstract_methods(cls)

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


COSBase.__abstractmethods__ = _compute_abstract_methods(COSBase)
