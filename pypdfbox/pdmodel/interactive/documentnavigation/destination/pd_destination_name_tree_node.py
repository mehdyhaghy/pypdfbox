from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString

from .pd_destination import PDDestination

_NAMES: COSName = COSName.get_pdf_name("Names")


class PDDestinationNameTreeNode:
    """
    Lightweight destination name-tree wrapper.

    This intentionally handles the common flat ``/Names`` array shape only;
    the full generic ``PDNameTreeNode`` machinery is deferred until more
    pdmodel callers need it.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        self._node = node if node is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._node

    def get_value(self, name: str) -> PDDestination | None:
        names = self._node.get_dictionary_object(_NAMES)
        if not isinstance(names, COSArray):
            return None
        i = 0
        while i + 1 < names.size():
            key = names.get_object(i)
            value = names.get_object(i + 1)
            i += 2
            if _key_text(key) == name:
                return PDDestination.create(value)
        return None

    def set_value(self, name: str, destination: PDDestination | None) -> None:
        names = self._node.get_dictionary_object(_NAMES)
        if not isinstance(names, COSArray):
            names = COSArray()
            self._node.set_item(_NAMES, names)

        entries: dict[str, COSBase] = {}
        i = 0
        while i + 1 < names.size():
            key = names.get_object(i)
            value = names.get_object(i + 1)
            i += 2
            key_text = _key_text(key)
            if key_text is not None and value is not None:
                entries[key_text] = value

        if destination is None:
            entries.pop(name, None)
        else:
            entries[name] = destination.get_cos_object()

        names.clear()
        for key in sorted(entries):
            value = entries[key]
            names.add(COSString(key))
            names.add(value)

    def get_names(self) -> list[str]:
        names = self._node.get_dictionary_object(_NAMES)
        if not isinstance(names, COSArray):
            return []
        out: list[str] = []
        i = 0
        while i + 1 < names.size():
            key = _key_text(names.get_object(i))
            if key is not None:
                out.append(key)
            i += 2
        return out

    def names(self) -> list[str]:
        return self.get_names()


def _key_text(key: object) -> str | None:
    if isinstance(key, COSString):
        return key.get_string()
    if isinstance(key, COSName):
        return key.get_name()
    return None


__all__ = ["PDDestinationNameTreeNode"]
