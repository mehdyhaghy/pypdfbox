"""Fuzz / parity pins for ``PDDocumentInformation`` + PDF date conversion (wave 1577).

Hammers the ``/Info`` dictionary surface
(:class:`pypdfbox.pdmodel.pd_document_information.PDDocumentInformation`) and the
PDF-date string parsing / formatting it delegates to
(``DateConverter.toCalendar`` / ``DateConverter.toString`` via the COS layer).

Every literal expectation below was captured from live Apache PDFBox 3.0.7 via
``oracle/probes/DateConvertProbe.java`` (parse + format modes) and the documented
``org.apache.pdfbox.pdmodel.PDDocumentInformation`` contract, so the suite holds
WITHOUT the oracle jar. The trailing ``_oracle`` test re-asserts the parse/format
results against the live jar when it is available (skipped otherwise), guarding
against silent drift.

Coverage:

* get/set each standard field (Title/Author/Subject/Keywords/Creator/Producer).
* ``get_creation_date`` / ``get_modification_date`` parsing the full PDF date
  shape ``D:YYYYMMDDHHmmSS(+|-)HH'mm'`` and every truncation (``D:2020`` ..
  ``D:YYYYMMDDHHmmSS``).
* Timezone variants: ``Z``, ``+``, ``-``, missing trailing apostrophe,
  ``Z``-then-offset, no-apostrophe ``+HHMM`` form.
* Malformed dates -> the typed accessor returns ``None`` (matching upstream's
  ``null``).
* ``set_creation_date`` round-tripping a ``datetime`` back to the ``D:`` string
  (zero offset renders ``+00'00'``, never ``Z``; naive anchored to UTC).
* Custom metadata keys: ``get_custom_metadata_value`` /
  ``get_metadata_keys`` / standard-vs-custom partition.
* ``/Trapped`` name values (``True``/``False``/``Unknown``), string fallback,
  and the ``ValueError`` on an out-of-spec value.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.pd_document_information import (
    PDDocumentInformation,
)

# --------------------------------------------------------------------------- #
# Standard string fields
# --------------------------------------------------------------------------- #

_STD_FIELDS = [
    ("title", "get_title", "set_title", "Title"),
    ("author", "get_author", "set_author", "Author"),
    ("subject", "get_subject", "set_subject", "Subject"),
    ("keywords", "get_keywords", "set_keywords", "Keywords"),
    ("creator", "get_creator", "set_creator", "Creator"),
    ("producer", "get_producer", "set_producer", "Producer"),
]


@pytest.mark.parametrize(
    ("name", "getter", "setter", "cos_key"),
    _STD_FIELDS,
    ids=[f[0] for f in _STD_FIELDS],
)
def test_standard_field_get_set_clear(name, getter, setter, cos_key):
    info = PDDocumentInformation()
    assert getattr(info, getter)() is None
    getattr(info, setter)(f"value-{name}")
    assert getattr(info, getter)() == f"value-{name}"
    # The COS value is a real COSString under the spec key.
    cos_val = info.get_cos_object().get_dictionary_object(cos_key)
    assert isinstance(cos_val, COSString)
    assert cos_val.get_string() == f"value-{name}"
    # Setting None clears the entry entirely.
    getattr(info, setter)(None)
    assert getattr(info, getter)() is None
    assert not info.get_cos_object().contains_key(cos_key)


def test_standard_field_unicode_roundtrip():
    info = PDDocumentInformation()
    info.set_title("Tïtlé — café ☕")
    info.set_author("Łukasz")
    assert info.get_title() == "Tïtlé — café ☕"
    assert info.get_author() == "Łukasz"


def test_non_string_typed_value_reads_none():
    # A COSName value under /Title is not a string -> typed accessor None,
    # but the key is still present (has_* reports presence only).
    info = PDDocumentInformation()
    info.get_cos_object().set_item("Title", COSName.get_pdf_name("notastring"))
    assert info.get_title() is None
    assert info.has_title()


# --------------------------------------------------------------------------- #
# PDF date parsing — full shape + truncations + tz variants
# --------------------------------------------------------------------------- #

# (date string, expected epoch millis, expected offset millis) — captured from
# live PDFBox 3.0.7 DateConvertProbe parse mode. None expected => upstream null.
_PARSE_CASES: list[tuple[str, _dt.datetime | None]] = [
    # Full shape, +05'30'.
    (
        "D:20200304121530+05'30'",
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
        ),
    ),
    # Truncations — missing components default to Jan/1/00:00:00 UTC.
    ("D:2020", _dt.datetime(2020, 1, 1, tzinfo=_dt.UTC)),
    ("D:202003", _dt.datetime(2020, 3, 1, tzinfo=_dt.UTC)),
    ("D:20200304", _dt.datetime(2020, 3, 4, tzinfo=_dt.UTC)),
    ("D:2020030412", _dt.datetime(2020, 3, 4, 12, tzinfo=_dt.UTC)),
    ("D:202003041215", _dt.datetime(2020, 3, 4, 12, 15, tzinfo=_dt.UTC)),
    ("D:20200304121530", _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.UTC)),
    # Z timezone.
    ("D:20200304121530Z", _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.UTC)),
    # Negative offset.
    (
        "D:20200304121530-08'00'",
        _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=-8))),
    ),
    # Missing trailing apostrophe still parses.
    (
        "D:20200304121530+05'",
        _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5))),
    ),
    # No apostrophes at all.
    (
        "D:20200304121530+0530",
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
        ),
    ),
    # Z followed by an explicit offset — PDFBox takes the offset.
    (
        "D:20200304121530Z05'00'",
        _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5))),
    ),
    # GMT / UTC prefixed offsets.
    (
        "D:20200304121530GMT+05:30",
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
        ),
    ),
    ("D:20200304121530UTC", _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.UTC)),
    # Fractional seconds dropped, offset retained.
    (
        "D:20200304121530.123+05'30'",
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
        ),
    ),
    # ISO 8601.
    ("2024-03-15T12:00:00Z", _dt.datetime(2024, 3, 15, 12, 0, 0, tzinfo=_dt.UTC)),
    # Named-month shape.
    ("26 May 2020 11:25:10", _dt.datetime(2020, 5, 26, 11, 25, 10, tzinfo=_dt.UTC)),
    # Epoch.
    ("D:19700101000000Z", _dt.datetime(1970, 1, 1, tzinfo=_dt.UTC)),
    # Malformed / out-of-range -> None (PDFBox null).
    ("D:20200304121560Z", None),  # second 60
    ("D:20201304121530Z", None),  # month 13
    ("D:20200231121530Z", None),  # Feb 31
    ("D:20200304241530Z", None),  # hour 24
    ("D:20200304121530+", None),  # dangling sign
    ("garbage", None),
    ("D:", None),
    ("D:    ", None),
    ("", None),
]


@pytest.mark.parametrize(
    ("date_str", "expected"),
    _PARSE_CASES,
    ids=[c[0].replace("'", "q").replace(" ", "_").replace(":", "c") or "empty"
         for c in _PARSE_CASES],
)
def test_get_creation_date_parses(date_str, expected):
    info = PDDocumentInformation()
    info.set_property_string_value("CreationDate", date_str)
    got = info.get_creation_date()
    if expected is None:
        assert got is None
    else:
        assert got is not None
        # Compare absolute instant + displayed offset (matches the oracle's
        # epoch-millis + offset-millis pinning).
        assert got == expected
        assert got.utcoffset() == expected.utcoffset()


def test_get_modification_date_uses_mod_date_key():
    info = PDDocumentInformation()
    info.set_property_string_value("ModDate", "D:20991231235959Z")
    assert info.get_modification_date() == _dt.datetime(
        2099, 12, 31, 23, 59, 59, tzinfo=_dt.UTC
    )
    # CreationDate untouched.
    assert info.get_creation_date() is None


# --------------------------------------------------------------------------- #
# Date formatting (set_* -> D: string)
# --------------------------------------------------------------------------- #

_FORMAT_CASES = [
    (
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
        ),
        "D:20200304121530+05'30'",
    ),
    (
        _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.UTC),
        "D:20200304121530+00'00'",  # zero offset is +00'00', never Z
    ),
    (
        _dt.datetime(2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=-8))),
        "D:20200304121530-08'00'",
    ),
    (
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=-3, minutes=-30))
        ),
        "D:20200304121530-03'30'",
    ),
    (
        # Naive datetime -> anchored to UTC -> +00'00'.
        _dt.datetime(2021, 6, 1, 8, 0, 0),
        "D:20210601080000+00'00'",
    ),
]


@pytest.mark.parametrize(
    ("dt_value", "expected"),
    _FORMAT_CASES,
    ids=["plus0530", "utc", "minus08", "minus0330", "naive"],
)
def test_set_creation_date_formats(dt_value, expected):
    info = PDDocumentInformation()
    info.set_creation_date(dt_value)
    assert info.get_property_string_value("CreationDate") == expected


@pytest.mark.parametrize(
    "dt_value",
    [
        _dt.datetime(
            2020, 3, 4, 12, 15, 30, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
        ),
        _dt.datetime(1999, 12, 31, 23, 59, 59, tzinfo=_dt.timezone(_dt.timedelta(hours=-7))),
        _dt.datetime(2000, 1, 1, 0, 0, 0, tzinfo=_dt.UTC),
    ],
    ids=["plus0530", "minus07", "utc"],
)
def test_date_round_trip(dt_value):
    info = PDDocumentInformation()
    info.set_modification_date(dt_value)
    back = info.get_modification_date()
    assert back == dt_value
    assert back.utcoffset() == dt_value.utcoffset()


def test_set_date_none_clears():
    info = PDDocumentInformation()
    info.set_creation_date(_dt.datetime(2020, 1, 1, tzinfo=_dt.UTC))
    assert info.has_creation_date()
    info.set_creation_date(None)
    assert not info.has_creation_date()
    assert info.get_creation_date() is None


# --------------------------------------------------------------------------- #
# /Trapped
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("value", "expected_bool"),
    [("True", True), ("False", False), ("Unknown", None)],
)
def test_trapped_name_values(value, expected_bool):
    info = PDDocumentInformation()
    info.set_trapped(value)
    assert info.get_trapped() == value
    # Stored as a COSName per spec.
    assert isinstance(info.get_cos_object().get_dictionary_object("Trapped"), COSName)
    assert info.is_trapped() is expected_bool


def test_trapped_invalid_raises():
    info = PDDocumentInformation()
    with pytest.raises(ValueError):
        info.set_trapped("Maybe")
    # Nothing was written.
    assert not info.has_trapped()


def test_trapped_none_clears():
    info = PDDocumentInformation()
    info.set_trapped("True")
    info.set_trapped(None)
    assert not info.has_trapped()
    assert info.get_trapped() is None


def test_trapped_string_fallback_read():
    # Some real-world PDFs store /Trapped as a COSString; PDFBox's
    # getNameAsString accepts it, so get_trapped must too.
    info = PDDocumentInformation()
    info.get_cos_object().set_item("Trapped", COSString("Unknown"))
    assert info.get_trapped() == "Unknown"
    assert info.is_trapped() is None


def test_trapped_unexpected_type_reads_none():
    info = PDDocumentInformation()
    info.get_cos_object().set_int("Trapped", 1)
    assert info.get_trapped() is None
    assert info.is_trapped() is None


# --------------------------------------------------------------------------- #
# Custom metadata
# --------------------------------------------------------------------------- #

def test_custom_metadata_value_get_set():
    info = PDDocumentInformation()
    assert info.get_custom_metadata_value("Department") is None
    info.set_custom_metadata_value("Department", "Engineering")
    assert info.get_custom_metadata_value("Department") == "Engineering"
    assert info.has_custom_metadata_value("Department")
    info.set_custom_metadata_value("Department", None)
    assert info.get_custom_metadata_value("Department") is None
    assert not info.has_custom_metadata_value("Department")


def test_metadata_keys_partition_standard_and_custom():
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_author("A")
    info.set_custom_metadata_value("Foo", "1")
    info.set_custom_metadata_value("Bar", "2")
    # get_metadata_keys returns ALL keys, sorted.
    assert info.get_metadata_keys() == ["Author", "Bar", "Foo", "Title"]
    # Custom-only excludes the standard spec keys.
    assert info.get_custom_metadata_keys() == ["Bar", "Foo"]
    # Standard-only excludes the custom keys.
    assert info.get_standard_metadata_keys() == ["Author", "Title"]


def test_metadata_keys_set_membership():
    info = PDDocumentInformation()
    info.set_creator("c")
    info.set_custom_metadata_value("X", "y")
    keys = info.get_metadata_keys_set()
    assert keys == {"Creator", "X"}


def test_custom_value_shares_standard_field_storage():
    # set_custom_metadata_value on a standard key collides with the typed
    # setter (same underlying dict), matching upstream's flat /Info map.
    info = PDDocumentInformation()
    info.set_custom_metadata_value("Title", "from-custom")
    assert info.get_title() == "from-custom"
    assert info.get_custom_metadata_value("Title") == "from-custom"


# --------------------------------------------------------------------------- #
# Live oracle re-pin (skipped without the jar)
# --------------------------------------------------------------------------- #

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except ImportError:  # pragma: no cover - harness always present in-repo
    requires_oracle = None


_ORACLE_PARSE = [c[0] for c in _PARSE_CASES if c[1] is not None]


@pytest.mark.skipif(requires_oracle is None, reason="oracle harness unavailable")
@pytest.mark.parametrize(
    "date_str",
    _ORACLE_PARSE,
    ids=[s.replace("'", "q").replace(" ", "_").replace(":", "c") for s in _ORACLE_PARSE],
)
def test_parse_matches_live_oracle(date_str):
    pytest.importorskip("tests.oracle.harness")
    from tests.oracle.harness import oracle_available

    if not oracle_available():
        pytest.skip("oracle jar not downloaded")
    java = run_probe_text("DateConvertProbe", "parse", date_str).strip()
    info = PDDocumentInformation()
    info.set_property_string_value("CreationDate", date_str)
    got = info.get_creation_date()
    assert got is not None
    epoch = int(got.timestamp() * 1000)
    off = int(got.utcoffset().total_seconds() * 1000)
    assert java == f"{epoch} {off}"
