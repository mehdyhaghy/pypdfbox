"""Locale-aware ``SimpleDateFormat``-style date parsing.

Java's ``java.text.SimpleDateFormat`` is the workhorse parser for the format
strings PDFBox's :class:`DateConverter` carries in its ``ALPHA_START_FORMATS``
list — e.g. ``"EEEE, MMM dd, yyyy 'at' hh:mma"``. The Python stdlib ``datetime``
module's :meth:`~datetime.datetime.strptime` honours locale-sensitive month and
weekday names only by reaching into the process-wide ``LC_TIME`` env var, which
is unreliable across host platforms (mismatched locale install on Windows /
Alpine / minimal containers will silently break parsing). Wave 1387 closes the
``SimpleDateFormat`` locale-sensitive parsing divergence by bundling canonical
CLDR month + weekday names for the 10 most common locales and routing
locale-sensitive parsing through a self-contained regex-based tokeniser that
never touches the host's locale.

The public entry point is :func:`parse_with_locale`. It accepts the same Java
pattern letters PDFBox's format strings use:

  ============  =======================================================
  Pattern       Meaning
  ============  =======================================================
  ``yyyy``      4-digit year (e.g. ``2115``)
  ``yy``        2-digit year (Java's sliding window: ``[today-79, +20]``)
  ``MMMM``      Full month name (e.g. ``January``, ``janvier``)
  ``MMM``       Abbreviated month name (e.g. ``Jan``, ``janv.``)
  ``MM``        2-digit month
  ``M``         1-or-2-digit month
  ``dd``        2-digit day
  ``d``         1-or-2-digit day
  ``EEEE``      Full weekday name (e.g. ``Friday``, ``vendredi``)
  ``EEE``       Abbreviated weekday name (e.g. ``Fri``, ``ven.``)
  ``HH``        Hour 0-23, 2-digit
  ``H``         Hour 0-23, 1-or-2-digit
  ``hh``        Hour 1-12, 2-digit (paired with ``a``)
  ``h``         Hour 1-12, 1-or-2-digit (paired with ``a``)
  ``mm``        2-digit minute
  ``m``         1-or-2-digit minute
  ``ss``        2-digit second
  ``s``         1-or-2-digit second
  ``a``         AM/PM marker (case-insensitive)
  ``'…'``       Literal text quoted with single-quotes (e.g. ``'at'``)
  ============  =======================================================

Other characters in the pattern (punctuation, spaces) match literally — and
whitespace in the input is collapsed at the boundary so trailing / leading
spaces in fixtures don't cause spurious mismatches.

The implementation is intentionally read-only — no host-locale fallback, no
process-wide state. Callers pick the locale explicitly; if they get it wrong,
the parse returns ``None`` rather than silently guessing.
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime

from pypdfbox.util.locale_data import (
    get_month_names_abbrev,
    get_month_names_full,
    get_weekday_names_abbrev,
    get_weekday_names_full,
)

# Order matters: longer tokens must come first so ``MMMM`` beats ``MMM`` etc.
_PATTERN_TOKENS: tuple[str, ...] = (
    "yyyy",
    "yy",
    "MMMM",
    "MMM",
    "MM",
    "M",
    "dd",
    "d",
    "EEEE",
    "EEE",
    "HH",
    "H",
    "hh",
    "h",
    "mm",
    "m",
    "ss",
    "s",
    "a",
    "z",
)


def _normalise(text: str) -> str:
    """Strip diacritics and casefold for tolerant locale-name matching.

    Mirrors the parity intent of Java ``Collator.setStrength(PRIMARY)`` — base
    letters only, no accents, no case. So ``fevrier`` matches ``février`` and
    ``JANUARY`` matches ``January`` and ``MONDAY`` matches ``Monday``.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def _tokenise_pattern(pattern: str) -> list[tuple[str, str]]:
    """Split ``pattern`` into ``(kind, value)`` tuples.

    ``kind`` is one of ``"token"`` (a SimpleDateFormat pattern token like
    ``"MMM"``), ``"literal"`` (a stretch of non-pattern chars), or
    ``"quoted"`` (text wrapped in single-quotes). ``value`` is the raw token
    text or the literal/quoted string contents.
    """
    out: list[tuple[str, str]] = []
    index = 0
    n = len(pattern)
    while index < n:
        ch = pattern[index]
        if ch == "'":
            # Java SimpleDateFormat: '' is a literal single-quote, otherwise
            # everything up to the closing quote is literal.
            if index + 1 < n and pattern[index + 1] == "'":
                out.append(("literal", "'"))
                index += 2
                continue
            close = pattern.find("'", index + 1)
            if close == -1:
                # Unterminated quote — treat the rest as a literal.
                out.append(("quoted", pattern[index + 1 :]))
                return out
            out.append(("quoted", pattern[index + 1 : close]))
            index = close + 1
            continue
        # Try to match a known pattern token (longest first).
        matched: str | None = None
        for tok in _PATTERN_TOKENS:
            if pattern.startswith(tok, index):
                # Disallow a longer-token gobbling its prefix when the
                # following char is also a pattern letter — Java collapses
                # runs of the same letter, so ``EEEEEEEEEE`` is the same as
                # ``EEEE``.
                if (
                    index + len(tok) < n
                    and pattern[index + len(tok)] == tok[-1]
                    and tok[-1] in "yMdEHhmsa"
                ):
                    # Extend the run — skip ahead to the end of identical chars.
                    run_end = index + len(tok)
                    while run_end < n and pattern[run_end] == tok[-1]:
                        run_end += 1
                    out.append(("token", tok))
                    index = run_end
                    matched = tok
                    break
                out.append(("token", tok))
                index += len(tok)
                matched = tok
                break
        if matched is not None:
            continue
        # Accumulate a literal run.
        start = index
        while index < n and pattern[index] != "'":
            # Stop at any character that starts a known token.
            if any(pattern.startswith(tok, index) for tok in _PATTERN_TOKENS):
                break
            index += 1
        out.append(("literal", pattern[start:index]))
    return out


