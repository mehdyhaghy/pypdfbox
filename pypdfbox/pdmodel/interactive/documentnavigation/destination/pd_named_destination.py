from __future__ import annotations

from pypdfbox.cos import COSName, COSString

from .pd_destination import PDDestination


class PDNamedDestination(PDDestination):
    """Named destination. Mirrors PDFBox ``PDNamedDestination``.

    Mirrors all four upstream constructors:

    * ``PDNamedDestination()`` — empty, ``get_named_destination()`` is ``None``.
    * ``PDNamedDestination(COSString)`` — wraps an existing COS string.
    * ``PDNamedDestination(COSName)`` — wraps an existing COS name.
    * ``PDNamedDestination(str)`` — convenience that wraps in a ``COSString``.
    """

    def __init__(
        self, name: COSName | COSString | str | bytes | None = None
    ) -> None:
        if name is None:
            self._name: COSName | COSString | None = None
        elif isinstance(name, (COSName, COSString)):
            self._name = name
        elif isinstance(name, bytes):
            self._name = COSString(name)
        else:
            self._name = COSString(name)

    def get_named_destination(self) -> str | None:
        if self._name is None:
            return None
        if isinstance(self._name, COSName):
            return self._name.get_name()
        return self._name.get_string()

    def set_named_destination(self, name: str | bytes | None) -> None:
        """Set the named destination. ``None`` clears the value, mirroring
        ``setNamedDestination(null)`` in upstream Java.

        Accepts ``str`` (the upstream contract) and also ``bytes`` for
        symmetry with the ``__init__`` constructor — useful when callers
        already hold raw PDFDocEncoding/UTF-16BE bytes (e.g. round-tripping
        a destination read from another PDF). Both forms are stored as a
        ``COSString``; upstream always converts to ``COSString`` even when
        the slot was previously a ``COSName``.
        """
        if name is None:
            self._name = None
        else:
            self._name = COSString(name)

    def get_cos_object(self) -> COSName | COSString | None:
        return self._name

    # ---------- typed-introspection predicates ----------

    def is_name_form(self) -> bool:
        """Return ``True`` if the underlying COS object is a ``COSName``.

        PDF 32000-1 §12.3.2.3 allows a named destination value to be either
        a name (``/Foo``) or a byte string (``(Foo)``); this predicate lets
        callers distinguish without re-importing ``COSName`` and doing an
        ``isinstance`` check on ``get_cos_object()``.
        """
        return isinstance(self._name, COSName)

    def is_string_form(self) -> bool:
        """Return ``True`` if the underlying COS object is a ``COSString``.

        Counterpart to :meth:`is_name_form`. Returns ``False`` for an empty
        (default-constructed) :class:`PDNamedDestination` whose underlying
        COS object is ``None``.
        """
        return isinstance(self._name, COSString)

    def is_empty(self) -> bool:
        """Return ``True`` when no destination name has been set.

        Equivalent to ``get_named_destination() is None`` but spelled as a
        predicate so callers don't need a separate ``None`` check after
        invoking the named accessor.
        """
        return self._name is None

    def __repr__(self) -> str:
        if self._name is None:
            return "PDNamedDestination(<empty>)"
        if isinstance(self._name, COSName):
            return f"PDNamedDestination(name={self._name.get_name()!r})"
        return f"PDNamedDestination(string={self._name.get_string()!r})"


__all__ = ["PDNamedDestination"]
