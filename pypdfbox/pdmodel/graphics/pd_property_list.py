from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OCG: COSName = COSName.get_pdf_name("OCG")
_OCMD: COSName = COSName.get_pdf_name("OCMD")


class PDPropertyList:
    """A property list dictionary used in marked content.

    Mirrors PDFBox ``PDPropertyList``. Concrete subclasses include
    ``PDOptionalContentGroup`` (/Type /OCG) and
    ``PDOptionalContentMembershipDictionary`` (/Type /OCMD).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    @staticmethod
    def create(dictionary: COSDictionary | None) -> PDPropertyList | None:
        """Dispatch a raw COSDictionary to the appropriate concrete subclass.

        Returns ``None`` when ``dictionary`` is ``None`` or carries no /Type
        entry recognised here. Upstream returns a bare ``PDPropertyList`` for
        unknown types; we deliberately return ``None`` (the task spec).
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
        return None

    def get_cos_object(self) -> COSDictionary:
        return self._dict


__all__ = ["PDPropertyList"]
