from __future__ import annotations

import datetime as _dt
import re
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


# PDF 32000-1:2008 §7.9.4 date string ``D:YYYYMMDDHHmmSSOHH'mm'``.
# Keep this regex local — duplicated from PDDocumentInformation deliberately
# so the filespecification module stays self-contained (no upward import into
# pdmodel root).
_PDF_DATE_RE = re.compile(
    r"^D?:?"
    r"(?P<year>\d{4})"
    r"(?P<month>\d{2})?"
    r"(?P<day>\d{2})?"
    r"(?P<hour>\d{2})?"
    r"(?P<minute>\d{2})?"
    r"(?P<second>\d{2})?"
    r"(?:(?P<offsign>[Z+\-])"
    r"(?P<offhour>\d{2})?'?"
    r"(?P<offminute>\d{2})?'?)?"
    r"$"
)


def _parse_pdf_date(value: str) -> _dt.datetime | None:
    if not value:
        return None
    m = _PDF_DATE_RE.match(value.strip())
    if m is None:
        return None
    year = int(m.group("year"))
    month = int(m.group("month") or 1)
    day = int(m.group("day") or 1)
    hour = int(m.group("hour") or 0)
    minute = int(m.group("minute") or 0)
    second = int(m.group("second") or 0)
    sign = m.group("offsign")
    if sign is None or sign == "Z":
        tz: _dt.tzinfo = _dt.timezone.utc
    else:
        off_hour = int(m.group("offhour") or 0)
        off_minute = int(m.group("offminute") or 0)
        delta = _dt.timedelta(hours=off_hour, minutes=off_minute)
        if sign == "-":
            delta = -delta
        tz = _dt.timezone(delta)
    try:
        return _dt.datetime(year, month, day, hour, minute, second, tzinfo=tz)
    except ValueError:
        return None


def _format_pdf_date(value: _dt.datetime) -> str:
    base = value.strftime("D:%Y%m%d%H%M%S")
    offset = value.utcoffset()
    if offset is None:
        return base + "Z00'00'"
    total_seconds = int(offset.total_seconds())
    if total_seconds == 0:
        return base + "Z00'00'"
    sign = "+" if total_seconds > 0 else "-"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{base}{sign}{hours:02d}'{minutes:02d}'"


def _get_or_create_dict(parent: COSDictionary, key: COSName) -> COSDictionary:
    inner = parent.get_dictionary_object(key)
    if isinstance(inner, COSDictionary):
        return inner
    fresh = COSDictionary()
    parent.set_item(key, fresh)
    return fresh


def _get_embedded_string(
    parent: COSDictionary, outer: COSName, inner: COSName
) -> str | None:
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


