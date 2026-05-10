"""Parity tests for the upstream-named COSWriter accessors / aliases.

These exercise the surface contributed in the COSWriter parity wave:
``write_header``, ``get_x_ref_entries``, ``set_pdf_version`` /
``get_pdf_version``, ``set_xref_stream`` / ``is_xref_stream_output``,
and ``to_hex_string``.

Mirrors the public-API shape of ``org.apache.pdfbox.pdfwriter.COSWriter``.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSName, COSObjectKey
from pypdfbox.pdfwriter import COSWriter, COSWriterXRefEntry

# ---------- helpers ---------------------------------------------------------


def _make_writer() -> COSWriter:
    """Return a fresh writer over a discardable BytesIO sink."""
    return COSWriter(io.BytesIO())


# ---------- write_header ----------------------------------------------------


def test_write_header_emits_pdf_version_line() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write_header("1.7")
    out = sink.getvalue()
    assert out.startswith(b"%PDF-1.7\n")
    # Binary marker comment must follow per PDF 32000-1 §7.5.2.
    assert b"%\xf6\xe4\xfc\xdf\n" in out


def test_write_header_uses_set_pdf_version_when_no_arg() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.set_pdf_version(2, 0)
        w.write_header()
    assert sink.getvalue().startswith(b"%PDF-2.0\n")


def test_write_header_round_trip_preserves_version_text() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write_header("1.5")
    assert sink.getvalue().startswith(b"%PDF-1.5\n")


def test_write_header_rejects_non_string_version() -> None:
    with COSWriter(io.BytesIO()) as w, pytest.raises(TypeError):
        w.write_header(1.7)  # type: ignore[arg-type]


# ---------- get_x_ref_entries ----------------------------------------------


def test_get_x_ref_entries_returns_list_initially_empty() -> None:
    with _make_writer() as w:
        entries = w.get_x_ref_entries()
        assert isinstance(entries, list)
        assert entries == []


def test_get_x_ref_entries_aliases_get_xref_entries() -> None:
    with _make_writer() as w:
        # Both accessors must expose the same underlying list — mutations
        # via either spelling are visible through the other.
        assert w.get_x_ref_entries() is w.get_xref_entries()


def test_get_x_ref_entries_element_type() -> None:
    with _make_writer() as w:
        entries = w.get_x_ref_entries()
        # Empty list is fine; the contract is "list of COSWriterXRefEntry".
        # Mutate the underlying state to verify type round-trips.
        free = COSWriterXRefEntry.get_null_entry()
        entries.append(free)
        assert isinstance(w.get_x_ref_entries()[-1], COSWriterXRefEntry)
        # Cleanup so we don't leak state across writers (each test makes
        # its own anyway, but be tidy).
        entries.pop()


# ---------- get_x_ref_ranges -----------------------------------------------


def test_get_x_ref_ranges_groups_sparse_entries() -> None:
    entries = [
        COSWriterXRefEntry(0, COSObjectKey(0, 65535), free=True),
        COSWriterXRefEntry(10, COSObjectKey(1, 0)),
        COSWriterXRefEntry(20, COSObjectKey(2, 0)),
        COSWriterXRefEntry(50, COSObjectKey(5, 0)),
        COSWriterXRefEntry(60, COSObjectKey(6, 0)),
        COSWriterXRefEntry(70, COSObjectKey(7, 0)),
        COSWriterXRefEntry(80, COSObjectKey(8, 0)),
        COSWriterXRefEntry(100, COSObjectKey(10, 0)),
    ]

    with _make_writer() as w:
        assert w.get_x_ref_ranges(entries) == [0, 3, 5, 4, 10, 1]


def test_get_x_ref_ranges_sorts_input_before_grouping() -> None:
    entries = [
        COSWriterXRefEntry(70, COSObjectKey(7, 0)),
        COSWriterXRefEntry(0, COSObjectKey(0, 65535), free=True),
        COSWriterXRefEntry(60, COSObjectKey(6, 0)),
        COSWriterXRefEntry(10, COSObjectKey(1, 0)),
    ]

    with _make_writer() as w:
        assert w.get_x_ref_ranges(entries) == [0, 2, 6, 2]


def test_get_x_ref_ranges_empty_entries() -> None:
    with _make_writer() as w:
        assert w.get_x_ref_ranges([]) == []


# ---------- set_pdf_version / get_pdf_version ------------------------------


def test_set_pdf_version_round_trip() -> None:
    with _make_writer() as w:
        w.set_pdf_version(1, 7)
        assert w.get_pdf_version() == "1.7"


def test_get_pdf_version_default_is_pdfbox_default() -> None:
    with _make_writer() as w:
        # PDFBox's default (no override set) is "1.4".
        assert w.get_pdf_version() == "1.4"


def test_set_pdf_version_supports_two_oh() -> None:
    with _make_writer() as w:
        w.set_pdf_version(2, 0)
        assert w.get_pdf_version() == "2.0"


def test_set_pdf_version_rejects_negative() -> None:
    with _make_writer() as w, pytest.raises(ValueError):
        w.set_pdf_version(-1, 0)


def test_set_pdf_version_rejects_non_int() -> None:
    with _make_writer() as w, pytest.raises(TypeError):
        w.set_pdf_version(1, "7")  # type: ignore[arg-type]


# ---------- set_xref_stream / is_xref_stream_output ------------------------


def test_xref_stream_toggle_default_false() -> None:
    with _make_writer() as w:
        assert w.is_xref_stream_output() is False


def test_xref_stream_toggle_round_trip() -> None:
    with _make_writer() as w:
        w.set_xref_stream(True)
        assert w.is_xref_stream_output() is True
        w.set_xref_stream(False)
        assert w.is_xref_stream_output() is False


# ---------- to_hex_string ---------------------------------------------------


def test_to_hex_string_smoke() -> None:
    assert COSWriter.to_hex_string(b"\x00\x01\xab\xcd") == "0001ABCD"


def test_to_hex_string_empty() -> None:
    assert COSWriter.to_hex_string(b"") == ""


def test_to_hex_string_accepts_bytearray() -> None:
    assert COSWriter.to_hex_string(bytearray(b"\xde\xad\xbe\xef")) == "DEADBEEF"


def test_to_hex_string_rejects_str() -> None:
    with pytest.raises(TypeError):
        COSWriter.to_hex_string("deadbeef")  # type: ignore[arg-type]


# ---------- additional parity surface --------------------------------------


def test_get_started_streams_returns_set() -> None:
    with _make_writer() as w:
        started = w.get_started_streams()
        assert isinstance(started, set)
        assert started == set()


def test_release_is_idempotent_alias_for_close() -> None:
    w = _make_writer()
    w.release()
    # Second release must not blow up — same idempotency guarantee close has.
    w.release()


def test_add_signature_is_noop_placeholder() -> None:
    with _make_writer() as w:
        # Should not raise; signature pipeline is owned by PDDocument.
        assert w.add_signature() is None


def test_get_object_number_raises_for_unknown_object() -> None:
    from pypdfbox.cos import COSDictionary

    with _make_writer() as w, pytest.raises(KeyError):
        w.get_object_number(COSDictionary())


def test_get_generation_number_raises_for_unknown_object() -> None:
    from pypdfbox.cos import COSDictionary

    with _make_writer() as w, pytest.raises(KeyError):
        w.get_generation_number(COSDictionary())


# ---------- upstream protected/public dispatch surface ----------------------


def test_add_x_ref_entry_aliases_add_xref_entry() -> None:
    with _make_writer() as w:
        entry = COSWriterXRefEntry(
            offset=0, key=COSObjectKey(0, 65535), obj=None, free=True
        )
        w.add_x_ref_entry(entry)
        assert w.get_xref_entries() == [entry]


def test_get_object_key_assigns_and_caches_key() -> None:
    from pypdfbox.cos import COSDictionary

    with _make_writer() as w:
        d = COSDictionary()
        first = w.get_object_key(d)
        # Caching: a second lookup must return the same key (no fresh mint).
        assert w.get_object_key(d) is first
        assert isinstance(first, COSObjectKey)


def test_is_need_to_be_updated_handles_none_and_plain_objects() -> None:
    from pypdfbox.cos import COSDictionary
    from pypdfbox.cos.cos_document_state import COSDocumentState

    # ``None`` → ``False`` (matches upstream's null-tolerant signature).
    assert COSWriter.is_need_to_be_updated(None) is False
    d = COSDictionary()
    # Fresh dictionary is clean.
    assert COSWriter.is_need_to_be_updated(d) is False
    # Wire a document state in "accepting updates" mode so the dirty
    # flag actually flips. Mirrors how the parser links dictionaries
    # post-load before incremental edits are accepted.
    state = COSDocumentState()
    state.set_parsing(False)  # closes the parser phase → accepting updates
    d.get_update_state().set_origin_document_state(state)
    d.set_needs_to_be_updated(True)
    assert COSWriter.is_need_to_be_updated(d) is True


def test_visit_from_int_aliases_visit_from_integer() -> None:
    from pypdfbox.cos import COSInteger

    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.visit_from_int(COSInteger.get(42))
    assert sink.getvalue() == b"42"


def test_write_xref_range_emits_first_count_pair() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write_xref_range(0, 5)
    out = sink.getvalue()
    assert out.startswith(b"0 5")
    # Trailing EOL.
    assert out.endswith(b"\n")


def test_write_xref_entry_emits_20_byte_row_for_used_entry() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        entry = COSWriterXRefEntry(
            offset=12345,
            key=COSObjectKey(1, 0),
            obj=None,
            free=False,
        )
        w.write_xref_entry(entry)
    out = sink.getvalue()
    # 10-digit offset + space + 5-digit gen + space + 'n' + CRLF = 20 bytes.
    assert len(out) == 20
    assert out[:10] == b"0000012345"
    assert out[11:16] == b"00000"
    assert out[17:18] == b"n"


def test_write_xref_entry_emits_20_byte_row_for_free_entry() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        entry = COSWriterXRefEntry(
            offset=0,
            key=COSObjectKey(0, 65535),
            obj=None,
            free=True,
        )
        w.write_xref_entry(entry)
    out = sink.getvalue()
    assert len(out) == 20
    assert out[:10] == b"0000000000"
    assert out[11:16] == b"65535"
    assert out[17:18] == b"f"


def test_get_data_to_sign_raises_when_not_prepared() -> None:
    with _make_writer() as w, pytest.raises(RuntimeError, match="signing"):
        w.get_data_to_sign()


def test_write_external_signature_raises_when_not_prepared() -> None:
    with _make_writer() as w, pytest.raises(RuntimeError, match="signature"):
        w.write_external_signature(b"\x00" * 32)


def test_write_external_signature_rejects_non_bytes() -> None:
    with _make_writer() as w, pytest.raises(TypeError):
        w.write_external_signature("not-bytes")  # type: ignore[arg-type]


def test_do_write_signature_raises_when_not_prepared() -> None:
    with _make_writer() as w, pytest.raises(RuntimeError):
        w.do_write_signature()


def test_detect_possible_signature_no_op_for_non_dictionary() -> None:
    with _make_writer() as w:
        # Non-dict input must not raise — matches the no-op upstream
        # behaviour (the visitor never calls it with non-dicts but the
        # method tolerates anything).
        w.detect_possible_signature(None)  # type: ignore[arg-type]
        assert w._reached_signature is False  # noqa: SLF001


def test_detect_possible_signature_skips_non_signature_dicts() -> None:
    from pypdfbox.cos import COSDictionary

    sink = io.BytesIO()
    with COSWriter(sink, incremental=False) as w:
        d = COSDictionary()
        d.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
        w.detect_possible_signature(d)
        assert w._reached_signature is False  # noqa: SLF001


def test_write_array_emits_inline_when_direct() -> None:
    from pypdfbox.cos import COSArray, COSInteger

    sink = io.BytesIO()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSInteger.get(2))
    arr.set_direct(True)
    with COSWriter(sink) as w:
        w.write_array(arr)
    out = sink.getvalue()
    assert out.startswith(b"[")
    assert b"1" in out and b"2" in out
    # Inline array end token.
    assert b"]" in out


def test_write_dictionary_emits_inline_when_direct() -> None:
    from pypdfbox.cos import COSDictionary, COSInteger

    sink = io.BytesIO()
    d = COSDictionary()
    d.set_item(COSName.SIZE, COSInteger.get(7))  # type: ignore[attr-defined]
    d.set_direct(True)
    with COSWriter(sink) as w:
        w.write_dictionary(d)
    out = sink.getvalue()
    assert out.startswith(b"<<")
    assert b"/Size" in out
    assert b">>" in out


def test_add_object_to_write_queues_object() -> None:
    from pypdfbox.cos import COSDictionary

    with _make_writer() as w:
        d = COSDictionary()
        # In non-incremental mode `_add_object_to_write` queues unseen
        # actuals directly. We verify via the underlying queue length.
        before = len(w._objects_to_write)  # noqa: SLF001
        w.add_object_to_write(d)
        after = len(w._objects_to_write)  # noqa: SLF001
        assert after == before + 1


def test_do_write_objects_drains_queue() -> None:
    from pypdfbox.cos import COSDictionary

    sink = io.BytesIO()
    with COSWriter(sink) as w:
        d = COSDictionary()
        d.set_int(COSName.SIZE, 1)  # type: ignore[attr-defined]
        w.add_object_to_write(d)
        # Mint a key for the dict so the indirect-frame emit succeeds.
        w.do_write_objects()
        assert len(w._objects_to_write) == 0  # noqa: SLF001
    out = sink.getvalue()
    # Indirect-object frame markers must appear.
    assert b"obj" in out
    assert b"endobj" in out
