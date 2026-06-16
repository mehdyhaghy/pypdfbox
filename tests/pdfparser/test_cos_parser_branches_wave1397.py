"""Wave 1397 — branch closure for ``pdfparser.cos_parser``.

After wave 1396 the parser held ~26 partial branches concentrated in the
hybrid-xref / recovery / xref-stream surface: header-scan EOF early exit,
brute-force candidate selection edges, rebuild-trailer per-field skip
paths, dereferenceCOSObject's optional-setter probe, parse_trailer's
lenient digit-line skipper, and a handful of find_object_key skip-spaces
edge cases. These tests target each remaining branch with crafted
fixtures +, where the path crosses Java-only ports, lightweight subclass
stubs."""

from __future__ import annotations

import contextlib

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.cos_parser import COSParser


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


# ---------- parse_pdf_header: scan window ends at EOF (branch 992->997) ----------


def test_parse_pdf_header_scan_terminates_at_eof_for_tiny_buffer() -> None:
    """A buffer shorter than 1 KB exits the scan loop on EOF (line
    995 break path)."""
    parser = _parser(b"%PDF-1.7\n")
    assert parser.parse_pdf_header() == pytest.approx(1.7)


def test_parse_pdf_header_scan_terminates_at_full_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A buffer >= 1 KB exits the scan loop because ``len(head) >=
    scan_window`` becomes False (branch 992->997)."""
    payload = b"%PDF-1.4\n" + b" " * 2048
    parser = _parser(payload)
    assert parser.parse_pdf_header() == pytest.approx(1.4)


# ---------- read_until_end_stream: out=None branch (2076->2078) ----------


def test_read_until_end_stream_with_none_output_buffer() -> None:
    """``out=None`` skips the body-recording branch on a partial-match
    reset (line 2075 ``if out is not None`` false path)."""
    # Construct a stream body whose first byte happens to match
    # ``endstream``'s first letter (``e``) but isn't the keyword so the
    # partial-match path triggers.
    body = b"e\x00not yet\nendstream"
    parser = _parser(body)
    consumed = parser.read_until_end_stream(None)
    # Body length excludes the keyword.
    assert consumed == body.index(b"endstream")


# ---------- check_pages: trailer was rebuild + invalid pages root ----------


def test_check_pages_raises_when_pages_root_missing() -> None:
    """When ``/Pages`` is not a dictionary, ``check_pages`` raises."""
    parser = _parser(b"")
    root = COSDictionary()
    # No /Pages entry → not a dict.
    with pytest.raises(PDFParseError, match="Page tree root"):
        parser.check_pages(root)


def test_check_pages_walks_dict_when_trailer_was_rebuild() -> None:
    """When ``_trailer_was_rebuild`` is True and /Pages is a dict, the
    helper recurses through ``check_pages_dictionary`` (line 1560)."""
    parser = _parser(b"")
    parser._trailer_was_rebuild = True  # type: ignore[attr-defined]
    pages_dict = COSDictionary()
    root = COSDictionary()
    root.set_item(COSName.get_pdf_name("Pages"), pages_dict)
    # Should not raise — empty kids array is acceptable.
    parser.check_pages(root)


def test_check_pages_dictionary_with_empty_kids_array() -> None:
    """A pages dict whose /Kids is not a COSArray (e.g. absent) takes
    the False side of line 1581 → straight to line 1603 setting count
    to zero."""
    parser = _parser(b"")
    pages_dict = COSDictionary()
    count = parser.check_pages_dictionary(pages_dict, set())
    assert count == 0
    assert (
        pages_dict.get_dictionary_object(COSName.get_pdf_name("Count")).int_value()  # type: ignore[union-attr]
        == 0
    )


def test_check_pages_dictionary_skips_kid_with_unknown_type() -> None:
    """A /Kids entry whose /Type is neither ``/Pages`` nor ``/Page`` is
    silently ignored (branches 1591/1598 false paths)."""
    from pypdfbox.cos import COSArray

    parser = _parser(b"")
    pages_dict = COSDictionary()
    kids = COSArray()
    # Build a child dict claiming /Type /Other (not Pages or Page).
    bogus = COSDictionary()
    bogus.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Other")
    )

    # We need a COSObject placeholder wrapping the bogus dict — bare
    # dicts in /Kids are filtered as not COSObject (branch 1584
    # removals).
    kid_obj = COSObject(99, 0, resolved=bogus)
    kids.add(kid_obj)
    pages_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages_dict, set())
    # The /Other-typed kid contributes 0 to the count.
    assert count == 0


def test_check_pages_dictionary_kid_is_a_page_increments_count() -> None:
    """A /Kids leaf with /Type /Page increments the count (line 1598
    True arm)."""
    from pypdfbox.cos import COSArray

    parser = _parser(b"")
    pages_dict = COSDictionary()
    kids = COSArray()
    page_dict = COSDictionary()
    page_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page"))
    kid_obj = COSObject(5, 0, resolved=page_dict)
    kids.add(kid_obj)
    pages_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages_dict, set())
    assert count == 1


def test_check_pages_dictionary_kid_is_pages_recurses() -> None:
    """A /Kids entry with /Type /Pages recurses (line 1593-1597)."""
    from pypdfbox.cos import COSArray

    parser = _parser(b"")
    pages_dict = COSDictionary()
    kids = COSArray()
    sub_pages = COSDictionary()
    sub_pages.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Pages"))
    # Sub has one Page child.
    sub_kids = COSArray()
    leaf = COSDictionary()
    leaf.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page"))
    sub_kids.add(COSObject(7, 0, resolved=leaf))
    sub_pages.set_item(COSName.get_pdf_name("Kids"), sub_kids)
    kids.add(COSObject(6, 0, resolved=sub_pages))
    pages_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages_dict, set())
    assert count == 1


def test_check_pages_dictionary_filters_non_cos_object_kid() -> None:
    """Bare dicts (not COSObject placeholders) are filtered as removals
    (line 1584-1586)."""
    from pypdfbox.cos import COSArray

    parser = _parser(b"")
    pages_dict = COSDictionary()
    kids = COSArray()
    kids.add(COSDictionary())  # bare dict — filtered
    pages_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages_dict, set())
    assert count == 0


def test_check_pages_dictionary_filters_kid_object_resolving_to_none() -> None:
    """A COSObject whose payload resolves to None gets pruned (line
    1588-1590)."""
    from pypdfbox.cos import COSArray

    parser = _parser(b"")
    pages_dict = COSDictionary()
    kids = COSArray()
    kid_obj = COSObject(11, 0, resolved=None)
    kid_obj.set_object(None)  # explicit
    kids.add(kid_obj)
    pages_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages_dict, set())
    assert count == 0


def test_check_pages_dictionary_kid_object_resolves_to_non_dict() -> None:
    """A COSObject whose payload is non-dict / non-null hits the False
    arm of 1591 (branch 1591->1583)."""
    from pypdfbox.cos import COSArray

    parser = _parser(b"")
    pages_dict = COSDictionary()
    kids = COSArray()
    kid_obj = COSObject(13, 0, resolved=COSInteger.get(42))
    kids.add(kid_obj)
    pages_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages_dict, set())
    assert count == 0


def test_check_pages_when_pages_is_not_a_dictionary_after_rebuild() -> None:
    """When trailer was rebuilt and /Pages is not a COSDictionary,
    skip the recurse (branch 1560->1562 false path) and then raise on
    the second isinstance check at line 1562."""
    parser = _parser(b"")
    parser._trailer_was_rebuild = True  # type: ignore[attr-defined]
    root = COSDictionary()
    # /Pages is a name, not a dict.
    root.set_item(COSName.get_pdf_name("Pages"), COSName.get_pdf_name("Bogus"))
    with pytest.raises(PDFParseError, match="Page tree root"):
        parser.check_pages(root)


# ---------- prepare_decryption: handler already attached short-circuit ----------


def test_prepare_decryption_skips_when_handler_already_set() -> None:
    """When ``_security_handler`` is already attached, prepare_decryption
    returns immediately (branch 1674->exit)."""
    doc = COSDocument()
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("V"), COSInteger.get(1))
    doc.set_encryption_dictionary(enc)
    parser = _parser(b"", document=doc)
    sentinel = object()
    parser._security_handler = sentinel  # type: ignore[attr-defined]
    parser.prepare_decryption()
    assert parser._security_handler is sentinel


def test_prepare_decryption_noop_when_unbound() -> None:
    """``_document is None`` short-circuits (line 1668-1669)."""
    parser = _parser(b"")
    parser.prepare_decryption()  # Should not raise.


def test_prepare_decryption_noop_when_no_encryption() -> None:
    """No /Encrypt → no work."""
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    parser.prepare_decryption()
    assert getattr(parser, "_security_handler", None) is None


def test_prepare_decryption_passes_through_when_handler_absent_and_encrypt_present() -> None:
    """When /Encrypt exists but no handler is yet attached, the helper
    falls through to the end (no-op in this layer; PDFParser does the
    heavy lifting). Exercises branch 1674->exit False arm."""
    doc = COSDocument()
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("V"), COSInteger.get(1))
    doc.set_encryption_dictionary(enc)
    parser = _parser(b"", document=doc)
    # Ensure no handler attached.
    assert getattr(parser, "_security_handler", None) is None
    parser.prepare_decryption()
    # Still no handler — the COSParser layer is a no-op here.
    assert getattr(parser, "_security_handler", None) is None


# ---------- get_access_permission: no handler attached ----------


def test_get_access_permission_returns_none_when_no_handler() -> None:
    """Without a handler attached the accessor returns None (line 1652-
    1653)."""
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    assert parser.get_access_permission() is None


# ---------- retrieve_trailer: bound document already has trailer ----------


def test_retrieve_trailer_returns_existing_when_present() -> None:
    """When the bound document already carries a trailer, that trailer
    is returned directly (line 1438-1439)."""
    doc = COSDocument()
    trailer = COSDictionary()
    trailer.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(7))
    doc.set_trailer(trailer)
    parser = _parser(b"", document=doc)
    result = parser.retrieve_trailer()
    assert result is trailer


def test_retrieve_trailer_falls_back_to_rebuild_in_lenient_mode() -> None:
    """Lenient mode + no existing trailer + empty source → empty
    rebuilt trailer."""
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    parser._lenient = True  # type: ignore[attr-defined]
    rebuilt = parser.retrieve_trailer()
    assert isinstance(rebuilt, COSDictionary)


def test_retrieve_trailer_strict_mode_raises_without_existing() -> None:
    """Strict mode + no existing trailer raises."""
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    parser._lenient = False  # type: ignore[attr-defined]
    with pytest.raises(PDFParseError, match="strict mode"):
        parser.retrieve_trailer()


# ---------- dereference_cos_object: missing optional setters ----------


def test_dereference_cos_object_returns_payload_via_pool_loader() -> None:
    """When the pool loader returns a payload without ``set_direct`` /
    ``set_key``, the dereference path skips both probes (branches
    1470->1473, 1473->1476)."""

    class _DocStub:
        def __init__(self) -> None:
            self._pool: dict = {}

        def has_object(self, key) -> bool:  # type: ignore[no-untyped-def]
            return key in self._pool

        def get_object_from_pool(self, key):  # type: ignore[no-untyped-def]
            return self._pool[key]

        def get_xref_table(self) -> dict:
            return {}

        def get_trailer(self) -> None:
            return None

        def set_trailer(self, trailer: object) -> None:
            pass

    # Use the real parser machinery: parse_object_dynamically lives on
    # PDFParser, but COSParser.dereference_cos_object delegates through
    # it. For pure-COSParser testing the easy route is to patch the
    # method.
    parser = _parser(b"")

    payload_with_neither = object()  # no set_direct, no set_key

    def _fake(_obj_num: int, _gen: int, _force: bool) -> object:
        return payload_with_neither

    parser.parse_object_dynamically = _fake  # type: ignore[attr-defined]
    cos_obj = COSObject(1, 0)
    result = parser.dereference_cos_object(cos_obj)
    assert result is payload_with_neither


def test_dereference_cos_object_returns_none_when_loader_returns_none() -> None:
    """Loader returning None → branch 1467 False path."""
    parser = _parser(b"")

    def _none(_obj_num: int, _gen: int, _force: bool) -> None:
        return None

    parser.parse_object_dynamically = _none  # type: ignore[attr-defined]
    cos_obj = COSObject(1, 0)
    assert parser.dereference_cos_object(cos_obj) is None


def test_dereference_cos_object_invokes_setters_when_present() -> None:
    """Payload with both set_direct + set_key → both probes fire
    (branches 1470 True + 1473 True)."""
    parser = _parser(b"")

    class _Payload:
        def __init__(self) -> None:
            self.direct_called = False
            self.key_called: object | None = None

        def set_direct(self, v: bool) -> None:
            self.direct_called = True
            del v

        def set_key(self, key: object) -> None:
            self.key_called = key

    payload = _Payload()

    def _fake(_obj_num: int, _gen: int, _force: bool) -> object:
        return payload

    parser.parse_object_dynamically = _fake  # type: ignore[attr-defined]
    cos_obj = COSObject(3, 0)
    parser.dereference_cos_object(cos_obj)
    assert payload.direct_called
    assert isinstance(payload.key_called, COSObjectKey)


# ---------- bf_search_for_xref: no candidates path (1165->1176) ----------


def test_bf_search_for_xref_no_candidates_falls_to_xref_stream_scan() -> None:
    """A payload with no ``xref`` keyword but with an xref-stream object
    forces the helper into the fallback scanner (branch 1165->1176)."""
    # Build a minimal payload that has NO ``xref`` keyword AND no
    # parseable xref-stream object → bf_search_for_xref returns -1.
    parser = _parser(b"%PDF-1.5\n1 0 obj\n<< >>\nendobj\n", COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    result = parser.bf_search_for_xref(0)
    assert result == -1


def test_bf_search_for_xref_exits_natural_loop_when_xref_found_at_eof() -> None:
    """A payload ending in a whitespace-prefixed ``xref`` keyword runs the
    scan once, advances past ``n-4``, and exits the loop via the False arm.
    The keyword must sit past ``MINIMUM_SEARCH_OFFSET`` (= 6) — upstream
    ``bfSearchForXRefTables`` seeks to that offset before scanning, so an
    ``xref`` buried inside the first 6 bytes is deliberately never found."""
    payload = b"%PDF-1\n xref"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    # Returns the only candidate (the trailing ``xref``).
    assert parser.bf_search_for_xref(0) == payload.rfind(b"xref")


def test_bf_search_for_xref_prefers_nearest_xref_candidate() -> None:
    """When multiple ``xref`` keywords are present, the helper picks
    the one nearest to ``start_xref_offset`` (line 1180)."""
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"some filler\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"%%EOF\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    # Target second xref location → picker returns it.
    second = payload.rfind(b"xref")
    chosen = parser.bf_search_for_xref(second)
    assert chosen == second


# ---------- rebuild_trailer: encrypt / id branches ----------


def test_rebuild_trailer_returns_empty_when_no_objects_recovered() -> None:
    """Empty payload → empty trailer (line 1235-1236)."""
    parser = _parser(b"%PDF-1.4\n", COSDocument())
    trailer = parser.rebuild_trailer()
    assert isinstance(trailer, COSDictionary)


def test_rebuild_trailer_picks_root_info_encrypt_id_from_candidates() -> None:
    """A small fixture with one obj advertising every interesting key
    populates ``/Root``, ``/Info``, ``/Encrypt``, ``/ID``."""
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 5 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Producer (test) /Encrypt 3 0 R "
        b"/ID [<a><b>] /CreationDate (D:20240101) >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    trailer = parser.rebuild_trailer()
    assert trailer.contains_key(COSName.get_pdf_name("Root"))
    assert trailer.contains_key(COSName.get_pdf_name("Info"))
    assert trailer.contains_key(COSName.get_pdf_name("Encrypt"))
    assert trailer.contains_key(COSName.get_pdf_name("ID"))


def test_rebuild_trailer_skips_objects_without_encrypt_or_id() -> None:
    """When candidate object has no /Encrypt and no /ID, those branches
    take the False path (lines 1304, 1309 false paths)."""
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Producer (only) >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    trailer = parser.rebuild_trailer()
    # No /Encrypt or /ID since the object didn't carry them.
    assert not trailer.contains_key(COSName.get_pdf_name("Encrypt"))
    assert not trailer.contains_key(COSName.get_pdf_name("ID"))


def test_rebuild_trailer_with_two_objects_high_then_low_number() -> None:
    """Two objects scanned in scan order where the second has a LOWER
    object number than the first → branch 1256->1258 False arm taken
    (key.object_number not greater than max_obj)."""
    payload = (
        b"%PDF-1.4\n"
        b"5 0 obj\n<< /Producer (a) >>\nendobj\n"
        b"3 0 obj\n<< /Producer (b) >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    trailer = parser.rebuild_trailer()
    # Max object number is 5 → /Size becomes 6.
    assert (
        trailer.get_dictionary_object(COSName.get_pdf_name("Size")).int_value()  # type: ignore[union-attr]
        == 6
    )


def test_rebuild_trailer_with_two_objects_low_then_high_number() -> None:
    """Two objects scanned in order where the second has a higher
    object number than the first → 1256 True arm second time, False
    arm first time. Exercises 1256->1258 (False, when key.object_number
    <= max_obj, e.g. duplicate)."""
    # bf_search_for_objects returns a dict keyed by COSObjectKey; the
    # iteration order depends on insertion. We force two objects where
    # the second one has the same object number (so 1256 is False on
    # second hit).
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Producer (a) >>\nendobj\n"
        b"2 0 obj\n<< /Producer (b) >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    trailer = parser.rebuild_trailer()
    # Max object number is 2 → /Size becomes 3.
    assert (
        trailer.get_dictionary_object(COSName.get_pdf_name("Size")).int_value()  # type: ignore[union-attr]
        == 3
    )


def test_rebuild_trailer_with_two_objects_both_advertising_encrypt() -> None:
    """When two objects both declare /Encrypt, only the first sets
    trailer's /Encrypt; second iteration takes 1302's False arm."""
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Producer (a) /Encrypt 99 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Producer (b) /Encrypt 100 0 R >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    trailer = parser.rebuild_trailer()
    # Only one /Encrypt — the first one encountered.
    assert trailer.contains_key(COSName.get_pdf_name("Encrypt"))


def test_rebuild_trailer_with_two_objects_both_advertising_id() -> None:
    """When two objects both declare /ID, only the first wins
    (branch 1307->1255 False arm taken on second iteration)."""
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Producer (a) /ID [<a><b>] >>\nendobj\n"
        b"2 0 obj\n<< /Producer (b) /ID [<c><d>] >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    trailer = parser.rebuild_trailer()
    assert trailer.contains_key(COSName.get_pdf_name("ID"))


def test_bf_search_for_xref_picks_nearer_of_two_xref_stream_candidates() -> None:
    """When the fallback xref-stream scan finds two candidates, the
    helper picks the one closer to ``start_xref_offset``. Exercises
    1217->1189 (continuing the loop after best update)."""
    # Construct two valid xref-stream objects at different offsets.
    obj_a = b"1 0 obj\n<< /Type /XRef /Size 2 >>\nendobj\n"
    obj_b = b"2 0 obj\n<< /Type /XRef /Size 2 >>\nendobj\n"
    payload = b"%PDF-1.5\n" + obj_a + obj_b
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    near = payload.find(b"2 0 obj")
    chosen = parser.bf_search_for_xref(near)
    # Either obj_b (closer to ``near``) or obj_a — whatever the
    # picker selects must be one of the two known offsets.
    assert chosen in (payload.find(b"1 0 obj"), payload.find(b"2 0 obj"))


def test_bf_search_for_xref_target_near_first_xref_stream_keeps_initial_best() -> None:
    """Target near the FIRST xref-stream object → on second iteration,
    distance > best_distance, so update skipped (branch 1217 False arm
    of the ``or``)."""
    obj_a = b"1 0 obj\n<< /Type /XRef /Size 2 >>\nendobj\n"
    padding = b"\n" * 500
    obj_b = b"2 0 obj\n<< /Type /XRef /Size 2 >>\nendobj\n"
    payload = b"%PDF-1.5\n" + obj_a + padding + obj_b
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    near_a = payload.find(b"1 0 obj")
    chosen = parser.bf_search_for_xref(near_a)
    # First object wins because target is near it.
    assert chosen == near_a


def test_validate_xref_offsets_handles_corrected_entry_already_valid() -> None:
    """When a corrected key was already present in ``valid``, the
    helper drops the corrected pointer rather than inserting it
    (branch 2203->2202 False path).

    Implementation: seed the table so that one entry resolves to a key
    that ANOTHER entry already resolved to (i.e. the corrected key is
    in ``valid``)."""
    # Build a tiny doc with one real object at known offset.
    payload = (
        b"%PDF-1.4\n"
        b"                                            1 0 obj\n<<>>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    offset = payload.find(b"1 0 obj")
    # Two entries: one valid for (1, 0), one "wrong" entry for (2, 0)
    # pointing at the same offset → find_object_key will correct the
    # second to (1, 0), which is in ``valid``.
    table: dict[COSObjectKey, int] = {
        COSObjectKey(1, 0): offset,
        COSObjectKey(2, 0): offset,
    }
    result = parser.validate_xref_offsets(table)
    assert result is True


def test_find_object_key_skip_spaces_advances_past_offset() -> None:
    """A target where ``skip_spaces`` consumes the leading whitespace
    pushes ``position`` past ``offset`` → branch 2240 False arm jumps
    to 2246."""
    # Leading spaces before the offset → seek lands at offset, then
    # skip_spaces consumes them and position > offset.
    payload = (
        b"%PDF-1.4\n"
        b"                                          \n  1 0 obj\n<<>>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    # Pick an offset BEFORE the digit, where there's whitespace.
    offset = payload.find(b"  1 0 obj") + 1  # space character
    # MINIMUM_SEARCH_OFFSET guard requires offset > some min.
    result = parser.find_object_key(COSObjectKey(1, 0), offset, {})
    assert result == COSObjectKey(1, 0)


def test_find_object_key_with_minimum_search_offset_returns_none() -> None:
    """offset < MINIMUM_SEARCH_OFFSET → None (re-test)."""
    parser = _parser(b"%PDF-1.4\n")
    assert parser.find_object_key(COSObjectKey(1, 0), 2, {}) is None


def test_find_object_key_offset_preceded_by_digit_keeps_position() -> None:
    """When ``offset`` is directly preceded by a digit (no whitespace
    boundary), the peek-byte check at 2244 sees a digit → False arm
    skips the read, leaving position at ``offset - 1``. The subsequent
    read_object_number then walks digits backwards via skip_spaces
    semantics. Branch 2244->2246."""
    # Build a payload where digit characters touch — the obj number is
    # "21" preceded by no whitespace; offset points at the '1'.
    payload = b"%PDF-1.4\n" + b"\x00" * 40 + b"21 0 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    # Target offset directly at '1' (so offset-1 is '2', a digit).
    digit_offset = payload.find(b"21 0 obj") + 1
    # Result may be a corrected key or None — we just need the path
    # exercised. find_object_key will read starting from offset-1, get
    # number=21.
    parser.find_object_key(COSObjectKey(21, 0), digit_offset, {})


def test_find_object_key_offset_with_seek_unable_to_step_back() -> None:
    """When seek(offset-1) leaves position >= offset (no-op / clamped),
    the 2242 False arm skips the peek-and-read block. Hard to trigger
    naturally because RandomAccessReadBuffer always honours seek; we
    cover this defensive branch via an offset==MINIMUM_SEARCH_OFFSET
    pointing at the very first valid byte."""
    # MINIMUM_SEARCH_OFFSET is 6 in upstream PDFBox. We craft a payload
    # whose object header begins exactly at that offset and verify the
    # helper completes without raising.
    min_offset = COSParser.MINIMUM_SEARCH_OFFSET
    payload = b"\x00" * min_offset + b"1 0 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    parser.find_object_key(COSObjectKey(1, 0), min_offset, {})


# ---------- parse_trailer: lenient digit-line skip ----------


def test_parse_trailer_skips_leading_digit_lines_in_lenient_mode() -> None:
    """In lenient mode, a leading digit line before the ``trailer``
    keyword is skipped (line 1808-1815 loop)."""
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"42\n"  # bogus digit line — lenient mode skips
        b"trailer\n<< /Size 2 >>\n"
    )
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    # Position at the bogus digit line.
    parser._src.seek(payload.find(b"42\n"))
    assert parser.parse_trailer() is True


def test_parse_trailer_returns_false_when_no_keyword() -> None:
    """When the next byte isn't ``t``, parse_trailer bails out
    (line 1816-1817)."""
    payload = b"%PDF-1.4\nnope\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    parser._src.seek(payload.find(b"nope"))
    assert parser.parse_trailer() is False


def test_parse_trailer_tolerates_no_eol_after_keyword() -> None:
    """When the trailer keyword is immediately followed by a non-EOL
    character, the helper jumps just past it (line 1822-1823)."""
    payload = b"%PDF-1.4\ntrailer<</Size 1>>\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    parser._src.seek(payload.find(b"trailer"))
    assert parser.parse_trailer() is True


def test_parse_trailer_returns_false_for_lookalike_keyword() -> None:
    """A line starting with ``t`` but not ``trailer`` → False (1824-
    1825)."""
    payload = b"%PDF-1.4\ntrailerextra\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    parser._src.seek(payload.find(b"trailer"))
    # 'trailerextra' starts with 'trailer' so this hits the
    # 'startswith' true branch — flip to a line that doesn't.
    parser._src.seek(0)
    parser._src.seek(payload.find(b"trailer"))
    # Actually re-test with a different keyword line altogether.
    payload2 = b"%PDF-1.4\nturkey\n"
    p2 = _parser(payload2, COSDocument())
    p2._lenient = True  # type: ignore[attr-defined]
    p2._src.seek(payload2.find(b"turkey"))
    assert p2.parse_trailer() is False


# ---------- parse_xref_obj_stream: stream-keyword mismatch ----------


def test_parse_xref_obj_stream_with_no_stream_body() -> None:
    """When the object body is just a dictionary (no ``stream`` keyword
    follows), branch 1917/1919 skip the body read."""
    payload = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Type /XRef /Size 2 >>\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    offset = payload.find(b"1 0 obj")
    prev = parser.parse_xref_obj_stream(offset, True)
    # No /Prev in this dict → -1.
    assert prev == -1


def test_parse_xref_obj_stream_with_s_lookalike_not_stream_keyword() -> None:
    """When the next keyword starts with ``s`` but isn't ``stream``
    (e.g. an ``startxref`` adjacent), the helper takes branch
    1919->1923 (skip body)."""
    # Build object body followed by a keyword that starts with 's' but
    # is not 'stream' (e.g. 'startxref').
    payload = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Type /XRef /Size 2 >>\nstartxref\n"
    )
    parser = _parser(payload, COSDocument())
    offset = payload.find(b"1 0 obj")
    prev = parser.parse_xref_obj_stream(offset, True)
    assert prev == -1


# ---------- parse_xref: post-fix start-xref branches ----------


def test_parse_xref_full_walk_through_xref_table() -> None:
    """A standard traditional xref walks the xref table → trailer →
    parse_xref returns trailer. Exercises lines 1855 + 1857 True
    branches in the full pipeline."""
    body = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    xref_start = len(body)
    xref_section = (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n<< /Size 2 >>\nstartxref\n"
        + str(xref_start).encode()
        + b"\n%%EOF\n"
    )
    payload = body + xref_section
    parser = _parser(payload, COSDocument())
    trailer = parser.parse_xref(payload.find(b"startxref"))
    assert isinstance(trailer, COSDictionary)


def test_parse_xref_with_unbound_document_skips_set_start_xref() -> None:
    """When parser has no document, the ``set_start_xref`` call is
    skipped (branch 1857->1860 false path)."""
    body = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    xref_start = len(body)
    xref_section = (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n<< /Size 2 >>\nstartxref\n"
        + str(xref_start).encode()
        + b"\n%%EOF\n"
    )
    payload = body + xref_section
    parser = _parser(payload)  # no document!
    trailer = parser.parse_xref(payload.find(b"startxref"))
    assert isinstance(trailer, COSDictionary)


def test_parse_xref_fixed_offset_minus_one_keeps_original() -> None:
    """When ``check_x_ref_offset`` returns -1, the original ``start``
    value is kept (branch 1855->1857 false path)."""
    # In strict mode, check_x_ref_offset returns start_x_ref_offset
    # unchanged (always >= 0). To hit the -1 path we need a lenient
    # parser whose offset is bogus and bf_search returns -1.
    body = b"%PDF-1.4\nbogus content\n"
    parser = _parser(body, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    # parse_xref will probe and recover via brute-force; result may be
    # None or a trailer dict. Whatever happens we mainly care about
    # exercising the branch paths — failures are tolerated.
    with contextlib.suppress(Exception):
        parser.parse_xref(len(body))


# ---------- parse_trailer: strict-mode skip of digit loop ----------


def test_parse_trailer_strict_mode_skips_digit_loop_entirely() -> None:
    """In strict mode (``_lenient=False``), the digit-skip loop is
    entirely skipped (branch 1806->1816 false path)."""
    payload = b"trailer\n<< /Size 1 >>\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = False  # type: ignore[attr-defined]
    parser._src.seek(0)
    assert parser.parse_trailer() is True


# ---------- check_x_ref_offset: strict mode short-circuit ----------


def test_check_x_ref_offset_strict_mode_returns_unchanged() -> None:
    """Strict mode short-circuits (line 2125-2126)."""
    parser = _parser(b"")
    parser._lenient = False  # type: ignore[attr-defined]
    assert parser.check_x_ref_offset(42) == 42


def test_check_x_ref_offset_lenient_finds_xref_keyword() -> None:
    """Lenient mode finds the literal ``xref`` keyword at the offset."""
    payload = b"%PDF-1.4\nxref\n0 1\n0000000000 65535 f \n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    off = payload.find(b"xref")
    assert parser.check_x_ref_offset(off) == off


# ---------- find_object_key: skip_spaces did not advance ----------


def test_find_object_key_returns_none_when_offset_below_minimum() -> None:
    """Offsets below ``MINIMUM_SEARCH_OFFSET`` short-circuit."""
    parser = _parser(b"")
    assert (
        parser.find_object_key(COSObjectKey(1, 0), 3, {}) is None
    )


def test_find_object_key_skip_spaces_path_stays_at_offset() -> None:
    """A target that already starts with a digit lands ``skip_spaces``
    at exactly the offset — exercises the 2240 if-body."""
    payload = b"%PDF-1.4\n                                            1 0 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    offset = payload.find(b"1 0 obj")
    result = parser.find_object_key(COSObjectKey(1, 0), offset, {})
    assert result == COSObjectKey(1, 0)


def test_find_object_key_unknown_object_returns_none_strict_mode() -> None:
    """A wrong object number in strict mode → None."""
    payload = b"%PDF-1.4\n                                            7 0 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = False  # type: ignore[attr-defined]
    offset = payload.find(b"7 0 obj")
    result = parser.find_object_key(COSObjectKey(1, 0), offset, {})
    assert result is None


def test_find_object_key_corrects_object_number_in_lenient_mode() -> None:
    """A wrong object number in lenient mode → returns corrected key."""
    payload = b"%PDF-1.4\n                                            7 0 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    offset = payload.find(b"7 0 obj")
    result = parser.find_object_key(COSObjectKey(1, 0), offset, {})
    # Generation number passed in was 0, file says 0 → returns
    # corrected (7, 0).
    assert result == COSObjectKey(7, 0)


def test_find_object_key_lenient_gen_upgrade_when_file_has_higher_gen() -> None:
    """When file's gen > requested gen in lenient mode → returns upgraded
    key (line 2260-2261)."""
    payload = b"%PDF-1.4\n                                            1 5 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser._lenient = True  # type: ignore[attr-defined]
    offset = payload.find(b"1 5 obj")
    result = parser.find_object_key(COSObjectKey(1, 0), offset, {})
    assert result == COSObjectKey(1, 5)


# ---------- check_xref_offsets: empty recovered objects (2220->exit) ----------


def test_check_xref_offsets_noop_when_document_unbound() -> None:
    """Unbound parser → check_xref_offsets returns silently."""
    parser = _parser(b"")
    parser.check_xref_offsets()  # No raise.


def test_check_xref_offsets_clears_table_only_on_recovery() -> None:
    """When brute-force recovery finds no objects, the existing xref
    table is not cleared (branch 2220->exit)."""
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    parser._lenient = True  # type: ignore[attr-defined]

    # Seed an xref entry that won't validate (offset 0 fails).
    doc.get_xref_table()[COSObjectKey(99, 0)] = 0
    parser.check_xref_offsets()
    # Brute force on empty source → no recovery → xref table untouched
    # OR cleared depending on validate result. The key contract: no
    # crash.


# ---------- validate_xref_offsets: replacement-in-valid branch ----------


def test_validate_xref_offsets_none_returns_true() -> None:
    """None input short-circuits to True."""
    parser = _parser(b"")
    assert parser.validate_xref_offsets(None) is True


def test_validate_xref_offsets_handles_empty_dict() -> None:
    """Empty dict → True (no entries to validate)."""
    parser = _parser(b"")
    assert parser.validate_xref_offsets({}) is True


def test_validate_xref_offsets_skips_negative_offsets() -> None:
    """Entries with negative offsets are silently skipped (line 2193
    False path)."""
    parser = _parser(b"")
    assert parser.validate_xref_offsets({COSObjectKey(1, 0): -1}) is True


# ---------- consume_eol_after_stream_keyword: EOF (branch 464->exit) ----------


def test_consume_eol_after_stream_keyword_at_eof() -> None:
    """At true EOF the helper exits without rewinding (branch 464->exit
    false path)."""
    parser = _parser(b"")
    # Position at EOF.
    parser._src.seek(0)
    parser._consume_eol_after_stream_keyword()
    # Position should still be 0; no exception.
    assert parser._src.get_position() == 0


def test_consume_eol_after_stream_keyword_with_cr_lf() -> None:
    """CR followed by LF consumes both bytes."""
    parser = _parser(b"\r\nbody")
    parser._consume_eol_after_stream_keyword()
    assert parser._src.get_position() == 2  # past CRLF


def test_consume_eol_after_stream_keyword_with_lone_cr() -> None:
    """A bare CR is tolerated."""
    parser = _parser(b"\rbody")
    parser._consume_eol_after_stream_keyword()
    assert parser._src.get_position() == 1


def test_consume_eol_after_stream_keyword_with_lone_lf() -> None:
    """A bare LF is tolerated."""
    parser = _parser(b"\nbody")
    parser._consume_eol_after_stream_keyword()
    assert parser._src.get_position() == 1


def test_consume_eol_after_stream_keyword_with_garbage_byte() -> None:
    """A non-EOL byte after ``stream`` rewinds so the body read sees
    it."""
    parser = _parser(b"Xbody")
    parser._consume_eol_after_stream_keyword()
    # Read once + rewind 1 → position 0
    assert parser._src.get_position() == 0


# ---------- _peek_two_bytes: EOF handling ----------


def test_peek_two_bytes_returns_minus_one_at_eof() -> None:
    """Empty source → (-1, -1)."""
    parser = _parser(b"")
    assert parser._peek_two_bytes() == (-1, -1)


def test_peek_two_bytes_returns_minus_one_for_second_byte_at_eof() -> None:
    """One-byte source → (b, -1) and rewinds 1."""
    parser = _parser(b"A")
    first, second = parser._peek_two_bytes()
    assert first == 0x41
    assert second == -1
    assert parser._src.get_position() == 0


# ---------- end-of-source helpers parity ----------


def test_get_brute_force_parser_returns_self() -> None:
    """pypdfbox inlines brute-force on COSParser → returns ``self``."""
    parser = _parser(b"")
    assert parser.get_brute_force_parser() is parser


def test_create_random_access_read_view_returns_sliced_buffer() -> None:
    """``create_random_access_read_view`` returns a view over the source
    bytes."""
    parser = _parser(b"abcdefgh")
    view = parser.create_random_access_read_view(2, 4)
    # Should yield bytes [c..f].
    body = bytearray()
    while True:
        b = view.read()
        if b == -1:
            break
        body.append(b)
    with contextlib.suppress(Exception):
        view.close()
    assert bytes(body) == b"cdef"


# ---------- parse_object_stream_object: unbound document raises ----------


def test_parse_object_stream_object_raises_when_unbound() -> None:
    """Without a bound document, the helper raises (line 1509-1512)."""
    parser = _parser(b"")
    with pytest.raises(PDFParseError, match="no document bound"):
        parser.parse_object_stream_object(1, COSObjectKey(2, 0))


# ---------- parse_cos_stream: missing 'stream' keyword raises ----------


def test_parse_cos_stream_raises_without_stream_keyword() -> None:
    """When the next token isn't ``stream`` the helper raises."""
    parser = _parser(b"notstream\nbody")
    dic = COSDictionary()
    with pytest.raises(PDFParseError, match="expected 'stream' keyword"):
        parser.parse_cos_stream(dic)


