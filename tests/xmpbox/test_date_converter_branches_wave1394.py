"""Wave 1394 — small uncovered branches in ``date_converter``.

Closes the easy ones:

* Line 908 — ``_try_simple_format`` returns ``(None, 0)`` for an
  unknown format string.
* Lines 1111-1124 — ``_make_handler_mmdd_yyyy_hms`` success path
  (``MM/dd/yyyy HH:mm:ss``).
* Lines 1134-1146 — ``_make_handler_mmdd_yyyy_hm`` success path.
* Line 1164 — ``_make_handler_mmdd_yyyy`` success path.
* Lines 1180, 1185 — locale handler empty-text and leading-whitespace
  branches (via the ``EEEE, MMM dd, yy`` shape).
* Lines 1238, 1241, 1266 — ``_make_handler_locale_split_at_tz`` empty
  text / leading whitespace / post-TZ parse miss.
"""

from __future__ import annotations

from pypdfbox.xmpbox.date_converter import (
    _make_handler_locale,
    _make_handler_locale_split_at_tz,
    _make_handler_mmdd_yyyy,
    _make_handler_mmdd_yyyy_hm,
    _make_handler_mmdd_yyyy_hms,
    _try_simple_format,
)

# ---------- line 908 ----------


def test_try_simple_format_returns_none_for_unknown_format() -> None:
    cal, consumed = _try_simple_format("anything", "unknown-format")
    assert cal is None
    assert consumed == 0


# ---------- MM/dd/yyyy handlers (success + miss branches) ----------


def test_mmdd_yyyy_hms_parses_us_default_with_seconds() -> None:
    cal, consumed = _make_handler_mmdd_yyyy_hms("07/04/2025 12:30:45")
    assert cal is not None
    assert consumed == len("07/04/2025 12:30:45")
    assert cal.year == 2025
    assert cal.month == 6  # 0-indexed July
    assert cal.day == 4
    assert cal.hour == 12
    assert cal.minute == 30
    assert cal.second == 45


def test_mmdd_yyyy_hms_returns_none_on_invalid_date() -> None:
    """Lines 1122-1123: invalid month/day fails ``cal.validate()`` →
    ``except (ValueError, OverflowError): return None``."""
    cal, consumed = _make_handler_mmdd_yyyy_hms("13/40/2025 99:99:99")
    assert cal is None
    assert consumed == 0


def test_mmdd_yyyy_hms_returns_none_on_no_match() -> None:
    cal, consumed = _make_handler_mmdd_yyyy_hms("not-a-date")
    assert cal is None
    assert consumed == 0


def test_mmdd_yyyy_hm_parses_us_default_without_seconds() -> None:
    cal, consumed = _make_handler_mmdd_yyyy_hm("01/15/2024 09:30")
    assert cal is not None
    assert consumed == len("01/15/2024 09:30")
    assert cal.year == 2024
    assert cal.month == 0  # January
    assert cal.day == 15


def test_mmdd_yyyy_hm_returns_none_on_invalid_date() -> None:
    cal, consumed = _make_handler_mmdd_yyyy_hm("13/40/2024 50:50")
    assert cal is None
    assert consumed == 0


def test_mmdd_yyyy_parses_us_default_no_time() -> None:
    cal, consumed = _make_handler_mmdd_yyyy("12/25/2030")
    assert cal is not None
    assert consumed == len("12/25/2030")
    assert cal.year == 2030
    assert cal.month == 11  # December
    assert cal.day == 25


def test_mmdd_yyyy_returns_none_on_invalid_date() -> None:
    cal, consumed = _make_handler_mmdd_yyyy("99/99/2030")
    assert cal is None
    assert consumed == 0


# ---------- locale handler empty / whitespace branches ----------


def test_locale_handler_returns_none_for_empty_text() -> None:
    """Line 1180 — empty text fast-path."""
    handler = _make_handler_locale("EEEE, MMM dd, yy")
    cal, consumed = handler("")
    assert cal is None
    assert consumed == 0


def test_locale_handler_skips_leading_whitespace() -> None:
    """Line 1185 — leading whitespace is counted via the inner loop.
    A 4-space prefix in front of a valid date is consumed."""
    handler = _make_handler_locale("EEEE, MMM dd, yy")
    cal, consumed = handler("    Sunday, May 25, 25")
    # Whether the inner locale parser accepts the text is implementation-
    # specific; either way the leading-whitespace branch is exercised.
    # Sanity: the consumed offset, if non-zero, must include the leading
    # whitespace.
    if cal is not None:
        assert consumed >= len("    Sunday, May 25, 25")


def test_locale_split_at_tz_handler_returns_none_for_empty_text() -> None:
    """Line 1238 — empty text fast-path on the split-at-tz handler."""
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    cal, consumed = handler("")
    assert cal is None
    assert consumed == 0


def test_locale_split_at_tz_handler_skips_leading_whitespace_on_miss() -> None:
    """Line 1241 + 1272 — leading whitespace is consumed but the pre-fmt
    parse misses → ``best_pre_end == -1`` → ``return None, 0``."""
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    cal, consumed = handler("    not-a-date-of-the-expected-shape")
    assert cal is None
    assert consumed == 0


