from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


def _parse_iso8601(value: str) -> datetime:
    # XMP / upstream DateConverter handles a few oddball ISO 8601 forms;
    # stdlib datetime.fromisoformat covers the canonical RFC 3339 subset
    # used in XMP packets. Trailing 'Z' is normalised to '+00:00' so 3.10
    # callers parse cleanly.
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    return datetime.fromisoformat(cleaned)


def _format_iso8601(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


class DateType(AbstractSimpleProperty):
    """
    XMP Date simple property.

    Ported from ``org.apache.xmpbox.type.DateType``. Upstream stores a
    ``java.util.Calendar``; the Python port stores a timezone-aware
    :class:`datetime.datetime` (the closest stdlib equivalent — ``Calendar``
    is a TZ-aware moment in time). Accepts a :class:`datetime`, :class:`date`,
    or an ISO 8601 string.
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
            raise ValueError("Value null is not allowed for the Date type")
        if isinstance(value, datetime):
            self._date_value = value
            return
        if isinstance(value, date):
            self._date_value = datetime(value.year, value.month, value.day, tzinfo=UTC)
            return
        if isinstance(value, str):
            try:
                self._date_value = _parse_iso8601(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Value given is not allowed for the Date type: {value!r}"
                ) from exc
            return
        raise ValueError(
            f"Value given is not allowed for the Date type: {type(value).__name__},"
            f" value: {value!r}"
        )

    def get_value(self) -> datetime:
        return self._date_value

    def get_string_value(self) -> str:
        return _format_iso8601(self._date_value)
