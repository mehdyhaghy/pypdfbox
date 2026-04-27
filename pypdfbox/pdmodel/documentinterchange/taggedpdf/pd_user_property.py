from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance
    from .pd_user_attribute_object import PDUserAttributeObject


_N: COSName = COSName.get_pdf_name("N")
_V: COSName = COSName.get_pdf_name("V")
_F: COSName = COSName.get_pdf_name("F")
_H: COSName = COSName.get_pdf_name("H")


class PDUserProperty:
    """A user property entry inside a ``/UserProperties`` attribute object.

    Mirrors PDFBox ``PDUserProperty`` (in
    ``org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure``) — a
    typed wrapper over a ``COSDictionary`` carrying ``/N`` (name), ``/V``
    (value), ``/F`` (formatted display, optional) and ``/H`` (hidden,
    default ``false``).

    Upstream extends ``PDDictionaryWrapper``; that helper is not ported in
    pypdfbox, so this class implements the small wrapper surface
    (``get_cos_object`` + dictionary-equality semantics) directly.
    """

    def __init__(
        self,
        user_attribute_object: PDUserAttributeObject | None = None,
        dictionary: COSDictionary | None = None,
    ) -> None:
        """Construct a ``PDUserProperty``.

        Mirrors the two upstream constructors:

        * ``PDUserProperty(PDUserAttributeObject)`` — fresh dictionary.
        * ``PDUserProperty(COSDictionary, PDUserAttributeObject)`` — wrap
          an existing ``COSDictionary``.

        Both arguments are optional here so callers may build a detached
        property without an owning attribute object.
        """
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )
        self._user_attribute_object: PDUserAttributeObject | None = (
            user_attribute_object
        )

    # ---------- COSObjectable / PDDictionaryWrapper surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /N name ----------

    def get_name(self) -> str | None:
        # ``get_string`` resolves both ``COSString`` and ``COSName`` forms,
        # matching upstream ``getNameAsString`` (which similarly tolerates
        # either). Pre-existing dict-form callers in pypdfbox write ``/N``
        # as ``COSString``; the typed setter below preserves that
        # convention so both surfaces stay interchangeable.
        return self._dictionary.get_string(_N)

    def set_name(self, name: str) -> None:
        self._potentially_notify_changed(self.get_name(), name)
        # Diverges from upstream ``setName`` (which writes ``COSName``):
        # pypdfbox stores ``/N`` as ``COSString`` to match the value type
        # required by ISO 32000-1 §14.8.5 (user-property name shall be a
        # text string) and to interop with the long-standing dict-form
        # accessors. See CHANGES.md.
        self._dictionary.set_string(_N, name)

    # ---------- /V value ----------

    def get_value(self) -> COSBase | None:
        return self._dictionary.get_dictionary_object(_V)

    def set_value(self, value: COSBase | None) -> None:
        self._potentially_notify_changed(self.get_value(), value)
        if value is None:
            self._dictionary.remove_item(_V)
        else:
            self._dictionary.set_item(_V, value)

    # ---------- /F formatted-value ----------

    def get_formatted_value(self) -> str | None:
        return self._dictionary.get_string(_F)

    def set_formatted_value(self, formatted_value: str | None) -> None:
        self._potentially_notify_changed(
            self.get_formatted_value(), formatted_value
        )
        self._dictionary.set_string(_F, formatted_value)

    # ---------- /H hidden ----------

    def is_hidden(self) -> bool:
        return self._dictionary.get_boolean(_H, False)

    def set_hidden(self, hidden: bool) -> None:
        self._potentially_notify_changed(self.is_hidden(), hidden)
        self._dictionary.set_boolean(_H, hidden)

    # ---------- change notification ----------

    def _potentially_notify_changed(self, old_entry: object, new_entry: object) -> None:
        """Forward a change to the owning ``PDUserAttributeObject``.

        Mirrors upstream ``potentiallyNotifyChanged``. Notification is
        suppressed when the value is unchanged (``oldEntry.equals(newEntry)``).
        """
        if self._user_attribute_object is None:
            return
        if self._is_entry_changed(old_entry, new_entry):
            self._user_attribute_object.user_property_changed(self)

    @staticmethod
    def _is_entry_changed(old_entry: object, new_entry: object) -> bool:
        if old_entry is None:
            return new_entry is not None
        return old_entry != new_entry

    # ---------- equality / hash / repr (upstream parity) ----------

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, PDUserProperty):
            return False
        if self._dictionary is not other._dictionary and (
            self._dictionary != other._dictionary
        ):
            return False
        return self._user_attribute_object is other._user_attribute_object or (
            self._user_attribute_object == other._user_attribute_object
        )

    def __hash__(self) -> int:
        # Identity-based hash mirrors PDFBox's reliance on identity-equal
        # ``userAttributeObject`` references; the underlying COSDictionary is
        # mutable so we cannot fold its contents into the hash safely.
        return hash((id(self._dictionary), id(self._user_attribute_object)))

    def __repr__(self) -> str:
        return (
            f"Name={self.get_name()}, "
            f"Value={self.get_value()}, "
            f"FormattedValue={self.get_formatted_value()}, "
            f"Hidden={self.is_hidden()}"
        )


__all__ = ["PDUserProperty"]
