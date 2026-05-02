from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from ..date_converter import to_calendar, to_iso8601
from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class DateType(AbstractSimpleProperty):
    """
    XMP Date simple property.

    Ported from ``org.apache.xmpbox.type.DateType``. Upstream stores a
    ``java.util.Calendar``; the Python port stores a timezone-aware
    :class:`datetime.datetime` (the closest stdlib equivalent — ``Calendar``
    is a TZ-aware moment in time). Accepts a :class:`datetime`, :class:`date`,
    or any string form recognised by :func:`pypdfbox.xmpbox.DateConverter`
    (full ISO 8601, partial ISO 8601 like ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``,
    or PDF dictionary form ``D:YYYYMMDDhhmmss``).
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, namespace_uri, prefix, property_name, value)

    def set_value(self, value: Any) -> None:
        if value is None:
            # Upstream's setValue rejects null with IllegalArgumentException
            # before ever reaching the field; we mirror that with ValueError.
            raise ValueError("Value null is not allowed for the Date type")
        if isinstance(value, datetime):
            self._date_value = value
            return
        if isinstance(value, date):
            self._date_value = datetime(value.year, value.month, value.day, tzinfo=UTC)
            return
        if isinstance(value, str):
            # Delegate to DateConverter so we accept the same string surface as
            # upstream Java's DateType (which calls DateConverter.toCalendar).
            try:
                parsed = to_calendar(value)
            except OSError as exc:
                raise ValueError(
                    f"Value given is not allowed for the Date type: {value!r}"
                ) from exc
            if parsed is None:
                # to_calendar returns None for empty / whitespace strings;
                # upstream rejects those at isGoodType.
                raise ValueError(
                    f"Value given is not allowed for the Date type: {value!r}"
                )
            self._date_value = parsed
            return
        raise ValueError(
            f"Value given is not allowed for the Date type: {type(value).__name__},"
            f" value: {value!r}"
        )

    def get_value(self) -> datetime:
        return self._date_value

    def get_string_value(self) -> str:
        # Mirror DateConverter.toISO8601 used by upstream DateType.getStringValue.
        return to_iso8601(self._date_value)
