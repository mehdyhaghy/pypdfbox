from __future__ import annotations

from typing import BinaryIO

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.pd_stream import PDStream

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_PARAMS: COSName = COSName.PARAMS  # type: ignore[attr-defined]
_SIZE: COSName = COSName.SIZE  # type: ignore[attr-defined]
_EMBEDDED_FILE: COSName = COSName.get_pdf_name("EmbeddedFile")
_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")
_MOD_DATE: COSName = COSName.get_pdf_name("ModDate")
_CHECK_SUM: COSName = COSName.get_pdf_name("CheckSum")
_MAC: COSName = COSName.get_pdf_name("Mac")
_CREATOR: COSName = COSName.get_pdf_name("Creator")
_RES_FORK: COSName = COSName.get_pdf_name("ResFork")


def _get_or_create_dict(parent: COSDictionary, key: COSName) -> COSDictionary:
    inner = parent.get_dictionary_object(key)
    if isinstance(inner, COSDictionary):
        return inner
    fresh = COSDictionary()
    parent.set_item(key, fresh)
    return fresh


def _get_embedded_string(parent: COSDictionary, outer: COSName, inner: COSName) -> str | None:
    nested = parent.get_dictionary_object(outer)
    if isinstance(nested, COSDictionary):
        return nested.get_string(inner)
    return None


def _set_embedded_string(
    parent: COSDictionary, outer: COSName, inner: COSName, value: str | None
) -> None:
    if value is None:
        nested = parent.get_dictionary_object(outer)
        if isinstance(nested, COSDictionary):
            nested.remove_item(inner)
        return
    nested = _get_or_create_dict(parent, outer)
    nested.set_string(inner, value)


def _get_embedded_int(parent: COSDictionary, outer: COSName, inner: COSName) -> int:
    nested = parent.get_dictionary_object(outer)
    if isinstance(nested, COSDictionary):
        return nested.get_int(inner, -1)
    return -1


def _set_embedded_int(
    parent: COSDictionary, outer: COSName, inner: COSName, value: int
) -> None:
    nested = _get_or_create_dict(parent, outer)
    nested.set_item(inner, COSInteger.get(int(value)))


class PDEmbeddedFile(PDStream):
    """An embedded file stream within a file specification (``/EF``).
    Mirrors PDFBox ``PDEmbeddedFile``.

    Date getters/setters operate on the raw ``COSString`` form
    (PDF date string, e.g. ``D:YYYYMMDDHHmmSS``) — Python ``datetime``
    parsing/formatting will be added when the cos date helper lands.
    """

    def __init__(
        self,
        stream_or_document: COSStream | object | None = None,
        input_data: bytes | bytearray | memoryview | BinaryIO | None = None,
        filter_name: COSName | None = None,
    ) -> None:
        if isinstance(stream_or_document, COSStream):
            super().__init__(stream_or_document)
            # Existing stream — preserve its /Type as-is.
            return
        # Otherwise treat as document (or None) + optional input bytes.
        super().__init__(stream_or_document, input_data, filter_name)
        self.get_cos_object().set_item(_TYPE, _EMBEDDED_FILE)

    # ---------- /Subtype (mime type) ----------

    def set_subtype(self, mime_type: str) -> None:
        self.get_cos_object().set_name(_SUBTYPE, mime_type)

    def get_subtype(self) -> str | None:
        return self.get_cos_object().get_name(_SUBTYPE)

    # ---------- /Params/Size ----------

    def get_size(self) -> int:
        return _get_embedded_int(self.get_cos_object(), _PARAMS, _SIZE)

    def set_size(self, size: int) -> None:
        _set_embedded_int(self.get_cos_object(), _PARAMS, _SIZE, size)

    # ---------- /Params/CreationDate, /Params/ModDate (raw COSString form) ----------

    def get_creation_date(self) -> str | None:
        return _get_embedded_string(self.get_cos_object(), _PARAMS, _CREATION_DATE)

    def set_creation_date(self, creation: str | None) -> None:
        _set_embedded_string(self.get_cos_object(), _PARAMS, _CREATION_DATE, creation)

    def get_mod_date(self) -> str | None:
        return _get_embedded_string(self.get_cos_object(), _PARAMS, _MOD_DATE)

    def set_mod_date(self, mod: str | None) -> None:
        _set_embedded_string(self.get_cos_object(), _PARAMS, _MOD_DATE, mod)

    # ---------- /Params/CheckSum ----------

    def get_check_sum(self) -> str | None:
        return _get_embedded_string(self.get_cos_object(), _PARAMS, _CHECK_SUM)

    def set_check_sum(self, checksum: str | None) -> None:
        cos = self.get_cos_object()
        if checksum is None:
            params = cos.get_dictionary_object(_PARAMS)
            if isinstance(params, COSDictionary):
                params.remove_item(_CHECK_SUM)
            return
        params = _get_or_create_dict(cos, _PARAMS)
        # CheckSum is a byte string per PDF spec — use COSString to avoid
        # accidental name encoding.
        params.set_item(_CHECK_SUM, COSString(checksum))

    # ---------- /Params/Mac/{Subtype,Creator,ResFork} ----------

    def _params_dict(self) -> COSDictionary | None:
        params = self.get_cos_object().get_dictionary_object(_PARAMS)
        if isinstance(params, COSDictionary):
            return params
        return None

    def get_mac_subtype(self) -> str | None:
        params = self._params_dict()
        return _get_embedded_string(params, _MAC, _SUBTYPE) if params is not None else None

    def set_mac_subtype(self, mac_subtype: str | None) -> None:
        params = self._params_dict()
        if params is None and mac_subtype is not None:
            params = _get_or_create_dict(self.get_cos_object(), _PARAMS)
        if params is not None:
            _set_embedded_string(params, _MAC, _SUBTYPE, mac_subtype)

    def get_mac_creator(self) -> str | None:
        params = self._params_dict()
        return _get_embedded_string(params, _MAC, _CREATOR) if params is not None else None

    def set_mac_creator(self, mac_creator: str | None) -> None:
        params = self._params_dict()
        if params is None and mac_creator is not None:
            params = _get_or_create_dict(self.get_cos_object(), _PARAMS)
        if params is not None:
            _set_embedded_string(params, _MAC, _CREATOR, mac_creator)

    def get_mac_resource_fork(self) -> str | None:
        params = self._params_dict()
        return _get_embedded_string(params, _MAC, _RES_FORK) if params is not None else None

    def set_mac_resource_fork(self, mac_res_fork: str | None) -> None:
        params = self._params_dict()
        if params is None and mac_res_fork is not None:
            params = _get_or_create_dict(self.get_cos_object(), _PARAMS)
        if params is not None:
            _set_embedded_string(params, _MAC, _RES_FORK, mac_res_fork)


__all__ = ["PDEmbeddedFile"]
