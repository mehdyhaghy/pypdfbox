"""Live PDFBox differential fuzz for ``DateConverter.toCalendar`` (wave 1522).

Drives a deep malformed-input corpus of ``D:YYYYMMDDHHmmSSOHH'mm'`` date
strings through ``org.apache.pdfbox.util.DateConverter.toCalendar(String)`` (the
parser backing ``COSDictionary.getDate``) and pypdfbox's faithful port
:func:`pypdfbox.xmpbox.date_converter.to_calendar`, asserting byte-identical
results over the existing ``DateConvertProbe`` battery's blind spots:

* **Whitespace leniency** — upstream treats ONLY the ASCII space (0x20) as
  skippable. A leading/trailing TAB / newline / CR / vertical-tab / form-feed
  is rejected (its ``parseDate`` skips spaces only, then enforces
  ``where.index == text.length()``), while a surrounding space is tolerated.
  Wave 1522 found pypdfbox used Python ``str.strip()`` / ``lstrip()`` here,
  which strip *all* Unicode whitespace and so silently accepted tab/newline
  bracketed inputs PDFBox rejects. The parser core was correct; the wrapper
  pre-strip was the bug. Fixed in
  :func:`pypdfbox.xmpbox.date_converter.to_calendar`,
  :func:`pypdfbox.xmpbox.date_converter._try_parse_date_fallback`, and
  :func:`pypdfbox.xmpbox.date_converter._from_iso8601`.
* **Prefix shapes** — only a contiguous ``D:`` (after optional leading spaces)
  is honoured; ``D`` alone, ``:`` alone, ``DD:``, ``D:D:``, ``D : `` are all
  rejected.
* **Truncation** — year-only … missing-one-digit shapes; PDFBox fills the
  big-endian fields it can and rejects the rest.
* **Out-of-range fields** — month 13 / day 32 / hour 25 / minute 70 /
  second 60-61 / all-zero (the non-lenient calendar rejects).
* **Malformed timezone offsets** — ``+24'00'`` (folded, NOT rejected),
  ``-13'70'``, ``+5``, bare ``+`` / ``-``, missing-quote forms, ``Z+05'00'``,
  ``ZZ``, lowercase ``z`` (rejected), colon offset, dot offset (rejected).
* **Trailing junk / embedded non-digits / very long strings.**

The probe is file-based: the corpus is written as base64-per-line so empty /
whitespace / control-char inputs survive line-splitting. Both sides decode the
exact same bytes.

Parity contract for ``NULL`` rows: PDFBox returns ``null`` for unparseable
input (it never throws in 3.0.7); pypdfbox surfaces a reject as
:class:`OSError` (or ``None`` for empty / whitespace / bare ``D:``). Both
rejection forms collapse to ``"NULL"`` here — the parity check is *which inputs
are accepted*, never the rejection mechanism.
"""

from __future__ import annotations

import base64
import datetime as _dt
import tempfile
from pathlib import Path

from pypdfbox.xmpbox.date_converter import to_calendar
from tests.oracle.harness import requires_oracle, run_probe_text

