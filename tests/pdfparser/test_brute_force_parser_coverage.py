"""Wave 1315: hand-written coverage tests for ``BruteForceParser``.

Targets the recovery parser's public surface — object marker scanning,
xref rebuild, catalog/info heuristics, nearest-value helper, and the
``getattr``-based fallbacks for delegators that have no specialized
implementation in the inherited ``COSParser`` yet."""

from __future__ import annotations

from pypdfbox.cos import COSDocument
from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BruteForceParser


def _make_parser(payload: bytes) -> BruteForceParser:
    return BruteForceParser(RandomAccessReadBuffer(payload), COSDocument())


# ----------------------------------------------------------------------
# bf_search_for_objects — delegates to inherited COSParser implementation
# ----------------------------------------------------------------------


def test_bf_search_for_objects_finds_single_marker() -> None:
    """``1 0 obj`` header is detected and mapped to its byte offset."""
    payload = b"%PDF-1.4\n1 0 obj\n<< /Length 0 >>\nendobj\n%%EOF\n"
    parser = _make_parser(payload)
    offsets = parser.bf_search_for_objects()
    key = COSObjectKey(1, 0)
    assert key in offsets
    # Offset points at the start of the object number digit.
    assert payload[offsets[key]:offsets[key] + 1] == b"1"


def test_bf_search_for_objects_finds_multiple_objects() -> None:
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /A 1 >>\nendobj\n"
        b"2 0 obj\n<< /B 2 >>\nendobj\n"
        b"7 0 obj\n<< /C 3 >>\nendobj\n"
        b"%%EOF\n"
    )
    parser = _make_parser(payload)
    offsets = parser.bf_search_for_objects()
    assert COSObjectKey(1, 0) in offsets
    assert COSObjectKey(2, 0) in offsets
    assert COSObjectKey(7, 0) in offsets


def test_bf_search_for_objects_empty_source_returns_empty_map() -> None:
    parser = _make_parser(b"")
    assert parser.bf_search_for_objects() == {}


def test_bf_search_for_objects_skips_endobj_substring() -> None:
    """Bare ``endobj`` token must not be misread as an ``obj`` marker."""
    payload = b"%PDF-1.4\nendobj endobj %%EOF\n"
    parser = _make_parser(payload)
    offsets = parser.bf_search_for_objects()
    assert offsets == {}


# ----------------------------------------------------------------------
# bf_search_for_xref / bf_search_for_x_ref — literal xref + alias
# ----------------------------------------------------------------------


def test_bf_search_for_xref_locates_literal_xref_table() -> None:
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"trailer\n<< /Size 1 >>\nstartxref\n22\n%%EOF\n"
    )
    parser = _make_parser(payload)
    expected_offset = payload.find(b"xref\n")
    assert parser.bf_search_for_xref(0) == expected_offset


def test_bf_search_for_x_ref_alias_matches_canonical() -> None:
    """The upstream-cased alias forwards to the snake_case method."""
    payload = b"%PDF-1.4\nxref\n0 1\n0000000000 65535 f \n%%EOF\n"
    parser = _make_parser(payload)
    assert parser.bf_search_for_x_ref(0) == parser.bf_search_for_xref(0)


def test_bf_search_for_xref_returns_minus_one_when_absent() -> None:
    """No xref token and no recovered objects → ``-1``."""
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.bf_search_for_xref(0) == -1


# ----------------------------------------------------------------------
# Fallback delegators — ``getattr(super(), ..., None)`` paths
# ----------------------------------------------------------------------


def test_bf_search_for_last_eof_marker_fallback_returns_minus_one() -> None:
    """COSParser exposes no ``find_last_eof_marker`` → fallback ``-1``."""
    parser = _make_parser(b"%%EOF\n")
    assert parser.bf_search_for_last_eof_marker() == -1


def test_bf_search_for_obj_stream_offsets_fallback_returns_empty() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.bf_search_for_obj_stream_offsets() == {}


def test_bf_search_for_obj_streams_fallback_is_noop() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    trailer = COSDictionary()
    # Must not raise even with a security_handler kwarg.
    assert parser.bf_search_for_obj_streams(trailer) is None
    assert parser.bf_search_for_obj_streams(trailer, security_handler=None) is None


def test_bf_search_for_x_ref_streams_fallback_returns_empty_list() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.bf_search_for_x_ref_streams() == []


def test_bf_search_for_x_ref_tables_fallback_returns_empty_list() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.bf_search_for_x_ref_tables() == []


