from __future__ import annotations

import io
import zlib

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter

# ---------- helpers ---------------------------------------------------------


def _write(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


def _make_doc(catalog_dict: COSDictionary | None = None) -> COSDocument:
    """Build a minimal COSDocument: trailer with /Root pointing at a
    Catalog dictionary plus an /ID array."""
    doc = COSDocument()
    doc.set_version(1.4)
    catalog = catalog_dict if catalog_dict is not None else COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


# ---------- header / version ------------------------------------------------


def test_header_includes_version_and_binary_marker() -> None:
    doc = _make_doc()
    out = _write(doc)
    assert out.startswith(b"%PDF-1.4\n%\xf6\xe4\xfc\xdf\n")


def test_header_version_reflects_document() -> None:
    doc = _make_doc()
    doc.set_version(1.7)
    out = _write(doc)
    assert out.startswith(b"%PDF-1.7\n")


def test_header_version_2_0() -> None:
    doc = _make_doc()
    doc.set_version(2.0)
    out = _write(doc)
    assert out.startswith(b"%PDF-2.0\n")


# ---------- xref table format ----------------------------------------------


def test_xref_table_format_byte_for_byte() -> None:
    doc = _make_doc()
    out = _write(doc)
    # Every xref entry row must be exactly 20 bytes including the trailing
    # CR LF — ISO 32000-1 §7.5.4.
    xref_idx = out.index(b"\nxref\n") + len(b"\nxref\n")
    # The trailer keyword sits just past the last xref row's CR LF; locate
    # ``trailer\n`` (no leading EOL) so we don't eat the row's trailing LF.
    trailer_idx = out.index(b"trailer\n", xref_idx)
    body = out[xref_idx:trailer_idx]
    # Body shape: "<first> <count>\n" then 20-byte rows.
    header_end = body.index(b"\n") + 1
    rows = body[header_end:]
    assert len(rows) % 20 == 0, f"xref body not aligned: {rows!r}"

    # First row must be the free-list head.
    assert rows[:20] == b"0000000000 65535 f\r\n"
    # Subsequent rows: 20 bytes each, ending with CR LF.
    for i in range(0, len(rows), 20):
        row = rows[i:i + 20]
        assert row.endswith(b"\r\n"), f"row {i // 20} doesn't end CRLF: {row!r}"


def test_xref_size_matches_max_obj_num_plus_one() -> None:
    doc = _make_doc()
    out = _write(doc)
    # Catalog object #1 + an info dict optional. We expect /Size at least 2.
    trailer_idx = out.index(b"\ntrailer\n")
    trailer_text = out[trailer_idx:].decode("latin-1")
    # Look for "/Size 2" — exactly one indirect object was written.
    assert "/Size 2" in trailer_text


def test_eof_marker_present() -> None:
    doc = _make_doc()
    out = _write(doc)
    assert out.rstrip().endswith(b"%%EOF")


def test_startxref_offset_matches_xref_position() -> None:
    doc = _make_doc()
    out = _write(doc)
    xref_pos = out.index(b"xref\n")
    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    declared = int(out[line_start:line_end].strip())
    assert declared == xref_pos


# ---------- round-trip via parser ------------------------------------------


def test_round_trip_via_loader() -> None:
    catalog = COSDictionary()
    catalog.set_int(COSName.get_pdf_name("Custom"), 7)
    doc = _make_doc(catalog)

    pdf_bytes = _write(doc)

    # Round-trip via the parser.
    parsed = Loader.load_pdf(pdf_bytes)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]
        assert cat.get_int(COSName.get_pdf_name("Custom")) == 7
    finally:
        parsed.close()


def test_round_trip_preserves_id_array() -> None:
    doc = _make_doc()
    pdf_bytes = _write(doc)
    parsed = Loader.load_pdf(pdf_bytes)
    try:
        ids = parsed.get_document_id()
        assert ids is not None
        assert ids.size() == 2
    finally:
        parsed.close()


# ---------- stream round-trip ----------------------------------------------


def test_stream_round_trip_with_flate() -> None:
    raw = b"hello world" * 32
    encoded = zlib.compress(raw)
    stream = COSStream()
    stream.set_raw_data(encoded)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    stream.set_int(COSName.LENGTH, len(encoded))  # type: ignore[attr-defined]

    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    stream_obj = COSObject(2, 0, resolved=stream)
    catalog.set_item(COSName.get_pdf_name("Body"), stream_obj)
    doc = _make_doc(catalog)

    pdf_bytes = _write(doc)

    parsed = Loader.load_pdf(pdf_bytes)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        body_ref = cat.get_dictionary_object(COSName.get_pdf_name("Body"))
        assert isinstance(body_ref, COSStream)
        # Re-decompress the round-tripped raw bytes.
        round_tripped = zlib.decompress(body_ref.get_raw_data())
        assert round_tripped == raw
    finally:
        parsed.close()


# ---------- string escaping ------------------------------------------------


def test_string_literal_form_escapes_parens() -> None:
    s = COSString(b"(escaped)")
    sink = io.BytesIO()
    from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream

    out = COSStandardOutputStream(sink)
    COSWriter.write_string(s, out)
    assert sink.getvalue() == b"(\\(escaped\\))"


def test_string_with_backslash_escaped() -> None:
    s = COSString(b"a\\b")
    sink = io.BytesIO()
    from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream

    out = COSStandardOutputStream(sink)
    COSWriter.write_string(s, out)
    assert sink.getvalue() == b"(a\\\\b)"


