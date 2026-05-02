from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from pypdfbox.cos import COSDictionary, COSName, COSString

# PDF info dictionary keys (PDF 32000-1:2008 §14.3.3, Table 317).
_TITLE: COSName = COSName.get_pdf_name("Title")
_AUTHOR: COSName = COSName.get_pdf_name("Author")
_SUBJECT: COSName = COSName.get_pdf_name("Subject")
_KEYWORDS: COSName = COSName.get_pdf_name("Keywords")
_CREATOR: COSName = COSName.get_pdf_name("Creator")
_PRODUCER: COSName = COSName.get_pdf_name("Producer")
_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")
_MOD_DATE: COSName = COSName.get_pdf_name("ModDate")
_TRAPPED: COSName = COSName.get_pdf_name("Trapped")


_VALID_TRAPPED = frozenset({"True", "False", "Unknown"})


# Standard /Info dictionary keys per PDF 32000-1:2008 §14.3.3, Table 317.
# Anything else found in the dictionary is considered "custom metadata".
_STANDARD_KEYS: frozenset[str] = frozenset(
    {
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreationDate",
        "ModDate",
        "Trapped",
    }
)


# Matches PDF 32000-1:2008 §7.9.4 date strings: ``D:YYYYMMDDHHmmSSOHH'mm'``.
# Every component after the year is optional (per spec, missing components
# default to zero / GMT). The trailing apostrophes are also optional in
# practice — many writers omit the closing one.
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
    """Parse a PDF date string into a timezone-aware ``datetime``.

    Mirrors ``org.apache.pdfbox.util.DateConverter.toCalendar`` for the
    common subset; returns ``None`` if the string is unparseable. Operates
    in lenient mode per real-world PDF producers (Adobe / Word / etc.):

    * The ``D:`` prefix is optional.
    * Time components may be truncated; missing fields default to 1
      (month/day) or 0 (time) per PDF 32000-1:2008 §7.9.4.
    * Missing timezone is treated as UTC.
    * Bare ``Z`` (no offset) is UTC; offsets accept either ``+0530`` or
      ``+05'30'`` form.
    * Surrounding whitespace is stripped.
    * A ``60``-second leap-second value is clamped to ``59`` (Python's
      ``datetime`` does not represent leap seconds).
    """
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    m = _PDF_DATE_RE.match(stripped)
    if m is None:
        return None
    year = int(m.group("year"))
    month = int(m.group("month") or 1)
    day = int(m.group("day") or 1)
    hour = int(m.group("hour") or 0)
    minute = int(m.group("minute") or 0)
    second = int(m.group("second") or 0)
    # Clamp leap-second padding (e.g. "235960") — Python's datetime does
    # not represent leap seconds; upstream PDFBox silently truncates.
    if second == 60:
        second = 59
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
    """Format a ``datetime`` as a PDF date string (``D:YYYYMMDDHHmmSSOHH'mm'``)."""
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


