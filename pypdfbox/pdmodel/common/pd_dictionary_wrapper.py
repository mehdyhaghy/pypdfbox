from __future__ import annotations

from pypdfbox.cos import COSDictionary


class PDDictionaryWrapper:
    """Lightweight wrapper around a ``COSDictionary``.

    Mirrors ``org.apache.pdfbox.pdmodel.common.PDDictionaryWrapper`` (Java
    lines 27-79). Many PD-level classes carry just a backing dictionary
    plus a handful of typed accessors; PDFBox factored that pattern into
    this two-method base class. We mirror the same shape so subclasses can
    ``super().__init__()`` and read ``self.get_cos_object()`` exactly as
    upstream does.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``. Mirrors upstream
        ``getCOSObject()`` (Java line 54)."""
        return self._dictionary

    # ---------- equality / hashing ----------

    def __eq__(self, obj: object) -> bool:
        if self is obj:
            return True
        if isinstance(obj, PDDictionaryWrapper):
            return self._dictionary == obj._dictionary
        return False

    def __hash__(self) -> int:
        return id(self._dictionary)

    def equals(self, obj: object) -> bool:
        """Mirrors upstream ``equals(Object)`` (Java line 60)."""
        return self.__eq__(obj)

    def hash_code(self) -> int:
        """Mirrors upstream ``hashCode()`` (Java line 74)."""
        return self.__hash__()


__all__ = ["PDDictionaryWrapper"]