# (short_id, raw_input) — keep IDs short (no raw bytes); the input never reaches
# the pytest test-ID (Windows 32 KB env-var cap).
_CASES: tuple[tuple[str, str], ...] = (
    # --- whitespace leniency (the wave-1522 fix) ---
    ("lead_space", " D:20240315120000"),
    ("lead_2space", "  D:20240315120000"),
    ("lead_tab", "\tD:20240315120000"),
    ("lead_nl", "\nD:20240315120000"),
    ("lead_cr", "\rD:20240315120000"),
    ("lead_vtab", "\x0bD:20240315120000"),
    ("lead_ff", "\x0cD:20240315120000"),
    ("trail_space", "D:20240315120000 "),
    ("trail_tab", "D:20240315120000\t"),
    ("trail_nl", "D:20240315120000\n"),
    ("trail_spaces", "D:20240315120000   "),
    ("noprefix_lead_space", " 20240315120000"),
    ("noprefix_lead_tab", "\t20240315120000"),
    ("space_after_prefix", "D: 20240315120000"),
    ("tab_after_prefix", "D:\t20240315120000"),
    ("iso_lead_tab", "\t2024-03-15T12:00:00Z"),
    ("iso_lead_space", " 2024-03-15T12:00:00Z"),
    ("iso_trail_tab", "2024-03-15T12:00:00Z\t"),
    ("iso_trail_space", "2024-03-15T12:00:00Z "),
    # --- prefix shapes ---
    ("lower_d", "d:20240315120000"),
    ("d_no_colon", "D20240315120000"),
    ("colon_only", ":20240315120000"),
    ("double_d", "DD:20240315120000"),
    ("double_prefix", "D:D:20240315120000"),
    ("d_space_colon", "D : 20240315120000"),
    ("double_colon", "D:: 20240315120000"),
    # --- truncation ---
    ("trunc_1", "D:2"),
    ("trunc_3", "D:202"),
    ("trunc_7", "D:2024031"),
    ("trunc_9", "D:202403151"),
    ("trunc_13", "D:2024031512000"),
    # --- out-of-range fields ---
    ("month13_day32", "D:20241332120000"),
    ("month00", "D:20240015120000"),
    ("day32", "D:20240132120000"),
    ("hour25", "D:20240315250000"),
    ("minute70", "D:20240315127000"),
    ("second61", "D:20240315120061"),
    ("second60", "D:20240315235960"),
    ("all_zero", "D:00000000000000"),
    # --- malformed timezone offsets ---
    ("tz_hour24", "D:20240315120000+24'00'"),
    ("tz_min70", "D:20240315120000-13'70'"),
    ("tz_plus5", "D:20240315120000+5"),
    ("tz_bare_plus", "D:20240315120000+"),
    ("tz_bare_minus", "D:20240315120000-"),
    ("tz_1h_quoted", "D:20240315120000+5'00'"),
    ("tz_1m_quoted", "D:20240315120000+05'5'"),
    ("tz_1m_noclose", "D:20240315120000+05'5"),
    ("tz_plus0", "D:20240315120000+0"),
    ("tz_z_then_off", "D:20240315120000Z+05'00'"),
    ("tz_zz", "D:20240315120000ZZ"),
    ("tz_lower_z", "D:20240315120000z"),
    ("tz_colon", "D:20240315120000+05:00"),
    ("tz_dot", "D:20240315120000+05.00"),
    # --- trailing junk / extra digits ---
    ("trail_alpha", "D:20240315120000xyz"),
    ("extra_digits", "D:2024031512000000"),
    ("junk_after_tz", "D:20240315120000+05'00'X"),
    # --- embedded non-digits ---
    ("dashes", "D:2024-03-15"),
    ("slashes", "D:2024/03/15"),
    ("spaces_sep", "D:2024 03 15"),
    ("colons_sep", "D:2024:03:15"),
    ("alpha_in_year", "D:20a40315120000"),
    # --- weird / boundary ---
    ("ws_only", "   "),
    ("tab_only", "\t"),
    ("bare_prefix", "D:"),
    ("prefix_space", "D: "),
    ("null_byte", "\x00"),
    ("very_long", "D:9999999999999999999999999999999999999999"),
    ("long_trail_digits", "D:20240315120000" + "0" * 200),
    ("leading_plus", "+20240315120000"),
    ("noprefix_z", "20240315120000Z"),
    ("noprefix_date", "20240315"),
    ("noprefix_year", "2024"),
    ("two_digit", "99"),
    ("named_month", "D:March 15, 2024"),
    ("dd_mmm_yyyy", "15 Mar 2024"),
)


def _py_fingerprint(date_str: str) -> str:
    """pypdfbox ``to_calendar`` rendered as the probe's ``"<epoch> <offset>"``.

    ``"NULL"`` for any rejection — ``None`` (empty / whitespace / bare ``D:``)
    or :class:`OSError` (every other unparseable shape) — matching PDFBox's
    null return for the same inputs.
    """
    try:
        dt = to_calendar(date_str)
    except OSError:
        return "NULL"
    if dt is None:
        return "NULL"
    epoch = int(dt.timestamp() * 1000)
    off = dt.utcoffset() or _dt.timedelta()
    return f"{epoch} {int(off.total_seconds() * 1000)}"


@requires_oracle
def test_date_converter_fuzz_matches_pdfbox() -> None:
    """Every malformed date case parses identically on both engines.

    A single probe invocation over the whole corpus (base64-per-line) keeps the
    JVM spin-up cost to one launch; the per-case assertion still names the
    diverging input.
    """
    corpus_lines = [
        base64.b64encode(raw.encode("utf-8")).decode("ascii") for _name, raw in _CASES
    ]
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus.txt"
        corpus.write_text("\n".join(corpus_lines), encoding="utf-8")
        java_out = run_probe_text("DateConverterFuzzProbe", str(corpus))

    java_lines = java_out.splitlines()
    assert len(java_lines) == len(_CASES), (
        f"probe emitted {len(java_lines)} lines for {len(_CASES)} cases"
    )

    mismatches: list[str] = []
    for (name, raw), java in zip(_CASES, java_lines, strict=True):
        py = _py_fingerprint(raw)
        if py != java:
            mismatches.append(f"{name}: pypdfbox={py!r} pdfbox={java!r}")
    assert not mismatches, "DateConverter parse divergences:\n" + "\n".join(mismatches)
