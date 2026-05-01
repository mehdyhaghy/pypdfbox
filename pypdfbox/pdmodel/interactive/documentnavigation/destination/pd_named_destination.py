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

    def set_named_destination(self, name: str | None) -> None:
        """Set the named destination. ``None`` clears the value, mirroring
        ``setNamedDestination(null)`` in upstream Java."""
        if name is None:
            self._name = None
        else:
            self._name = COSString(name)

    def get_cos_object(self) -> COSName | COSString | None:
        return self._name


__all__ = ["PDNamedDestination"]
