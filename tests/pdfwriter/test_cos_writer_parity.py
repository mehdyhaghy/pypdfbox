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