def test_find_string_fallback_returns_minus_one() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.find_string(b"%%EOF") == -1


def test_get_bfcos_object_offsets_fallback_returns_empty() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.get_bfcos_object_offsets() == {}


def test_search_for_trailer_items_fallback_returns_false() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.search_for_trailer_items(COSDictionary()) is False


def test_bf_search_for_trailer_fallback_returns_false() -> None:
    parser = _make_parser(b"%PDF-1.4\n%%EOF\n")
    assert parser.bf_search_for_trailer(COSDictionary()) is False


# ----------------------------------------------------------------------
# compare_cos_objects — static helper
# ----------------------------------------------------------------------


class _FakeCOSObject:
    def __init__(self, object_number: int) -> None:
        self.object_number = object_number


def test_compare_cos_objects_equal_returns_zero() -> None:
    a = _FakeCOSObject(5)
    b = _FakeCOSObject(5)
    assert BruteForceParser.compare_cos_objects(a, b) == 0


def test_compare_cos_objects_less_than_returns_negative_one() -> None:
    a = _FakeCOSObject(1)
    b = _FakeCOSObject(9)
    assert BruteForceParser.compare_cos_objects(a, b) == -1


def test_compare_cos_objects_greater_than_returns_positive_one() -> None:
    a = _FakeCOSObject(42)
    b = _FakeCOSObject(7)
    assert BruteForceParser.compare_cos_objects(a, b) == 1


def test_compare_cos_objects_handles_missing_attr_via_default_zero() -> None:
    """``object_number`` missing on either side falls back to ``0``."""
    assert BruteForceParser.compare_cos_objects(object(), object()) == 0


# ----------------------------------------------------------------------
# is_catalog — static heuristic
# ----------------------------------------------------------------------


def test_is_catalog_true_for_typed_catalog_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.CATALOG)
    assert BruteForceParser.is_catalog(d) is True


def test_is_catalog_false_for_dict_without_type() -> None:
    assert BruteForceParser.is_catalog(COSDictionary()) is False


def test_is_catalog_false_for_non_dictionary() -> None:
    assert BruteForceParser.is_catalog("not a dict") is False
    assert BruteForceParser.is_catalog(None) is False
    assert BruteForceParser.is_catalog(COSArray()) is False


# ----------------------------------------------------------------------
# is_info — static heuristic
# ----------------------------------------------------------------------


def test_is_info_true_when_producer_present() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Producer"), COSName.get_pdf_name("pypdfbox"))
    assert BruteForceParser.is_info(d) is True


def test_is_info_true_when_creation_date_present() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("CreationDate"), COSName.get_pdf_name("D:20260516"))
    assert BruteForceParser.is_info(d) is True


def test_is_info_false_for_unrelated_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Length"), COSName.get_pdf_name("0"))
    assert BruteForceParser.is_info(d) is False


def test_is_info_false_for_non_dictionary() -> None:
    assert BruteForceParser.is_info(None) is False
    assert BruteForceParser.is_info(42) is False


# ----------------------------------------------------------------------
# search_nearest_value — pure helper
# ----------------------------------------------------------------------


def test_search_nearest_value_picks_closest() -> None:
    parser = _make_parser(b"")
    assert parser.search_nearest_value([10, 20, 35, 90], 28) == 35


def test_search_nearest_value_first_match_wins_on_tie() -> None:
    """On equal distances the iteration order keeps the first candidate."""
    parser = _make_parser(b"")
    # Distance from 5 → 0 is 5, distance from 10 → 0 is 10; 0 wins.
    # On equal distances (e.g. 5 vs 15 → target 10) the first value seen
    # is kept since ``d < diff`` is strict.
    assert parser.search_nearest_value([5, 15], 10) == 5


def test_search_nearest_value_empty_iterable_returns_minus_one() -> None:
    parser = _make_parser(b"")
    assert parser.search_nearest_value([], 99) == -1


def test_search_nearest_value_single_element() -> None:
    parser = _make_parser(b"")
    assert parser.search_nearest_value([7], 100) == 7


# ----------------------------------------------------------------------
# bf_search_triggered — state mirror
# ----------------------------------------------------------------------


def test_bf_search_triggered_reflects_internal_state() -> None:
    parser = _make_parser(b"%%EOF\n")
    assert parser.bf_search_triggered() is False
    parser._bf_search_triggered = True
    assert parser.bf_search_triggered() is True