class PDDocumentInformation:
    """
    Wrapper around the trailer's ``/Info`` dictionary. Mirrors
    ``org.apache.pdfbox.pdmodel.PDDocumentInformation``.

    Each ``get_*`` accessor returns ``None`` if the entry is absent;
    each ``set_*`` accessor with a ``None`` argument clears the entry.
    """

    #: Names defined for the standard /Info dictionary keys per PDF 32000-1:2008
    #: §14.3.3, Table 317. Anything else stored on the dictionary is treated as
    #: custom metadata.
    STANDARD_KEYS: frozenset[str] = _STANDARD_KEYS

    def __init__(self, info: COSDictionary | None = None) -> None:
        self._info = info if info is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._info

    # ---------- low-level passthrough ----------

    def get_property_string_value(self, property_key: str) -> str | None:
        """Return the raw string at ``property_key`` (no type coercion).

        Allows callers to pull date strings unparsed for validation.
        """
        return self._info.get_string(property_key)

    # ---------- standard fields ----------

    def get_title(self) -> str | None:
        return self._info.get_string(_TITLE)

    def set_title(self, title: str | None) -> None:
        self._info.set_string(_TITLE, title)

    def get_author(self) -> str | None:
        return self._info.get_string(_AUTHOR)

    def set_author(self, author: str | None) -> None:
        self._info.set_string(_AUTHOR, author)

    def get_subject(self) -> str | None:
        return self._info.get_string(_SUBJECT)

    def set_subject(self, subject: str | None) -> None:
        self._info.set_string(_SUBJECT, subject)

    def get_keywords(self) -> str | None:
        return self._info.get_string(_KEYWORDS)

    def set_keywords(self, keywords: str | None) -> None:
        self._info.set_string(_KEYWORDS, keywords)

    def get_creator(self) -> str | None:
        return self._info.get_string(_CREATOR)

    def set_creator(self, creator: str | None) -> None:
        self._info.set_string(_CREATOR, creator)

    def get_producer(self) -> str | None:
        return self._info.get_string(_PRODUCER)

    def set_producer(self, producer: str | None) -> None:
        self._info.set_string(_PRODUCER, producer)

    # ---------- dates ----------

    def get_creation_date(self) -> _dt.datetime | None:
        raw = self._info.get_string(_CREATION_DATE)
        return _parse_pdf_date(raw) if raw is not None else None

    def set_creation_date(self, date: _dt.datetime | None) -> None:
        if date is None:
            self._info.remove_item(_CREATION_DATE)
            return
        self._info.set_item(_CREATION_DATE, COSString(_format_pdf_date(date)))

    def get_modification_date(self) -> _dt.datetime | None:
        raw = self._info.get_string(_MOD_DATE)
        return _parse_pdf_date(raw) if raw is not None else None

    def set_modification_date(self, date: _dt.datetime | None) -> None:
        if date is None:
            self._info.remove_item(_MOD_DATE)
            return
        self._info.set_item(_MOD_DATE, COSString(_format_pdf_date(date)))

    # ---------- trapped ----------

    def get_trapped(self) -> str | None:
        # Mirrors upstream ``getNameAsString`` semantics: real-world PDFs
        # occasionally store /Trapped as a COSString instead of the
        # spec-mandated COSName. Accept both so we don't surprise readers
        # with ``None`` for files Java PDFBox happily reads.
        v = self._info.get_dictionary_object(_TRAPPED)
        if isinstance(v, COSName):
            return v.name
        if isinstance(v, COSString):
            return v.get_string()
        return None

    def set_trapped(self, value: str | None) -> None:
        if value is not None and value not in _VALID_TRAPPED:
            raise ValueError(
                "Valid values for trapped are 'True', 'False', or 'Unknown'"
            )
        if value is None:
            self._info.remove_item(_TRAPPED)
        else:
            self._info.set_name(_TRAPPED, value)

    # ---------- custom metadata ----------

    def get_metadata_keys(self) -> list[str]:
        """Return all metadata key names present in the info dictionary, in
        sorted order (upstream returns ``TreeSet`` — sorted ``list`` matches
        the documented ordering and stays stable for callers that iterate)."""
        return sorted(key.get_name() for key in self._info.key_set())

    def get_metadata_keys_set(self) -> set[str]:
        """Return all metadata key names as a ``set``. Mirrors the upstream
        ``Set<String> getMetadataKeys()`` contract for callers that want
        membership-test semantics rather than the sorted list. The two
        accessors share underlying state — order is the only difference."""
        return {key.get_name() for key in self._info.key_set()}

    def contains_property(self, property_key: str) -> bool:
        """Return ``True`` when ``property_key`` is present in the underlying
        info dictionary. A convenience over inspecting
        ``get_metadata_keys()`` for a one-off membership check."""
        return self._info.contains_key(property_key)

    def get_custom_metadata_value(self, field_name: str) -> str | None:
        return self._info.get_string(field_name)

    def set_custom_metadata_value(
        self, field_name: str, field_value: str | None
    ) -> None:
        self._info.set_string(field_name, field_value)

    def get_custom_metadata_keys(self) -> list[str]:
        """Return only the *non-standard* metadata keys present in the info
        dictionary, in sorted order. Filters out keys defined by PDF
        32000-1:2008 §14.3.3 (``Title``, ``Author``, ..., ``Trapped``).

        Pypdfbox addition — upstream PDFBox returns *all* keys via
        ``getMetadataKeys()``; this convenience layers on top of the same
        underlying state for callers iterating only custom fields.
        """
        return sorted(
            key.get_name()
            for key in self._info.key_set()
            if key.get_name() not in _STANDARD_KEYS
        )

    # ---------- introspection ----------

    def is_empty(self) -> bool:
        """Return ``True`` if the underlying info dictionary holds no entries."""
        return self._info.is_empty()

    def __len__(self) -> int:
        return self._info.size()

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, (str, COSName)):
            return False
        return self._info.contains_key(key)

    def __repr__(self) -> str:
        return (
            f"PDDocumentInformation(title={self.get_title()!r}, "
            f"author={self.get_author()!r})"
        )


__all__ = ["PDDocumentInformation"]


# Suppress unused-import in typing-only branch (kept for future expansion).
_ = Any