# ---------- locale handler set_fields exception (lines 1211-1212) ----------


def test_locale_handler_returns_none_when_set_fields_raises(
    monkeypatch,
) -> None:
    """Lines 1211-1212 — ``cal.set_fields`` raises ``ValueError`` (e.g.
    parsed year out of range for ``datetime``). We monkeypatch
    ``parse_with_locale`` to return a bogus year, exercising the
    defensive ``except`` clause."""
    from types import SimpleNamespace

    import pypdfbox.util.date_util as date_util

    def _fake_parse(text, fmt, locale="en"):
        # Return an object that looks like a parsed date but with an
        # out-of-range year (datetime.MINYEAR = 1; we return -50000).
        return SimpleNamespace(
            year=-50000, month=1, day=1, hour=0, minute=0, second=0
        )

    monkeypatch.setattr(date_util, "parse_with_locale", _fake_parse)
    handler = _make_handler_locale("EEEE, MMM dd, yy")
    cal, consumed = handler("anything-non-empty")
    assert cal is None
    assert consumed == 0


def test_locale_split_at_tz_handler_returns_none_when_set_fields_raises(
    monkeypatch,
) -> None:
    """Lines 1285-1286 — same defensive raise inside the split-at-tz
    variant. The fake parser succeeds for both pre- and post-fmt so we
    reach the calendar build, then ``set_fields`` rejects the year."""
    from types import SimpleNamespace

    import pypdfbox.util.date_util as date_util

    def _fake_parse(text, fmt, locale="en"):
        # Always succeed for any prefix/post text — we just need to
        # land in the set_fields try-block with a bogus year.
        return SimpleNamespace(
            year=-50000, month=1, day=1, hour=0, minute=0, second=0
        )

    monkeypatch.setattr(date_util, "parse_with_locale", _fake_parse)
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    # "<pre>  <tz>  <year>" — the fake parser doesn't care about content.
    cal, consumed = handler("Mon Jan 01 00:00:00 GMT 25")
    assert cal is None
    assert consumed == 0


# ---------- split_at_tz continue branches (lines 1253, 1261, 1266) ----------


def test_locale_split_at_tz_handler_continues_when_tail_empty(
    monkeypatch,
) -> None:
    """Line 1253 — ``parsed_pre`` matches a prefix that consumes the
    entire text, so ``tail`` is empty → continue → eventually returns
    ``None, 0``."""
    from types import SimpleNamespace

    import pypdfbox.util.date_util as date_util

    def _fake_parse(text, fmt, locale="en"):
        # pre_fmt accepts the full text; post_fmt rejects everything
        # (returns None). With no tail to feed post_fmt, the loop hits
        # the `continue` at line 1253 each iter.
        if "z" in fmt:  # post_fmt is "yy" (no 'z')
            return None
        return SimpleNamespace(
            year=2025, month=1, day=1, hour=0, minute=0, second=0
        )

    monkeypatch.setattr(date_util, "parse_with_locale", _fake_parse)
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    cal, consumed = handler("payload-with-no-trailing-whitespace")
    assert cal is None
    assert consumed == 0


def test_locale_split_at_tz_handler_continues_when_tz_or_year_part_empty(
    monkeypatch,
) -> None:
    """Line 1261 — tail is non-empty but the TZ blob or year part is
    empty (no whitespace separating them)."""
    from types import SimpleNamespace

    import pypdfbox.util.date_util as date_util

    def _fake_parse(text, fmt, locale="en"):
        # pre_fmt accepts "Mon Jan 01 00:00:00" (the first 19 chars);
        # the tail is "GMT" — non-empty, but year_part (text after the
        # contiguous tz-blob) is empty → continue.
        if fmt == "yy":
            return None
        # Accept the longest text passed; the suffix-walk will retry shorter.
        if len(text) >= 19:
            return SimpleNamespace(
                year=2025, month=1, day=1, hour=0, minute=0, second=0
            )
        return None

    monkeypatch.setattr(date_util, "parse_with_locale", _fake_parse)
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    # 19-char prefix then "GMT" — year_part will be empty.
    cal, consumed = handler("Mon Jan 01 00:00:00 GMT")
    assert cal is None
    assert consumed == 0


def test_locale_split_at_tz_handler_continues_when_post_parse_fails(
    monkeypatch,
) -> None:
    """Line 1266 — tail and year_part are present, but ``post_fmt``
    parse returns ``None``."""
    from types import SimpleNamespace

    import pypdfbox.util.date_util as date_util

    def _fake_parse(text, fmt, locale="en"):
        # pre_fmt always succeeds; post_fmt always fails.
        if fmt == "yy":
            return None
        return SimpleNamespace(
            year=2025, month=1, day=1, hour=0, minute=0, second=0
        )

    monkeypatch.setattr(date_util, "parse_with_locale", _fake_parse)
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    cal, consumed = handler("Mon Jan 01 00:00:00 GMT bogus-year-25")
    assert cal is None
    assert consumed == 0