def test_string_hex_form_for_high_bytes() -> None:
    s = COSString(bytes([0xDE, 0xAD, 0xBE, 0xEF]))
    sink = io.BytesIO()
    from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream

    out = COSStandardOutputStream(sink)
    COSWriter.write_string(s, out)
    assert sink.getvalue() == b"<DEADBEEF>"


def test_string_force_hex_form_kept() -> None:
    s = COSString(b"abc")
    s.set_force_hex_form(True)
    sink = io.BytesIO()
    from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream

    out = COSStandardOutputStream(sink)
    COSWriter.write_string(s, out)
    assert sink.getvalue() == b"<616263>"


def test_string_round_trip_literal() -> None:
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_item(COSName.get_pdf_name("S"), COSString(b"(parens)"))
    doc = _make_doc(catalog)
    pdf_bytes = _write(doc)
    parsed = Loader.load_pdf(pdf_bytes)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        s = cat.get_dictionary_object(COSName.get_pdf_name("S"))
        assert isinstance(s, COSString)
        assert s.get_bytes() == b"(parens)"
    finally:
        parsed.close()


def test_string_round_trip_hex() -> None:
    raw = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_item(COSName.get_pdf_name("S"), COSString(raw))
    doc = _make_doc(catalog)
    pdf_bytes = _write(doc)
    parsed = Loader.load_pdf(pdf_bytes)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        s = cat.get_dictionary_object(COSName.get_pdf_name("S"))
        assert isinstance(s, COSString)
        assert s.get_bytes() == raw
    finally:
        parsed.close()


# ---------- name escaping --------------------------------------------------


def test_name_escapes_spaces() -> None:
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_int(COSName.get_pdf_name("Name with spaces"), 1)
    doc = _make_doc(catalog)
    pdf_bytes = _write(doc)
    # The encoded name should contain #20 for each space.
    assert b"/Name#20with#20spaces" in pdf_bytes


def test_name_round_trip_with_escapes() -> None:
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_int(COSName.get_pdf_name("Weird/Name"), 1)
    doc = _make_doc(catalog)
    pdf_bytes = _write(doc)
    parsed = Loader.load_pdf(pdf_bytes)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_int(COSName.get_pdf_name("Weird/Name")) == 1
    finally:
        parsed.close()


# ---------- primitives -----------------------------------------------------


def test_boolean_emission() -> None:
    doc = _make_doc()
    catalog = doc.get_catalog()
    assert catalog is not None
    catalog.set_boolean(COSName.get_pdf_name("Flag"), True)
    out = _write(doc)
    assert b"/Flag true" in out


def test_null_emission() -> None:
    doc = _make_doc()
    catalog = doc.get_catalog()
    assert catalog is not None
    catalog.set_item(COSName.get_pdf_name("X"), COSNull.NULL)
    out = _write(doc)
    assert b"/X null" in out


def test_integer_emission() -> None:
    doc = _make_doc()
    catalog = doc.get_catalog()
    assert catalog is not None
    catalog.set_int(COSName.get_pdf_name("N"), -42)
    out = _write(doc)
    assert b"/N -42" in out


def test_float_emission_preserves_original_form() -> None:
    doc = _make_doc()
    catalog = doc.get_catalog()
    assert catalog is not None
    catalog.set_item(COSName.get_pdf_name("F"), COSFloat("3.14"))
    out = _write(doc)
    assert b"/F 3.14" in out


def test_float_emission_no_scientific_for_small() -> None:
    formatted = COSWriter.format_float(0.0001)
    assert b"e" not in formatted
    assert b"E" not in formatted


# ---------- array / dict structure -----------------------------------------


def test_array_inline() -> None:
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    arr = COSArray.of_cos_integers([1, 2, 3])
    arr.set_direct(True)
    catalog.set_item(COSName.get_pdf_name("Box"), arr)
    doc = _make_doc(catalog)
    out = _write(doc)
    assert b"/Box [1 2 3]" in out


def test_dictionary_pretty_print() -> None:
    doc = _make_doc()
    out = _write(doc)
    # Trailer dictionary uses << ... >> with newlines between entries.
    assert b"<<\n" in out
    assert b"\n>>" in out


# ---------- writer state guards --------------------------------------------


def test_incremental_without_source_raises() -> None:
    """``incremental=True`` is accepted by the constructor (cluster #2) but
    ``write()`` requires either an explicit ``incremental_input`` or a
    document carrying a source from the parser."""
    sink = io.BytesIO()
    doc = _make_doc()
    with pytest.raises(ValueError), COSWriter(sink, incremental=True) as w:
        w.write(doc)


def test_encrypted_document_rejected() -> None:
    doc = _make_doc()
    trailer = doc.get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, COSDictionary())  # type: ignore[attr-defined]
    sink = io.BytesIO()
    with pytest.raises(NotImplementedError), COSWriter(sink) as w:
        w.write(doc)


def test_pddocument_not_supported() -> None:
    sink = io.BytesIO()
    with pytest.raises(TypeError), COSWriter(sink) as w:
        w.write(object())  # type: ignore[arg-type]


def test_close_is_idempotent() -> None:
    sink = io.BytesIO()
    w = COSWriter(sink)
    w.close()
    w.close()  # should not raise
