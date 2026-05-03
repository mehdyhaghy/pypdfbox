from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_attribute_object import PDAttributeObject

_O: COSName = COSName.get_pdf_name("O")


class PDDefaultAttributeObject(PDAttributeObject):
    """
    A default (owner-agnostic) attribute object. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDDefaultAttributeObject``.

    Used when an attribute dictionary on a structure element has no specialized
    owner subclass (i.e. ``/O`` doesn't match Layout / List / PrintField /
    Table / XML-1.00 / HTML-3.20 / HTML-4.01 / OEB-1.00 / RTF-1.05 /
    CSS-1.00 / CSS-2.00 / UserProperties). Exposes generic name/value
    helpers and reflects every entry except the ``/O`` owner key as an
    "attribute".
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)

    # ---------- attribute introspection ----------

    def get_attribute_names(self) -> list[str]:
        """Names of all entries in the dictionary, excluding ``/O``.

        Mirrors upstream ``getAttributeNames()`` semantics: every key in
        the underlying COSDictionary except the owner key, in dictionary
        iteration order.
        """
        return [
            key.get_name()
            for key in self._dictionary.key_set()
            if key != _O
        ]

    def get_attribute_value(
        self, attr_name: str, default_value: COSBase | None = None
    ) -> COSBase | None:
        """Resolved value for ``attr_name``, or ``default_value`` if absent.

        Combines upstream's two overloads — public ``getAttributeValue(String)``
        and protected ``getAttributeValue(String, COSBase)`` — into one
        Python method using a default keyword. Returns the resolved
        ``COSBase`` (dereferences indirect references) or ``default_value``
        when the key is missing.
        """
        value = self._dictionary.get_dictionary_object(attr_name)
        if value is None:
            return default_value
        return value

    def is_specified(self, name: str) -> bool:
        """Return ``True`` when ``name`` is explicitly written into the
        dictionary (resolved value is not ``None``).

        pypdfbox addition for parity with
        ``PDStandardAttributeObject.isSpecified(String)`` upstream — the
        typed taggedpdf subclasses already rely on this predicate, but the
        owner-agnostic default attribute object inherits the same storage
        and benefits from the same predicate when callers iterate
        :meth:`get_attribute_names`. Skips ``/O`` so probing the owner key
        through ``is_specified`` doesn't conflate the owner marker with a
        real attribute (mirrors :meth:`get_attribute_names` exclusion).
        """
        if name == "O":
            return False
        return self._dictionary.get_dictionary_object(name) is not None

    # ---------- attribute mutation ----------

    def set_attribute(self, attr_name: str, attr_value: COSBase) -> None:
        """Set ``attr_name`` to ``attr_value`` and notify the owning
        structure element of the change.

        Mirrors upstream ``setAttribute``: captures the previous value,
        writes the new one, then fires ``potentiallyNotifyChanged``. Our
        ``notify_change()`` is currently a debug-level no-op (see
        ``CHANGES.md``); the call site is preserved for parity.
        """
        old = self.get_attribute_value(attr_name)
        self._dictionary.set_item(COSName.get_pdf_name(attr_name), attr_value)
        self._potentially_notify_changed(old, attr_value)

    def remove_attribute(self, attr_name: str) -> None:
        """Remove ``attr_name`` from the dictionary and notify the owning
        structure element when the entry was actually present.

        pypdfbox addition: upstream PDFBox doesn't expose a removal helper
        on ``PDDefaultAttributeObject`` (callers reach for the underlying
        ``COSDictionary``), but we surface one for symmetry with
        :meth:`set_attribute`. ``/O`` (the owner marker) is rejected — the
        owner is mandatory on a non-empty attribute dictionary and clearing
        it would corrupt :meth:`PDAttributeObject.create` dispatch. Removing
        a missing key is a silent no-op (no notification fired).
        """
        if attr_name == "O":
            raise ValueError(
                "remove_attribute cannot remove the /O owner key; use "
                "set_owner instead"
            )
        old = self.get_attribute_value(attr_name)
        if old is None:
            return
        self._dictionary.remove_item(COSName.get_pdf_name(attr_name))
        self._potentially_notify_changed(old, None)

    # ---------- internal ----------

    def _potentially_notify_changed(
        self, old: COSBase | None, new: COSBase | None
    ) -> None:
        """Fire :meth:`notify_change` when ``old`` and ``new`` differ.

        Mirrors upstream ``PDAttributeObject.potentiallyNotifyChanged``:
        upstream guards the structure-element notification behind an
        equality check so no-op writes don't trigger spurious revisions.
        """
        if old is None and new is None:
            return
        if old is not None and new is not None and old == new:
            return
        self.notify_change()

    def __str__(self) -> str:
        """Mirror upstream ``PDDefaultAttributeObject.toString()`` exactly.

        Format: ``"O=<owner>, attributes={<name>=<value>, ...}"``.
        Iterates :meth:`get_attribute_names` (which excludes the ``/O``
        owner key) in dictionary order and joins each entry with ``", "``.
        Values are stringified via ``str(...)`` — matching upstream's
        Java string concatenation which calls ``toString()`` on the
        underlying ``COSBase``.
        """
        attrs = ", ".join(
            f"{name}={self.get_attribute_value(name)}"
            for name in self.get_attribute_names()
        )
        return f"{super().__str__()}, attributes={{{attrs}}}"

    def __repr__(self) -> str:
        attrs = ", ".join(
            f"{name}={self.get_attribute_value(name)!r}"
            for name in self.get_attribute_names()
        )
        return f"{super().__repr__()}, attributes={{{attrs}}}"


__all__ = ["PDDefaultAttributeObject"]
