from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OCG: COSName = COSName.get_pdf_name("OCG")
_OCMD: COSName = COSName.get_pdf_name("OCMD")


class PDPropertyList:
    """A property list dictionary used in marked content.

    Mirrors upstream
    ``org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList``.
    Concrete subclasses include :class:`PDOptionalContentGroup` (``/Type /OCG``)
    and :class:`PDOptionalContentMembershipDictionary` (``/Type /OCMD``).

    Note: pypdfbox keeps the implementation file under ``pdmodel.graphics``
    to avoid churn for existing callers; an upstream-named alias is also
    re-exported from
    ``pypdfbox.pdmodel.documentinterchange.markedcontent.pd_property_list``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    @staticmethod
    def create(dictionary: COSDictionary | None) -> PDPropertyList | None:
        """Dispatch a raw ``COSDictionary`` to the appropriate concrete
        subclass.

        Mirrors upstream ``PDPropertyList.create(COSDictionary)``:

        - ``/Type /OCG``  → :class:`PDOptionalContentGroup`
        - ``/Type /OCMD`` → :class:`PDOptionalContentMembershipDictionary`
        - any other ``/Type`` (or none) → bare :class:`PDPropertyList`
          wrapping the dictionary, matching upstream's "todo: more types"
          fallback. This is a behavioural fix vs. earlier pypdfbox releases
          that returned ``None`` for unknown types.

        ``None`` input still returns ``None`` — upstream would NPE on a null
        argument; the Python port is intentionally permissive here.
        """
        if dictionary is None:
            return None
        if not isinstance(dictionary, COSDictionary):
            raise TypeError(
                "PDPropertyList.create expects COSDictionary, "
                f"got {type(dictionary).__name__}"
            )
        item = dictionary.get_item(_TYPE)
        if item == _OCG:
            # local import to avoid circular dependency
            from .optionalcontent.pd_optional_content_group import (
                PDOptionalContentGroup,
            )

            return PDOptionalContentGroup(dictionary)
        if item == _OCMD:
            from .optionalcontent.pd_optional_content_membership_dictionary import (
                PDOptionalContentMembershipDictionary,
            )

            return PDOptionalContentMembershipDictionary(dictionary)
        # Unknown / missing /Type — upstream returns a bare PDPropertyList
        # wrapping the supplied dictionary. We follow.
        return PDPropertyList(dictionary)

    def get_cos_object(self) -> COSDictionary:
        return self._dict


__all__ = ["PDPropertyList"]
