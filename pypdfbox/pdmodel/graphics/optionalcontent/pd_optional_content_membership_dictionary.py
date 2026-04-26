from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from ..pd_property_list import PDPropertyList
from .pd_optional_content_group import PDOptionalContentGroup

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OCMD: COSName = COSName.get_pdf_name("OCMD")
_OCGS: COSName = COSName.get_pdf_name("OCGs")
_P: COSName = COSName.get_pdf_name("P")
_VE: COSName = COSName.get_pdf_name("VE")
_ANY_ON: COSName = COSName.get_pdf_name("AnyOn")

_VALID_POLICIES: frozenset[str] = frozenset(
    {"AllOn", "AnyOn", "AnyOff", "AllOff"}
)


class PDOptionalContentMembershipDictionary(PDPropertyList):
    """Optional content membership dictionary (OCMD).

    Mirrors PDFBox ``PDOptionalContentMembershipDictionary``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            super().__init__()
            self._dict.set_item(_TYPE, _OCMD)
            return
        existing = dictionary.get_dictionary_object(_TYPE)
        if existing is not None and existing != _OCMD:
            raise ValueError(f"Provided dictionary is not of type '{_OCMD}'")
        super().__init__(dictionary)
        if existing is None:
            self._dict.set_item(_TYPE, _OCMD)

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /OCGs ----------

    def get_o_cgs(self) -> list[PDOptionalContentGroup]:
        """Return the referenced optional content groups, never ``None``.

        /OCGs may be either a single OCG dictionary or a COSArray of them.
        Non-OCG dictionaries (e.g. nested OCMDs) are skipped — this lite
        port returns only ``PDOptionalContentGroup`` instances.
        """
        base = self._dict.get_dictionary_object(_OCGS)
        if base is None:
            return []
        if isinstance(base, COSDictionary):
            wrapped = PDPropertyList.create(base)
            if isinstance(wrapped, PDOptionalContentGroup):
                return [wrapped]
            return []
        if isinstance(base, COSArray):
            result: list[PDOptionalContentGroup] = []
            for i in range(base.size()):
                elem = base.get_object(i)
                if isinstance(elem, COSDictionary):
                    wrapped = PDPropertyList.create(elem)
                    if isinstance(wrapped, PDOptionalContentGroup):
                        result.append(wrapped)
            return result
        return []

    def set_o_cgs(
        self,
        ocgs: list[PDOptionalContentGroup | COSDictionary],
    ) -> None:
        """Write /OCGs as a COSArray.

        Accepts ``PDOptionalContentGroup`` wrappers or raw ``COSDictionary``
        entries.
        """
        arr = COSArray()
        for item in ocgs:
            if isinstance(item, PDOptionalContentGroup):
                arr.add(item.get_cos_object())
            elif isinstance(item, COSDictionary):
                arr.add(item)
            else:
                raise TypeError(
                    "ocgs entries must be PDOptionalContentGroup or "
                    f"COSDictionary, got {type(item).__name__}"
                )
        self._dict.set_item(_OCGS, arr)

    # ---------- /P (visibility policy) ----------

    def get_visibility_policy(self) -> str:
        """Return /P name. Defaults to "AnyOn" per PDF 1.7 §8.11.2.2."""
        value = self._dict.get_dictionary_object(_P)
        if isinstance(value, COSName):
            return value.name
        return _ANY_ON.name

    def set_visibility_policy(self, policy: str) -> None:
        if policy not in _VALID_POLICIES:
            raise ValueError(
                "visibility_policy must be one of "
                f"{sorted(_VALID_POLICIES)}, got {policy!r}"
            )
        self._dict.set_item(_P, COSName.get_pdf_name(policy))

    # ---------- /VE (visibility expression) ----------

    def get_visibility_expression(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_VE)
        return value if isinstance(value, COSArray) else None

    def set_visibility_expression(self, ve: COSArray | None) -> None:
        if ve is None:
            self._dict.remove_item(_VE)
            return
        if not isinstance(ve, COSArray):
            raise TypeError(
                "visibility_expression must be COSArray or None, "
                f"got {type(ve).__name__}"
            )
        self._dict.set_item(_VE, ve)


__all__ = ["PDOptionalContentMembershipDictionary"]
