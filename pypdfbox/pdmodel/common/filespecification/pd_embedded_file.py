from __future__ import annotations

import datetime as _dt
import re
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

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
        tz: _dt.tzinfo = _dt.UTC
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

    #: Value written to the ``/Type`` entry of an embedded file stream
    #: dictionary. Mirrors upstream ``COSName.EMBEDDED_FILE``.
    EMBEDDED_FILE: str = "EmbeddedFile"

    #: Name of the nested dictionary holding optional file parameters
    #: (Size, CreationDate, ModDate, CheckSum, Mac sub-dict). PDF 32000-1
    #: §7.11.3, Table 46.
    PARAMS: str = "Params"

    #: Name of the nested Mac-platform sub-dictionary inside ``/Params``
    #: (legacy macOS metadata: Subtype, Creator, ResFork). PDF 32000-1
    #: §7.11.3, Table 46.
    MAC: str = "Mac"

    def __init__(
        self,
        stream_or_document: COSStream | COSDocument | PDDocument | None = None,
        input_data: bytes | bytearray | memoryview | BinaryIO | None = None,
        filter_name: COSName | COSArray | None = None,
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

    def has_params(self) -> bool:
        """Return ``True`` when this embedded-file stream carries a
        ``/Params`` sub-dictionary. Useful to short-circuit access to
        Size / CreationDate / ModDate / CheckSum without forcing creation
        of an empty dictionary.

        Not part of the upstream Java surface — pythonic predicate sugar.
        """
        return self._params_dict() is not None

    def clear_params(self) -> None:
        """Remove the ``/Params`` sub-dictionary. No-op if absent."""
        self.get_cos_object().remove_item(_PARAMS)

    def has_mac_info(self) -> bool:
        """Return ``True`` when the embedded file carries a ``/Params/Mac``
        sub-dictionary (legacy macOS metadata: Subtype/Creator/ResFork).

        Not part of the upstream Java surface — pythonic predicate sugar.
        """
        params = self._params_dict()
        if params is None:
            return False
        mac = params.get_dictionary_object(_MAC)
        return isinstance(mac, COSDictionary)

    def clear_mac_info(self) -> None:
        """Remove the ``/Params/Mac`` sub-dictionary. No-op if absent."""
        params = self._params_dict()
        if params is not None:
            params.remove_item(_MAC)

    # ---------- /Subtype (mime type, e.g. "application/pdf") ----------

    def get_subtype(self) -> str | None:
        return self.get_cos_object().get_name(_SUBTYPE)

    def set_subtype(self, mime_type: str | None) -> None:
        cos = self.get_cos_object()
        if mime_type is None:
            cos.remove_item(_SUBTYPE)
            return
        cos.set_name(_SUBTYPE, mime_type)

    def has_subtype(self) -> bool:
        """Return ``True`` when ``/Subtype`` is present as a PDF name."""
        return self.get_cos_object().get_name(_SUBTYPE) is not None

    def clear_subtype(self) -> None:
        """Remove ``/Subtype``. Equivalent to ``set_subtype(None)``."""
        self.set_subtype(None)

    def is_subtype(self, mime_type: str | None) -> bool:
        """Return ``True`` when the ``/Subtype`` entry equals ``mime_type``
        (case-insensitive ASCII comparison). Returns ``False`` when either
        side is ``None`` or the entry is absent.

        Mime type matching is case-insensitive per RFC 2045 §5.1, so
        ``application/pdf`` and ``Application/PDF`` are equivalent.

        Not part of the upstream Java surface — pythonic predicate sugar
        avoiding callers having to ``.lower()`` the result of
        :meth:`get_subtype` themselves.
        """
        if mime_type is None:
            return False
        current = self.get_subtype()
        if current is None:
            return False
        return current.casefold() == mime_type.casefold()

    # ---------- /Params/Size ----------

    def get_size(self) -> int | None:
        params = self._params_dict()
        if params is None:
            return None
        v = params.get_dictionary_object(_SIZE)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def has_size(self) -> bool:
        """Return ``True`` when ``/Params/Size`` is present as an integer."""
        return self.get_size() is not None

    def set_size(self, size: int | None) -> None:
        if size is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(_SIZE)
            return
        self._ensure_params_dict().set_item(_SIZE, COSInteger.get(int(size)))

    def clear_size(self) -> None:
        """Remove ``/Params/Size``. No-op if absent."""
        self.set_size(None)

    # ---------- /Params/CreationDate ----------

    def get_creation_date(self) -> _dt.datetime | None:
        params = self._params_dict()
        if params is None:
            return None
        raw = params.get_string(_CREATION_DATE)
        return _parse_pdf_date(raw) if raw is not None else None

    def has_creation_date(self) -> bool:
        """Return ``True`` when ``/Params/CreationDate`` is present."""
        params = self._params_dict()
        return params is not None and params.contains_key(_CREATION_DATE)

    def set_creation_date(self, d: _dt.datetime | str | None) -> None:
        self._set_date(_CREATION_DATE, d)

    def clear_creation_date(self) -> None:
        """Remove ``/Params/CreationDate``. No-op if absent."""
        self.set_creation_date(None)

    # ---------- /Params/ModDate ----------

    def get_mod_date(self) -> _dt.datetime | None:
        params = self._params_dict()
        if params is None:
            return None
        raw = params.get_string(_MOD_DATE)
        return _parse_pdf_date(raw) if raw is not None else None

    def has_mod_date(self) -> bool:
        """Return ``True`` when ``/Params/ModDate`` is present."""
        params = self._params_dict()
        return params is not None and params.contains_key(_MOD_DATE)

    def set_mod_date(self, d: _dt.datetime | str | None) -> None:
        self._set_date(_MOD_DATE, d)

    def clear_mod_date(self) -> None:
        """Remove ``/Params/ModDate``. No-op if absent."""
        self.set_mod_date(None)

    def _set_date(self, key: COSName, d: _dt.datetime | str | None) -> None:
        if d is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(key)
            return
        text = _format_pdf_date(d) if isinstance(d, _dt.datetime) else d
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

    def has_check_sum(self) -> bool:
        """Return ``True`` when ``/Params/CheckSum`` is present as a string."""
        return self.get_check_sum() is not None

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

    def clear_check_sum(self) -> None:
        """Remove ``/Params/CheckSum``. No-op if absent."""
        self.set_check_sum(None)

    # Upstream's ``getCheckSum()`` / ``setCheckSum(String)`` are typed as
    # ``String`` not ``byte[]``, so the string-form aliases below preserve
    # the verbatim Java surface. They round-trip the checksum as a textual
    # COSString — useful when callers already have a textual representation.
    # The byte-form ``get_check_sum`` / ``set_check_sum`` above remains the
    # primary API in pypdfbox (a deviation noted in CHANGES.md).

    def get_check_sum_string(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return params.get_string(_CHECK_SUM)

    def set_check_sum_string(self, checksum: str | None) -> None:
        if checksum is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(_CHECK_SUM)
            return
        self._ensure_params_dict().set_string(_CHECK_SUM, checksum)

    # ---------- /Params/Creator ----------

    def get_creator(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return params.get_string(_CREATOR)

    def has_creator(self) -> bool:
        """Return ``True`` when ``/Params/Creator`` is present."""
        params = self._params_dict()
        return params is not None and params.contains_key(_CREATOR)

    def set_creator(self, creator: str | None) -> None:
        if creator is None:
            params = self._params_dict()
            if params is not None:
                params.remove_item(_CREATOR)
            return
        self._ensure_params_dict().set_string(_CREATOR, creator)

    def clear_creator(self) -> None:
        """Remove ``/Params/Creator``. No-op if absent."""
        self.set_creator(None)

    # ---------- /Params/Mac/{Subtype,Creator,ResFork} ----------

    def get_mac_subtype(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return _get_embedded_string(params, _MAC, _SUBTYPE)

    def has_mac_subtype(self) -> bool:
        """Return ``True`` when ``/Params/Mac/Subtype`` is present."""
        params = self._params_dict()
        if params is None:
            return False
        mac = params.get_dictionary_object(_MAC)
        return isinstance(mac, COSDictionary) and mac.contains_key(_SUBTYPE)

    def set_mac_subtype(self, mac_subtype: str | None) -> None:
        params = (
            self._params_dict()
            if mac_subtype is None
            else self._ensure_params_dict()
        )
        if params is not None:
            _set_embedded_string(params, _MAC, _SUBTYPE, mac_subtype)

    def clear_mac_subtype(self) -> None:
        """Remove ``/Params/Mac/Subtype``. No-op if absent."""
        self.set_mac_subtype(None)

    def get_mac_creator(self) -> str | None:
        params = self._params_dict()
        if params is None:
            return None
        return _get_embedded_string(params, _MAC, _CREATOR)

    def has_mac_creator(self) -> bool:
        """Return ``True`` when ``/Params/Mac/Creator`` is present."""
        params = self._params_dict()
        if params is None:
            return False
        mac = params.get_dictionary_object(_MAC)
        return isinstance(mac, COSDictionary) and mac.contains_key(_CREATOR)

    def set_mac_creator(self, mac_creator: str | None) -> None:
        params = (
            self._params_dict()
            if mac_creator is None
            else self._ensure_params_dict()
        )
        if params is not None:
            _set_embedded_string(params, _MAC, _CREATOR, mac_creator)

    def clear_mac_creator(self) -> None:
        """Remove ``/Params/Mac/Creator``. No-op if absent."""
        self.set_mac_creator(None)

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

    def has_mac_resource_fork(self) -> bool:
        """Return ``True`` when ``/Params/Mac/ResFork`` is a stream."""
        return self.get_mac_resource_fork() is not None

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

    def clear_mac_resource_fork(self) -> None:
        """Remove ``/Params/Mac/ResFork``. No-op if absent."""
        self.set_mac_resource_fork(None)

    # Upstream Java method names ``getMacResFork`` / ``setMacResFork`` —
    # mechanical snake_case aliases delegating to the resource-fork accessors.
    # The parameter type stays ``COSStream`` (deviation noted in CHANGES.md);
    # upstream Java types it as ``String`` but the PDF spec defines /ResFork
    # as a stream entry.
    def get_mac_res_fork(self) -> COSStream | None:
        return self.get_mac_resource_fork()

    def set_mac_res_fork(self, stream: COSStream | None) -> None:
        self.set_mac_resource_fork(stream)

    def has_mac_res_fork(self) -> bool:
        return self.has_mac_resource_fork()

    def clear_mac_res_fork(self) -> None:
        self.clear_mac_resource_fork()


__all__ = ["PDEmbeddedFile"]
