from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSObject

from .pd_attribute_object import PDAttributeObject


class PDStructureClassMap:
    """
    Typed wrapper for the ``/StructTreeRoot/ClassMap`` dictionary
    (PDF 32000-1:2008 § 14.7.3 ``ClassMap``).

    Maps a class name to a single :class:`PDAttributeObject` or to a list of
    :class:`PDAttributeObject` instances. Mirrors the inline ``getClassMap``
    / ``setClassMap`` behavior on upstream PDFBox ``PDStructureTreeRoot``;
    no standalone Java class exists upstream — we introduce this typed
    wrapper for symmetry with :class:`PDMarkInfo` / :class:`PDStructureNode`
    wrappers.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_class_definitions(self) -> dict[str, list[PDAttributeObject]]:
        """Return every class definition keyed by class name.

        Single-attribute entries are normalized to a one-element list so
        callers can iterate uniformly. Mirrors upstream's ``getClassMap``
        return shape but always wraps single dictionaries in a list."""
        out: dict[str, list[PDAttributeObject]] = {}
        for key, base in self._dictionary.entry_set():
            attrs = self._coerce_to_attribute_list(base)
            if attrs is not None:
                out[key.get_name()] = attrs
        return out

    def get_class(self, name: str) -> list[PDAttributeObject]:
        """Return the list of :class:`PDAttributeObject` for ``name``,
        or an empty list when the entry is absent.

        Single-attribute entries are wrapped in a one-element list."""
        base = self._dictionary.get_dictionary_object(name)
        if base is None:
            return []
        attrs = self._coerce_to_attribute_list(base)
        return attrs if attrs is not None else []

    def add_class(
        self, name: str, attribute: PDAttributeObject | Iterable[PDAttributeObject]
    ) -> None:
        """Add a single attribute (or iterable of attributes) under ``name``.

        If ``name`` already has entries, the new attribute(s) are appended,
        promoting a single-attribute entry into a ``COSArray``."""
        if attribute is None:
            raise TypeError("attribute must not be None")
        new_items: list[PDAttributeObject]
        if isinstance(attribute, PDAttributeObject):
            new_items = [attribute]
        else:
            new_items = list(attribute)
            for item in new_items:
                if not isinstance(item, PDAttributeObject):
                    raise TypeError(
                        f"add_class entries must be PDAttributeObject, got "
                        f"{type(item).__name__}"
                    )
        existing = self._dictionary.get_dictionary_object(name)
        if existing is None:
            if len(new_items) == 1:
                self._dictionary.set_item(name, new_items[0].get_cos_object())
            else:
                arr = COSArray()
                for attr in new_items:
                    arr.add(attr.get_cos_object())
                self._dictionary.set_item(name, arr)
            return
        if isinstance(existing, COSArray):
            for attr in new_items:
                existing.add(attr.get_cos_object())
            return
        # Existing single COSDictionary — promote to COSArray.
        arr = COSArray()
        arr.add(existing)
        for attr in new_items:
            arr.add(attr.get_cos_object())
        self._dictionary.set_item(name, arr)

    def remove_class(self, name: str) -> None:
        """Remove the entry for ``name``. No-op when absent."""
        self._dictionary.remove_item(name)

    def is_empty(self) -> bool:
        return self._dictionary.is_empty()

    def __repr__(self) -> str:
        return f"PDStructureClassMap(size={self._dictionary.size()})"

    @staticmethod
    def _coerce_to_attribute_list(
        base: COSBase | None,
    ) -> list[PDAttributeObject] | None:
        if isinstance(base, COSObject):
            base = base.get_object()
        if isinstance(base, COSDictionary):
            return [PDAttributeObject.create(base)]
        if isinstance(base, COSArray):
            attrs: list[PDAttributeObject] = []
            for i in range(base.size()):
                item = base.get_object(i)
                if isinstance(item, COSDictionary):
                    attrs.append(PDAttributeObject.create(item))
            return attrs
        return None


__all__ = ["PDStructureClassMap"]