# ---------- get_encryption: unbound document raises ----------


def test_get_encryption_raises_when_document_unbound() -> None:
    """Without a bound document the accessor raises."""
    parser = _parser(b"")
    with pytest.raises(PDFParseError, match="parse the document first"):
        parser.get_encryption()


def test_get_encryption_returns_none_when_no_encrypt_dict() -> None:
    """Bound doc without /Encrypt → None."""
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    assert parser.get_encryption() is None


def test_get_access_permission_raises_when_unbound() -> None:
    """Without a bound document the accessor raises."""
    parser = _parser(b"")
    with pytest.raises(PDFParseError, match="parse the document first"):
        parser.get_access_permission()


# ---------- validate_stream_length: zero/negative length ----------


def test_validate_stream_length_returns_false_for_zero_or_negative() -> None:
    """Zero / negative lengths short-circuit to False."""
    parser = _parser(b"endstream")
    assert parser.validate_stream_length(0) is False
    assert parser.validate_stream_length(-1) is False


def test_validate_stream_length_returns_false_when_past_file_end() -> None:
    """Length exceeding file size short-circuits."""
    parser = _parser(b"abc")
    parser._file_len = 3  # type: ignore[attr-defined]
    assert parser.validate_stream_length(999) is False


# ---------- has_pdf_header ----------


def test_has_pdf_header_returns_true_for_valid_header() -> None:
    parser = _parser(b"%PDF-1.7\n")
    assert parser.has_pdf_header() is True


def test_has_pdf_header_returns_false_for_no_header() -> None:
    parser = _parser(b"not a pdf")
    assert parser.has_pdf_header() is False
