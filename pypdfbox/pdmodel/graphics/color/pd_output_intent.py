from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_logger = logging.getLogger(__name__)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OUTPUT_INTENT: COSName = COSName.get_pdf_name("OutputIntent")
_S: COSName = COSName.get_pdf_name("S")
_INFO: COSName = COSName.get_pdf_name("Info")
_OUTPUT_CONDITION: COSName = COSName.get_pdf_name("OutputCondition")
_OUTPUT_CONDITION_IDENTIFIER: COSName = COSName.get_pdf_name("OutputConditionIdentifier")
_REGISTRY_NAME: COSName = COSName.get_pdf_name("RegistryName")
_DEST_OUTPUT_PROFILE: COSName = COSName.get_pdf_name("DestOutputProfile")
_N: COSName = COSName.get_pdf_name("N")

# ICC.1:2010 §7.2 table 17 — bytes 36..40 of an ICC profile header carry
# the magic "acsp" signature. Used for a soft (warn-only) sniff in set_data.
_ICC_MAGIC_OFFSET = 36
_ICC_MAGIC = b"acsp"


class PDOutputIntent:
    """
    Wrapper for an ``/OutputIntent`` dictionary. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent``.

    ``/DestOutputProfile`` is exposed as a typed :class:`PDStream`. Raw
    ICC bytes can be embedded via :meth:`set_data`.
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

    def get_dest_output_profile(self) -> PDStream | None:
        """``/DestOutputProfile`` ICC profile stream as a typed
        :class:`PDStream`, or ``None`` when absent."""
        cos = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if cos is None:
            return None
        if not isinstance(cos, COSStream):
            raise TypeError(
                f"unexpected /DestOutputProfile type: {type(cos).__name__}"
            )
        return PDStream(cos)

    def get_dest_output_profile_cos(self) -> COSStream | None:
        """Back-compat raw accessor: returns the underlying
        ``COSStream`` (no ``PDStream`` wrapping)."""
        cos = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if cos is None:
            return None
        if not isinstance(cos, COSStream):
            raise TypeError(
                f"unexpected /DestOutputProfile type: {type(cos).__name__}"
            )
        return cos

    def set_dest_output_profile(
        self, profile: PDStream | COSStream | None
    ) -> None:
        """Set ``/DestOutputProfile``. Accepts ``None`` (removes the
        entry), a typed :class:`PDStream`, or a raw ``COSStream``."""
        if profile is None:
            self._dictionary.remove_item(_DEST_OUTPUT_PROFILE)
            return
        if isinstance(profile, COSStream):
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, profile)
            return
        if isinstance(profile, PDStream):
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, profile.get_cos_object())
            return
        raise TypeError(
            f"set_dest_output_profile expected PDStream, COSStream, or None; "
            f"got {type(profile).__name__}"
        )

    def set_data(self, profile_bytes: bytes, num_components: int = 3) -> None:
        """Embed raw ICC profile bytes into ``/DestOutputProfile`` and
        record ``/N`` (number of components — required per PDF 32000-1
        Table 401, defaults to 3 for RGB).

        Reuses the existing ``/DestOutputProfile`` stream when present so
        any indirect-object identity is preserved; otherwise creates a
        fresh one.

        The bytes are sniffed for the ICC ``acsp`` magic at offset 36
        (ICC.1:2010 §7.2 table 17). If absent, a warning is logged but
        the bytes are still written — some legacy ICC profiles omit the
        marker."""
        if (
            len(profile_bytes) < _ICC_MAGIC_OFFSET + len(_ICC_MAGIC)
            or profile_bytes[_ICC_MAGIC_OFFSET : _ICC_MAGIC_OFFSET + len(_ICC_MAGIC)]
            != _ICC_MAGIC
        ):
            _logger.warning(
                "ICC profile bytes lack the 'acsp' signature at offset %d; "
                "embedding anyway",
                _ICC_MAGIC_OFFSET,
            )

        existing = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if isinstance(existing, COSStream):
            cos_stream = existing
        else:
            cos_stream = COSStream()
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, cos_stream)
        cos_stream.set_raw_data(profile_bytes)
        cos_stream.set_int(_N, int(num_components))


__all__ = ["PDOutputIntent"]