class PDEmbeddedFile(PDStream):
    """An embedded file stream within a file specification (``/EF``).
    Mirrors PDFBox ``PDEmbeddedFile``.

    Date getters return timezone-aware ``datetime`` values parsed from the
    PDF date string form (``D:YYYYMMDDHHmmSSOHH'mm'``). Setters accept either
    ``datetime`` (formatted) or ``str`` (written verbatim — useful when the
    caller already has a PDF-formatted date) or ``None`` (clears the entry).
    """

    def __init__(
        self,
        stream_or_document: COSStream | object | None = None,
        input_data: bytes | bytearray | memoryview | BinaryIO | None = None,
        filter_name: COSName | None = None,
    ) -> None:
        if isinstance(stream_or_document, COSStream):
            super().__init__(stream_or_document)
            # Existing stream - preserve its /Type as-is.
            return
        # Otherwise treat as document (or None) + optional input bytes.
        super().__init__(stream_or_document, input_data, filter_name)
        self.get_cos_object().set_item(_TYPE, _EMBEDDED_FILE)

    # ---------- internal helpers ----------

    def _params_dict(self) -> COSDictionary | None:
        params = self.get_cos_object().get_dictionary_object(_PARAMS)
        if isinstance(params, COSDictionary):
            return params
        return None

    def _ensure_params_dict(self) -> COSDictionary:
        return _get_or_create_dict(self.get_cos_object(), _PARAMS)

    # ---------- /Subtype (mime type, e.g. "application/pdf") ----------

    def get_subtype(self) -> str | None:
        return self.get_cos_object().get_name(_SUBTYPE)

    def set_subtype(self, mime_type: str | None) -> None:
        cos = self.get_cos_object()
        if mime_type is None:
            cos.remove_item(_SUBTYPE)
            return
        cos.set_name(_SUBTYPE, mime_type)

    # ---------- /Params/Size ----------

    def get_size(self) -> int | None:
        params = self._params_dict()
        if params is None:
            return None
        v = params.get_dictionary_object(_SIZE)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_size(self, size: int | None) -> None:
        if size is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(_SIZE)
            return
        self._ensure_params_dict().set_item(_SIZE, COSInteger.get(int(size)))

    # ---------- /Params/CreationDate ----------

    def get_creation_date(self) -> _dt.datetime | None:
        params = self._params_dict()
        if params is None:
            return None
        raw = params.get_string(_CREATION_DATE)
        return _parse_pdf_date(raw) if raw is not None else None

    def set_creation_date(self, d: _dt.datetime | str | None) -> None:
        self._set_date(_CREATION_DATE, d)

    # ---------- /Params/ModDate ----------

    def get_mod_date(self) -> _dt.datetime | None:
        params = self._params_dict()
        if params is None:
            return None
        raw = params.get_string(_MOD_DATE)
        return _parse_pdf_date(raw) if raw is not None else None

    def set_mod_date(self, d: _dt.datetime | str | None) -> None:
        self._set_date(_MOD_DATE, d)

    def _set_date(self, key: COSName, d: _dt.datetime | str | None) -> None:
        if d is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(key)
            return
        if isinstance(d, _dt.datetime):
            text = _format_pdf_date(d)
        else:
            text = d
        self._ensure_params_dict().set_item(key, COSString(text))

    # ---------- /Params/CheckSum (16-byte MD5) ----------

    def get_check_sum(self) -> bytes | None:
        params = self._params_dict()
        if params is None:
            return None
        v = params.get_dictionary_object(_CHECK_SUM)
        if isinstance(v, COSString):
            return v.get_bytes()
        return None

    def set_check_sum(self, checksum: bytes | bytearray | memoryview | None) -> None:
        if checksum is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(_CHECK_SUM)
            return
        # CheckSum is a byte string per PDF spec; the writer will emit it in
        # hex form when bytes contain non-printable values.
        cs = COSString(bytes(checksum))
        cs.set_force_hex_form(True)
        self._ensure_params_dict().set_item(_CHECK_SUM, cs)

    # ---------- /Params/Creator ----------

    def get_creator(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return params.get_string(_CREATOR)

    def set_creator(self, creator: str | None) -> None:
        if creator is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(_CREATOR)
            return
        self._ensure_params_dict().set_string(_CREATOR, creator)

    # ---------- /Params/Mac/{Subtype,Creator,ResFork} ----------

    def get_mac_subtype(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return _get_embedded_string(params, _MAC, _SUBTYPE)

    def set_mac_subtype(self, mac_subtype: str | None) -> None:
        params = self._params_dict() if mac_subtype is None else self._ensure_params_dict()
        if params is not None:
            _set_embedded_string(params, _MAC, _SUBTYPE, mac_subtype)

    def get_mac_creator(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return _get_embedded_string(params, _MAC, _CREATOR)

    def set_mac_creator(self, mac_creator: str | None) -> None:
        params = self._params_dict() if mac_creator is None else self._ensure_params_dict()
        if params is not None:
            _set_embedded_string(params, _MAC, _CREATOR, mac_creator)

    def get_mac_resource_fork(self) -> COSStream | None:
        params = self._params_dict()
        if params is None:
            return None
        mac = params.get_dictionary_object(_MAC)
        if not isinstance(mac, COSDictionary):
            return None
        rf = mac.get_dictionary_object(_RES_FORK)
        if isinstance(rf, COSStream):
            return rf
        return None

    def set_mac_resource_fork(self, stream: COSStream | None) -> None:
        if stream is None:
            params = self._params_dict()
            if params is None:
                return
            mac = params.get_dictionary_object(_MAC)
            if isinstance(mac, COSDictionary):
                mac.remove_item(_RES_FORK)
            return
        params = self._ensure_params_dict()
        mac = _get_or_create_dict(params, _MAC)
        mac.set_item(_RES_FORK, stream)

    # Upstream Java method names ``getMacResFork`` / ``setMacResFork`` —
    # mechanical snake_case aliases delegating to the resource-fork accessors.
    # The parameter type stays ``COSStream`` (deviation noted in CHANGES.md);
    # upstream Java types it as ``String`` but the PDF spec defines /ResFork
    # as a stream entry.
    def get_mac_res_fork(self) -> COSStream | None:
        return self.get_mac_resource_fork()

    def set_mac_res_fork(self, stream: COSStream | None) -> None:
        self.set_mac_resource_fork(stream)


__all__ = ["PDEmbeddedFile"]
