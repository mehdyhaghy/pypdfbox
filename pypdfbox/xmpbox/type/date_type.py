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

    def is_good_type(self, value: Any) -> bool:
        """Check if the value has a type which can be understood.

        Mirrors upstream ``DateType#isGoodType`` (DateType.java L88-107):
        returns True for ``Calendar`` (here: :class:`datetime`/:class:`date`)
        and for any string that :func:`to_calendar` can parse without raising.
        """
        if isinstance(value, datetime | date):
            return True
        if isinstance(value, str):
            try:
                parsed = to_calendar(value)
            except OSError:
                return False
            # Upstream's DateConverter.toCalendar throws on unparseable strings;
            # the port returns None for empty/whitespace, which upstream's
            # isGoodType also rejects (the empty string would have thrown there).
            return parsed is not None
        return False

    def set_value_from_calendar(self, value: datetime | date) -> None:
        """Set the property value from a Python equivalent of ``Calendar``.

        Mirrors upstream ``DateType#setValueFromCalendar``
        (DateType.java L65-68). ``date`` (without time) is promoted to UTC
        midnight, matching upstream Calendar behavior with a date-only input.
        """
        if isinstance(value, datetime):
            self._date_value = value
        else:
            # plain date -> midnight UTC
            self._date_value = datetime(
                value.year, value.month, value.day, tzinfo=UTC
            )

    def set_value_from_string(self, value: str) -> None:
        """Set the property value from a string.

        Mirrors upstream ``DateType#setValueFromString``
        (DateType.java L162-175): delegates to :func:`to_calendar` and
        raises if the string is unparseable. Upstream's comment says this
        "SHOULD NEVER HAPPEN" because :meth:`set_value` pre-validates via
        :meth:`is_good_type`; we still surface the error as ``ValueError``.
        """
        try:
            parsed = to_calendar(value)
        except OSError as exc:
            raise ValueError(
                f"Value given is not allowed for the Date type: {value!r}"
            ) from exc
        if parsed is None:
            raise ValueError(
                f"Value given is not allowed for the Date type: {value!r}"
            )
        self.set_value_from_calendar(parsed)

    def set_value(self, value: Any) -> None:
        # Mirror upstream DateType#setValue (DateType.java L116-144): null
        # rejection first, then is_good_type check, then dispatch to the
        # appropriate typed setter.
        if not self.is_good_type(value):
            if value is None:
                raise ValueError("Value null is not allowed for the Date type")
            raise ValueError(
                f"Value given is not allowed for the Date type:"
                f" {type(value).__name__}, value: {value!r}"
            )
        if isinstance(value, str):
            self.set_value_from_string(value)
        else:
            self.set_value_from_calendar(value)

    def get_value(self) -> datetime:
        return self._date_value

    def get_string_value(self) -> str:
        # Mirror DateConverter.toISO8601 used by upstream DateType.getStringValue.
        if self._date_value is None:
            return None
        return to_iso8601(self._date_value)