def _two_digit_year(yy: int) -> int:
    """Mirror Java SimpleDateFormat's 2-digit year sliding window.

    Picks the year in ``[thisyear-79, thisyear+20]`` (the JDK default).
    """
    today = datetime.now(UTC).year
    base = today - 79
    century = (base // 100) * 100
    candidate = century + yy
    if candidate < base:
        candidate += 100
    if candidate > base + 99:  # pragma: no cover - unreachable given today's pivot
        candidate -= 100
    return candidate


def _lookup_locale_index(
    text: str, position: int, names: tuple[str, ...]
) -> tuple[int, int] | None:
    """Find the longest entry in ``names`` that matches ``text`` at ``position``.

    Match is normalised (diacritics stripped + casefold) on both sides.
    Returns ``(index_in_names, chars_consumed)`` or ``None`` if no entry matches.
    """
    if position >= len(text):  # pragma: no cover - parser never calls past EOS
        return None
    # Pre-normalise the input slice once per call.
    candidate_slice = text[position : position + 64]
    norm_text = _normalise(candidate_slice)
    # Walk names in descending length order so e.g. "September" beats "Sep".
    indexed = sorted(
        enumerate(names), key=lambda iv: len(iv[1]), reverse=True
    )
    for idx, name in indexed:
        norm_name = _normalise(name)
        if norm_text.startswith(norm_name):
            # Map normalised-name length back to the original input length.
            # Diacritic stripping decomposes a char and drops combining marks,
            # so a normalised char count corresponds to (potentially) more
            # input chars. We scan the input forward letter-by-letter until
            # the running normalised prefix matches the normalised name.
            consumed = 0
            running = ""
            while consumed < len(candidate_slice) and len(running) < len(norm_name):
                consumed += 1
                running = _normalise(candidate_slice[:consumed])
            if running == norm_name:
                return idx, consumed
    return None


def _lookup_locale_index_multi(
    text: str, position: int, name_lists: list[tuple[str, ...]]
) -> tuple[int, int] | None:
    """Like :func:`_lookup_locale_index` but searches multiple name lists.

    Lists are assumed parallel (same canonical indices — e.g. full + abbrev
    months both indexed 0..11). The match with the longest input consumption
    wins, mirroring Java ``DateFormatSymbols`` greedy parsing.
    """
    best: tuple[int, int] | None = None
    for names in name_lists:
        candidate = _lookup_locale_index(text, position, names)
        if candidate is None:
            continue
        if best is None or candidate[1] > best[1]:
            best = candidate
    return best


def _consume_digits(
    text: str, position: int, min_len: int, max_len: int
) -> tuple[int, int] | None:
    """Eat ``min_len..max_len`` consecutive digits at ``position``.

    Returns ``(int_value, chars_consumed)`` or ``None`` on failure.
    """
    end = position
    while end < len(text) and text[end].isdigit() and (end - position) < max_len:
        end += 1
    if (end - position) < min_len:
        return None
    return int(text[position:end]), end - position


def parse_with_locale(
    input_str: str, pattern: str, locale: str = "en"
) -> datetime | None:
    """Parse ``input_str`` against a SimpleDateFormat ``pattern`` for ``locale``.

    Returns a :class:`datetime.datetime` (naive — caller attaches a tz if
    needed, mirroring upstream ``Calendar.set`` semantics) on success, or
    ``None`` if the input does not match the pattern.

    Whitespace in the input is collapsed at literal boundaries — a single
    space in the pattern matches one-or-more spaces in the input, and leading
    / trailing whitespace in the input is stripped.

    Supported ``locale`` codes: see :data:`pypdfbox.util.locale_data.SUPPORTED_LOCALES`.
    Unknown locales fall back to English (matches Java's behaviour with an
    unknown ``Locale``).
    """
    if input_str is None or pattern is None:  # pragma: no cover - defensive
        return None
    text = input_str.strip()
    if not text:
        return None

    tokens = _tokenise_pattern(pattern)

    # Field accumulator. AM/PM is tracked separately and folded into hour at the
    # end (matches Java's ``Calendar.set(AM_PM, …)`` semantics).
    fields: dict[str, int] = {
        "year": 1970,
        "month": 1,
        "day": 1,
        "hour": 0,
        "minute": 0,
        "second": 0,
    }
    am_pm: str | None = None
    has_hour12 = False

    months_full = get_month_names_full(locale)
    months_abbrev = get_month_names_abbrev(locale)
    weekdays_full = get_weekday_names_full(locale)
    weekdays_abbrev = get_weekday_names_abbrev(locale)

    pos = 0

    for kind, value in tokens:
        if pos > len(text):  # pragma: no cover - defensive; sub-token consumers stop at pos == len
            return None
        if kind == "literal":
            # Match the literal, tolerating whitespace collapsing.
            j = 0
            while j < len(value):
                lit_char = value[j]
                if lit_char == " ":
                    # one-or-more whitespace
                    if pos >= len(text) or not text[pos].isspace():
                        # Allow the literal space to be absent only if we're
                        # at a boundary the pattern already accounts for.
                        if (
                            pos < len(text)
                            and j + 1 < len(value)
                            and text[pos] == value[j + 1]
                        ):
                            j += 1
                            continue
                        return None
                    while pos < len(text) and text[pos].isspace():
                        pos += 1
                    j += 1
                    continue
                if pos >= len(text) or text[pos] != lit_char:
                    return None
                pos += 1
                j += 1
            continue
        if kind == "quoted":
            if not text.startswith(value, pos):
                # Tolerate case differences on quoted literals like 'at' / 'AT'.
                seg = text[pos : pos + len(value)]
                if seg.casefold() != value.casefold():
                    return None
            pos += len(value)
            continue
        # token
        if value == "yyyy":
            got = _consume_digits(text, pos, 4, 4)
            if got is None:
                return None
            fields["year"], consumed = got
            pos += consumed
        elif value == "yy":
            got = _consume_digits(text, pos, 2, 4)
            if got is None:
                return None
            raw, consumed = got
            # Two-digit years convert via the sliding window; four-digit years
            # pass through (Java does this when "yy" is in the pattern).
            if consumed == 4:
                fields["year"] = raw
            else:
                fields["year"] = _two_digit_year(raw)
            pos += consumed
        elif value == "MM" or value == "M":
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["month"], consumed = got
            pos += consumed
        elif value == "MMMM":
            # Search both full + abbrev, pick the longest match (Java's
            # ``DateFormatSymbols`` parser is greedy — "January" beats "Jan").
            found = _lookup_locale_index_multi(
                text, pos, [months_full, months_abbrev]
            )
            if found is None:
                return None
            idx, consumed = found
            fields["month"] = idx + 1
            pos += consumed
        elif value == "MMM":
            # Java permits the full month name to be parsed under ``MMM`` too
            # — same greedy longest-match rule (so ``January`` still wins
            # over ``Jan`` when both shapes appear). This is the upstream
            # ``DateFormatSymbols.getShortMonths()`` + ``getMonths()`` walk.
            found = _lookup_locale_index_multi(
                text, pos, [months_full, months_abbrev]
            )
            if found is None:
                return None
            idx, consumed = found
            fields["month"] = idx + 1
            pos += consumed
        elif value == "dd":
            # Java's parser is lenient on field width — ``dd`` accepts 1..2
            # digits at parse time (the strict-2-digit rule only applies on
            # *format*). See SimpleDateFormat javadoc, "Number: For parsing,
            # the number of pattern letters is ignored unless …".
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["day"], consumed = got
            pos += consumed
        elif value == "d":
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["day"], consumed = got
            pos += consumed
        elif value == "EEEE":
            found = _lookup_locale_index_multi(
                text, pos, [weekdays_full, weekdays_abbrev]
            )
            if found is None:
                return None
            # Weekday is informational — it disambiguates input but the year/
            # month/day fields drive the final date.
            _, consumed = found
            pos += consumed
        elif value == "EEE":
            found = _lookup_locale_index_multi(
                text, pos, [weekdays_full, weekdays_abbrev]
            )
            if found is None:
                return None
            _, consumed = found
            pos += consumed
        elif value == "HH" or value == "H":
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["hour"], consumed = got
            pos += consumed
        elif value == "hh" or value == "h":
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["hour"], consumed = got
            has_hour12 = True
            pos += consumed
        elif value == "mm" or value == "m":
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["minute"], consumed = got
            pos += consumed
        elif value == "ss" or value == "s":
            got = _consume_digits(text, pos, 1, 2)
            if got is None:
                return None
            fields["second"], consumed = got
            pos += consumed
        elif value == "a":
            # AM / PM marker — case insensitive. Allow surrounding optional
            # whitespace (Java's parser is permissive here).
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos + 1 >= len(text):
                return None
            marker = text[pos : pos + 2].upper()
            if marker not in ("AM", "PM"):
                return None
            am_pm = marker
            pos += 2
        elif value == "z":
            # Time-zone token: ``GMT+nn:nn``, ``UTC``, three-letter abbrev
            # (``PST`` / ``EST`` / ``EDT``), or zoneinfo ID
            # (``America/Chicago``). Java parses the longest matching tz
            # designation here; we accept any non-whitespace run that doesn't
            # start with a digit (so the following year token isn't
            # accidentally swallowed). The value is discarded — the upstream
            # tests using this format don't depend on the TZ being applied
            # via the locale parser (``parse_t_zoffset`` in the outer
            # dispatcher handles TZ semantics for the wider PDFBox port).
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos >= len(text):
                return None
            tz_start = pos
            while pos < len(text) and not text[pos].isspace():
                pos += 1
            if pos == tz_start:  # pragma: no cover - whitespace was just skipped above
                return None
        else:  # pragma: no cover - defensive; _PATTERN_TOKENS exhaustively listed
            return None

    # Trailing whitespace in the input is benign — strip it back off rather than
    # rejecting an otherwise valid parse. (We already stripped at entry; this
    # catches input where the pattern ends mid-token and there's residue.)
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos != len(text):
        return None

    # Apply AM/PM rollover.
    hour = fields["hour"]
    if has_hour12:
        if not 1 <= hour <= 12:
            return None
        if am_pm == "PM" and hour != 12:
            hour += 12
        elif am_pm == "AM" and hour == 12:
            hour = 0
    fields["hour"] = hour

    try:
        return datetime(
            fields["year"],
            fields["month"],
            fields["day"],
            fields["hour"],
            fields["minute"],
            fields["second"],
        )
    except (ValueError, OverflowError):
        return None


# ----------------------------------------------------------------------------- #
# Backwards-compat re-exports for callers that imported from this module before
# the locale work landed.
# ----------------------------------------------------------------------------- #

__all__ = ["parse_with_locale"]
