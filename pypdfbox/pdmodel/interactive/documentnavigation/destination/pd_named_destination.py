from __future__ import annotations

from pypdfbox.cos import COSName, COSString

from .pd_destination import PDDestination


class PDNamedDestination(PDDestination):
    """Named destination. Mirrors PDFBox ``PDNamedDestination``."""

    def __init__(self, name: COSName | COSString | str | bytes) -> None:
        if isinstance(name, (COSName, COSString)):
            self._name = name
        elif isinstance(name, bytes):
            self._name = COSString(name)
        else:
            self._name = COSString(name)

    def get_named_destination(self) -> str:
        if isinstance(self._name, COSName):
            return self._name.get_name()
        return self._name.get_string()

    def set_named_destination(self, name: str) -> None:
        self._name = COSString(name)

    def get_cos_object(self) -> COSName | COSString:
        return self._name


__all__ = ["PDNamedDestination"]
