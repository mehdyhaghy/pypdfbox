"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/COSDictionaryTest.java
"""

from __future__ import annotations

import datetime as dt

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)


def test_cos_dictionary_not_equals_cos_stream() -> None:
    cos_dictionary = COSDictionary()
    cos_stream = COSStream()
    cos_dictionary.set_item(COSName.BE, COSName.BE)  # type: ignore[attr-defined]
    cos_dictionary.set_int(COSName.LENGTH, 0)  # type: ignore[attr-defined]
    cos_stream.set_item(COSName.BE, COSName.BE)  # type: ignore[attr-defined]
    assert cos_dictionary != cos_stream, (
        "a COSDictionary shall not be equal to a COSStream with the same dictionary entries"
    )
    assert cos_stream != cos_dictionary, (
        "a COSStream shall not be equal to a COSDictionary with the same dictionary entries"
    )
    cos_stream.close()


# ---------- additional parity coverage for round-out wave ----------
#
# These are pypdfbox-original tests (no upstream JUnit equivalent), kept
# alongside the upstream port because they verify behavior parity with
# Apache PDFBox 3.0's ``COSDictionary`` API surface (date / embedded
# helpers, indirect-object-key traversal, ``getObjectFromPath``,
# ``forEach``).


def test_for_each_visits_every_entry() -> None:
    d = COSDictionary([(COSName.A, COSInteger(1)), (COSName.B, COSInteger(2))])
    seen: list[tuple[str, int]] = []
    d.for_each(lambda k, v: seen.append((k.name, v.value)))  # type: ignore[attr-defined]
    assert seen == [("A", 1), ("B", 2)]


def test_get_cos_name_two_arg_default() -> None:
    fallback = COSName.get_pdf_name("XObject")
    d = COSDictionary([(COSName.TYPE, COSName.PAGE)])
    assert d.get_cos_name(COSName.TYPE) is COSName.PAGE
    assert d.get_cos_name(COSName.SUBTYPE, fallback) is fallback


def test_get_cos_object_distinguishes_indirect_from_direct() -> None:
    inner = COSInteger(7)
    indirect = COSObject(5, 0, resolved=inner)
    d = COSDictionary([(COSName.A, indirect), (COSName.B, inner)])
    assert d.get_cos_object(COSName.A) is indirect
    assert d.get_cos_object(COSName.B) is None


def test_get_cos_stream_returns_resolved_stream() -> None:
    stream = COSStream()
    d = COSDictionary([(COSName.A, stream)])
    assert d.get_cos_stream(COSName.A) is stream
    stream.close()


def test_get_date_round_trip_with_timezone() -> None:
    d = COSDictionary()
    when = dt.datetime(2026, 5, 9, 12, 34, 56, tzinfo=dt.timezone(dt.timedelta(hours=-5)))
    d.set_date(COSName.A, when)
    parsed = d.get_date(COSName.A)
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.utcoffset() == dt.timedelta(hours=-5)


def test_get_embedded_string_default_when_embedded_missing() -> None:
    d = COSDictionary()
    assert d.get_embedded_string(COSName.PARAMS, COSName.A, "fallback") == "fallback"

    d.set_embedded_string(COSName.PARAMS, COSName.A, "value")
    assert d.get_embedded_string(COSName.PARAMS, COSName.A) == "value"


def test_get_embedded_int_default_when_embedded_missing() -> None:
    d = COSDictionary()
    assert d.get_embedded_int(COSName.PARAMS, COSName.A) == -1
    assert d.get_embedded_int(COSName.PARAMS, COSName.A, 99) == 99

    d.set_embedded_int(COSName.PARAMS, COSName.A, 11)
    assert d.get_embedded_int(COSName.PARAMS, COSName.A) == 11


def test_get_object_from_path_dict_array_traversal() -> None:
    rect = COSArray([COSInteger(0), COSInteger(0), COSInteger(72), COSInteger(72)])
    annot = COSDictionary([(COSName.A, rect)])
    page = COSDictionary([(COSName.B, COSArray([annot]))])

    assert page.get_object_from_path("B/[0]") is annot
    assert page.get_object_from_path("B/[0]/A") is rect


def test_get_indirect_object_keys_visits_arrays_and_dicts() -> None:
    referenced = COSObject(7, 0, resolved=COSString("leaf"))
    arr = COSArray([referenced])
    d = COSDictionary([(COSName.A, arr)])
    keys: set[COSObjectKey] = set()
    d.get_indirect_object_keys(keys)
    assert COSObjectKey(7, 0) in keys


def test_to_string_includes_entry_keys() -> None:
    d = COSDictionary([(COSName.TYPE, COSName.PAGE), (COSName.LENGTH, COSInteger(0))])
    assert "Type" in d.to_string()
    assert "Length" in d.to_string()
