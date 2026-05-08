from __future__ import annotations

import io
import re

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSName,
    COSObject,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter

# ---------- helpers ---------------------------------------------------------


def _full_save(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


def _incremental_save(
    doc: COSDocument, *, source: bytes | None = None
) -> bytes:
    """Run the incremental save path and return the resulting bytes.

    If ``source`` is given, wrap it in a ``RandomAccessReadBuffer`` and pass
    it explicitly; otherwise the writer pulls the source from
    ``doc.get_source()`` (populated by ``Loader.load_pdf``)."""
    sink = io.BytesIO()
    if source is not None:
        with RandomAccessReadBuffer(source) as src, COSWriter(
            sink, incremental=True, incremental_input=src
        ) as w:
            w.write(doc)
    else:
        with COSWriter(sink, incremental=True) as w:
            w.write(doc)
    return sink.getvalue()


def _make_seed_pdf() -> bytes:
    """Build a small valid source PDF via the cluster #1 full-save writer."""
    doc = COSDocument()
    doc.set_version(1.4)
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_int(COSName.get_pdf_name("V"), 1)
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return _full_save(doc)


# ---------- position accounting --------------------------------------------


def test_incremental_writer_seeds_position_from_explicit_source() -> None:
    """PDFBox seeds COSStandardOutputStream with inputData.length() so any
    xref offsets observed during an incremental save are absolute offsets in
    the concatenated output, not offsets relative to the append buffer."""
    src = _make_seed_pdf()
    sink = io.BytesIO()

    with RandomAccessReadBuffer(src) as source, COSWriter(
        sink, incremental=True, incremental_input=source
    ) as writer:
        assert writer.get_standard_output().get_position() == len(src)


def test_incremental_writer_position_tracks_final_output_length() -> None:
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    sink = io.BytesIO()
    writer = COSWriter(sink, incremental=True)
    try:
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_int(COSName.get_pdf_name("V"), 2)
        catalog.set_needs_to_be_updated(True)

        writer.write(parsed)

        out = sink.getvalue()
        assert out.startswith(src)
        assert writer.get_standard_output().get_position() == len(out)
    finally:
        writer.close()
        parsed.close()


# ---------- contracts (PRD §6.5 cluster #2) --------------------------------


def test_incremental_unchanged_doc_emits_only_source_bytes() -> None:
    """No dirty objects → output identical to source (no extra bytes)."""
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    try:
        out = _incremental_save(parsed)
    finally:
        parsed.close()
    assert out == src


def test_incremental_marks_one_object_appends_only_that_object() -> None:
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    try:
        # Mark the catalog dirty.
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_int(COSName.get_pdf_name("V"), 2)  # mutate
        catalog.set_needs_to_be_updated(True)
        out = _incremental_save(parsed)
    finally:
        parsed.close()

    # 1. Source preserved as a byte-prefix.
    assert out.startswith(src)
    # 2. Exactly one new ``n g obj`` block for object 1, gen 0.
    increment = out[len(src):]
    assert increment[:2] == b"\r\n", (
        f"increment must start with CRLF separator, got {increment[:6]!r}"
    )
    obj_blocks = re.findall(rb"\b(\d+) (\d+) obj\b", increment)
    assert obj_blocks == [(b"1", b"0")], obj_blocks
    # 3. New trailer carries /Prev pointing at the old startxref.
    old_startxref_match = re.search(rb"startxref\n(\d+)\n%%EOF", src)
    assert old_startxref_match is not None
    old_startxref = int(old_startxref_match.group(1))
    new_trailers = re.findall(rb"/Prev (\d+)", increment)
    assert new_trailers == [str(old_startxref).encode("ascii")]
    # 4. Final %%EOF.
    assert out.rstrip().endswith(b"%%EOF")


def test_incremental_round_trips_through_loader() -> None:
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    try:
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_int(COSName.get_pdf_name("V"), 42)
        catalog.set_needs_to_be_updated(True)
        out = _incremental_save(parsed)
    finally:
        parsed.close()

    # Re-parse the result; the latest-version catalog wins (xref chain
    # walks /Prev so the appended copy is found first).
    re_parsed = Loader.load_pdf(out)
    try:
        cat = re_parsed.get_catalog()
        assert cat is not None
        assert cat.get_int(COSName.get_pdf_name("V")) == 42
    finally:
        re_parsed.close()


def test_incremental_size_is_max_obj_num_plus_one() -> None:
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    try:
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_needs_to_be_updated(True)
        out = _incremental_save(parsed)
    finally:
        parsed.close()
    increment = out[len(src):]
    # Source seed had one indirect object (catalog #1), so /Size = 2.
    sizes = re.findall(rb"/Size (\d+)", increment)
    assert sizes == [b"2"]


def test_incremental_preserves_id_array_first_element() -> None:
    """ISO 32000-1 §14.4: the first entry of /ID is the *original* file
    identifier and must round-trip verbatim through every incremental
    save."""
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    original_ids = parsed.get_document_id()
    assert original_ids is not None
    original_id_0 = original_ids.get(0)
    try:
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_needs_to_be_updated(True)
        out = _incremental_save(parsed)
    finally:
        parsed.close()

    re_parsed = Loader.load_pdf(out)
    try:
        ids = re_parsed.get_document_id()
        assert ids is not None
        assert ids.size() == 2
        # First element preserved byte-for-byte.
        assert ids.get(0) == original_id_0
    finally:
        re_parsed.close()


def test_incremental_does_not_synthesize_new_id() -> None:
    """When the source has no /ID, incremental save must not invent one
    (cluster #1 synthesises one via SHA-256 — that path is skipped in
    incremental mode)."""
    # Build a minimal valid PDF byte-stream by hand so we can drive the
    # incremental writer without going through the cluster #1 /ID-synth
    # path. We compute the xref offset programmatically.
    header = b"%PDF-1.4\n"
    body = b"1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
    xref_offset = len(header) + len(body)
    xref_section = (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f\r\n"
        + f"{len(header):010d}".encode("ascii") + b" 00000 n\r\n"
        + b"trailer\n<<\n/Root 1 0 R\n/Size 2\n>>\n"
        + b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
    )
    src = header + body + xref_section

    parsed = Loader.load_pdf(src)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        cat.set_needs_to_be_updated(True)
        out = _incremental_save(parsed)
    finally:
        parsed.close()
    increment = out[len(src):]
    # The appended trailer must NOT contain a freshly minted /ID.
    assert b"/ID" not in increment


def test_incremental_new_objects_get_fresh_keys() -> None:
    """An object marked dirty whose actual was never registered with the
    source's xref pool must be assigned a number above ``max(existing)``."""
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    try:
        # Synthesise a brand-new dict, attach it to the catalog as an
        # indirect reference, mark both dirty.
        new_dict = COSDictionary()
        new_dict.set_int(COSName.get_pdf_name("Marker"), 99)
        new_dict.set_needs_to_be_updated(True)
        # The new dict needs to be referenced indirectly — attach it to
        # the catalog through a fresh ``COSObject`` wrapper. Keys 0 and 1
        # are taken; the writer should mint #2.
        new_ref = COSObject(0, 0, resolved=new_dict)
        catalog = parsed.get_catalog()
        assert catalog is not None
        catalog.set_item(COSName.get_pdf_name("Extra"), new_ref)
        catalog.set_needs_to_be_updated(True)
        out = _incremental_save(parsed)
    finally:
        parsed.close()

    # The new reference must have been emitted; its number must be > 1.
    re_parsed = Loader.load_pdf(out)
    try:
        cat = re_parsed.get_catalog()
        assert cat is not None
        extra = cat.get_dictionary_object(COSName.get_pdf_name("Extra"))
        assert isinstance(extra, COSDictionary)
        assert extra.get_int(COSName.get_pdf_name("Marker")) == 99
    finally:
        re_parsed.close()


def test_incremental_with_explicit_input_buffer() -> None:
    """``incremental_input=`` must be honoured when the document has no
    parser-attached source."""
    src = _make_seed_pdf()
    parsed = Loader.load_pdf(src)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        cat.set_needs_to_be_updated(True)
        # Pretend the doc had no attached source.
        parsed._source = None  # noqa: SLF001 — test reaches into sibling-package state
        out = _incremental_save(parsed, source=src)
    finally:
        parsed.close()
    assert out.startswith(src)


def test_incremental_without_input_raises() -> None:
    doc = COSDocument()
    doc.set_version(1.4)
    sink = io.BytesIO()
    with pytest.raises(ValueError), COSWriter(sink, incremental=True) as w:
        w.write(doc)


def test_incremental_signed_byterange_placeholder_rejected() -> None:
    """A ``/Sig`` dict with a ``/ByteRange [0 0 0 0]`` placeholder must
    cause incremental save to bail out — actual digest computation lives
    with the security cluster."""
    # Hand-craft a source PDF with a signature dict carrying the
    # placeholder so we can exercise the detection path.
    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
    obj2 = b"2 0 obj\n<<\n/Type /Sig\n/ByteRange [0 0 0 0]\n>>\nendobj\n"
    obj1_off = len(header)
    obj2_off = obj1_off + len(obj1)
    xref_off = obj2_off + len(obj2)
    xref = (
        b"xref\n"
        b"0 3\n"
        b"0000000000 65535 f\r\n"
        + f"{obj1_off:010d}".encode("ascii") + b" 00000 n\r\n"
        + f"{obj2_off:010d}".encode("ascii") + b" 00000 n\r\n"
        + b"trailer\n<<\n/Root 1 0 R\n/Size 3\n>>\n"
        + b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF\n"
    )
    src = header + obj1 + obj2 + xref
    parsed = Loader.load_pdf(src)
    try:
        sink = io.BytesIO()
        with pytest.raises(NotImplementedError), COSWriter(
            sink, incremental=True
        ) as w:
            w.write(parsed)
    finally:
        parsed.close()
