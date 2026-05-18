"""Wave 1354 tail-sweep: cover ``DateType.get_string_value`` None path.

A freshly-constructed :class:`DateType` always has a non-None
``_date_value`` because the constructor rejects ``None`` via
``set_value``. The defensive ``return None`` at line 114 of
``date_type.py`` mirrors upstream's ``Calendar`` getter parity — if a
subclass or parser sets the value back to ``None`` the getter must not
crash. This test forces that state directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox.type.date_type import DateType


def test_get_string_value_returns_none_when_date_value_is_none() -> None:
    dt = DateType(None, "urn:test", "t", "when", datetime(2024, 1, 2, tzinfo=UTC))
    dt._date_value = None  # type: ignore[attr-defined]
    assert dt.get_string_value() is None
