from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OUTPUT_INTENT: COSName = COSName.get_pdf_name("OutputIntent")
_S: COSName = COSName.get_pdf_name("S")
_INFO: COSName = COSName.get_pdf_name("Info")
_OUTPUT_CONDITION: COSName = COSName.get_pdf_name("OutputCondition")
_OUTPUT_CONDITION_IDENTIFIER: COSName = COSName.get_pdf_name("OutputConditionIdentifier")
_REGISTRY_NAME: COSName = COSName.get_pdf_name("RegistryName")
_DEST_OUTPUT_PROFILE: COSName = COSName.get_pdf_name("DestOutputProfile")


class PDOutputIntent:
    """
    Wrapper for an ``/OutputIntent`` dictionary. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent``.

    Lite surface: ICC stream embedding via ``setData(InputStream)`` is
    deferred until ``PDColorSpace`` / ICC profile parsing lands.
    """

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        document: PDDocument | None = None,
    ) -> None:
        self._document = document
        if dictionary is None:
            dictionary = COSDictionary()
            dictionary.set_item(_TYPE, _OUTPUT_INTENT)
        elif dictionary.get_dictionary_object(_TYPE) is None:
            dictionary.set_item(_TYPE, _OUTPUT_INTENT)
        self._dictionary = dictionary

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /S (subtype) ----------

    def get_subtype(self) -> str | None:
        return self._dictionary.get_name(_S)

    def set_subtype(self, subtype: str | None) -> None:
        if subtype is None:
            self._dictionary.remove_item(_S)
            return
        self._dictionary.set_name(_S, subtype)

    # ---------- /Info ----------

    def get_info(self) -> str | None:
        return self._dictionary.get_string(_INFO)

    def set_info(self, info: str | None) -> None:
        self._dictionary.set_string(_INFO, info)

    # ---------- /OutputCondition ----------

    def get_output_condition(self) -> str | None:
        return self._dictionary.get_string(_OUTPUT_CONDITION)

    def set_output_condition(self, cond: str | None) -> None:
        self._dictionary.set_string(_OUTPUT_CONDITION, cond)

    # ---------- /OutputConditionIdentifier ----------

    def get_output_condition_identifier(self) -> str | None:
        return self._dictionary.get_string(_OUTPUT_CONDITION_IDENTIFIER)

    def set_output_condition_identifier(self, identifier: str | None) -> None:
        self._dictionary.set_string(_OUTPUT_CONDITION_IDENTIFIER, identifier)

    # ---------- /RegistryName ----------

    def get_registry_name(self) -> str | None:
        return self._dictionary.get_string(_REGISTRY_NAME)

    def set_registry_name(self, name: str | None) -> None:
        self._dictionary.set_string(_REGISTRY_NAME, name)

    # ---------- /DestOutputProfile ----------

    def get_dest_output_profile(self) -> COSBase | None:
        """Raw ``/DestOutputProfile`` ICC stream. Returns the underlying
        ``COSStream`` (no PDStream wrapping yet)."""
        return self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)

    def set_dest_output_profile(self, profile: Any) -> None:
        if profile is None:
            self._dictionary.remove_item(_DEST_OUTPUT_PROFILE)
            return
        if isinstance(profile, COSStream):
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, profile)
            return
        # PDStream-like with get_cos_object()
        cos = profile.get_cos_object() if hasattr(profile, "get_cos_object") else profile
        self._dictionary.set_item(_DEST_OUTPUT_PROFILE, cos)


__all__ = ["PDOutputIntent"]
