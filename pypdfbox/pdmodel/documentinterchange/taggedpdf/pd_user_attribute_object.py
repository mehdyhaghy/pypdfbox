from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)

from .pd_standard_attribute_object import PDStandardAttributeObject
from .pd_user_property import PDUserProperty


def _cos_to_py(value: COSBase | None) -> Any:
    """Best-effort scalar projection for /V values used in /P entries."""
    if value is None:
        return None
    if isinstance(value, COSBoolean):
        return value.value
    if isinstance(value, (COSInteger, COSFloat)):
        return value.value
    if isinstance(value, COSString):
        return value.get_string()
    if isinstance(value, COSName):
        return value.name
    return value


def _py_to_cos(value: Any) -> COSBase:
    """Inverse of ``_cos_to_py`` for accepted /V scalars."""
    if isinstance(value, COSBase):
        return value
    if isinstance(value, bool):
        return COSBoolean.get(value)
    if isinstance(value, int):
        return COSInteger.get(value)
    if isinstance(value, float):
        return COSFloat(value)
    if isinstance(value, str):
        return COSString(value)
    raise TypeError(f"Unsupported /V value type: {type(value).__name__}")


class PDUserAttributeObject(PDStandardAttributeObject):
    """
    A user-properties attribute object (``/O /UserProperties``). Mirrors
    PDFBox ``PDUserAttributeObject``.

    The ``/P`` entries can be accessed two ways:

    * The upstream-style typed surface — ``get_owner_user_properties`` /
      ``set_user_properties`` / ``add_user_property`` /
      ``remove_user_property`` — which returns/accepts the typed
      :class:`PDUserProperty` wrapper.
    * A back-compat dict surface — ``get_property`` / ``set_property`` /
      ``get_owner_properties`` / ``set_owner_properties`` / etc. — which
      returns/accepts plain Python dicts ``{"N", "V", "F", "H"}``. This
      surface predates the typed wrapper and is preserved so existing
      callers continue to work.

    Both surfaces operate on the same underlying ``/P`` array.
    """

    OWNER: str = "UserProperties"
    OWNER_USER_PROPERTIES: str = "UserProperties"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER)

    # ---------- /P ----------

    def get_property(self) -> list[dict[str, Any]]:
        v = self._dictionary.get_dictionary_object("P")
        if not isinstance(v, COSArray):
            return []
        out: list[dict[str, Any]] = []
        for i in range(v.size()):
            entry = v.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            out.append(
                {
                    "N": entry.get_string("N"),
                    "V": _cos_to_py(entry.get_dictionary_object("V")),
                    "F": entry.get_string("F"),
                    "H": entry.get_boolean("H", False),
                }
            )
        return out

    def set_property(
        self,
        name: str,
        value: Any,
        format: str | None = None,
        hidden: bool = False,
    ) -> None:
        """Append a single user-property entry to ``/P``."""
        v = self._dictionary.get_dictionary_object("P")
        if isinstance(v, COSArray):
            array = v
        else:
            array = COSArray()
            self._dictionary.set_item("P", array)

        entry = COSDictionary()
        entry.set_string("N", name)
        entry.set_item("V", _py_to_cos(value))
        if format is not None:
            entry.set_string("F", format)
        if hidden:
            entry.set_boolean("H", True)
        array.add(entry)

    # ---------- PDFBox parity surface ----------
    #
    # Upstream ``PDUserAttributeObject`` exposes ``getOwnerProperties`` /
    # ``setOwnerProperties``. We add snake_case mirrors plus convenience
    # ``add_owner_property`` / ``remove_owner_property`` helpers. These read
    # and write the same ``/P`` array as the legacy ``get_property`` /
    # ``set_property`` accessors, which remain for back-compat.

    def get_owner_properties(self) -> list[dict[str, Any]]:
        """Return the ``/P`` user-property entries as plain dicts.

        Mirrors PDFBox ``PDUserAttributeObject.getOwnerProperties`` (which
        returns ``List<PDUserProperty>``). Each dict has keys ``N``, ``V``,
        ``F``, ``H``; ``H`` defaults to ``False`` when absent.
        """
        return self.get_property()

    def set_owner_properties(self, values: list[dict[str, Any]]) -> None:
        """Replace the ``/P`` array with ``values``.

        Mirrors PDFBox ``PDUserAttributeObject.setOwnerProperties``. Each
        dict in ``values`` is expected to carry an ``N`` key (property
        name) and a ``V`` key (value); ``F`` (formatted display) and ``H``
        (hidden) are optional.
        """
        array = COSArray()
        self._dictionary.set_item("P", array)
        for entry in values:
            name = entry.get("N")
            if name is None:
                raise ValueError("user property entry missing required 'N' key")
            value = entry.get("V")
            cos_entry = COSDictionary()
            cos_entry.set_string("N", str(name))
            cos_entry.set_item("V", _py_to_cos(value))
            formatted = entry.get("F")
            if formatted is not None:
                cos_entry.set_string("F", str(formatted))
            hidden = entry.get("H", False)
            if hidden:
                cos_entry.set_boolean("H", True)
            array.add(cos_entry)

    def add_owner_property(
        self,
        name: str,
        value: Any,
        formatted: str | None = None,
        hidden: bool = False,
    ) -> None:
        """Append a single user-property entry to ``/P`` (convenience)."""
        self.set_property(name, value, format=formatted, hidden=hidden)

    def remove_owner_property(self, name: str) -> bool:
        """Remove the first ``/P`` entry whose ``/N`` equals ``name``.

        Returns ``True`` when an entry was removed, ``False`` otherwise.
        """
        v = self._dictionary.get_dictionary_object("P")
        if not isinstance(v, COSArray):
            return False
        for index in range(v.size()):
            entry = v.get_object(index)
            if not isinstance(entry, COSDictionary):
                continue
            if entry.get_string("N") == name:
                v.remove_at(index)
                return True
        return False

    # ---------- typed PDUserProperty surface (PDFBox parity) ----------

    def get_owner_user_properties(self) -> list[PDUserProperty]:
        """Return the ``/P`` entries as :class:`PDUserProperty` wrappers.

        Mirrors upstream ``PDUserAttributeObject.getOwnerUserProperties``.
        Each wrapper is bound back to ``self`` so subsequent setter calls
        on the returned property notify the owning attribute object.
        """
        v = self._dictionary.get_dictionary_object("P")
        if not isinstance(v, COSArray):
            return []
        out: list[PDUserProperty] = []
        for index in range(v.size()):
            entry = v.get_object(index)
            if not isinstance(entry, COSDictionary):
                continue
            out.append(PDUserProperty(self, entry))
        return out

    def set_user_properties(self, user_properties: list[PDUserProperty]) -> None:
        """Replace the ``/P`` array with the given wrappers.

        Mirrors upstream ``PDUserAttributeObject.setUserProperties``.
        """
        array = COSArray()
        for user_property in user_properties:
            array.add(user_property.get_cos_object())
        self._dictionary.set_item("P", array)

    def add_user_property(self, user_property: PDUserProperty) -> None:
        """Append a single ``PDUserProperty`` wrapper to ``/P``.

        Mirrors upstream ``PDUserAttributeObject.addUserProperty``: if no
        ``/P`` array exists one is created.
        """
        v = self._dictionary.get_dictionary_object("P")
        if isinstance(v, COSArray):
            array = v
        else:
            array = COSArray()
            self._dictionary.set_item("P", array)
        array.add(user_property.get_cos_object())
        self.notify_change()

    def remove_user_property(self, user_property: PDUserProperty | None) -> None:
        """Remove ``user_property`` from ``/P`` (by COSDictionary identity).

        Mirrors upstream ``PDUserAttributeObject.removeUserProperty``: a
        ``None`` argument is silently ignored, and ``notifyChanged`` only
        fires when an entry was actually removed.
        """
        if user_property is None:
            return
        v = self._dictionary.get_dictionary_object("P")
        if not isinstance(v, COSArray):
            return
        if v.remove(user_property.get_cos_object()):
            self.notify_change()

    def user_property_changed(self, user_property: PDUserProperty) -> None:
        """Hook invoked by ``PDUserProperty`` setters when the property
        mutates. Upstream is a no-op extension point for subclasses; we
        forward to ``notify_change`` so any registered structure-element
        observer learns of the change.
        """
        # Match upstream behaviour: the base implementation is empty. We
        # avoid calling notify_change here because doing so during a
        # set_owner / set_revision_number flow would double-notify.
        _ = user_property

    def __repr__(self) -> str:
        return (
            f"PDUserAttributeObject(O={self.get_owner()}, "
            f"properties={len(self.get_property())})"
        )


__all__ = ["PDUserAttributeObject", "PDUserProperty"]
