from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_O: COSName = COSName.get_pdf_name("O")


class PDAttributeObject:
    """
    A structure-element attribute object (``/A`` entry value). Mirrors
    PDFBox ``PDAttributeObject``.

    Lite surface: typed owner subclasses (``PDLayoutAttributeObject``,
    ``PDListAttributeObject``, ``PDPrintFieldAttributeObject``,
    ``PDTableAttributeObject``, ``PDExportFormatAttributeObject``,
    ``PDUserAttributeObject``, ``PDDefaultAttributeObject``) and the
    structure-element change-notification plumbing are deferred. The
    factory currently wraps every dictionary as a generic
    ``PDAttributeObject``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    @staticmethod
    def create(dictionary: COSDictionary) -> PDAttributeObject:
        if not isinstance(dictionary, COSDictionary):
            raise TypeError(
                f"PDAttributeObject.create expects COSDictionary, got "
                f"{type(dictionary).__name__}"
            )
        return PDAttributeObject(dictionary)

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /O owner ----------

    def get_owner(self) -> str | None:
        return self._dictionary.get_name(_O)

    def set_owner(self, owner: str) -> None:
        self._dictionary.set_name(_O, owner)

    def is_empty(self) -> bool:
        return self._dictionary.size() == 1 and self.get_owner() is not None

    def __repr__(self) -> str:
        return f"O={self.get_owner()}"


__all__ = ["PDAttributeObject"]
