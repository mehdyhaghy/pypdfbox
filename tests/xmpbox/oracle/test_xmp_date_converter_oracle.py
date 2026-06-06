"""Live xmpbox differential parity for ``org.apache.xmpbox.DateConverter``.

This is the *xmpbox* date helper — a class distinct from
``org.apache.pdfbox.util.DateConverter`` (covered by
``tests/xmpbox/oracle/test_date_convert_oracle.py`` via ``DateConvertProbe``).
The pypdfbox port collapses both Java classes into one
:mod:`pypdfbox.xmpbox.date_converter` module, so this probe pins the surface
that the xmpbox class owns and the pdfbox.util one does not:

* **toISO8601** — ``DateConverter.toISO8601(Calendar)`` and the two-arg
  ``toISO8601(Calendar, boolean)`` (the boolean prints milliseconds). xmpbox's
  formatter always emits a colon-separated ``±HH:MM`` zone offset (the
  pdfbox.util ``toString`` emits the PDF ``±HH'mm'`` form instead). This is the
  format used inside serialized XMP packets.

* **toCalendar strictness** — xmpbox's ``toCalendar(String)`` is *stricter*
  than pdfbox.util's: it rejects the PDF ``D:`` dictionary form (IOException)
  and raises ``NullPointerException`` on the empty string. The pypdfbox port,
  by design, shares one lenient :func:`to_calendar` (which accepts ``D:`` and
  returns ``None`` for empty). That structural divergence is pinned by the
  strict-xfail at the bottom and recorded in ``DEFERRED.md``.

The ``iso`` probe rows are fixed instants in fixed-offset zones, so the
absolute output is deterministic and machine-independent (the ``parse`` rows
for partial dates are NOT — xmpbox resolves them in the JVM's default zone — so
those are deliberately excluded from the asserted set).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox.date_converter import DateConverter, to_calendar, to_iso8601
from tests.oracle.harness import requires_oracle, run_probe_text

# (epoch_millis, offset_minutes) — fixed instants across the interesting offset
# shapes: UTC, half-hour (+05:30), three-quarter (+05:45 / +13:45), negative
# half-hour (-06:30), pre-epoch, and a 5-digit-second-bearing millis value.
_ISO_CASES = [
    (0, 0),
    (0, 330),
    (0, -300),
    (0, -390),
    (1000, 60),
    (999, 0),
    (1, 825),
    (-1000, 0),
    (1234567890123, 330),
    (1234567890123, -300),
    (1000000000000, 345),
]


def _py_iso(epoch_millis: int, offset_minutes: int) -> tuple[str, str]:
    """Mirror the probe: build an offset-aware datetime at the instant and
    return (toISO8601 without millis, toISO8601 with millis)."""
    tz = timezone(timedelta(minutes=offset_minutes))
    dt = datetime.fromtimestamp(epoch_millis / 1000, tz=UTC).astimezone(tz)
    return to_iso8601(dt, False), to_iso8601(dt, True)


@requires_oracle
@pytest.mark.parametrize(
    ("epoch_millis", "offset_minutes"),
    _ISO_CASES,
    ids=[f"{e}@{o}" for e, o in _ISO_CASES],
)
def test_to_iso8601_matches_xmpbox(epoch_millis: int, offset_minutes: int) -> None:
    java = run_probe_text(
        "XmpDateConverterProbe", "iso", str(epoch_millis), str(offset_minutes)
    ).strip()
    no_millis, with_millis = java.split("\t")
    py_no_millis, py_with_millis = _py_iso(epoch_millis, offset_minutes)
    assert py_no_millis == no_millis
    assert py_with_millis == with_millis


@requires_oracle
def test_to_iso8601_via_classmethod_matches() -> None:
    """The ``DateConverter.to_iso8601`` classmethod must agree with the
    module-level function the probe pins."""
    java = run_probe_text("XmpDateConverterProbe", "iso", "1234567890123", "330").strip()
    no_millis, with_millis = java.split("\t")
    tz = timezone(timedelta(minutes=330))
    dt = datetime.fromtimestamp(1234567890123 / 1000, tz=UTC).astimezone(tz)
    assert DateConverter.to_iso8601(dt, False) == no_millis
    assert DateConverter.to_iso8601(dt, True) == with_millis


# ISO 8601 input strings whose absolute instant is fully specified by an
# explicit offset — these parse identically in both libraries regardless of the
# host JVM's default zone.
_PARSE_ABSOLUTE = [
    "2024-01-02T03:04:05+05:30",
    "2024-01-02T03:04:05.123Z",
]


@requires_oracle
@pytest.mark.parametrize("s", _PARSE_ABSOLUTE, ids=["plus_offset", "z_millis"])
def test_to_calendar_absolute_offset_matches_xmpbox(s: str) -> None:
    java = run_probe_text("XmpDateConverterProbe", "parse", s).strip()
    epoch_str, off_str = java.split("\t")
    py = to_calendar(s)
    assert py is not None
    py_epoch_millis = round(py.timestamp() * 1000)
    py_offset_millis = int((py.utcoffset() or timedelta(0)).total_seconds() * 1000)
    assert py_epoch_millis == int(epoch_str)
    assert py_offset_millis == int(off_str)


@requires_oracle
@pytest.mark.xfail(
    reason="structural: pypdfbox shares one lenient to_calendar for both the "
    "pdfbox.util and xmpbox DateConverter classes. The xmpbox variant is "
    "stricter — it rejects the PDF D: form (IOException) and raises on the "
    "empty string — so its accept-set diverges. See DEFERRED.md.",
    strict=True,
)
def test_to_calendar_xmpbox_strictness_diverges() -> None:
    # xmpbox rejects the D: PDF dictionary form; pypdfbox's shared lenient
    # parser accepts it (matching pdfbox.util.DateConverter instead).
    java_d = run_probe_text(
        "XmpDateConverterProbe", "parse", "D:20240102030405+05'30'"
    ).strip()
    assert java_d.startswith("ERR")  # xmpbox -> IOException
    # If pypdfbox matched xmpbox here it would reject too; it does not.
    assert to_calendar("D:20240102030405+05'30'") is None
