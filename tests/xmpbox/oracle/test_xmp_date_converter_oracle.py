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
  than pdfbox.util's: it rejects the PDF apostrophe time-zone form
  (``D:YYYYMMDDhhmmss+hh'mm'`` → IOException), rejects the SimpleDateFormat
  locale shapes, and returns ``null`` for the empty string (a downstream
  null-deref then surfaces ``NullPointerException``). Wave 1495 gives pypdfbox a
  separate :func:`to_calendar_strict` that ports the xmpbox parser 1:1; the
  lenient :func:`to_calendar` (pdfbox.util semantics) is retained for the FDF /
  document-info callers. The strictness split is now asserted differentially
  against the live jar below (the wave-1494 strict-xfail + ``DEFERRED.md`` entry
  are closed).

The ``iso`` probe rows are fixed instants in fixed-offset zones, so the
absolute output is deterministic and machine-independent (the ``parse`` rows
for partial dates are NOT — xmpbox resolves them in the JVM's default zone — so
those are deliberately excluded from the asserted set).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox.date_converter import (
    DateConverter,
    to_calendar,
    to_calendar_strict,
    to_iso8601,
)
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
    # Both the lenient and the strict parser must agree with the jar for a
    # fully-specified ISO instant (both share the fromISO8601 fast path).
    for py in (to_calendar(s), to_calendar_strict(s)):
        assert py is not None
        py_epoch_millis = round(py.timestamp() * 1000)
        py_offset_millis = int((py.utcoffset() or timedelta(0)).total_seconds() * 1000)
        assert py_epoch_millis == int(epoch_str)
        assert py_offset_millis == int(off_str)


# Strings that the STRICT xmpbox parser parses to a definite instant *with an
# explicit time zone in the string* — so the result is host-zone-independent and
# can be asserted differentially against the jar. The numeric ``Z`` / ``±HHMM``
# forms are the ones the strict parser accepts (apostrophe TZ is rejected).
_STRICT_ABSOLUTE = [
    "20240102030405Z",
    "20240102030405+0530",
    "20240102030405-0530",
    "D:20240102030405Z",
]


@requires_oracle
@pytest.mark.parametrize(
    "s",
    _STRICT_ABSOLUTE,
    ids=["zulu", "plus0530", "minus0530", "d_prefix_zulu"],
)
def test_to_calendar_strict_numeric_tz_matches_xmpbox(s: str) -> None:
    java = run_probe_text("XmpDateConverterProbe", "parse", s).strip()
    epoch_str, off_str = java.split("\t")
    py = to_calendar_strict(s)
    assert py is not None
    assert round(py.timestamp() * 1000) == int(epoch_str)
    py_offset_millis = int((py.utcoffset() or timedelta(0)).total_seconds() * 1000)
    assert py_offset_millis == int(off_str)


# Strings the STRICT xmpbox parser REJECTS with IOException (the jar throws,
# the probe emits "ERR<TAB>IOException"). The lenient pdfbox.util parser
# accepts several of these — the divergence is the whole point of the split.
_STRICT_REJECT = [
    "D:20240102030405+05'30'",  # PDF apostrophe TZ — Integer.parseInt chokes
    "D:20240102030405-05'30'",
    "Friday, January 11, 2115",  # SimpleDateFormat locale shape — not parsed
    "7/6/1973 17:22:1",  # slash date — not parsed
    "20240102T030405",  # T separator not at position 10
    "20",  # < 4 chars after separator collapse
]


@requires_oracle
@pytest.mark.parametrize(
    "s",
    _STRICT_REJECT,
    ids=["apos_plus", "apos_minus", "locale_named", "slash", "bad_t", "too_short"],
)
def test_to_calendar_strict_rejects_match_xmpbox(s: str) -> None:
    java = run_probe_text("XmpDateConverterProbe", "parse", s).strip()
    # The jar rejects each of these (IOException -> probe "ERR<TAB>IOException").
    assert java.startswith("ERR\tIOException"), java
    # The strict port rejects them too (IOException -> OSError).
    with pytest.raises(OSError):
        to_calendar_strict(s)


@requires_oracle
def test_to_calendar_strict_empty_returns_none_matches_npe() -> None:
    # xmpbox toCalendar("") returns null (no throw); the probe then derefs the
    # null Calendar -> NullPointerException. The strict port returns None, and a
    # downstream deref of that None raises AttributeError — the same null-deref
    # contract, surfaced in Python terms.
    java = run_probe_text("XmpDateConverterProbe", "parse", "").strip()
    assert java.startswith("ERR\tNullPointerException"), java
    assert to_calendar_strict("") is None
    assert to_calendar_strict("   ") is None
    assert to_calendar_strict(None) is None


def test_lenient_and_strict_diverge_on_apostrophe_form() -> None:
    # The split made visible without the oracle: the lenient pdfbox.util-style
    # parser accepts the PDF apostrophe TZ form; the strict xmpbox-style parser
    # rejects it. This is the closed wave-1494 DEFERRED divergence.
    s = "D:20240102030405+05'30'"
    assert to_calendar(s) is not None  # lenient accepts
    with pytest.raises(OSError):  # strict rejects
        to_calendar_strict(s)
